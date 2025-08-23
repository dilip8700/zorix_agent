"""Project memory management for persistent workspace knowledge."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from agent.config import get_settings
from agent.llm.bedrock_client import BedrockClient
from agent.memory.models import (
    MemoryEntry,
    MemoryType,
    ProjectContext,
)
from agent.security.sandbox import SecuritySandbox
from agent.vector.index import VectorIndex

logger = logging.getLogger(__name__)


class ProjectMemoryError(Exception):
    """Exception for project memory operations."""
    pass


class ProjectMemory:
    """Manages project-specific context and persistent knowledge."""
    
    def __init__(
        self,
        storage_path: Optional[Path] = None,
        bedrock_client: Optional[BedrockClient] = None,
        vector_index: Optional[VectorIndex] = None,
        workspace_root: Optional[str] = None,
    ):
        """Initialize project memory.
        
        Args:
            storage_path: Path to store project data
            bedrock_client: Bedrock client for embeddings
            vector_index: Vector index for code search integration
            workspace_root: Root directory for workspace operations
        """
        settings = get_settings()
        
        self.storage_path = storage_path or Path(settings.memory_db_path) / "projects"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.workspace_root = Path(workspace_root or settings.workspace_root).resolve()
        self.bedrock = bedrock_client or BedrockClient()
        self.vector_index = vector_index
        self.sandbox = SecuritySandbox(self.workspace_root)
        
        # In-memory cache
        self.projects: Dict[str, ProjectContext] = {}
        self.current_project_id: Optional[str] = None
        self.project_memories: Dict[str, List[MemoryEntry]] = {}  # project_id -> memories
        
        # Load existing projects
        self._load_projects()
        
        logger.info(f"Initialized ProjectMemory with {len(self.projects)} projects")
    
    def _load_projects(self):
        """Load existing projects from storage."""
        try:
            projects_file = self.storage_path / "projects.json"
            if projects_file.exists():
                with open(projects_file, 'r', encoding='utf-8') as f:
                    projects_data = json.load(f)
                
                for project_data in projects_data:
                    project = ProjectContext.from_dict(project_data)
                    self.projects[project.id] = project
                
                logger.info(f"Loaded {len(self.projects)} projects")
            
            # Load current project ID
            current_file = self.storage_path / "current_project.txt"
            if current_file.exists():
                self.current_project_id = current_file.read_text().strip()
            
            # Load project memories
            self._load_project_memories()
                
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
    
    def _load_project_memories(self):
        """Load project-specific memories."""
        try:
            for project_id in self.projects.keys():
                memories_file = self.storage_path / f"memories_{project_id}.json"
                if memories_file.exists():
                    with open(memories_file, 'r', encoding='utf-8') as f:
                        memories_data = json.load(f)
                    
                    memories = [MemoryEntry.from_dict(data) for data in memories_data]
                    self.project_memories[project_id] = memories
                    
                    logger.debug(f"Loaded {len(memories)} memories for project {project_id}")
                
        except Exception as e:
            logger.error(f"Failed to load project memories: {e}")
    
    def _save_projects(self):
        """Save projects to storage."""
        try:
            projects_file = self.storage_path / "projects.json"
            projects_data = [project.to_dict() for project in self.projects.values()]
            
            with open(projects_file, 'w', encoding='utf-8') as f:
                json.dump(projects_data, f, indent=2, ensure_ascii=False)
            
            # Save current project ID
            if self.current_project_id:
                current_file = self.storage_path / "current_project.txt"
                current_file.write_text(self.current_project_id)
            
            logger.debug(f"Saved {len(self.projects)} projects")
            
        except Exception as e:
            logger.error(f"Failed to save projects: {e}")
    
    def _save_project_memories(self, project_id: str):
        """Save memories for a specific project."""
        try:
            if project_id in self.project_memories:
                memories_file = self.storage_path / f"memories_{project_id}.json"
                memories_data = [memory.to_dict() for memory in self.project_memories[project_id]]
                
                with open(memories_file, 'w', encoding='utf-8') as f:
                    json.dump(memories_data, f, indent=2, ensure_ascii=False)
                
                logger.debug(f"Saved {len(memories_data)} memories for project {project_id}")
                
        except Exception as e:
            logger.error(f"Failed to save memories for project {project_id}: {e}")
    
    def create_project(
        self,
        name: str,
        description: str = "",
        workspace_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProjectContext:
        """Create a new project context.
        
        Args:
            name: Project name
            description: Project description
            workspace_path: Path to project workspace
            metadata: Additional metadata
            
        Returns:
            New project context
        """
        project = ProjectContext(
            name=name,
            description=description,
            workspace_path=workspace_path or str(self.workspace_root),
            metadata=metadata or {}
        )
        
        self.projects[project.id] = project
        self.current_project_id = project.id
        self.project_memories[project.id] = []
        
        # Analyze workspace if provided
        if workspace_path:
            self._analyze_workspace(project)
        
        self._save_projects()
        
        logger.info(f"Created new project: {project.name} ({project.id})")
        return project
    
    def get_project(self, project_id: str) -> Optional[ProjectContext]:
        """Get a project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project context or None if not found
        """
        return self.projects.get(project_id)
    
    def get_current_project(self) -> Optional[ProjectContext]:
        """Get the current active project.
        
        Returns:
            Current project or None
        """
        if self.current_project_id:
            return self.projects.get(self.current_project_id)
        return None
    
    def set_current_project(self, project_id: str) -> bool:
        """Set the current active project.
        
        Args:
            project_id: Project ID to make current
            
        Returns:
            True if successful, False if project not found
        """
        if project_id in self.projects:
            self.current_project_id = project_id
            self._save_projects()
            return True
        return False
    
    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Update project information.
        
        Args:
            project_id: Project ID
            name: New name
            description: New description
            metadata: New metadata
            tags: New tags
            
        Returns:
            True if updated, False if project not found
        """
        project = self.get_project(project_id)
        if not project:
            return False
        
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if metadata is not None:
            project.metadata.update(metadata)
        if tags is not None:
            project.tags = tags
        
        project.updated_at = datetime.now(timezone.utc)
        self._save_projects()
        
        logger.info(f"Updated project: {project.name} ({project_id})")
        return True
    
    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT,
        project_id: Optional[str] = None,
        summary: str = "",
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """Add a memory entry to a project.
        
        Args:
            content: Memory content
            memory_type: Type of memory
            project_id: Project ID (uses current if None)
            summary: Memory summary
            tags: Memory tags
            importance: Importance score (0.0 to 1.0)
            metadata: Additional metadata
            
        Returns:
            Created memory entry
        """
        # Use current project if not specified
        if not project_id:
            project_id = self.current_project_id
            if not project_id:
                raise ProjectMemoryError("No current project set")
        
        # Verify project exists
        if project_id not in self.projects:
            raise ProjectMemoryError(f"Project not found: {project_id}")
        
        # Create memory entry
        memory = MemoryEntry(
            memory_type=memory_type,
            content=content,
            summary=summary,
            project_id=project_id,
            tags=tags or [],
            importance=importance,
            metadata=metadata or {}
        )
        
        # Add to project memories
        if project_id not in self.project_memories:
            self.project_memories[project_id] = []
        
        self.project_memories[project_id].append(memory)
        
        # Save to storage
        self._save_project_memories(project_id)
        
        logger.debug(f"Added memory to project {project_id}: {memory_type.value}")
        return memory
    
    async def add_memory_with_embedding(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.PROJECT,
        project_id: Optional[str] = None,
        **kwargs
    ) -> MemoryEntry:
        """Add a memory entry with generated embedding.
        
        Args:
            content: Memory content
            memory_type: Type of memory
            project_id: Project ID
            **kwargs: Additional arguments for add_memory
            
        Returns:
            Created memory entry with embedding
        """
        # Generate embedding
        embedding = None
        try:
            embeddings = await self.bedrock.generate_embeddings([content])
            if embeddings:
                embedding = embeddings[0]
        except Exception as e:
            logger.warning(f"Failed to generate embedding for memory: {e}")
        
        # Create memory with embedding
        memory = self.add_memory(
            content=content,
            memory_type=memory_type,
            project_id=project_id,
            **kwargs
        )
        
        memory.embedding = embedding
        
        # Save updated memory
        if project_id or self.current_project_id:
            self._save_project_memories(project_id or self.current_project_id)
        
        return memory
    
    def search_memories(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_types: Optional[List[MemoryType]] = None,
        tags: Optional[List[str]] = None,
        min_importance: float = 0.0,
        max_results: int = 10
    ) -> List[MemoryEntry]:
        """Search project memories.
        
        Args:
            query: Search query
            project_id: Project ID (searches current if None)
            memory_types: Filter by memory types
            tags: Filter by tags
            min_importance: Minimum importance threshold
            max_results: Maximum results to return
            
        Returns:
            List of matching memory entries
        """
        # Determine which projects to search
        projects_to_search = []
        if project_id:
            if project_id in self.project_memories:
                projects_to_search = [project_id]
        else:
            # Search current project
            if self.current_project_id and self.current_project_id in self.project_memories:
                projects_to_search = [self.current_project_id]
        
        if not projects_to_search:
            return []
        
        results = []
        query_lower = query.lower()
        
        for pid in projects_to_search:
            memories = self.project_memories[pid]
            
            for memory in memories:
                # Apply filters
                if memory_types and memory.memory_type not in memory_types:
                    continue
                
                if memory.importance < min_importance:
                    continue
                
                if tags and not any(tag in memory.tags for tag in tags):
                    continue
                
                # Simple text search (could be enhanced with embeddings)
                content_match = query_lower in memory.content.lower()
                summary_match = query_lower in memory.summary.lower()
                tag_match = any(query_lower in tag.lower() for tag in memory.tags)
                
                if content_match or summary_match or tag_match:
                    memory.mark_accessed()
                    results.append(memory)
        
        # Sort by importance and access patterns
        results.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        
        return results[:max_results]
    
    def get_project_context(
        self,
        project_id: Optional[str] = None,
        include_memories: bool = True,
        memory_limit: int = 20
    ) -> Dict[str, Any]:
        """Get comprehensive project context.
        
        Args:
            project_id: Project ID (uses current if None)
            include_memories: Whether to include recent memories
            memory_limit: Maximum memories to include
            
        Returns:
            Dictionary with project context
        """
        project = self.get_project(project_id) if project_id else self.get_current_project()
        if not project:
            return {}
        
        context = {
            "project": project.to_dict(),
            "workspace_analysis": self._get_workspace_summary(project),
        }
        
        if include_memories:
            memories = self.project_memories.get(project.id, [])
            # Get most important and recently accessed memories
            sorted_memories = sorted(
                memories,
                key=lambda m: (m.importance, m.access_count, m.timestamp.timestamp()),
                reverse=True
            )
            
            context["recent_memories"] = [
                memory.to_dict() for memory in sorted_memories[:memory_limit]
            ]
        
        return context
    
    def _analyze_workspace(self, project: ProjectContext):
        """Analyze workspace and update project context."""
        try:
            workspace_path = Path(project.workspace_path)
            if not workspace_path.exists():
                return
            
            # Analyze file patterns
            file_extensions = set()
            important_files = []
            dependencies = []
            
            for file_path in workspace_path.rglob('*'):
                if file_path.is_file():
                    # Collect file extensions
                    if file_path.suffix:
                        file_extensions.add(file_path.suffix)
                    
                    # Identify important files
                    filename = file_path.name.lower()
                    if filename in ['readme.md', 'package.json', 'requirements.txt', 'pyproject.toml', 'cargo.toml']:
                        relative_path = str(file_path.relative_to(workspace_path))
                        important_files.append(relative_path)
                        
                        # Extract dependencies
                        if filename == 'requirements.txt':
                            dependencies.extend(self._parse_requirements_txt(file_path))
                        elif filename == 'package.json':
                            dependencies.extend(self._parse_package_json(file_path))
            
            # Update project context
            project.file_patterns = list(file_extensions)
            project.important_files = important_files
            project.dependencies = dependencies
            
            # Detect coding conventions
            project.coding_conventions = self._detect_coding_conventions(workspace_path)
            
            logger.info(f"Analyzed workspace for project {project.name}: "
                       f"{len(file_extensions)} file types, {len(important_files)} important files")
            
        except Exception as e:
            logger.error(f"Failed to analyze workspace for project {project.id}: {e}")
    
    def _parse_requirements_txt(self, file_path: Path) -> List[str]:
        """Parse Python requirements.txt file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            dependencies = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Extract package name (before version specifiers)
                    package = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0]
                    dependencies.append(package.strip())
            return dependencies
        except Exception:
            return []
    
    def _parse_package_json(self, file_path: Path) -> List[str]:
        """Parse Node.js package.json file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            data = json.loads(content)
            dependencies = []
            
            # Get dependencies and devDependencies
            for dep_type in ['dependencies', 'devDependencies']:
                if dep_type in data:
                    dependencies.extend(data[dep_type].keys())
            
            return dependencies
        except Exception:
            return []
    
    def _detect_coding_conventions(self, workspace_path: Path) -> Dict[str, str]:
        """Detect coding conventions from workspace files."""
        conventions = {}
        
        try:
            # Look for common config files
            config_files = {
                '.editorconfig': 'EditorConfig',
                '.prettierrc': 'Prettier',
                '.eslintrc.json': 'ESLint',
                'pyproject.toml': 'Python (pyproject.toml)',
                'setup.cfg': 'Python (setup.cfg)',
            }
            
            for config_file, description in config_files.items():
                if (workspace_path / config_file).exists():
                    conventions[config_file] = description
            
            # Analyze Python files for style
            python_files = list(workspace_path.rglob('*.py'))
            if python_files:
                # Sample a few files to detect indentation
                indent_style = self._detect_python_indentation(python_files[:5])
                if indent_style:
                    conventions['python_indentation'] = indent_style
            
        except Exception as e:
            logger.debug(f"Failed to detect coding conventions: {e}")
        
        return conventions
    
    def _detect_python_indentation(self, python_files: List[Path]) -> Optional[str]:
        """Detect Python indentation style."""
        try:
            space_count = 0
            tab_count = 0
            
            for file_path in python_files:
                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')
                
                for line in lines:
                    if line.startswith('    '):  # 4 spaces
                        space_count += 1
                    elif line.startswith('\t'):  # Tab
                        tab_count += 1
            
            if space_count > tab_count:
                return "4 spaces"
            elif tab_count > space_count:
                return "tabs"
            
        except Exception:
            pass
        
        return None
    
    def _get_workspace_summary(self, project: ProjectContext) -> Dict[str, Any]:
        """Get summary of workspace analysis."""
        return {
            "file_types": project.file_patterns,
            "important_files": project.important_files,
            "dependencies_count": len(project.dependencies),
            "coding_conventions": project.coding_conventions,
            "last_analyzed": project.updated_at.isoformat(),
        }
    
    def list_projects(
        self,
        active_only: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List projects.
        
        Args:
            active_only: Only return active projects
            limit: Maximum number of projects to return
            
        Returns:
            List of project summaries
        """
        projects = []
        
        for project in self.projects.values():
            if active_only and not project.is_active:
                continue
            
            memory_count = len(self.project_memories.get(project.id, []))
            
            projects.append({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "workspace_path": project.workspace_path,
                "memory_count": memory_count,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
                "is_current": project.id == self.current_project_id,
                "tags": project.tags,
            })
        
        # Sort by update time (most recent first)
        projects.sort(key=lambda x: x["updated_at"], reverse=True)
        
        return projects[:limit]
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project and its memories.
        
        Args:
            project_id: Project ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        if project_id in self.projects:
            # Delete project
            del self.projects[project_id]
            
            # Delete memories
            if project_id in self.project_memories:
                del self.project_memories[project_id]
            
            # Clear current project if it was deleted
            if self.current_project_id == project_id:
                self.current_project_id = None
            
            # Remove memory file
            memories_file = self.storage_path / f"memories_{project_id}.json"
            if memories_file.exists():
                memories_file.unlink()
            
            self._save_projects()
            logger.info(f"Deleted project: {project_id}")
            return True
        
        return False