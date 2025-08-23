"""Path utilities with security validation."""

import os
from pathlib import Path
from typing import List, Optional, Union

from agent.security.exceptions import SecurityError
from agent.security.sandbox import SecuritySandbox


class SecurePath:
    """A path wrapper that enforces security constraints."""
    
    def __init__(self, path: Union[str, Path], sandbox: SecuritySandbox):
        """Initialize secure path.
        
        Args:
            path: Path to wrap
            sandbox: Security sandbox for validation
        """
        self.sandbox = sandbox
        self._path = sandbox.validate_path(str(path))
    
    @property
    def path(self) -> Path:
        """Get the validated path."""
        return self._path
    
    def __str__(self) -> str:
        """String representation."""
        return str(self._path)
    
    def __repr__(self) -> str:
        """Repr representation."""
        return f"SecurePath({self._path})"
    
    def exists(self) -> bool:
        """Check if path exists."""
        return self._path.exists()
    
    def is_file(self) -> bool:
        """Check if path is a file."""
        return self._path.is_file()
    
    def is_dir(self) -> bool:
        """Check if path is a directory."""
        return self._path.is_dir()
    
    def read_text(self, encoding: str = "utf-8") -> str:
        """Read text from file with security validation."""
        if not self.is_file():
            raise SecurityError(f"Path is not a file: {self._path}")
        
        try:
            return self._path.read_text(encoding=encoding)
        except Exception as e:
            raise SecurityError(f"Cannot read file {self._path}: {e}") from e
    
    def write_text(self, content: str, encoding: str = "utf-8") -> None:
        """Write text to file with security validation."""
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self._path.write_text(content, encoding=encoding)
        except Exception as e:
            raise SecurityError(f"Cannot write file {self._path}: {e}") from e
    
    def mkdir(self, parents: bool = True, exist_ok: bool = True) -> None:
        """Create directory with security validation."""
        try:
            self._path.mkdir(parents=parents, exist_ok=exist_ok)
        except Exception as e:
            raise SecurityError(f"Cannot create directory {self._path}: {e}") from e
    
    def joinpath(self, *args) -> "SecurePath":
        """Join path components and return new SecurePath."""
        new_path = self._path.joinpath(*args)
        return SecurePath(new_path, self.sandbox)
    
    def parent(self) -> "SecurePath":
        """Get parent directory as SecurePath."""
        return SecurePath(self._path.parent, self.sandbox)
    
    def relative_to_workspace(self) -> Path:
        """Get path relative to workspace root."""
        return self._path.relative_to(self.sandbox.workspace_root)


def normalize_path_separators(path: str) -> str:
    """Normalize path separators for cross-platform compatibility.
    
    Args:
        path: Path string to normalize
        
    Returns:
        Normalized path string
    """
    return path.replace("\\", "/")


def is_hidden_file(path: Path) -> bool:
    """Check if a file or directory is hidden.
    
    Args:
        path: Path to check
        
    Returns:
        True if path is hidden
    """
    # Unix-style hidden files
    if path.name.startswith("."):
        return True
    
    # Windows hidden files
    if os.name == "nt" and path.exists():
        try:
            import stat
            return bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
        except (AttributeError, OSError):
            pass
    
    return False


def get_file_extension(path: Path) -> str:
    """Get file extension in lowercase.
    
    Args:
        path: Path to get extension from
        
    Returns:
        File extension (including dot) in lowercase
    """
    return path.suffix.lower()


def is_text_file(path: Path) -> bool:
    """Check if a file is likely a text file based on extension.
    
    Args:
        path: Path to check
        
    Returns:
        True if likely a text file
    """
    text_extensions = {
        ".txt", ".md", ".rst", ".py", ".js", ".ts", ".jsx", ".tsx",
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".xml", ".svg", ".csv", ".log",
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
        ".java", ".kt", ".scala", ".clj", ".cljs",
        ".go", ".rs", ".rb", ".php", ".pl", ".r",
        ".sql", ".dockerfile", ".makefile",
        ".gitignore", ".gitattributes", ".editorconfig",
    }
    
    extension = get_file_extension(path)
    return extension in text_extensions or path.name.lower() in {
        "makefile", "dockerfile", "readme", "license", "changelog"
    }


def is_code_file(path: Path) -> bool:
    """Check if a file is a code file based on extension.
    
    Args:
        path: Path to check
        
    Returns:
        True if it's a code file
    """
    code_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".kt", ".scala", ".clj", ".cljs",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
        ".go", ".rs", ".rb", ".php", ".pl", ".r",
        ".sh", ".bash", ".zsh", ".fish", ".ps1",
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".sql", ".dockerfile",
    }
    
    extension = get_file_extension(path)
    return extension in code_extensions


def get_safe_filename(filename: str) -> str:
    """Generate a safe filename by removing dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    # Remove or replace dangerous characters
    safe_chars = []
    for char in filename:
        if char.isalnum() or char in ".-_":
            safe_chars.append(char)
        elif char in " /\\:":
            safe_chars.append("_")
        # Skip other dangerous characters like <>|?*
    
    safe_name = "".join(safe_chars)
    
    # Ensure it's not empty and doesn't start with dot
    if not safe_name or safe_name.startswith("."):
        safe_name = "file_" + safe_name
    
    return safe_name


def find_files_by_pattern(
    root_path: SecurePath,
    pattern: str,
    recursive: bool = True,
    include_hidden: bool = False
) -> List[SecurePath]:
    """Find files matching a pattern within a secure path.
    
    Args:
        root_path: Root path to search in
        pattern: Glob pattern to match
        recursive: Whether to search recursively
        include_hidden: Whether to include hidden files
        
    Returns:
        List of matching SecurePath objects
    """
    if not root_path.is_dir():
        return []
    
    try:
        if recursive:
            matches = root_path.path.rglob(pattern)
        else:
            matches = root_path.path.glob(pattern)
        
        results = []
        for match in matches:
            if match.is_file():
                if not include_hidden and is_hidden_file(match):
                    continue
                
                try:
                    secure_match = SecurePath(match, root_path.sandbox)
                    results.append(secure_match)
                except SecurityError:
                    # Skip files that fail security validation
                    continue
        
        return results
    
    except Exception:
        # Return empty list on any error
        return []


def calculate_directory_size(path: SecurePath) -> int:
    """Calculate total size of directory contents.
    
    Args:
        path: Directory path
        
    Returns:
        Total size in bytes
    """
    if not path.is_dir():
        return 0
    
    total_size = 0
    try:
        for item in path.path.rglob("*"):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except OSError:
                    # Skip files we can't stat
                    continue
    except Exception:
        # Return partial size on error
        pass
    
    return total_size