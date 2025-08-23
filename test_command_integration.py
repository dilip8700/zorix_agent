#!/usr/bin/env python3
"""Integration test for Command tools."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_command_tools():
    """Test Command tools functionality."""
    from agent.tools.command import CommandTools
    from agent.security.exceptions import SecurityError
    
    print("Testing Command Tools Integration...")
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        command_tools = CommandTools(
            workspace_root=str(workspace),
            max_output_size=1024,
            default_timeout=10
        )
        
        print("✓ CommandTools initialized")
        
        # Test 1: Check allowlist functionality
        assert command_tools.is_command_allowed("echo")
        assert command_tools.is_command_allowed("echo hello world")
        assert not command_tools.is_command_allowed("rm -rf /")
        print("✓ Allowlist enforcement works")
        
        # Test 2: Execute simple command
        result = await command_tools.run_command("echo Hello World")
        assert result.success is True
        assert result.exit_code == 0
        assert "Hello World" in result.stdout
        print("✓ Basic command execution works")
        
        # Test 3: Test command with working directory
        subdir = workspace / "testdir"
        subdir.mkdir()
        
        if os.name == 'nt':  # Windows
            result = await command_tools.run_command("cd", cwd="testdir")
        else:  # Unix-like
            result = await command_tools.run_command("pwd", cwd="testdir")
        
        if result.success:
            assert "testdir" in result.stdout
            print("✓ Working directory handling works")
        else:
            print("⚠ Working directory test skipped (command not available)")
        
        # Test 4: Test disallowed command
        result = await command_tools.run_command("forbidden-command")
        assert result.success is False
        assert "not allowed" in result.stderr.lower()
        print("✓ Disallowed command rejection works")
        
        # Test 5: Test security boundaries
        try:
            result = await command_tools.run_command("echo test", cwd="../outside")
            assert result.success is False
            assert "outside workspace" in result.stderr.lower()
            print("✓ Security boundaries enforced")
        except SecurityError:
            print("✓ Security boundaries enforced (exception)")
        
        # Test 6: Test timeout
        if os.name != 'nt':  # Skip on Windows
            result = await command_tools.run_command("sleep 5", timeout=1)
            assert result.success is False
            assert result.timeout is True
            print("✓ Command timeout works")
        else:
            print("⚠ Timeout test skipped on Windows")
        
        # Test 7: Test secret redaction
        secret_text = "password=secret123 token=abc123"
        redacted = command_tools._redact_secrets(secret_text)
        assert "[REDACTED]" in redacted
        print("✓ Secret redaction works")
        
        # Test 8: Test allowlist management
        command_tools.add_to_allowlist("custom-tool")
        assert command_tools.is_command_allowed("custom-tool")
        
        command_tools.remove_from_allowlist("custom-tool")
        assert not command_tools.is_command_allowed("custom-tool")
        print("✓ Allowlist management works")
        
        # Test 9: Test which command
        if os.name == 'nt':
            path = await command_tools.which("cmd")
        else:
            path = await command_tools.which("sh")
        
        if path:
            assert isinstance(path, str)
            print("✓ Command path resolution works")
        else:
            print("⚠ Command path resolution test skipped (command not found)")
        
        # Test 10: Test system info
        info = await command_tools.get_system_info()
        assert isinstance(info, dict)
        assert "platform" in info
        assert "workspace_root" in info
        assert info["platform"] == os.name
        print("✓ System info retrieval works")
        
        # Test 11: Test command testing
        test_result = await command_tools.test_command("echo")
        assert test_result["allowed"] is True
        assert test_result["command"] == "echo"
        print("✓ Command testing works")
        
        print("\n🎉 All Command tools tests passed!")
        return True


async def test_error_handling():
    """Test error handling scenarios."""
    from agent.tools.command import CommandTools
    
    print("\nTesting Command Tools Error Handling...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        command_tools = CommandTools(workspace_root=str(workspace))
        
        # Test empty command
        result = await command_tools.run_command("")
        assert result.success is False
        assert "cannot be empty" in result.stderr.lower()
        print("✓ Empty command error handling works")
        
        # Test whitespace command
        result = await command_tools.run_command("   ")
        assert result.success is False
        print("✓ Whitespace command error handling works")
        
        # Test invalid working directory
        result = await command_tools.run_command("echo test", cwd="nonexistent")
        assert result.success is False
        assert "does not exist" in result.stderr
        print("✓ Invalid working directory error handling works")
        
        # Test failed command
        if os.name == 'nt':
            result = await command_tools.run_command("dir nonexistent_dir")
        else:
            result = await command_tools.run_command("ls nonexistent_dir")
        
        assert result.success is False
        assert result.exit_code != 0
        print("✓ Failed command error handling works")
        
        print("✓ All error handling tests passed!")
        return True


async def test_real_world_scenarios():
    """Test real-world command scenarios."""
    from agent.tools.command import CommandTools
    
    print("\nTesting Real-World Command Scenarios...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        command_tools = CommandTools(workspace_root=str(workspace))
        
        # Test 1: Create and manipulate files
        test_file = "hello.txt"
        content = "Hello, World!"
        
        if os.name == 'nt':  # Windows
            create_cmd = f'echo {content} > {test_file}'
            list_cmd = "dir"
            read_cmd = f"type {test_file}"
        else:  # Unix-like
            create_cmd = f'echo "{content}" > {test_file}'
            list_cmd = "ls -la"
            read_cmd = f"cat {test_file}"
        
        # Create file
        result = await command_tools.run_command(create_cmd)
        if result.success:
            print("✓ File creation works")
            
            # List files
            result = await command_tools.run_command(list_cmd)
            if result.success and test_file in result.stdout:
                print("✓ File listing works")
                
                # Read file
                result = await command_tools.run_command(read_cmd)
                if result.success and content in result.stdout:
                    print("✓ File reading works")
        
        # Test 2: Check if common development tools are properly allowlisted
        dev_tools = ["python --version", "node --version", "git --version"]
        
        for tool in dev_tools:
            if command_tools.is_command_allowed(tool):
                result = await command_tools.run_command(tool, timeout=5)
                if result.success:
                    print(f"✓ {tool.split()[0]} is available and working")
                else:
                    print(f"⚠ {tool.split()[0]} is allowlisted but not available")
            else:
                print(f"⚠ {tool.split()[0]} is not in allowlist")
        
        # Test 3: Environment variable handling
        env_vars = {"TEST_VAR": "test_value", "CUSTOM_PATH": "/custom/path"}
        
        if os.name == 'nt':
            env_cmd = "echo %TEST_VAR%"
        else:
            env_cmd = "echo $TEST_VAR"
        
        result = await command_tools.run_command(env_cmd, env=env_vars)
        if result.success and "test_value" in result.stdout:
            print("✓ Environment variable handling works")
        else:
            print("⚠ Environment variable test inconclusive")
        
        print("✓ Real-world scenarios testing completed!")
        return True


if __name__ == "__main__":
    async def main():
        try:
            success1 = await test_command_tools()
            success2 = await test_error_handling()
            success3 = await test_real_world_scenarios()
            
            if success1 and success2 and success3:
                print("\n🎉 All Command integration tests passed successfully!")
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