# Legacy Scripts Archive

This directory contains archived scripts from the codex-cli implementation that have been replaced by the gemini-cli implementation.

## Archived Files

### Core System Files
- **`start_system_legacy.sh`** - Original system startup script using codex-cli
- **`mcp_server_legacy.py`** - Original MCP server with codex-exec integration  
- **`local_worker_legacy.py`** - Original worker implementation using codex-cli

## Migration Notes

These files were archived on 2025-08-30 as part of the migration from codex-cli to gemini-cli implementation.

### Current Active Files (Replacements)
- `start_system_legacy.sh` → `.koubou/start_gemini_system.sh` 
- `mcp_server_legacy.py` → `.koubou/scripts/mcp_server_gemini.py`
- `local_worker_legacy.py` → `.koubou/scripts/workers/local_worker_gemini.py`

## Status
These files are **DEPRECATED** and should not be used in production. They are kept for reference purposes only.

Future versions may remove these files completely once the gemini-cli implementation has been fully validated in production.