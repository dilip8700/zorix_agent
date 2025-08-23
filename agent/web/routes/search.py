"""Search API routes."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from agent.web.api import get_app_state
from agent.web.models import SearchRequest, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=SearchResponse)
async def search(search_request: SearchRequest):
    """Perform search across code, memory, and files."""
    app_state = get_app_state()
    vector_index = app_state.get("vector_index")
    memory_provider = app_state.get("memory_provider")
    
    if not vector_index and not memory_provider:
        raise HTTPException(status_code=500, detail="Search components not available")
    
    results = []
    search_start_time = __import__('time').time()
    
    try:
        # Search code if requested
        if search_request.search_type in ["code", "all"] and vector_index:
            try:
                code_results = await vector_index.search(
                    query=search_request.query,
                    max_results=search_request.max_results // 2 if search_request.search_type == "all" else search_request.max_results,
                    file_patterns=search_request.file_patterns
                )
                
                for result in code_results:
                    results.append(SearchResult(
                        type="code",
                        title=f"Code: {result.get('file_path', 'Unknown')}",
                        content=result.get('content', ''),
                        path=result.get('file_path'),
                        score=result.get('score', 0.0),
                        metadata={
                            "line_number": result.get('line_number'),
                            "function_name": result.get('function_name'),
                            "class_name": result.get('class_name'),
                            "language": result.get('language')
                        }
                    ))
                    
            except Exception as e:
                logger.error(f"Code search failed: {e}")
        
        # Search memory if requested
        if search_request.search_type in ["memory", "all"] and memory_provider:
            try:
                memory_results = await memory_provider.search_memories(
                    query=search_request.query,
                    limit=search_request.max_results // 2 if search_request.search_type == "all" else search_request.max_results,
                    project_id=search_request.project_id
                )
                
                for memory in memory_results:
                    results.append(SearchResult(
                        type="memory",
                        title=f"Memory: {memory.memory_type}",
                        content=memory.content,
                        path=None,
                        score=memory.relevance_score if hasattr(memory, 'relevance_score') else 0.8,
                        metadata={
                            "memory_type": memory.memory_type,
                            "created_at": memory.created_at.isoformat(),
                            "project_id": memory.project_id,
                            "tags": memory.metadata.get('tags', []) if memory.metadata else []
                        }
                    ))
                    
            except Exception as e:
                logger.error(f"Memory search failed: {e}")
        
        # Search files if requested
        if search_request.search_type in ["files", "all"] and vector_index:
            try:
                # File search using vector index metadata
                file_results = await vector_index.search_files(
                    query=search_request.query,
                    max_results=search_request.max_results // 3 if search_request.search_type == "all" else search_request.max_results,
                    file_patterns=search_request.file_patterns
                )
                
                for result in file_results:
                    results.append(SearchResult(
                        type="file",
                        title=f"File: {result.get('file_path', 'Unknown')}",
                        content=result.get('summary', result.get('content', '')[:200] + '...'),
                        path=result.get('file_path'),
                        score=result.get('score', 0.0),
                        metadata={
                            "file_size": result.get('file_size'),
                            "modified_at": result.get('modified_at'),
                            "file_type": result.get('file_type'),
                            "language": result.get('language')
                        }
                    ))
                    
            except Exception as e:
                logger.error(f"File search failed: {e}")
        
        # Sort results by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Limit results
        results = results[:search_request.max_results]
        
        search_time_ms = (__import__('time').time() - search_start_time) * 1000
        
        return SearchResponse(
            query=search_request.query,
            results=results,
            total_results=len(results),
            search_time_ms=search_time_ms
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions(query: str, limit: int = 5):
    """Get search suggestions based on query."""
    app_state = get_app_state()
    memory_provider = app_state.get("memory_provider")
    
    suggestions = []
    
    try:
        if memory_provider:
            # Get recent memories that might be relevant
            recent_memories = await memory_provider.get_recent_memories(limit=20)
            
            # Simple suggestion logic based on content matching
            query_lower = query.lower()
            for memory in recent_memories:
                if query_lower in memory.content.lower():
                    # Extract relevant phrases
                    content_words = memory.content.split()
                    for i, word in enumerate(content_words):
                        if query_lower in word.lower():
                            # Get surrounding context
                            start = max(0, i - 2)
                            end = min(len(content_words), i + 3)
                            suggestion = " ".join(content_words[start:end])
                            if suggestion not in suggestions:
                                suggestions.append(suggestion)
                                if len(suggestions) >= limit:
                                    break
                    if len(suggestions) >= limit:
                        break
        
        # Add some common search patterns if no suggestions found
        if not suggestions:
            common_patterns = [
                f"{query} function",
                f"{query} class",
                f"{query} implementation",
                f"{query} example",
                f"how to {query}"
            ]
            suggestions = common_patterns[:limit]
        
        return {
            "query": query,
            "suggestions": suggestions[:limit]
        }
        
    except Exception as e:
        logger.error(f"Failed to get suggestions: {e}")
        return {
            "query": query,
            "suggestions": []
        }


@router.get("/recent")
async def get_recent_searches(limit: int = 10):
    """Get recent search queries."""
    # This would typically be stored in a database
    # For now, return empty list
    return {
        "recent_searches": [],
        "limit": limit
    }


@router.post("/index")
async def reindex_workspace():
    """Trigger workspace reindexing."""
    app_state = get_app_state()
    vector_index = app_state.get("vector_index")
    
    if not vector_index:
        raise HTTPException(status_code=500, detail="Vector index not available")
    
    try:
        # Get workspace root
        settings = app_state.get("settings")
        if not settings:
            raise HTTPException(status_code=500, detail="Settings not available")
        
        # Reindex workspace
        indexed_files = await vector_index.index_workspace(settings.workspace_root)
        
        return {
            "message": "Workspace reindexed successfully",
            "indexed_files": len(indexed_files),
            "files": indexed_files
        }
        
    except Exception as e:
        logger.error(f"Failed to reindex workspace: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reindex workspace: {str(e)}")


@router.get("/index/status")
async def get_index_status():
    """Get indexing status."""
    app_state = get_app_state()
    vector_index = app_state.get("vector_index")
    
    if not vector_index:
        raise HTTPException(status_code=500, detail="Vector index not available")
    
    try:
        status = await vector_index.get_status()
        
        return {
            "status": status.get("status", "unknown"),
            "total_documents": status.get("total_documents", 0),
            "last_updated": status.get("last_updated"),
            "index_size_mb": status.get("index_size_mb", 0),
            "supported_languages": status.get("supported_languages", [])
        }
        
    except Exception as e:
        logger.error(f"Failed to get index status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get index status: {str(e)}")


@router.delete("/index")
async def clear_index():
    """Clear the search index."""
    app_state = get_app_state()
    vector_index = app_state.get("vector_index")
    
    if not vector_index:
        raise HTTPException(status_code=500, detail="Vector index not available")
    
    try:
        await vector_index.clear()
        
        return {
            "message": "Search index cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear index: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear index: {str(e)}")


@router.get("/stats")
async def get_search_stats():
    """Get search statistics."""
    app_state = get_app_state()
    vector_index = app_state.get("vector_index")
    memory_provider = app_state.get("memory_provider")
    
    stats = {
        "total_indexed_files": 0,
        "total_memories": 0,
        "index_size_mb": 0,
        "supported_file_types": [],
        "last_index_update": None
    }
    
    try:
        if vector_index:
            index_status = await vector_index.get_status()
            stats.update({
                "total_indexed_files": index_status.get("total_documents", 0),
                "index_size_mb": index_status.get("index_size_mb", 0),
                "supported_file_types": index_status.get("supported_languages", []),
                "last_index_update": index_status.get("last_updated")
            })
        
        if memory_provider:
            memory_stats = await memory_provider.get_memory_stats()
            stats["total_memories"] = memory_stats.get("total_memories", 0)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        return stats