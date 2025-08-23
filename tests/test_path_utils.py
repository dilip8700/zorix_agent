"""Tests for secure path utilities."""

import tempfile
from pathlib import Path

import pytest

from agent.security.exceptions import SecurityError
from agent.security.path_utils import (
    SecurePath,
    calculate_directory_size,
    find_files_by_pattern,
    get_file_extension,
    get_safe_filename,
    is_code_file,
    is_hidden_file,
    is_text_file,
    normalize_path_separators,
)
from agent.security.sandbox import SecuritySandbox


class TestSecurePath:
    """Test cases for SecurePath."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            yield workspace
    
    @pytest.fixture
    def sandbox(self, temp_workspace):
        """Create a SecuritySandbox instance for testing."""
        return SecuritySandbox(temp_workspace)
    
    def test_secure_path_creation(self, sandbox, temp_workspace):
        """Test SecurePath creation."""
        secure_path = SecurePath("test.txt", sandbox)
        expected = temp_workspace / "test.txt"
        assert secure_path.path == expected.resolve()
    
    def test_secure_path_invalid(self, sandbox):
        """Test SecurePath creation with invalid path."""
        with pytest.raises(SecurityError):
            SecurePath("../../../etc/passwd", sandbox)
    
    def test_secure_path_read_write(self, sandbox, temp_workspace):
        """Test SecurePath read and write operations."""
        secure_path = SecurePath("test.txt", sandbox)
        
        # Write content
        content = "Hello, World!"
        secure_path.write_text(content)
        
        # Verify file exists
        assert secure_path.exists()
        assert secure_path.is_file()
        
        # Read content back
        read_content = secure_path.read_text()
        assert read_content == content
    
    def test_secure_path_mkdir(self, sandbox, temp_workspace):
        """Test SecurePath directory creation."""
        secure_path = SecurePath("new_dir", sandbox)
        
        secure_path.mkdir()
        
        assert secure_path.exists()
        assert secure_path.is_dir()
    
    def test_secure_path_joinpath(self, sandbox, temp_workspace):
        """Test SecurePath joinpath operation."""
        base_path = SecurePath("base", sandbox)
        joined_path = base_path.joinpath("subdir", "file.txt")
        
        expected = temp_workspace / "base" / "subdir" / "file.txt"
        assert joined_path.path == expected.resolve()
    
    def test_secure_path_parent(self, sandbox, temp_workspace):
        """Test SecurePath parent operation."""
        secure_path = SecurePath("dir/file.txt", sandbox)
        parent_path = secure_path.parent()
        
        expected = temp_workspace / "dir"
        assert parent_path.path == expected.resolve()
    
    def test_secure_path_relative_to_workspace(self, sandbox, temp_workspace):
        """Test getting path relative to workspace."""
        secure_path = SecurePath("subdir/file.txt", sandbox)
        relative = secure_path.relative_to_workspace()
        
        assert relative == Path("subdir/file.txt")
    
    def test_secure_path_read_nonexistent(self, sandbox):
        """Test reading nonexistent file."""
        secure_path = SecurePath("nonexistent.txt", sandbox)
        
        with pytest.raises(SecurityError):
            secure_path.read_text()
    
    def test_secure_path_read_directory(self, sandbox, temp_workspace):
        """Test reading directory as file."""
        dir_path = temp_workspace / "test_dir"
        dir_path.mkdir()
        
        secure_path = SecurePath("test_dir", sandbox)
        
        with pytest.raises(SecurityError):
            secure_path.read_text()


class TestPathUtilities:
    """Test cases for path utility functions."""
    
    def test_normalize_path_separators(self):
        """Test path separator normalization."""
        assert normalize_path_separators("path\\to\\file") == "path/to/file"
        assert normalize_path_separators("path/to/file") == "path/to/file"
        assert normalize_path_separators("mixed\\path/to\\file") == "mixed/path/to/file"
    
    def test_is_hidden_file(self):
        """Test hidden file detection."""
        assert is_hidden_file(Path(".hidden")) is True
        assert is_hidden_file(Path(".gitignore")) is True
        assert is_hidden_file(Path("visible.txt")) is False
        assert is_hidden_file(Path("dir/.hidden")) is True
    
    def test_get_file_extension(self):
        """Test file extension extraction."""
        assert get_file_extension(Path("file.txt")) == ".txt"
        assert get_file_extension(Path("file.TAR.GZ")) == ".gz"
        assert get_file_extension(Path("file")) == ""
        assert get_file_extension(Path(".hidden")) == ""
    
    def test_is_text_file(self):
        """Test text file detection."""
        text_files = [
            "file.txt", "script.py", "style.css", "data.json",
            "README.md", "Makefile", "Dockerfile"
        ]
        
        for filename in text_files:
            assert is_text_file(Path(filename)) is True
        
        binary_files = ["image.jpg", "archive.zip", "binary.exe"]
        
        for filename in binary_files:
            assert is_text_file(Path(filename)) is False
    
    def test_is_code_file(self):
        """Test code file detection."""
        code_files = [
            "script.py", "app.js", "component.tsx", "Main.java",
            "program.c", "style.css", "query.sql"
        ]
        
        for filename in code_files:
            assert is_code_file(Path(filename)) is True
        
        non_code_files = ["README.md", "data.json", "image.jpg"]
        
        for filename in non_code_files:
            assert is_code_file(Path(filename)) is False
    
    def test_get_safe_filename(self):
        """Test safe filename generation."""
        test_cases = [
            ("normal_file.txt", "normal_file.txt"),
            ("file with spaces.txt", "file_with_spaces.txt"),
            ("file/with\\slashes.txt", "file_with_slashes.txt"),
            ("file:with:colons.txt", "file_with_colons.txt"),
            ("", "file_"),
            (".hidden", "file_.hidden"),
            ("file<>|?*.txt", "file_.txt"),
        ]
        
        for input_name, expected in test_cases:
            result = get_safe_filename(input_name)
            assert result == expected
            # Ensure result contains only safe characters
            for char in result:
                assert char.isalnum() or char in ".-_"


class TestSecurePathIntegration:
    """Integration tests for secure path operations."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            
            # Create test structure
            (workspace / "src").mkdir()
            (workspace / "src" / "main.py").write_text("print('hello')")
            (workspace / "src" / "utils.js").write_text("console.log('utils')")
            (workspace / "docs").mkdir()
            (workspace / "docs" / "README.md").write_text("# Documentation")
            (workspace / ".hidden").write_text("hidden content")
            (workspace / "binary.jpg").write_bytes(b"fake image data")
            
            yield workspace
    
    @pytest.fixture
    def sandbox(self, temp_workspace):
        """Create a SecuritySandbox instance for testing."""
        return SecuritySandbox(temp_workspace)
    
    def test_find_files_by_pattern(self, sandbox, temp_workspace):
        """Test finding files by pattern."""
        root_path = SecurePath(".", sandbox)
        
        # Find all Python files
        py_files = find_files_by_pattern(root_path, "*.py", recursive=True)
        assert len(py_files) == 1
        assert py_files[0].path.name == "main.py"
        
        # Find all files in src directory
        src_files = find_files_by_pattern(
            SecurePath("src", sandbox), "*", recursive=False
        )
        assert len(src_files) == 2
        
        # Find files including hidden
        all_files = find_files_by_pattern(
            root_path, "*", recursive=True, include_hidden=True
        )
        hidden_files = [f for f in all_files if f.path.name.startswith(".")]
        assert len(hidden_files) >= 1
    
    def test_calculate_directory_size(self, sandbox, temp_workspace):
        """Test directory size calculation."""
        root_path = SecurePath(".", sandbox)
        total_size = calculate_directory_size(root_path)
        
        assert total_size > 0
        
        # Test with specific directory
        src_path = SecurePath("src", sandbox)
        src_size = calculate_directory_size(src_path)
        assert src_size > 0
        assert src_size < total_size
    
    def test_file_operations_workflow(self, sandbox, temp_workspace):
        """Test complete file operations workflow."""
        # Create a new file
        new_file = SecurePath("new_project/config.json", sandbox)
        config_content = '{"name": "test", "version": "1.0.0"}'
        
        new_file.write_text(config_content)
        
        # Verify file was created
        assert new_file.exists()
        assert new_file.is_file()
        
        # Read content back
        read_content = new_file.read_text()
        assert read_content == config_content
        
        # Check file properties
        assert is_text_file(new_file.path)
        assert not is_code_file(new_file.path)
        
        # Get relative path
        relative = new_file.relative_to_workspace()
        assert relative == Path("new_project/config.json")
    
    def test_security_enforcement(self, sandbox):
        """Test that security is enforced in path operations."""
        # Attempt to access file outside workspace
        with pytest.raises(SecurityError):
            SecurePath("../../../etc/passwd", sandbox)
        
        # Attempt to access denylisted file
        with pytest.raises(SecurityError):
            SecurePath("secret.key", sandbox)
        
        # Verify find_files_by_pattern respects security
        root_path = SecurePath(".", sandbox)
        
        # This should not raise an error but should not find anything dangerous
        results = find_files_by_pattern(root_path, "*secret*", recursive=True)
        assert len(results) == 0  # Should not find denylisted files