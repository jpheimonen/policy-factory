# Implementation Summary

## Overview

This task rewired the agent framework from a non-existent `claude_agent_sdk` package to the official Anthropic Python SDK with proper tool use. It also redesigned values seeding to produce axiomatic values instead of descriptive facts, made SA seeding re-runnable with optional human-provided context, and implemented a shared Anthropic client with connection pooling.

## Key Changes

- **Agent Framework Rewrite**: Replaced the nonexistent `claude_agent_sdk` with Anthropic Python SDK using streaming agentic loop
- **File Tools Module**: New sandboxed file tools (list_files, read_file, write_file, delete_file) with path traversal protection
- **Values Seeding**: New endpoint to generate axiomatic values from Claude's knowledge (no tools, single analysis call)
- **SA Seeding Fixes**: Removed 409 guard to allow re-seeding, added optional context parameter, clears existing items before reseeding
- **Shared Anthropic Client**: Connection pooling for concurrent agent runs (important for cascade with 6 parallel critics)
- **Seed Status Endpoint**: Now reports both values and SA layer counts
- **Prompt Updates**: All generator/seed prompts updated to reference explicit tool calls instead of direct file access
- **Data Initialization**: Removed pre-seeded values writing; values layer starts empty after initialization

## Files Modified

### Core Agent Framework
- `pyproject.toml` - Added `anthropic>=0.52.0` dependency
- `src/policy_factory/agent/session.py` - Complete rewrite of `_run_once()` with Anthropic SDK streaming
- `src/policy_factory/agent/tools.py` - New file tools module with sandbox validation
- `src/policy_factory/agent/config.py` - Updated AgentConfig, added values-seed role, tool configuration per role
- `src/policy_factory/agent/__init__.py` - Updated exports

### Server & Endpoints
- `src/policy_factory/server/deps.py` - Added shared Anthropic client dependency
- `src/policy_factory/server/routers/seed.py` - New values seed endpoint, fixed SA seed (no 409, context param), updated status endpoint
- `src/policy_factory/server/routers/cascade.py` - Updated to use shared client
- `src/policy_factory/server/routers/heartbeat.py` - Updated to use shared client
- `src/policy_factory/server/routers/ideas.py` - Updated to use shared client

### Prompts
- `src/policy_factory/prompts/seed/values.md` - New prompt for axiomatic values synthesis
- `src/policy_factory/prompts/seed/seed.md` - Updated for tool references
- `src/policy_factory/prompts/generators/*.md` - Updated all generator prompts for tool references
- `src/policy_factory/prompts/heartbeat/sa-update.md` - Updated for tool references

### Data Layer
- `src/policy_factory/data/init.py` - Removed pre-seeded values writing
- `src/policy_factory/data/seed_values.py` - Deleted (no longer used)

### Tests
- `tests/test_agent_session.py` - Complete rewrite with Anthropic SDK mocks
- `tests/test_agent_tools.py` - New file: comprehensive tests for file tools and sandbox validation
- `tests/test_seed_api.py` - Updated for new endpoint behaviors
- `tests/test_data_init.py` - Updated for no pre-seeded values

## How to Test

### Prerequisites
1. Ensure `ANTHROPIC_API_KEY` is set in environment for live agent testing
2. Backend is running on http://localhost:8769 (or auto-detected port)

### Test Flows

1. **Check Seed Status** (no auth required for health, auth required for seed status):
   ```bash
   curl http://localhost:8769/api/health/check
   # Should return: {"application":"policy-factory","status":"ok"}
   ```

2. **Values Seeding** (requires authentication):
   - POST to `/api/seed/values`
   - Should create 8-12 markdown files in `data/values/` with axiomatic values
   - Each value has frontmatter with `title` and `tensions` fields
   - Can be called multiple times (clears existing values)

3. **SA Seeding** (requires authentication):
   - POST to `/api/seed/` with optional `{"context": "..."}`
   - No longer returns 409 if SA layer has items
   - Clears existing SA items before creating new ones
   - Triggers cascade after completion

4. **Seed Status**:
   - GET `/api/seed/status`
   - Returns `values_seeded`, `values_count`, `sa_seeded`, `sa_count`

5. **Cascade Viewer**:
   - WebSocket at `/api/ws/events`
   - Text streaming with typewriter effect during agent execution

6. **Run Tests**:
   ```bash
   make test
   # All 1041 tests should pass
   ```

## Service Status

**Status: Running**

- **Backend**: Running on http://localhost:8769
- **Health Check**: `GET /api/health/check` returns `{"application":"policy-factory","status":"ok"}`
- **Frontend Dev Server**: Failed to start (Node.js 19.2.0 detected, Vite requires 20.19+)
  - The built frontend is served by the backend directly
  - Access the app at http://localhost:8769

**Warnings** (expected):
- `JWT_SECRET_KEY not set` - Using random key (tokens won't persist across restarts)
- `ANTHROPIC_API_KEY not set` - Agent operations will fail until set

## Notes/Concerns

1. **Live API Testing Required**: The agent operations (values seeding, SA seeding, cascade, heartbeat) require `ANTHROPIC_API_KEY` to be set. Unit tests mock at the session level, so live API testing is needed to verify actual Claude responses.

2. **Values Quality**: The values seed prompt instructs Claude to produce axiomatic Finnish policy values from training knowledge. The quality of output depends on Claude's knowledge and may need prompt refinement based on results.

3. **Node.js Version**: The Vite frontend dev server requires Node.js 20.19+. Current environment has 19.2.0. The built frontend is still served by the backend, but hot reload during UI development won't work until Node.js is upgraded.

4. **Web Search Tool**: The heartbeat and SA seeding use Anthropic's server-side `web_search_20250305` tool. This is handled automatically by the API - no client-side execution needed.
