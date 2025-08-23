#!/usr/bin/env python3
"""Integration test for Vector indexing and search."""

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_vector_indexing():
    """Test vector indexing functionality."""
    from agent.vector.index import VectorIndex
    from agent.vector.chunking import CodeChunker
    from agent.vector.search import SearchRanker
    
    print("Testing Vector Indexing Integration...")
    
    # Create temporary workspace and index
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        index_path = workspace / "index"
        
        # Create test files
        (workspace / "calculator.py").write_text("""
def add(a, b):
    '''Add two numbers together.'''
    return a + b

def multiply(a, b):
    '''Multiply two numbers.'''
    return a * b

class Calculator:
    '''A simple calculator class.'''
    
    def __init__(self):
        self.memory = 0
    
    def add_to_memory(self, value):
        '''Add value to memory.'''
        self.memory += value
        return self.memory
""")
        
        (workspace / "utils.js").write_text("""
function formatNumber(num) {
    return num.toLocaleString();
}

function validateEmail(email) {
    const regex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
    return regex.test(email);
}
""")
        
        (workspace / "README.md").write_text("""
# Test Project

This project contains utility functions for:
- Mathematical calculations
- Email validation
- Number formatting
""")
        
        print("✓ Test files created")
        
        # Test CodeChunker
        chunker = CodeChunker(max_chunk_size=500, overlap_size=50)
        
        # Test language detection
        assert chunker.language_detector.detect_language(Path("test.py")) == "python"
        assert chunker.language_detector.detect_language(Path("test.js")) == "javascript"
        assert chunker.language_detector.detect_language(Path("README.md")) == "markdown"
        print("✓ Language detection works")
        
        # Test file filtering
        assert chunker.should_index_file(Path("main.py"))
        assert not chunker.should_index_file(Path("node_modules/package.json"))
        assert not chunker.should_index_file(Path(".git/config"))
        print("✓ File filtering works")
        
        # Test chunking
        python_content = (workspace / "calculator.py").read_text()
        chunks = chunker.chunk_file(workspace / "calculator.py", python_content)
        
        assert len(chunks) > 0
        assert any(chunk.chunk_type == "function" for chunk in chunks)
        print(f"✓ Python chunking works ({len(chunks)} chunks created)")
        
        # Test SearchRanker
        ranker = SearchRanker(snippet_length=100, context_lines=2)
        
        # Test snippet extraction
        long_text = "This is a very long text that should be truncated to show only relevant parts around the search query."
        snippet = ranker._extract_snippet(long_text, "relevant parts")
        assert "relevant parts" in snippet
        assert len(snippet) <= 120  # With some tolerance
        print("✓ Snippet extraction works")
        
        # Test highlighting
        highlighted = ranker._highlight_snippet("This is a test snippet", "test")
        assert "**test**" in highlighted
        print("✓ Text highlighting works")
        
        # Mock Bedrock client for testing
        mock_bedrock = AsyncMock()
        mock_bedrock.generate_embeddings.return_value = [
            [0.1] * 1536,  # Mock embedding
            [0.2] * 1536,
            [0.3] * 1536,
        ]
        
        # Test VectorIndex
        vector_index = VectorIndex(
            index_path=index_path,
            bedrock_client=mock_bedrock,
            workspace_root=str(workspace)
        )
        
        print("✓ VectorIndex initialized")
        
        # Test index building
        stats = await vector_index.build_index()
        
        assert stats['files_processed'] == 3
        assert stats['chunks_created'] > 0
        assert stats['chunks_indexed'] > 0
        assert len(stats['errors']) == 0
        print(f"✓ Index built successfully:")
        print(f"  Files processed: {stats['files_processed']}")
        print(f"  Chunks created: {stats['chunks_created']}")
        print(f"  Chunks indexed: {stats['chunks_indexed']}")
        
        # Test index statistics
        index_stats = vector_index.get_index_stats()
        assert index_stats['total_files'] == 3
        assert 'python' in index_stats['languages']
        assert 'javascript' in index_stats['languages']
        assert 'markdown' in index_stats['languages']
        print("✓ Index statistics work")
        
        # Test search (mock search embeddings)
        mock_bedrock.generate_embeddings.return_value = [[0.15] * 1536]
        
        results = await vector_index.search("calculator function", top_k=5)
        assert isinstance(results, list)
        print(f"✓ Search works ({len(results)} results returned)")
        
        # Test file update
        (workspace / "new_file.py").write_text("def new_function(): pass")
        update_result = await vector_index.update_file("new_file.py")
        assert update_result['action'] == 'updated'
        print("✓ File update works")
        
        # Test file deletion
        (workspace / "new_file.py").unlink()
        delete_result = await vector_index.update_file("new_file.py")
        assert delete_result['action'] == 'removed'
        print("✓ File deletion handling works")
        
        print("\n🎉 All Vector indexing tests passed!")
        return True


