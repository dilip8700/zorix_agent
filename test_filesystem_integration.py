#!/usr/bin/env python3
"""Integration test for filesystem tools."""

import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_filesystem_tools():
    """Test filesystem tools functionality."""
    from agent.tools.filesystem import FilesystemTools
    from agent.security.exceptions import SecurityError
    
    print("Testing Filesystem Tools Integration...")
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        fs_tools = FilesystemTools(workspace_root=str(workspace))
        
        print("✓ Testing filesystem tools initialization...")
        assert fs_tools.workspace_root == workspace.resolve()
        print("  ✓ FilesystemTools initialized successfully")
        
        # Test 1: Write and read file
        print("✓ Testing file write and read operations...")
        
        test_content = """def hello_world():
    print("Hello, World!")
    return "success"

class TestClass:
    def __init__(self):
        self.value = 42
"""
        
        # Write file
        write_result = fs_tools.write_file("test_script.py", test_content)
        assert write_result["created"] is True
        assert write_result["lines"] == 7
        assert write_result["encoding"] == "utf-8"
        
        # Read file back
        read_result = fs_tools.read_file("test_script.py")
        # Normalize line endings for cross-platform compatibility
        read_content_normalized = read_result["content"].replace('\r\n', '\n')
        assert read_content_normalized == test_content
        print(f"  Debug: Detected encoding: {read_result['encoding']}")
        # Be flexible with encoding detection - utf-8 variants are acceptable
        assert read_result["encoding"].lower() in ["utf-8", "ascii", "utf-8-sig"]
        assert read_result["lines"] == 7
        
        print("  ✓ File write and read working correctly")
        
        # Test 2: Directory listing
        print("✓ Testing directory listing...")
        
        # Create more files
        fs_tools.write_file("data.json", '{"key": "value", "number": 123}')
        fs_tools.write_file("readme.md", "# Test Project\n\nThis is a test.")
        fs_tools.write_file("subdir/nested.txt", "Nested file content")
        
        # List directory
        list_result = fs_tools.list_directory(".")
        assert list_result["total_files"] == 3  # test_script.py, data.json, readme.md
        assert list_result["total_directories"] == 1  # subdir
        
        file_names = [f["name"] for f in list_result["files"]]
        assert "test_script.py" in file_names
        assert "data.json" in file_names
        assert "readme.md" in file_names
        
        # List with pattern
        py_files = fs_tools.list_directory(".", pattern="*.py")
        assert py_files["total_files"] == 1
        assert py_files["files"][0]["name"] == "test_script.py"
        
        # List recursively
        recursive_list = fs_tools.list_directory(".", recursive=True)
        all_files = [f["path"] for f in recursive_list["files"]]
        assert str(Path("subdir") / "nested.txt") in all_files
        
        print("  ✓ Directory listing working correctly")
        
        # Test 3: Code search
        print("✓ Testing code search...")
        
        # Search for specific text
        search_result = fs_tools.search_code("Hello, World!")
        assert len(search_result["results"]) >= 1
        assert any("test_script.py" in r["file"] for r in search_result["results"])
        
        # Search with regex
        class_search = fs_tools.search_code(r"class \w+:")
        assert len(class_search["results"]) >= 1
        assert any("TestClass" in r["match"] for r in class_search["results"])
        
        # Search with file pattern
        py_search = fs_tools.search_code("def", file_patterns=["*.py"])
        assert len(py_search["results"]) >= 1
        assert all(r["file"].endswith(".py") for r in py_search["results"])
        
        print("  ✓ Code search working correctly")
        
        # Test 4: Patch application
        print("✓ Testing patch application...")
        
        # Create patch to modify the hello_world function
        patch_content = """--- test_script.py
+++ test_script.py
@@ -1,3 +1,3 @@
 def hello_world():
-    print("Hello, World!")
+    print("Hello, Universe!")
     return "success\""""
        
        # Apply patch
        patch_result = fs_tools.apply_patch("test_script.py", patch_content, backup=True)
        assert patch_result["patch_applied"] is True
        assert patch_result["backup_created"] is True
        assert patch_result["changes"].lines_added == 1
        assert patch_result["changes"].lines_removed == 1
        
        # Verify patch was applied
        modified_content = fs_tools.read_file("test_script.py")["content"]
        assert "Hello, Universe!" in modified_content
        assert "Hello, World!" not in modified_content
        
        # Verify backup exists
        backup_path = Path(patch_result["backup_path"])
        assert backup_path.exists()
        backup_content = backup_path.read_text(encoding='utf-8')
        assert "Hello, World!" in backup_content
        
        print("  ✓ Patch application working correctly")
        
        # Test 5: File information
        print("✓ Testing file information...")
        
        info_result = fs_tools.get_file_info("test_script.py")
        assert info_result["is_file"] is True
        assert info_result["is_dir"] is False
        assert info_result["extension"] == ".py"
        assert info_result["file_type"] == "code"
        assert info_result["exists"] is True
        
        # Test directory info
        dir_info = fs_tools.get_file_info("subdir")
        assert dir_info["is_file"] is False
        assert dir_info["is_dir"] is True
        
        print("  ✓ File information working correctly")
        
        # Test 6: Security boundaries
        print("✓ Testing security boundaries...")
        
        # Try to access file outside workspace
        try:
            fs_tools.read_file("../outside.txt")
            assert False, "Should have raised SecurityError"
        except SecurityError:
            pass  # Expected
        
        try:
            fs_tools.write_file("../outside.txt", "content")
            assert False, "Should have raised SecurityError"
        except SecurityError:
            pass  # Expected
        
        print("  ✓ Security boundaries working correctly")
        
        # Test 7: Encoding handling
        print("✓ Testing encoding handling...")
        
        # Write file with different encoding
        unicode_content = "Café résumé naïve 🚀"
        fs_tools.write_file("unicode.txt", unicode_content, encoding="utf-8")
        
        # Read back and verify
        unicode_result = fs_tools.read_file("unicode.txt")
        assert unicode_result["content"] == unicode_content
        assert unicode_result["encoding"] == "utf-8"
        
        print("  ✓ Encoding handling working correctly")
        
        # Test 8: Atomic operations
        print("✓ Testing atomic operations...")
        
        # Write with atomic operation
        atomic_content = "Atomic write test content"
        atomic_result = fs_tools.write_file("atomic.txt", atomic_content, atomic=True)
        assert atomic_result["path"] == "atomic.txt"
        
        # Verify content
        atomic_read = fs_tools.read_file("atomic.txt")
        assert atomic_read["content"] == atomic_content
        
        print("  ✓ Atomic operations working correctly")
        
        print("🎉 All filesystem tools tests passed!")
        return True


if __name__ == "__main__":
    try:
        result = test_filesystem_tools()
        if result:
            print("\n✅ Filesystem tools integration test - PASSED")
        else:
            print("\n❌ Filesystem tools integration test - FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)