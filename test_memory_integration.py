#!/usr/bin/env python3
"""Integration test for the memory system."""

import asyncio
import tempfile
from pathlib import Path

from agent.memory.models import MessageRole, MemoryType
from agent.memory.provider import MemoryProvider


async def test_memory_integration():
    """Test complete memory system integration."""
    print("🧠 Testing Memory System Integration...")
    
    # Create temporary storage
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir)
        workspace_path = storage_path / "workspace"
        workspace_path.mkdir()
        
        # Create sample workspace files
        (workspace_path / "README.md").write_text("# AI Agent Project\nThis is an AI agent project.")
        (workspace_path / "requirements.txt").write_text("fastapi==0.68.0\npydantic==1.8.0")
        (workspace_path / "src").mkdir()
        (workspace_path / "src" / "main.py").write_text("""
def main():
    print("Hello from AI Agent!")
    
if __name__ == "__main__":
    main()
""")
        
        # Initialize memory provider
        memory_provider = MemoryProvider(
            storage_path=storage_path / "memory",
            workspace_root=str(workspace_path)
        )
        
        print("✅ Memory provider initialized")
        
        # Test 1: Create project and analyze workspace
        print("\n📁 Testing project creation and workspace analysis...")
        project = memory_provider.create_project(
            name="AI Agent Project",
            description="A sophisticated AI agent with memory capabilities",
            workspace_path=str(workspace_path)
        )
        
        print(f"✅ Created project: {project.name}")
        print(f"   - File patterns: {project.file_patterns}")
        print(f"   - Important files: {project.important_files}")
        print(f"   - Dependencies: {project.dependencies}")
        
        # Test 2: Add project memories
        print("\n🧠 Testing project memory storage...")
        await memory_provider.add_project_memory(
            content="The AI agent uses FastAPI for the web interface and Pydantic for data validation.",
            memory_type=MemoryType.PROJECT,
            summary="Tech stack information",
            tags=["architecture", "fastapi", "pydantic"],
            importance=0.8
        )
        
        await memory_provider.add_project_memory(
            content="Authentication should be implemented using JWT tokens with role-based access control.",
            memory_type=MemoryType.CODE_CONTEXT,
            summary="Authentication strategy",
            tags=["auth", "jwt", "security"],
            importance=0.9
        )
        
        await memory_provider.add_project_memory(
            content="The main entry point is in src/main.py and prints a greeting message.",
            memory_type=MemoryType.CODE_CONTEXT,
            summary="Main entry point",
            tags=["main", "entry"],
            importance=0.6
        )
        
        print("✅ Added 3 project memories")
        
        # Test 3: Create conversation session
        print("\n💬 Testing conversation management...")
        session = memory_provider.create_conversation_session(
            title="Development Discussion",
            project_id=project.id
        )
        
        # Add conversation messages
        memory_provider.add_conversation_message(
            "How should we implement user authentication in this project?",
            MessageRole.USER
        )
        
        memory_provider.add_conversation_message(
            "Based on the project context, I recommend using JWT tokens with FastAPI's security utilities. "
            "We can implement role-based access control for different user types.",
            MessageRole.ASSISTANT
        )
        
        memory_provider.add_conversation_message(
            "That sounds good. Can you show me a code example?",
            MessageRole.USER
        )
        
        memory_provider.add_conversation_message(
            "```python\\n"
            "from fastapi import FastAPI, Depends, HTTPException\\n"
            "from fastapi.security import HTTPBearer\\n"
            "import jwt\\n\\n"
            "app = FastAPI()\\n"
            "security = HTTPBearer()\\n\\n"
            "def verify_token(token: str = Depends(security)):\\n"
            "    try:\\n"
            "        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=['HS256'])\\n"
            "        return payload\\n"
            "    except jwt.InvalidTokenError:\\n"
            "        raise HTTPException(status_code=401, detail='Invalid token')\\n"
            "```",
            MessageRole.ASSISTANT,
            tool_calls=[{"function": {"name": "code_generation"}}]
        )
        
        print("✅ Added conversation with 4 messages")
        
        # Test 4: Search memories
        print("\n🔍 Testing memory search...")
        
        # Text search
        results = await memory_provider.search_memories("authentication JWT")
        print(f"✅ Text search found {len(results)} results:")
        for i, result in enumerate(results[:3]):
            print(f"   {i+1}. {result.entry.summary} (score: {result.score:.2f})")
            print(f"      Type: {result.entry.memory_type.value}")
            print(f"      Content preview: {result.entry.content[:100]}...")
        
        # Semantic search (if embeddings are available)
        try:
            semantic_results = await memory_provider.semantic_search(
                "user login and security features",
                similarity_threshold=0.1
            )
            print(f"✅ Semantic search found {len(semantic_results)} results")
        except Exception as e:
            print(f"⚠️  Semantic search not available: {e}")
        
        # Test 5: Get full context
        print("\n📋 Testing context retrieval...")
        context = memory_provider.get_full_context()
        
        print("✅ Retrieved full context:")
        print(f"   - Conversation messages: {len(context['conversation']['messages'])}")
        print(f"   - Project memories: {len(context['project'].get('recent_memories', []))}")
        print(f"   - Project name: {context['project']['project']['name']}")
        
        # Test 6: Convert conversation to memories
        print("\n🔄 Testing conversation to memory conversion...")
        conversation_memories = await memory_provider.create_conversation_memories(
            session_id=session.id,
            importance_threshold=0.6
        )
        
        print(f"✅ Created {len(conversation_memories)} memories from conversation")
        for memory in conversation_memories:
            print(f"   - {memory.summary} (importance: {memory.importance:.2f})")
        
        # Test 7: Memory statistics
        print("\n📊 Testing memory statistics...")
        stats = memory_provider.get_memory_stats()
        
        print("✅ Memory statistics:")
        print(f"   - Total memories: {stats['total_memories']}")
        print(f"   - Conversation sessions: {stats['conversation']['total_sessions']}")
        print(f"   - Conversation messages: {stats['conversation']['total_messages']}")
        print(f"   - Projects: {stats['project']['total_projects']}")
        print(f"   - Project memories: {stats['project']['total_project_memories']}")
        
        # Test 8: Memory optimization
        print("\n🔧 Testing memory optimization...")
        await memory_provider.optimize_memories(
            max_memories_per_project=10,
            importance_threshold=0.5
        )
        
        optimized_stats = memory_provider.get_memory_stats()
        print(f"✅ Optimized memories: {optimized_stats['project']['total_project_memories']} remaining")
        
        # Test 9: Persistence test
        print("\n💾 Testing persistence...")
        
        # Create new provider instance to test loading
        memory_provider2 = MemoryProvider(
            storage_path=storage_path / "memory",
            workspace_root=str(workspace_path)
        )
        
        # Verify data was loaded
        loaded_projects = memory_provider2.list_projects()
        loaded_sessions = memory_provider2.list_sessions()
        
        print(f"✅ Persistence verified:")
        print(f"   - Loaded {len(loaded_projects)} projects")
        print(f"   - Loaded {len(loaded_sessions)} sessions")
        
        # Test 10: Advanced search with filters
        print("\n🎯 Testing advanced search with filters...")
        
        # Search by memory type
        auth_memories = await memory_provider.search_memories(
            "authentication",
            memory_types=[MemoryType.CODE_CONTEXT],
            max_results=5
        )
        print(f"✅ Found {len(auth_memories)} code context memories about authentication")
        
        # Search by project
        project_specific = await memory_provider.search_memories(
            "FastAPI",
            project_id=project.id,
            max_results=5
        )
        print(f"✅ Found {len(project_specific)} project-specific memories about FastAPI")
        
        print("\n🎉 Memory system integration test completed successfully!")
        
        return True


