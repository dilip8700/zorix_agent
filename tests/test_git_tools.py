"""Tests for Git tools."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.tools.git import GitTools, GitError
from agent.security.exceptions import SecurityError


class TestGitTools:
    """Test cases for GitTools."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def git_tools(self, temp_workspace):
        """Create GitTools instance with temp workspace."""
        return GitTools(workspace_root=str(temp_workspace))
    
    @pytest.fixture
    def git_repo(self, temp_workspace, git_tools):
        """Create a test Git repository."""
        # Initialize repository
        git_tools.init_repository(".")
        
        # Configure git (required for commits)
        git_tools._run_git_command(['config', 'user.name', 'Test User'])
        git_tools._run_git_command(['config', 'user.email', 'test@example.com'])
        
        # Create initial file and commit
        test_file = temp_workspace / "README.md"
        test_file.write_text("# Test Repository\n\nThis is a test.")
        
        git_tools.git_add(["README.md"])
        git_tools.git_commit("Initial commit")
        
        return git_tools
    
    def test_initialization(self, temp_workspace):
        """Test GitTools initialization."""
        git_tools = GitTools(workspace_root=str(temp_workspace))
        
        assert git_tools.workspace_root == temp_workspace.resolve()
        assert git_tools.sandbox is not None
        assert temp_workspace.exists()
    
    def test_is_git_repository_false(self, git_tools):
        """Test is_git_repository with non-repository."""
        assert not git_tools.is_git_repository(".")
    
    def test_init_repository(self, git_tools, temp_workspace):
        """Test repository initialization."""
        result = git_tools.init_repository(".")
        
        assert result["success"] is True
        assert result["already_exists"] is False
        assert "Initialized" in result["message"]
        
        # Verify repository was created
        assert git_tools.is_git_repository(".")
        assert (temp_workspace / ".git").exists()
    
    def test_init_repository_already_exists(self, git_repo):
        """Test initializing repository that already exists."""
        result = git_repo.init_repository(".")
        
        assert result["already_exists"] is True
        assert "already exists" in result["message"]
    
    def test_git_status_clean_repo(self, git_repo):
        """Test git status on clean repository."""
        result = git_repo.git_status(".")
        
        assert result["path"] == "."
        assert result["clean"] is True
        assert result["has_changes"] is False
        assert result["current_branch"] is not None
        assert isinstance(result["files"], list)
    
    def test_git_status_with_changes(self, git_repo, temp_workspace):
        """Test git status with uncommitted changes."""
        # Create new file
        new_file = temp_workspace / "new_file.txt"
        new_file.write_text("New content")
        
        result = git_repo.git_status(".")
        
        assert result["clean"] is False
        assert result["has_changes"] is True
        assert len(result["files"]) > 0
        
        # Check that new file is listed
        filenames = [f["filename"] for f in result["files"]]
        assert "new_file.txt" in filenames
    
    def test_git_status_not_repository(self, git_tools):
        """Test git status on non-repository."""
        with pytest.raises(GitError, match="Not a git repository"):
            git_tools.git_status(".")
    
    def test_git_add_single_file(self, git_repo, temp_workspace):
        """Test adding single file to staging."""
        # Create new file
        new_file = temp_workspace / "test.txt"
        new_file.write_text("Test content")
        
        result = git_repo.git_add("test.txt")
        
        assert result["success"] is True
        assert result["files_added"] == ["test.txt"]
        assert result["all_files"] is False
        
        # Verify file is staged
        status = git_repo.git_status(".")
        staged_files = [f for f in status["files"] if f["index_status"] == "A"]
        assert len(staged_files) > 0
    
    def test_git_commit_success(self, git_repo, temp_workspace):
        """Test successful commit."""
        # Create and stage file
        new_file = temp_workspace / "commit_test.txt"
        new_file.write_text("Commit test")
        git_repo.git_add("commit_test.txt")
        
        result = git_repo.git_commit("Add commit test file")
        
        assert result["success"] is True
        assert result["message"] == "Add commit test file"
        assert result["commit_hash"] is not None
        assert len(result["commit_hash"]) >= 7
    
    def test_git_commit_no_staged_changes(self, git_repo):
        """Test commit with no staged changes."""
        with pytest.raises(GitError, match="No staged changes to commit"):
            git_repo.git_commit("Empty commit")
    
    def test_git_diff_no_changes(self, git_repo):
        """Test git diff with no changes."""
        result = git_repo.git_diff(".")
        
        assert result["path"] == "."
        assert result["has_changes"] is False
        assert result["diff"] == ""
        assert result["staged"] is False
    
    def test_git_diff_with_changes(self, git_repo, temp_workspace):
        """Test git diff with uncommitted changes."""
        # Modify existing file
        readme = temp_workspace / "README.md"
        readme.write_text("# Modified Test Repository\n\nThis is modified.")
        
        result = git_repo.git_diff(".")
        
        assert result["has_changes"] is True
        assert "Modified" in result["diff"]
        assert result["stats"]["total_changes"] > 0
    
    def test_git_branch_list(self, git_repo):
        """Test listing branches."""
        result = git_repo.git_branch(".")
        
        assert "branches" in result
        assert len(result["branches"]) >= 1
        assert result["current_branch"] is not None
        
        # Check that current branch is marked
        current_branches = [b for b in result["branches"] if b["current"]]
        assert len(current_branches) == 1
    
    def test_git_branch_create(self, git_repo):
        """Test creating new branch."""
        result = git_repo.git_branch(".", create="feature-branch")
        
        assert result["created"] == "feature-branch"
        
        # Verify branch exists
        list_result = git_repo.git_branch(".")
        branch_names = [b["name"] for b in list_result["branches"]]
        assert "feature-branch" in branch_names
    
    def test_git_log_with_commits(self, git_repo):
        """Test git log with commits."""
        result = git_repo.git_log(".")
        
        assert result["total_commits"] >= 1
        assert len(result["commits"]) >= 1
        
        # Check commit structure
        commit = result["commits"][0]
        assert "hash" in commit
        assert "author" in commit
        assert "message" in commit
        assert "date" in commit
    
    def test_git_reset_files(self, git_repo, temp_workspace):
        """Test git reset for specific files (unstage)."""
        # Create and stage file
        new_file = temp_workspace / "unstage_test.txt"
        new_file.write_text("Unstage test")
        git_repo.git_add("unstage_test.txt")
        
        # Reset specific file
        result = git_repo.git_reset(".", files="unstage_test.txt")
        
        assert result["success"] is True
        assert result["files"] == ["unstage_test.txt"]
    
    def test_git_reset_invalid_mode(self, git_repo):
        """Test git reset with invalid mode."""
        with pytest.raises(GitError, match="Invalid reset mode"):
            git_repo.git_reset(".", mode="invalid")
    
    def test_get_repository_info_not_repo(self, git_tools):
        """Test repository info for non-repository."""
        result = git_tools.get_repository_info(".")
        
        assert result["is_repository"] is False
        assert "Not a git repository" in result["message"]
    
    def test_get_repository_info_with_repo(self, git_repo):
        """Test repository info for valid repository."""
        result = git_repo.get_repository_info(".")
        
        assert result["is_repository"] is True
        assert result["current_branch"] is not None
        assert "status" in result
        assert "latest_commit" in result
    
    def test_security_boundaries(self, git_repo):
        """Test security boundaries for Git operations."""
        with pytest.raises(SecurityError):
            git_repo.git_status("../outside")
        
        with pytest.raises(SecurityError):
            git_repo.git_add("../outside/file.txt")
    
    def test_parse_status_porcelain(self, git_tools):
        """Test parsing git status --porcelain output."""
        output = """M  modified.txt
A  added.txt
?? untracked.txt
D  deleted.txt"""
        
        files = git_tools._parse_status_porcelain(output)
        
        assert len(files) == 4
        
        # Check specific files
        modified = next(f for f in files if f["filename"] == "modified.txt")
        assert modified["index_status"] == "M"
        assert modified["worktree_status"] == " "
        
        untracked = next(f for f in files if f["filename"] == "untracked.txt")
        assert untracked["status_code"] == "??"
    
    def test_parse_diff_stats(self, git_tools):
        """Test parsing diff statistics."""
        diff_output = """diff --git a/file.txt b/file.txt
index 1234567..abcdefg 100644
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,4 @@
 line 1
+added line
 line 2
-removed line
 line 3"""
        
        stats = git_tools._parse_diff_stats(diff_output)
        
        assert stats["files_changed"] == 1
        assert stats["insertions"] == 1
        assert stats["deletions"] == 1
        assert stats["total_changes"] == 2
    
    def test_parse_branch_list(self, git_tools):
        """Test parsing git branch output."""
        branch_output = """* main
  feature-branch
  remotes/origin/main
  remotes/origin/develop"""
        
        branches = git_tools._parse_branch_list(branch_output)
        
        assert len(branches) == 4
        
        # Check current branch
        main_branch = next(b for b in branches if b["name"] == "main" and not b["remote"])
        assert main_branch["current"] is True
        
        # Check remote branch
        remote_main = next(b for b in branches if b["name"] == "origin/main")
        assert remote_main["remote"] is True
        assert remote_main["current"] is False
    
    def test_parse_log_detailed(self, git_tools):
        """Test parsing detailed git log output."""
        log_output = """abc1234|John Doe|john@example.com|2024-01-01 12:00:00 +0000|Initial commit
def5678|Jane Smith|jane@example.com|2024-01-02 13:00:00 +0000|Add feature"""
        
        commits = git_tools._parse_log_detailed(log_output)
        
        assert len(commits) == 2
        
        first_commit = commits[0]
        assert first_commit["hash"] == "abc1234"
        assert first_commit["author"] == "John Doe"
        assert first_commit["email"] == "john@example.com"
        assert first_commit["message"] == "Initial commit"
    
    def test_parse_log_oneline(self, git_tools):
        """Test parsing oneline git log output."""
        log_output = """abc1234 Initial commit
def5678 Add feature
123abcd Fix bug"""
        
        commits = git_tools._parse_log_oneline(log_output)
        
        assert len(commits) == 3
        
        first_commit = commits[0]
        assert first_commit["hash"] == "abc1234"
        assert first_commit["message"] == "Initial commit"
        assert "author" not in first_commit