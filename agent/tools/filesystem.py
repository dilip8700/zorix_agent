"""Filesystem tools with security sandbox integration."""

import difflib
import glob
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import chardet

from agent.config import get_settings
from agent.security.sandbox import SecuritySandbox
from agent.models.base import FileChange

logger = logging.getLogger(__name__)


class FilesystemTools:
    """Filesystem operations with security sandbox integration."""
    
    def __init__(self, workspace_root: Optional[str] = None):
        """Initialize filesystem tools.
        
        Args:
            workspace_root: Root directory for all operations. If None, uses config.
        """
        settings = get_settings()
        self.workspace_root = Path(workspace_root or settings.workspace_root).resolve()
        self.sandbox = SecuritySandbox(self.workspace_root)
        
        # Ensure workspace exists
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized FilesystemTools with workspace: {self.workspace_root}")
    
    def read_file(self, path: str, encoding: Optional[str] = None) -> Dict[str, Any]:
        """Read the contents of a file with encoding detection.
        
        Args:
            path: Path to file relative to workspace root
            encoding: Optional encoding to use. If None, auto-detect.
            
        Returns:
            Dictionary with file content, encoding, and metadata
            
        Raises:
            SecurityError: If path is outside workspace or denied
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
        """
        try:
            # Validate path through sandbox
            abs_path = self.sandbox.validate_path(path)
            
            if not abs_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            if not abs_path.is_file():
                raise ValueError(f"Path is not a file: {path}")
            
            # Read file with encoding detection
            if encoding is None:
                # Auto-detect encoding
                with open(abs_path, 'rb') as f:
                    raw_data = f.read()
                
                if not raw_data:
                    # Empty file
                    content = ""
                    detected_encoding = "utf-8"
                else:
                    # Detect encoding
                    detection = chardet.detect(raw_data)
                    detected_encoding = detection.get('encoding', 'utf-8')
                    confidence = detection.get('confidence', 0.0)
                    
                    # Fallback to utf-8 if confidence is low
                    if confidence < 0.7:
                        detected_encoding = 'utf-8'
                    
                    try:
                        content = raw_data.decode(detected_encoding)
                    except UnicodeDecodeError:
                        # Fallback to utf-8 with error handling
                        content = raw_data.decode('utf-8', errors='replace')
                        detected_encoding = 'utf-8'
            else:
                # Use specified encoding
                with open(abs_path, 'r', encoding=encoding) as f:
                    content = f.read()
                detected_encoding = encoding
            
            # Get file metadata
            stat = abs_path.stat()
            
            result = {
                "content": content,
                "encoding": detected_encoding,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "path": path,
                "absolute_path": str(abs_path),
                "lines": len(content.splitlines()) if content else 0
            }
            
            logger.debug(f"Read file {path}: {len(content)} chars, encoding={detected_encoding}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            raise
    
    def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_backup: bool = True,
        atomic: bool = True
    ) -> Dict[str, Any]:
        """Write content to a file with atomic operations and backup.
        
        Args:
            path: Path to file relative to workspace root
            content: Content to write
            encoding: Encoding to use for writing
            create_backup: Whether to create backup of existing file
            atomic: Whether to use atomic write (write to temp then move)
            
        Returns:
            Dictionary with operation results and metadata
            
        Raises:
            SecurityError: If path is outside workspace or denied
            PermissionError: If file can't be written
        """
        try:
            # Validate path through sandbox
            abs_path = self.sandbox.validate_path(path)
            
            # Prepare result
            result = {
                "path": path,
                "absolute_path": str(abs_path),
                "encoding": encoding,
                "size": len(content.encode(encoding)),
                "lines": len(content.splitlines()) if content else 0,
                "created": not abs_path.exists(),
                "backup_created": False,
                "backup_path": None
            }
            
            # Create parent directories if needed
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup if file exists and backup is requested
            if create_backup and abs_path.exists():
                backup_path = abs_path.with_suffix(abs_path.suffix + '.bak')
                shutil.copy2(abs_path, backup_path)
                result["backup_created"] = True
                result["backup_path"] = str(backup_path)
                logger.debug(f"Created backup: {backup_path}")
            
            if atomic:
                # Atomic write: write to temp file then move
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding=encoding,
                    newline='\n',
                    dir=abs_path.parent,
                    prefix=f".{abs_path.name}.",
                    suffix='.tmp',
                    delete=False
                ) as temp_file:
                    temp_file.write(content)
                    temp_path = Path(temp_file.name)
                
                # Move temp file to final location
                temp_path.replace(abs_path)
                logger.debug(f"Atomic write completed: {path}")
            else:
                # Direct write
                with open(abs_path, 'w', encoding=encoding, newline='\n') as f:
                    f.write(content)
                logger.debug(f"Direct write completed: {path}")
            
            # Update result with final file info
            stat = abs_path.stat()
            result["modified"] = stat.st_mtime
            result["actual_size"] = stat.st_size
            
            logger.info(f"Wrote file {path}: {result['lines']} lines, {result['size']} bytes")
            return result
            
        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            raise
    
    def apply_patch(self, path: str, patch: str, backup: bool = True) -> Dict[str, Any]:
        """Apply a unified diff patch to a file.
        
        Args:
            path: Path to file relative to workspace root
            patch: Unified diff patch content
            backup: Whether to create backup before applying patch
            
        Returns:
            Dictionary with patch application results
            
        Raises:
            SecurityError: If path is outside workspace or denied
            ValueError: If patch format is invalid or doesn't apply
        """
        try:
            # Validate path through sandbox
            abs_path = self.sandbox.validate_path(path)
            
            if not abs_path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            
            # Read current file content
            current_content = self.read_file(path)["content"]
            current_lines = current_content.splitlines(keepends=True)
            
            # Parse patch
            patch_lines = patch.splitlines()
            
            # Simple unified diff parser
            # This is a basic implementation - for production, consider using a proper patch library
            patched_lines = self._apply_unified_diff(current_lines, patch_lines)
            
            # Create new content
            new_content = ''.join(patched_lines)
            
            # Calculate changes
            changes = self._calculate_file_changes(current_content, new_content, path)
            
            # Write patched content
            write_result = self.write_file(path, new_content, create_backup=backup)
            
            result = {
                "path": path,
                "patch_applied": True,
                "changes": changes,
                "backup_created": write_result["backup_created"],
                "backup_path": write_result.get("backup_path"),
                "lines_before": len(current_lines),
                "lines_after": len(patched_lines),
                "size_before": len(current_content),
                "size_after": len(new_content)
            }
            
            logger.info(f"Applied patch to {path}: +{changes.lines_added}/-{changes.lines_removed}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to apply patch to {path}: {e}")
            raise
    
    def list_directory(
        self,
        path: str = ".",
        pattern: str = "*",
        recursive: bool = False,
        include_hidden: bool = False
    ) -> Dict[str, Any]:
        """List directory contents with glob pattern support.
        
        Args:
            path: Directory path relative to workspace root
            pattern: Glob pattern to filter files
            recursive: Whether to list recursively
            include_hidden: Whether to include hidden files
            
        Returns:
            Dictionary with directory listing and metadata
            
        Raises:
            SecurityError: If path is outside workspace or denied
            NotADirectoryError: If path is not a directory
        """
        try:
            # Validate path through sandbox
            abs_path = self.sandbox.validate_path(path)
            
            if not abs_path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")
            
            if not abs_path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {path}")
            
            # Build glob pattern
            if recursive:
                glob_pattern = str(abs_path / "**" / pattern)
            else:
                glob_pattern = str(abs_path / pattern)
            
            # Get matching files
            matches = glob.glob(glob_pattern, recursive=recursive)
            
            files = []
            directories = []
            
            for match in sorted(matches):
                match_path = Path(match)
                
                # Skip hidden files if not requested
                if not include_hidden and match_path.name.startswith('.'):
                    continue
                
                # Get relative path from workspace root
                try:
                    rel_path = match_path.relative_to(self.workspace_root)
                except ValueError:
                    # Skip files outside workspace (shouldn't happen with sandbox)
                    continue
                
                # Get file info
                stat = match_path.stat()
                
                file_info = {
                    "name": match_path.name,
                    "path": str(rel_path),
                    "absolute_path": str(match_path),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "is_file": match_path.is_file(),
                    "is_dir": match_path.is_dir(),
                    "is_symlink": match_path.is_symlink()
                }
                
                if match_path.is_file():
                    files.append(file_info)
                elif match_path.is_dir():
                    directories.append(file_info)
            
            result = {
                "path": path,
                "absolute_path": str(abs_path),
                "pattern": pattern,
                "recursive": recursive,
                "files": files,
                "directories": directories,
                "total_files": len(files),
                "total_directories": len(directories),
                "total_size": sum(f["size"] for f in files)
            }
            
            logger.debug(f"Listed directory {path}: {len(files)} files, {len(directories)} dirs")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list directory {path}: {e}")
            raise
    
    def search_code(
        self,
        query: str,
        file_patterns: Optional[List[str]] = None,
        max_results: int = 20,
        context_lines: int = 2
    ) -> Dict[str, Any]:
        """Search for code patterns within the workspace using ripgrep-like functionality.
        
        Args:
            query: Search query or regex pattern
            file_patterns: List of file patterns to search (e.g., ['*.py', '*.js'])
            max_results: Maximum number of results to return
            context_lines: Number of context lines around matches
            
        Returns:
            Dictionary with search results and metadata
        """
        try:
            import re
            
            # Compile regex pattern
            try:
                pattern = re.compile(query, re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
            
            # Default file patterns if none provided
            if file_patterns is None:
                file_patterns = ['*.py', '*.js', '*.ts', '*.java', '*.cpp', '*.c', '*.h', 
                               '*.cs', '*.go', '*.rs', '*.rb', '*.php', '*.html', '*.css',
                               '*.md', '*.txt', '*.json', '*.yaml', '*.yml', '*.xml']
            
            results = []
            total_matches = 0
            truncated = False
            
            # Search through files
            for file_pattern in file_patterns:
                if len(results) >= max_results:
                    truncated = True
                    break
                
                # Get files matching pattern
                listing = self.list_directory(".", file_pattern, recursive=True)
                
                for file_info in listing["files"]:
                    if len(results) >= max_results:
                        truncated = True
                        break
                    
                    try:
                        # Read file content
                        file_content = self.read_file(file_info["path"])
                        content = file_content["content"]
                        lines = content.splitlines()
                        
                        # Search for matches
                        for line_num, line in enumerate(lines, 1):
                            match = pattern.search(line)
                            if match:
                                total_matches += 1
                                
                                if len(results) < max_results:
                                    # Get context lines
                                    start_line = max(0, line_num - context_lines - 1)
                                    end_line = min(len(lines), line_num + context_lines)
                                    context = lines[start_line:end_line]
                                    
                                    result = {
                                        "file": file_info["path"],
                                        "line": line_num,
                                        "column": match.start() + 1,
                                        "match": match.group(),
                                        "line_content": line,
                                        "context": context,
                                        "context_start": start_line + 1,
                                        "context_end": end_line
                                    }
                                    
                                    results.append(result)
                                else:
                                    truncated = True
                    
                    except Exception as e:
                        # Skip files that can't be read
                        logger.debug(f"Skipping file {file_info['path']}: {e}")
                        continue
            
            search_result = {
                "query": query,
                "file_patterns": file_patterns,
                "max_results": max_results,
                "context_lines": context_lines,
                "results": results,
                "total_matches": total_matches,
                "truncated": truncated
            }
            
            logger.info(f"Code search for '{query}': {len(results)} results")
            return search_result
            
        except Exception as e:
            logger.error(f"Failed to search code for '{query}': {e}")
            raise
    
    def _apply_unified_diff(self, original_lines: List[str], patch_lines: List[str]) -> List[str]:
        """Apply unified diff patch to original lines.
        
        This is a simplified implementation. For production use, consider
        using a proper patch library like `patch` or `unidiff`.
        """
        result_lines = original_lines.copy()
        
        # Parse patch header and hunks
        i = 0
        while i < len(patch_lines):
            line = patch_lines[i]
            
            # Skip non-hunk lines
            if not line.startswith('@@'):
                i += 1
                continue
            
            # Parse hunk header: @@ -start,count +start,count @@
            hunk_match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
            if not hunk_match:
                i += 1
                continue
            
            old_start = int(hunk_match.group(1)) - 1  # Convert to 0-based
            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_start = int(hunk_match.group(3)) - 1  # Convert to 0-based
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            
            # Apply hunk
            i += 1
            hunk_lines = []
            
            while i < len(patch_lines) and not patch_lines[i].startswith('@@'):
                hunk_line = patch_lines[i]
                if hunk_line.startswith(' '):
                    # Context line
                    hunk_lines.append(('context', hunk_line[1:]))
                elif hunk_line.startswith('-'):
                    # Deletion
                    hunk_lines.append(('delete', hunk_line[1:]))
                elif hunk_line.startswith('+'):
                    # Addition
                    hunk_lines.append(('add', hunk_line[1:]))
                i += 1
            
            # Apply hunk to result
            result_lines = self._apply_hunk(result_lines, old_start, hunk_lines)
        
        return result_lines
    
    def _apply_hunk(self, lines: List[str], start_pos: int, hunk_lines: List[tuple]) -> List[str]:
        """Apply a single hunk to the lines."""
        result = lines[:start_pos]
        pos = start_pos
        
        for action, content in hunk_lines:
            if action == 'context':
                # Verify context matches
                if pos < len(lines) and lines[pos].rstrip() == content.rstrip():
                    result.append(lines[pos])
                    pos += 1
                else:
                    raise ValueError(f"Context mismatch at line {pos + 1}")
            elif action == 'delete':
                # Skip the deleted line
                if pos < len(lines) and lines[pos].rstrip() == content.rstrip():
                    pos += 1
                else:
                    raise ValueError(f"Delete mismatch at line {pos + 1}")
            elif action == 'add':
                # Add the new line
                result.append(content + '\n' if not content.endswith('\n') else content)
        
        # Add remaining lines
        result.extend(lines[pos:])
        return result
    
    def _calculate_file_changes(self, old_content: str, new_content: str, path: str) -> FileChange:
        """Calculate file changes between old and new content."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        # Use difflib to calculate changes
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))
        
        lines_added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
        lines_removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
        
        return FileChange(
            path=path,
            operation="modify",
            size_before=len(old_content),
            size_after=len(new_content),
            lines_added=lines_added,
            lines_removed=lines_removed,
            summary=f"Modified {path}: +{lines_added}/-{lines_removed} lines"
        )
    
    def get_file_info(self, path: str) -> Dict[str, Any]:
        """Get detailed information about a file or directory.
        
        Args:
            path: Path relative to workspace root
            
        Returns:
            Dictionary with file information
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not abs_path.exists():
                raise FileNotFoundError(f"Path not found: {path}")
            
            stat = abs_path.stat()
            
            info = {
                "path": path,
                "absolute_path": str(abs_path),
                "name": abs_path.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "is_file": abs_path.is_file(),
                "is_dir": abs_path.is_dir(),
                "is_symlink": abs_path.is_symlink(),
                "permissions": oct(stat.st_mode)[-3:],
                "exists": True
            }
            
            if abs_path.is_file():
                # Add file-specific info
                info["extension"] = abs_path.suffix
                info["stem"] = abs_path.stem
                
                # Try to detect file type
                if abs_path.suffix.lower() in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h']:
                    info["file_type"] = "code"
                elif abs_path.suffix.lower() in ['.txt', '.md', '.rst']:
                    info["file_type"] = "text"
                elif abs_path.suffix.lower() in ['.json', '.yaml', '.yml', '.xml']:
                    info["file_type"] = "data"
                else:
                    info["file_type"] = "unknown"
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get file info for {path}: {e}")
            raise