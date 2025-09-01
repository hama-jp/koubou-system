#!/usr/bin/env python3
"""
Tool Executor for Worker File Operations
Parses Gemini CLI output and executes safe file operations
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Security configuration
ALLOWED_ROOT = Path("/home/hama/project/koubou-system").resolve()
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
TIMEOUT_SECONDS = 30
ALLOWED_COMMANDS = ["ls", "cat", "echo", "grep", "wc", "head", "tail", "find"]

class ToolExecutor:
    def __init__(self, sandbox_root: Optional[Path] = None):
        self.sandbox_root = sandbox_root or ALLOWED_ROOT
        self.logger = logging.getLogger(__name__)
        
    def _check_path(self, path: str) -> Path:
        """Validate and sanitize file paths"""
        try:
            p = Path(path).resolve()
            if not p.is_relative_to(self.sandbox_root):
                raise ValueError(f"Path {path} is outside sandbox")
            return p
        except Exception as e:
            raise ValueError(f"Invalid path {path}: {e}")
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Safely read a file"""
        try:
            safe_path = self._check_path(path)
            if not safe_path.exists():
                return {"success": False, "error": f"File not found: {path}"}
            
            if safe_path.stat().st_size > MAX_FILE_SIZE:
                return {"success": False, "error": f"File too large: {path}"}
            
            with open(safe_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Safely write to a file"""
        try:
            safe_path = self._check_path(path)
            
            # Create parent directories if needed
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {"success": True, "message": f"File written: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_shell_command(self, cmd: str) -> Dict[str, Any]:
        """Safely execute shell commands"""
        try:
            # Extract the base command
            base_cmd = cmd.split()[0] if cmd else ""
            
            # Check if command is allowed
            if base_cmd not in ALLOWED_COMMANDS:
                return {"success": False, "error": f"Command '{base_cmd}' not allowed"}
            
            # Execute in sandbox directory
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=self.sandbox_root
            )
            
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def parse_and_execute(self, gemini_output: str) -> str:
        """Parse Gemini CLI output and execute tools"""
        # Pattern to match tool calls in Gemini output
        patterns = [
            (r'<\|channel\|>commentary to=read_file.*?<\|message\|>({.*?})', 'read_file'),
            (r'<\|channel\|>commentary to=write_file.*?<\|message\|>({.*?})', 'write_file'),
            (r'<\|channel\|>commentary to=run_shell_command.*?<\|message\|>({.*?})', 'run_shell_command'),
        ]
        
        results = []
        
        for pattern, tool_name in patterns:
            matches = re.findall(pattern, gemini_output, re.DOTALL)
            for match in matches:
                try:
                    # Parse JSON arguments
                    args = json.loads(match)
                    
                    # Execute the appropriate tool
                    if tool_name == 'read_file':
                        result = self.read_file(args.get('absolute_path', args.get('path', '')))
                    elif tool_name == 'write_file':
                        result = self.write_file(
                            args.get('path', ''),
                            args.get('content', '')
                        )
                    elif tool_name == 'run_shell_command':
                        cmd_args = args.get('cmd', [])
                        if isinstance(cmd_args, list) and len(cmd_args) > 2:
                            # Extract the actual command from ["bash", "-lc", "command"]
                            cmd = cmd_args[-1]
                        else:
                            cmd = ' '.join(cmd_args) if isinstance(cmd_args, list) else cmd_args
                        result = self.run_shell_command(cmd)
                    else:
                        result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                    
                    results.append({
                        "tool": tool_name,
                        "args": args,
                        "result": result
                    })
                    
                except json.JSONDecodeError as e:
                    results.append({
                        "tool": tool_name,
                        "error": f"Failed to parse JSON: {e}"
                    })
                except Exception as e:
                    results.append({
                        "tool": tool_name,
                        "error": str(e)
                    })
        
        # If no tools were called, return the original output
        if not results:
            return gemini_output
        
        # Format results for return
        output_lines = []
        for r in results:
            if 'result' in r:
                if r['result'].get('success'):
                    if r['tool'] == 'read_file':
                        output_lines.append(f"File content:\n{r['result']['content']}")
                    elif r['tool'] == 'write_file':
                        output_lines.append(r['result']['message'])
                    elif r['tool'] == 'run_shell_command':
                        output_lines.append(f"Command output:\n{r['result']['stdout']}")
                        if r['result']['stderr']:
                            output_lines.append(f"Errors:\n{r['result']['stderr']}")
                else:
                    output_lines.append(f"Error: {r['result']['error']}")
            else:
                output_lines.append(f"Error: {r['error']}")
        
        return '\n'.join(output_lines)


def main():
    """CLI interface for testing"""
    if len(sys.argv) < 2:
        print("Usage: tool_executor.py '<gemini_output>'")
        sys.exit(1)
    
    executor = ToolExecutor()
    result = executor.parse_and_execute(sys.argv[1])
    print(result)


if __name__ == "__main__":
    main()