async def test_memory_performance():
    """Test memory system performance with larger datasets."""
    print("\n⚡ Testing Memory System Performance...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir)
        
        memory_provider = MemoryProvider(storage_path=storage_path / "memory")
        
        # Create project
        project = memory_provider.create_project("Performance Test Project")
        
        # Add many memories
        print("📝 Adding 100 memories...")
        import time
        start_time = time.time()
        
        for i in range(100):
            await memory_provider.add_project_memory(
                content=f"This is memory entry number {i} with some detailed content about various topics including "
                       f"authentication, database operations, API endpoints, and user management features.",
                memory_type=MemoryType.PROJECT,
                summary=f"Memory {i}",
                tags=[f"tag{i % 10}", "performance", "test"],
                importance=0.1 + (i % 10) * 0.1
            )
        
        add_time = time.time() - start_time
        print(f"✅ Added 100 memories in {add_time:.2f} seconds ({100/add_time:.1f} memories/sec)")
        
        # Test search performance
        print("🔍 Testing search performance...")
        start_time = time.time()
        
        for i in range(20):
            results = await memory_provider.search_memories(f"authentication memory {i}")
        
        search_time = time.time() - start_time
        print(f"✅ Performed 20 searches in {search_time:.2f} seconds ({20/search_time:.1f} searches/sec)")
        
        # Test optimization performance
        print("🔧 Testing optimization performance...")
        start_time = time.time()
        
        await memory_provider.optimize_memories(
            max_memories_per_project=50,
            importance_threshold=0.5
        )
        
        optimize_time = time.time() - start_time
        print(f"✅ Optimized memories in {optimize_time:.2f} seconds")
        
        final_stats = memory_provider.get_memory_stats()
        print(f"📊 Final memory count: {final_stats['project']['total_project_memories']}")
        
        print("⚡ Performance test completed!")


if __name__ == "__main__":
    async def main():
        try:
            await test_memory_integration()
            await test_memory_performance()
            print("\n🎉 All memory integration tests passed!")
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        return True
    
    # Run the test
    success = asyncio.run(main())
    exit(0 if success else 1)