#!/usr/bin/env python3
"""Integration test for Git tools."""

import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_git_tools():
    """Test Git tools functionality."""
    from agent.tools.git import GitTools, GitError
    from agent.security.exceptions import SecurityError
    
    print("Testing Git Tools Integration...")
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        git_tools = GitTools(workspace_root=str(workspace))
        
        print("✓ GitTools initialized")
        
        # Test 1: Check non-repository
        assert not git_tools.is_git_repository(".")
        print("✓ Non-repository detection works")
        
        # Test 2: Initialize repository
        result = git_tools.init_repository(".")
        assert result["success"] is True
        assert git_tools.is_git_repository(".")
        print("✓ Repository initialization works")
        
        # Configure git for testing
        git_tools._run_git_command(['config', 'user.name', 'Test User'])
        git_tools._run_git_command(['config', 'user.email', 'test@example.com'])
        print("✓ Git configuration set")
        
        # Test 3: Create files and check status
        test_file = workspace / "test.py"
        test_file.write_text("def hello():\n    print('Hello, World!')")
        
        status = git_tools.git_status(".")
        assert status["has_changes"] is True
        assert len(status["files"]) == 1
        print("✓ Git status detection works")
        
        # Test 4: Add files
        add_result = git_tools.git_add("test.py")
        assert add_result["success"] is True
        print("✓ Git add works")
        
        # Test 5: Check staged diff
        diff = git_tools.git_diff(".", staged=True)
        assert diff["has_changes"] is True
        assert "hello" in diff["diff"]
        print("✓ Git diff works")
        
        # Test 6: Commit changes
        commit_result = git_tools.git_commit("Initial commit")
        assert commit_result["success"] is True
        assert commit_result["commit_hash"] is not None
        print("✓ Git commit works")
        
        # Test 7: Check clean status
        status = git_tools.git_status(".")
        assert status["clean"] is True
        print("✓ Clean repository status works")
        
        # Test 8: Branch operations
        branch_result = git_tools.git_branch(".", create="feature")
        assert branch_result["created"] == "feature"
        
        switch_result = git_tools.git_branch(".", switch_to="feature")
        assert switch_result["current_branch"] == "feature"
        print("✓ Git branch operations work")
        
        # Test 9: Log operations
        log_result = git_tools.git_log(".")
        assert log_result["total_commits"] >= 1
        assert len(log_result["commits"]) >= 1
        print("✓ Git log works")
        
        # Test 10: Repository info
        repo_info = git_tools.get_repository_info(".")
        assert repo_info["is_repository"] is True
        assert repo_info["current_branch"] == "feature"
        print("✓ Repository info works")
        
        # Test 11: Security boundaries
        try:
            git_tools.git_status("../outside")
            assert False, "Should have raised SecurityError"
        except SecurityError:
            print("✓ Security boundaries enforced")
        
        print("\n🎉 All Git tools tests passed!")
        return True


def test_error_handling():
    """Test error handling scenarios."""
    from agent.tools.git import GitTools, GitError
    
    print("\nTesting Git Tools Error Handling...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        git_tools = GitTools(workspace_root=str(workspace))
        
        # Test operations on non-repository
        try:
            git_tools.git_status(".")
            assert False, "Should have raised GitError"
        except GitError:
            print("✓ Non-repository error handling works")
        
        try:
            git_tools.git_add("file.txt")
            assert False, "Should have raised GitError"
        except GitError:
            print("✓ Add to non-repository error handling works")
        
        try:
            git_tools.git_commit("Test commit")
            assert False, "Should have raised GitError"
        except GitError:
            print("✓ Commit to non-repository error handling works")
        
        # Initialize repository for further tests
        git_tools.init_repository(".")
        git_tools._run_git_command(['config', 'user.name', 'Test User'])
        git_tools._run_git_command(['config', 'user.email', 'test@example.com'])
        
        # Test commit without staged changes
        try:
            git_tools.git_commit("Empty commit")
            assert False, "Should have raised GitError"
        except GitError as e:
            assert "No staged changes" in str(e)
            print("✓ Empty commit error handling works")
        
        # Test invalid reset mode
        try:
            git_tools.git_reset(".", mode="invalid")
            assert False, "Should have raised GitError"
        except GitError as e:
            assert "Invalid reset mode" in str(e)
            print("✓ Invalid reset mode error handling works")
        
        print("✓ All error handling tests passed!")
        return True


if __name__ == "__main__":
    try:
        success1 = test_git_tools()
        success2 = test_error_handling()
        
        if success1 and success2:
            print("\n🎉 All Git integration tests passed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Integration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)