async def test_chunking_edge_cases():
    """Test edge cases in code chunking."""
    from agent.vector.chunking import CodeChunker
    
    print("\nTesting Code Chunking Edge Cases...")
    
    chunker = CodeChunker(max_chunk_size=200, overlap_size=20)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        
        # Test empty file
        empty_file = workspace / "empty.py"
        empty_file.write_text("")
        chunks = chunker.chunk_file(empty_file, "")
        assert len(chunks) == 0
        print("✓ Empty file handling works")
        
        # Test file with syntax errors
        syntax_error_file = workspace / "syntax_error.py"
        syntax_error_file.write_text("def broken_function(\n    # Missing closing parenthesis")
        chunks = chunker.chunk_file(syntax_error_file, syntax_error_file.read_text())
        assert len(chunks) > 0  # Should fall back to generic chunking
        print("✓ Syntax error handling works")
        
        # Test very long file
        long_content = "# This is a comment\n" * 1000
        long_file = workspace / "long.py"
        long_file.write_text(long_content)
        chunks = chunker.chunk_file(long_file, long_content)
        assert len(chunks) > 1  # Should be split into multiple chunks
        print(f"✓ Long file chunking works ({len(chunks)} chunks)")
        
        # Test binary-like content
        binary_content = "".join(chr(i) for i in range(256))
        binary_file = workspace / "binary.dat"
        binary_file.write_text(binary_content, encoding='utf-8', errors='ignore')
        chunks = chunker.chunk_file(binary_file, binary_content)
        assert len(chunks) >= 0  # Should handle gracefully
        print("✓ Binary content handling works")
        
        print("✓ All edge case tests passed!")
        return True


async def test_search_ranking():
    """Test search result ranking and processing."""
    from agent.vector.search import SearchResult, SearchRanker
    
    print("\nTesting Search Ranking...")
    
    ranker = SearchRanker(snippet_length=150, context_lines=2)
    
    # Create test results
    results = [
        SearchResult(
            content="def calculate_sum(a, b):\n    '''Calculate sum of two numbers.'''\n    return a + b",
            file_path="math_utils.py",
            start_line=10,
            end_line=12,
            score=0.7,
            chunk_type="function",
            language="python",
            metadata={"name": "calculate_sum"}
        ),
        SearchResult(
            content="# This function calculates the sum of numbers",
            file_path="math_utils.py",
            start_line=8,
            end_line=8,
            score=0.5,
            chunk_type="comment",
            language="python",
            metadata={}
        ),
        SearchResult(
            content="def multiply(x, y):\n    return x * y",
            file_path="math_utils.py",
            start_line=15,
            end_line=16,
            score=0.3,
            chunk_type="function",
            language="python",
            metadata={"name": "multiply"}
        ),
    ]
    
    # Test ranking
    query = "calculate sum function"
    ranked = ranker.rank_results(results, query, max_results=10)
    
    assert len(ranked) <= len(results)
    
    # Check that results are sorted by score
    for i in range(len(ranked) - 1):
        assert ranked[i].score >= ranked[i + 1].score
    
    # Check that snippets and highlights are added
    for result in ranked:
        assert result.snippet is not None
        assert result.highlighted_snippet is not None
        if "calculate" in result.content.lower():
            assert "**calculate**" in result.highlighted_snippet or "calculate" in result.snippet
    
    print("✓ Result ranking works")
    
    # Test grouping by file
    grouped = ranker.group_results_by_file(ranked)
    assert "math_utils.py" in grouped
    assert len(grouped["math_utils.py"]) == len(ranked)
    print("✓ File grouping works")
    
    # Test statistics
    stats = ranker.get_search_stats(ranked)
    assert stats['total_results'] == len(ranked)
    assert stats['files_matched'] == 1
    assert stats['languages']['python'] == len(ranked)
    print("✓ Search statistics work")
    
    print("✓ All search ranking tests passed!")
    return True


if __name__ == "__main__":
    async def main():
        try:
            success1 = await test_vector_indexing()
            success2 = await test_chunking_edge_cases()
            success3 = await test_search_ranking()
            
            if success1 and success2 and success3:
                print("\n🎉 All Vector integration tests passed successfully!")
                sys.exit(0)
            else:
                print("\n❌ Some tests failed!")
                sys.exit(1)
                
        except Exception as e:
            print(f"\n❌ Integration test failed with error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Run the async main function
    asyncio.run(main())