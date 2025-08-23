"""Task management API routes."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from agent.orchestrator.state import ExecutionStatus
from agent.planning.cost_estimator import ApprovalLevel
from agent.web.api import get_app_state
from agent.web.models import (
    ApprovalRequest,
    ApprovalResponse,
    StreamEvent,
    TaskPreview,
    TaskRequest,
    TaskResponse,
    TaskStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Active tasks storage
active_tasks: Dict[str, Dict] = {}
pending_approvals: Dict[str, Dict] = {}


@router.post("/execute", response_model=TaskResponse)
async def execute_task(task_request: TaskRequest, background_tasks: BackgroundTasks):
    """Execute a task with the agent."""
    app_state = get_app_state()
    planner = app_state.get("planner")
    executor = app_state.get("executor")
    
    if not planner or not executor:
        raise HTTPException(status_code=500, detail="Agent components not initialized")
    
    # Generate task ID
    task_id = str(uuid4())
    
    try:
        # Create execution plan
        plan = await planner.create_plan(
            instruction=task_request.instruction,
            context=task_request.context or {},
            mode=task_request.planning_mode,
            target_files=task_request.target_files
        )
        
        # Generate preview if requested
        preview_url = None
        if task_request.generate_preview:
            preview_url = f"/api/v1/tasks/{task_id}/preview"
        
        # Estimate cost and check approval requirements
        requires_approval = False
        approval_message = None
        
        if task_request.estimate_cost:
            cost_estimate = await planner.estimate_cost(plan)
            
            if cost_estimate.approval_required != ApprovalLevel.NONE and not task_request.auto_approve:
                requires_approval = True
                approval_message = f"Task requires {cost_estimate.approval_required.value} approval due to {cost_estimate.risk_level.value} risk level"
                
                # Store for approval
                pending_approvals[task_id] = {
                    "plan": plan,
                    "cost_estimate": cost_estimate,
                    "request": task_request,
                    "created_at": datetime.now()
                }
        
        # Store task info
        active_tasks[task_id] = {
            "id": task_id,
            "instruction": task_request.instruction,
            "status": ExecutionStatus.PENDING if requires_approval else ExecutionStatus.PLANNING,
            "plan": plan,
            "created_at": datetime.now(),
            "requires_approval": requires_approval
        }
        
        # Start execution if no approval required
        if not requires_approval:
            background_tasks.add_task(execute_task_background, task_id, plan, executor, task_request.dry_run)
        
        return TaskResponse(
            task_id=task_id,
            status="pending_approval" if requires_approval else "started",
            message="Task created successfully",
            requires_approval=requires_approval,
            approval_message=approval_message,
            preview_url=preview_url
        )
        
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


async def execute_task_background(task_id: str, plan, executor, dry_run: bool = False):
    """Execute task in background."""
    try:
        active_tasks[task_id]["status"] = ExecutionStatus.EXECUTING
        active_tasks[task_id]["started_at"] = datetime.now()
        
        # Execute the plan
        result = await executor.execute_plan(plan, dry_run=dry_run)
        
        # Update task status
        active_tasks[task_id]["status"] = ExecutionStatus.COMPLETED
        active_tasks[task_id]["completed_at"] = datetime.now()
        active_tasks[task_id]["result"] = result
        
        # Update app state
        app_state = get_app_state()
        app_state["completed_tasks"] = app_state.get("completed_tasks", 0) + 1
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        active_tasks[task_id]["status"] = ExecutionStatus.FAILED
        active_tasks[task_id]["error_message"] = str(e)


@router.get("/{task_id}/status", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get task status."""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = active_tasks[task_id]
    
    return TaskStatus(
        task_id=task_id,
        instruction=task["instruction"],
        status=task["status"],
        progress=task.get("progress", {}),
        created_at=task["created_at"],
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
        current_step=task.get("current_step"),
        error_message=task.get("error_message")
    )


