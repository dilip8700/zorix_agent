"""Git tools for repository operations."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agent.config import get_settings
from agent.security.sandbox import SecuritySandbox
from agent.models.base import FileChange

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Exception for Git operation errors."""
    pass


class GitTools:
    """Git operations with security sandbox integration."""
    
    def __init__(self, workspace_root: Optional[str] = None):
        """Initialize Git tools.
        
        Args:
            workspace_root: Root directory for all operations. If None, uses config.
        """
        settings = get_settings()
        self.workspace_root = Path(workspace_root or settings.workspace_root).resolve()
        self.sandbox = SecuritySandbox(self.workspace_root)
        
        # Ensure workspace exists
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized GitTools with workspace: {self.workspace_root}")
    
    def _run_git_command(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        capture_output: bool = True,
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a git command safely within the workspace.
        
        Args:
            args: Git command arguments (without 'git')
            cwd: Working directory (must be within workspace)
            capture_output: Whether to capture stdout/stderr
            check: Whether to raise exception on non-zero exit
            
        Returns:
            CompletedProcess result
            
        Raises:
            GitError: If command fails or path is invalid
            SecurityError: If path is outside workspace
        """
        try:
            # Validate working directory
            if cwd is None:
                cwd = self.workspace_root
            else:
                cwd = self.sandbox.validate_path(str(cwd))
            
            # Build command
            cmd = ['git'] + args
            
            logger.debug(f"Running git command: {' '.join(cmd)} in {cwd}")
            
            # Run command
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                check=False  # We'll handle errors manually
            )
            
            # Log result
            if result.returncode != 0:
                logger.warning(f"Git command failed (exit {result.returncode}): {result.stderr}")
                if check:
                    raise GitError(f"Git command failed: {result.stderr or 'Unknown error'}")
            else:
                logger.debug(f"Git command succeeded: {len(result.stdout)} chars output")
            
            return result
            
        except subprocess.TimeoutExpired as e:
            raise GitError(f"Git command timed out: {e}") from e
        except Exception as e:
            if isinstance(e, GitError):
                raise
            raise GitError(f"Failed to run git command: {e}") from e
    
    def is_git_repository(self, path: str = ".") -> bool:
        """Check if a directory is a Git repository.
        
        Args:
            path: Path to check (relative to workspace)
            
        Returns:
            True if path is within a Git repository
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            result = self._run_git_command(
                ['rev-parse', '--git-dir'],
                cwd=abs_path,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def init_repository(self, path: str = ".") -> Dict[str, Any]:
        """Initialize a new Git repository.
        
        Args:
            path: Path where to initialize repository
            
        Returns:
            Dictionary with initialization results
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            # Check if already a repository
            if self.is_git_repository(path):
                return {
                    "path": path,
                    "already_exists": True,
                    "message": "Repository already exists"
                }
            
            # Initialize repository
            result = self._run_git_command(['init'], cwd=abs_path)
            
            return {
                "path": path,
                "already_exists": False,
                "message": result.stdout.strip(),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize repository at {path}: {e}")
            raise
    
    def git_status(self, path: str = ".", porcelain: bool = True) -> Dict[str, Any]:
        """Get Git repository status.
        
        Args:
            path: Repository path (relative to workspace)
            porcelain: Use porcelain format for machine-readable output
            
        Returns:
            Dictionary with status information
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            # Get status
            args = ['status']
            if porcelain:
                args.append('--porcelain=v1')
            
            result = self._run_git_command(args, cwd=abs_path)
            
            if porcelain:
                # Parse porcelain output
                files = self._parse_status_porcelain(result.stdout)
            else:
                files = []
            
            # Get branch info
            branch_result = self._run_git_command(
                ['branch', '--show-current'],
                cwd=abs_path,
                check=False
            )
            current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
            
            # Check if there are uncommitted changes
            has_changes = bool(result.stdout.strip())
            
            return {
                "path": path,
                "current_branch": current_branch,
                "has_changes": has_changes,
                "files": files,
                "raw_output": result.stdout,
                "clean": not has_changes
            }
            
        except Exception as e:
            logger.error(f"Failed to get git status for {path}: {e}")
            raise
    
    def git_diff(
        self,
        path: str = ".",
        staged: bool = False,
        file_path: Optional[str] = None,
        commit: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Git diff output.
        
        Args:
            path: Repository path (relative to workspace)
            staged: Show staged changes (--cached)
            file_path: Specific file to diff
            commit: Compare against specific commit
            
        Returns:
            Dictionary with diff information
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            # Build diff command
            args = ['diff']
            
            if staged:
                args.append('--cached')
            
            if commit:
                args.append(commit)
            
            if file_path:
                # Validate file path
                file_abs_path = self.sandbox.validate_path(file_path)
                # Make path relative to repository root
                try:
                    rel_path = file_abs_path.relative_to(abs_path)
                    args.append(str(rel_path))
                except ValueError:
                    raise GitError(f"File {file_path} is not within repository {path}")
            
            result = self._run_git_command(args, cwd=abs_path)
            
            # Parse diff output
            diff_stats = self._parse_diff_stats(result.stdout)
            
            return {
                "path": path,
                "staged": staged,
                "file_path": file_path,
                "commit": commit,
                "diff": result.stdout,
                "has_changes": bool(result.stdout.strip()),
                "stats": diff_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get git diff for {path}: {e}")
            raise
    
    def git_add(
        self,
        files: Union[str, List[str]],
        path: str = ".",
        all_files: bool = False
    ) -> Dict[str, Any]:
        """Add files to Git staging area.
        
        Args:
            files: File(s) to add (relative to repository root)
            path: Repository path (relative to workspace)
            all_files: Add all modified files (git add -A)
            
        Returns:
            Dictionary with add operation results
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            # Build add command
            args = ['add']
            
            if all_files:
                args.append('-A')
            else:
                # Validate and add specific files
                if isinstance(files, str):
                    files = [files]
                
                for file_path in files:
                    # Validate file path
                    file_abs_path = self.sandbox.validate_path(file_path)
                    # Make path relative to repository root
                    try:
                        rel_path = file_abs_path.relative_to(abs_path)
                        args.append(str(rel_path))
                    except ValueError:
                        raise GitError(f"File {file_path} is not within repository {path}")
            
            result = self._run_git_command(args, cwd=abs_path)
            
            # Get updated status
            status = self.git_status(path)
            
            return {
                "path": path,
                "files_added": files if not all_files else "all",
                "all_files": all_files,
                "success": True,
                "message": "Files added to staging area",
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to add files to git: {e}")
            raise
    
    def git_commit(
        self,
        message: str,
        path: str = ".",
        author: Optional[str] = None,
        amend: bool = False
    ) -> Dict[str, Any]:
        """Commit staged changes.
        
        Args:
            message: Commit message
            path: Repository path (relative to workspace)
            author: Author string ("Name <email>")
            amend: Amend the last commit
            
        Returns:
            Dictionary with commit results
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            # Check if there are staged changes (unless amending)
            if not amend:
                status_result = self._run_git_command(
                    ['diff', '--cached', '--quiet'],
                    cwd=abs_path,
                    check=False
                )
                if status_result.returncode == 0:
                    raise GitError("No staged changes to commit")
            
            # Build commit command
            args = ['commit', '-m', message]
            
            if author:
                args.extend(['--author', author])
            
            if amend:
                args.append('--amend')
            
            result = self._run_git_command(args, cwd=abs_path)
            
            # Parse commit hash from output
            commit_hash = self._extract_commit_hash(result.stdout)
            
            return {
                "path": path,
                "message": message,
                "author": author,
                "amend": amend,
                "commit_hash": commit_hash,
                "success": True,
                "output": result.stdout.strip()
            }
            
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            raise
    
    def git_branch(
        self,
        path: str = ".",
        list_all: bool = False,
        create: Optional[str] = None,
        delete: Optional[str] = None,
        switch_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Git branch operations.
        
        Args:
            path: Repository path (relative to workspace)
            list_all: List all branches (local and remote)
            create: Create new branch with given name
            delete: Delete branch with given name
            switch_to: Switch to branch with given name
            
        Returns:
            Dictionary with branch operation results
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            result_data = {"path": path}
            
            # Create branch
            if create:
                create_result = self._run_git_command(
                    ['branch', create],
                    cwd=abs_path
                )
                result_data["created"] = create
                result_data["create_output"] = create_result.stdout.strip()
            
            # Delete branch
            if delete:
                delete_result = self._run_git_command(
                    ['branch', '-d', delete],
                    cwd=abs_path
                )
                result_data["deleted"] = delete
                result_data["delete_output"] = delete_result.stdout.strip()
            
            # Switch branch
            if switch_to:
                switch_result = self._run_git_command(
                    ['checkout', switch_to],
                    cwd=abs_path
                )
                result_data["switched_to"] = switch_to
                result_data["switch_output"] = switch_result.stdout.strip()
            
            # List branches
            list_args = ['branch']
            if list_all:
                list_args.append('-a')
            
            list_result = self._run_git_command(list_args, cwd=abs_path)
            
            branches = self._parse_branch_list(list_result.stdout)
            result_data["branches"] = branches
            
            # Get current branch
            current_result = self._run_git_command(
                ['branch', '--show-current'],
                cwd=abs_path,
                check=False
            )
            result_data["current_branch"] = current_result.stdout.strip() if current_result.returncode == 0 else None
            
            return result_data
            
        except Exception as e:
            logger.error(f"Failed git branch operation: {e}")
            raise
    
    def git_log(
        self,
        path: str = ".",
        max_count: int = 10,
        oneline: bool = False,
        since: Optional[str] = None,
        until: Optional[str] = None,
        author: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get Git commit log.
        
        Args:
            path: Repository path (relative to workspace)
            max_count: Maximum number of commits to show
            oneline: Use oneline format
            since: Show commits since date/commit
            until: Show commits until date/commit
            author: Filter by author
            file_path: Show log for specific file
            
        Returns:
            Dictionary with log information
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            # Build log command
            args = ['log', f'--max-count={max_count}']
            
            if oneline:
                args.append('--oneline')
            else:
                args.append('--pretty=format:%H|%an|%ae|%ad|%s')
                args.append('--date=iso')
            
            if since:
                args.extend(['--since', since])
            
            if until:
                args.extend(['--until', until])
            
            if author:
                args.extend(['--author', author])
            
            if file_path:
                # Validate file path
                file_abs_path = self.sandbox.validate_path(file_path)
                try:
                    rel_path = file_abs_path.relative_to(abs_path)
                    args.append('--')
                    args.append(str(rel_path))
                except ValueError:
                    raise GitError(f"File {file_path} is not within repository {path}")
            
            result = self._run_git_command(args, cwd=abs_path, check=False)
            
            if result.returncode != 0:
                # No commits or other error
                return {
                    "path": path,
                    "commits": [],
                    "total_commits": 0,
                    "message": "No commits found or repository error"
                }
            
            # Parse commits
            if oneline:
                commits = self._parse_log_oneline(result.stdout)
            else:
                commits = self._parse_log_detailed(result.stdout)
            
            return {
                "path": path,
                "commits": commits,
                "total_commits": len(commits),
                "max_count": max_count,
                "filters": {
                    "since": since,
                    "until": until,
                    "author": author,
                    "file_path": file_path
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get git log: {e}")
            raise
    
    def git_reset(
        self,
        path: str = ".",
        mode: str = "mixed",
        commit: Optional[str] = None,
        files: Optional[Union[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """Reset Git repository state.
        
        Args:
            path: Repository path (relative to workspace)
            mode: Reset mode (soft, mixed, hard)
            commit: Commit to reset to (default: HEAD)
            files: Specific files to reset
            
        Returns:
            Dictionary with reset results
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                raise GitError(f"Not a git repository: {path}")
            
            # Validate reset mode
            valid_modes = ['soft', 'mixed', 'hard']
            if mode not in valid_modes:
                raise GitError(f"Invalid reset mode: {mode}. Must be one of {valid_modes}")
            
            # Build reset command
            if files:
                # Reset specific files (unstage)
                args = ['reset']
                if commit:
                    args.append(commit)
                
                if isinstance(files, str):
                    files = [files]
                
                for file_path in files:
                    # Validate file path
                    file_abs_path = self.sandbox.validate_path(file_path)
                    try:
                        rel_path = file_abs_path.relative_to(abs_path)
                        args.append(str(rel_path))
                    except ValueError:
                        raise GitError(f"File {file_path} is not within repository {path}")
            else:
                # Reset repository state
                args = ['reset', f'--{mode}']
                if commit:
                    args.append(commit)
            
            result = self._run_git_command(args, cwd=abs_path)
            
            # Get updated status
            status = self.git_status(path)
            
            return {
                "path": path,
                "mode": mode,
                "commit": commit or "HEAD",
                "files": files,
                "success": True,
                "output": result.stdout.strip(),
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to reset git repository: {e}")
            raise
    
    def _parse_status_porcelain(self, output: str) -> List[Dict[str, Any]]:
        """Parse git status --porcelain output."""
        files = []
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            # Porcelain format: XY filename
            if len(line) < 3:
                continue
            
            index_status = line[0]
            worktree_status = line[1]
            filename = line[3:]  # Skip the space
            
            files.append({
                "filename": filename,
                "index_status": index_status,
                "worktree_status": worktree_status,
                "status_code": line[:2]
            })
        
        return files
    
    def _parse_diff_stats(self, diff_output: str) -> Dict[str, Any]:
        """Parse diff output to extract statistics."""
        lines = diff_output.split('\n')
        
        files_changed = 0
        insertions = 0
        deletions = 0
        
        for line in lines:
            if line.startswith('+++') or line.startswith('---'):
                if not line.endswith('/dev/null'):
                    files_changed += 1
            elif line.startswith('+') and not line.startswith('+++'):
                insertions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        return {
            "files_changed": files_changed // 2,  # Each file has +++ and ---
            "insertions": insertions,
            "deletions": deletions,
            "total_changes": insertions + deletions
        }
    
    def _extract_commit_hash(self, commit_output: str) -> Optional[str]:
        """Extract commit hash from git commit output."""
        lines = commit_output.strip().split('\n')
        for line in lines:
            if 'commit' in line.lower() or len(line) == 40:
                # Look for 40-character hash
                words = line.split()
                for word in words:
                    if len(word) >= 7 and all(c in '0123456789abcdef' for c in word[:7]):
                        return word
        return None
    
    def _parse_branch_list(self, branch_output: str) -> List[Dict[str, Any]]:
        """Parse git branch output."""
        branches = []
        for line in branch_output.strip().split('\n'):
            if not line:
                continue
            
            is_current = line.startswith('*')
            name = line[2:].strip() if is_current else line.strip()
            
            # Handle remote branches
            is_remote = name.startswith('remotes/')
            if is_remote:
                name = name[8:]  # Remove 'remotes/' prefix
            
            branches.append({
                "name": name,
                "current": is_current,
                "remote": is_remote
            })
        
        return branches
    
    def _parse_log_oneline(self, log_output: str) -> List[Dict[str, Any]]:
        """Parse git log --oneline output."""
        commits = []
        for line in log_output.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split(' ', 1)
            if len(parts) >= 2:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1]
                })
        
        return commits
    
    def _parse_log_detailed(self, log_output: str) -> List[Dict[str, Any]]:
        """Parse detailed git log output."""
        commits = []
        for line in log_output.strip().split('\n'):
            if not line:
                continue
            
            # Format: hash|author|email|date|message
            parts = line.split('|', 4)
            if len(parts) >= 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4]
                })
        
        return commits
    
    def get_repository_info(self, path: str = ".") -> Dict[str, Any]:
        """Get comprehensive repository information.
        
        Args:
            path: Repository path (relative to workspace)
            
        Returns:
            Dictionary with repository information
        """
        try:
            abs_path = self.sandbox.validate_path(path)
            
            if not self.is_git_repository(path):
                return {
                    "path": path,
                    "is_repository": False,
                    "message": "Not a git repository"
                }
            
            # Get basic info
            status = self.git_status(path)
            
            # Get remote info
            remote_result = self._run_git_command(
                ['remote', '-v'],
                cwd=abs_path,
                check=False
            )
            
            remotes = self._parse_remotes(remote_result.stdout) if remote_result.returncode == 0 else []
            
            # Get latest commit
            latest_commit_result = self._run_git_command(
                ['log', '-1', '--pretty=format:%H|%an|%ae|%ad|%s', '--date=iso'],
                cwd=abs_path,
                check=False
            )
            
            latest_commit = None
            if latest_commit_result.returncode == 0 and latest_commit_result.stdout:
                commits = self._parse_log_detailed(latest_commit_result.stdout)
                latest_commit = commits[0] if commits else None
            
            return {
                "path": path,
                "is_repository": True,
                "current_branch": status["current_branch"],
                "has_changes": status["has_changes"],
                "clean": status["clean"],
                "remotes": remotes,
                "latest_commit": latest_commit,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to get repository info: {e}")
            raise
    
    def _parse_remotes(self, remote_output: str) -> List[Dict[str, Any]]:
        """Parse git remote -v output."""
        remotes = []
        seen = set()
        
        for line in remote_output.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                url = parts[1]
                
                # Avoid duplicates (fetch/push entries)
                if name not in seen:
                    remotes.append({
                        "name": name,
                        "url": url
                    })
                    seen.add(name)
        
        return remotes