@router.get("/{task_id}/preview", response_model=TaskPreview)
async def get_task_preview(task_id: str):
    """Get task execution preview."""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = active_tasks[task_id]
    plan = task["plan"]
    
    app_state = get_app_state()
    planner = app_state.get("planner")
    
    if not planner:
        raise HTTPException(status_code=500, detail="Planner not available")
    
    try:
        # Generate preview
        preview = await planner.generate_preview(plan)
        
        return TaskPreview(
            task_id=task_id,
            title=preview.title,
            description=preview.description,
            mode=preview.mode,
            estimated_time_minutes=preview.estimated_time_minutes,
            complexity_score=preview.complexity_score,
            risk_level=preview.risk_level,
            approval_required=preview.approval_required,
            files_affected=preview.files_affected,
            commands_to_run=preview.commands_to_run,
            step_summaries=preview.step_summaries,
            potential_risks=preview.potential_risks,
            expected_outcomes=preview.expected_outcomes
        )
        
    except Exception as e:
        logger.error(f"Failed to generate preview for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")


@router.post("/{task_id}/approve", response_model=ApprovalResponse)
async def approve_task(task_id: str, approval: ApprovalResponse, background_tasks: BackgroundTasks):
    """Approve or reject a pending task."""
    if task_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    approval_data = pending_approvals[task_id]
    
    if approval.approved:
        # Start execution
        plan = approval_data["plan"]
        request = approval_data["request"]
        
        app_state = get_app_state()
        executor = app_state.get("executor")
        
        if not executor:
            raise HTTPException(status_code=500, detail="Executor not available")
        
        # Update task status
        active_tasks[task_id]["status"] = ExecutionStatus.EXECUTING
        active_tasks[task_id]["requires_approval"] = False
        
        # Start background execution
        background_tasks.add_task(execute_task_background, task_id, plan, executor, request.dry_run)
        
        # Remove from pending approvals
        del pending_approvals[task_id]
        
        return ApprovalResponse(
            task_id=task_id,
            approved=True,
            response_message="Task approved and started"
        )
    else:
        # Reject task
        active_tasks[task_id]["status"] = ExecutionStatus.CANCELLED
        del pending_approvals[task_id]
        
        return ApprovalResponse(
            task_id=task_id,
            approved=False,
            response_message=approval.response_message or "Task rejected"
        )


@router.get("/{task_id}/stream")
async def stream_task_events(task_id: str):
    """Stream task execution events."""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def event_generator():
        """Generate server-sent events for task updates."""
        last_status = None
        
        while True:
            task = active_tasks.get(task_id)
            if not task:
                break
            
            current_status = task["status"]
            
            # Send status update if changed
            if current_status != last_status:
                event = StreamEvent(
                    event_type="status_update",
                    task_id=task_id,
                    timestamp=datetime.now(),
                    data={
                        "status": current_status.value,
                        "current_step": task.get("current_step"),
                        "progress": task.get("progress", {})
                    }
                )
                
                yield f"data: {event.json()}\n\n"
                last_status = current_status
            
            # Break if task is complete or failed
            if current_status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@router.get("/", response_model=List[TaskStatus])
async def list_tasks(limit: int = 50, status: str = None):
    """List recent tasks."""
    tasks = []
    
    for task_id, task_data in list(active_tasks.items())[-limit:]:
        if status and task_data["status"].value != status:
            continue
        
        tasks.append(TaskStatus(
            task_id=task_id,
            instruction=task_data["instruction"],
            status=task_data["status"],
            progress=task_data.get("progress", {}),
            created_at=task_data["created_at"],
            started_at=task_data.get("started_at"),
            completed_at=task_data.get("completed_at"),
            current_step=task_data.get("current_step"),
            error_message=task_data.get("error_message")
        ))
    
    return tasks


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = active_tasks[task_id]
    
    if task["status"] in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Task is already finished")
    
    # Cancel the task
    active_tasks[task_id]["status"] = ExecutionStatus.CANCELLED
    
    # Remove from pending approvals if present
    if task_id in pending_approvals:
        del pending_approvals[task_id]
    
    return {"message": f"Task {task_id} cancelled"}


@router.get("/pending-approvals")
async def list_pending_approvals():
    """List tasks pending approval."""
    approvals = []
    
    for task_id, approval_data in pending_approvals.items():
        cost_estimate = approval_data["cost_estimate"]
        
        approvals.append(ApprovalRequest(
            task_id=task_id,
            message=f"Task requires approval: {approval_data['request'].instruction}",
            approval_level=cost_estimate.approval_required,
            cost_summary={
                "estimated_time_minutes": cost_estimate.estimated_time_minutes,
                "complexity_score": cost_estimate.complexity_score,
                "risk_level": cost_estimate.risk_level.value
            },
            safety_concerns=cost_estimate.potential_risks,
            timeout_seconds=300
        ))
    
    return approvals