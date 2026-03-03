# Research — cc-runner Codebase Patterns

Investigation of the ModernPath Software Factory (cc-runner) codebase at `/home/jp/projects/modernpath/cc-runner` to identify patterns, reuse opportunities, and architectural decisions relevant to Policy Factory.

## Related Code

### Project Structure

```
cc-runner/
├── src/cc_runner/           # Python backend package
│   ├── main.py              # CLI entry point (argparse, .env loading, server startup)
│   ├── events.py            # Event system (dataclass events + EventEmitter pub/sub)
│   ├── spar.py              # Spar session management (dataclasses, prompt loading, agent config)
│   ├── server/
│   │   ├── app.py           # FastAPI app factory (create_app with lifespan)
│   │   ├── ws.py            # WebSocket ConnectionManager (connect/disconnect/broadcast)
│   │   ├── deps.py          # Dependency injection (module-level singletons)
│   │   ├── port_utils.py    # Port auto-detection
│   │   └── routers/         # 16+ APIRouter files (health, spar, runs, tasks, etc.)
│   ├── session/
│   │   ├── base.py          # AgentSession ABC + create_agent_session() factory
│   │   ├── cc_session.py    # ClaudeCodeSession — claude-agent-sdk wrapper
│   │   ├── controller.py    # SessionController for stop/resume
│   │   ├── state.py         # SessionConfig, RalphConfig, RunState dataclasses
│   │   └── message_handler.py
│   ├── store/
│   │   ├── schema.py        # SQLite schema (CREATE TABLE IF NOT EXISTS + migrations)
│   │   ├── base.py          # BaseRunStore (CRUD with raw sqlite3)
│   │   └── __init__.py      # RunStore = BaseRunStore + mixin composition
│   ├── prompts/
│   │   ├── loader.py        # PromptLoader class + convenience functions
│   │   ├── __init__.py      # Public API: load_prompt, load_section, load_sections
│   │   ├── spar/            # Spar prompt variants (default.md, bugfix.md, etc.)
│   │   ├── worker/          # Build/implementation prompts
│   │   ├── specify/         # Specification generation prompts
│   │   └── sections/        # Reusable prompt fragments (core_autonomy.md, etc.)
│   └── static/dist/         # Built frontend assets (output of ui build)
├── ui/                      # Frontend (Vite + React 19 + TypeScript)
│   ├── vite.config.ts       # Dev proxy, build output to ../src/cc_runner/static/dist/
│   ├── package.json         # Dependencies: react 19, styled-components 6, zustand 5, etc.
│   └── src/
│       ├── main.tsx          # React root (StrictMode)
│       ├── App.tsx           # ThemeProvider + BrowserRouter + Routes
│       ├── App.styles.ts     # Root styled component
│       ├── styles/
│       │   ├── theme.ts      # Design tokens (colors, fonts, spacing, shadows, etc.)
│       │   ├── styled.d.ts   # TypeScript augmentation for DefaultTheme
│       │   └── GlobalStyles.ts
│       ├── stores/           # Zustand stores (projectInfoStore, projectConfigStore, etc.)
│       ├── hooks/            # Custom hooks (useWebSocket, useRunData, useAutoScroll, etc.)
│       ├── components/
│       │   ├── atoms/        # Primitive UI (Button, Card, Badge, Input, Select, Toggle, etc.)
│       │   ├── molecules/    # Composite UI (FormField, ButtonGroup, ListInput, etc.)
│       │   ├── organisms/    # Complex UI (SettingsPanel, TaskSteps, ChatView, etc.)
│       │   └── utils/        # ErrorBoundary, etc.
│       ├── pages/            # Route-level page components
│       └── types/            # TypeScript type definitions
├── Makefile                  # Dev workflow (make dev, make run, make build)
└── pyproject.toml            # Hatchling build, dependencies, entry point
```

### Key Files Examined

| File | Relevance | Key Pattern |
|------|-----------|-------------|
| `pyproject.toml` | Package setup | hatchling build, `packages = ["src/cc_runner"]`, artifacts include static/dist |
| `Makefile` | Dev workflow | `make dev` finds port, launches backend+frontend with `trap 'kill 0' EXIT` |
| `main.py` | CLI entry | argparse subcommands, multi-location .env loading, port auto-detection |
| `server/app.py` | App factory | `create_app()` with lifespan, router registration, WS endpoint, SPA fallback |
| `server/ws.py` | WebSocket | `ConnectionManager` class with connect/disconnect/broadcast/send_to |
| `server/deps.py` | DI | Module-level singletons, `init_deps()` at startup, getter functions |
| `server/routers/health.py` | Router pattern | `APIRouter(prefix="/api/health", tags=["health"])`, dataclass responses |
| `server/routers/spar.py` | Complex router | Streaming responses, store integration, agent lifecycle management |
| `events.py` | Event system | Typed dataclass events, EventEmitter pub/sub, async handlers |
| `session/base.py` | Agent ABC | `AgentSession` ABC with `run(prompt)` → dict, factory dispatch |
| `session/cc_session.py` | Claude SDK | Full wrapper: retry logic, hooks, MCP servers, quota handling, stderr capture |
| `spar.py` | Spar lifecycle | SparSession dataclass, SparEvent streaming, prompt loading via `load_prompt()` |
| `store/schema.py` | DB schema | CREATE TABLE IF NOT EXISTS, WAL mode, migrations via ALTER TABLE try/except |
| `store/base.py` | Store pattern | Raw sqlite3, `row_factory = sqlite3.Row`, manual dataclass conversion |
| `store/__init__.py` | Store composition | Mixin pattern: `RunStore(BaseRunStore, SparStoreMixin, ApiKeyStoreMixin)` |
| `prompts/loader.py` | Prompt loading | `PromptLoader` class, `str.format(**variables)` templating, sections |
| `ui/src/styles/theme.ts` | Design tokens | Flat const object with colors, fonts, spacing, radii, shadows, transitions |
| `ui/src/styles/GlobalStyles.ts` | Global CSS | `createGlobalStyle` with theme-aware scrollbars, reset |
| `ui/src/App.tsx` | App root | ThemeProvider → GlobalStyles → BrowserRouter → Routes |
| `ui/src/hooks/useWebSocket.ts` | WS client | Auto-reconnect with exponential backoff, event deduplication, REST replay |
| `ui/src/stores/projectInfoStore.ts` | Store pattern | `create<State>()` with fetch, polling, visibility refresh |

---

## Reuse Opportunities

### Direct Reuse (copy and adapt)

1. **Makefile pattern**: The `make dev` target that finds an available port, sets `VITE_BACKEND_PORT`, and runs backend+frontend concurrently with `trap 'kill 0' EXIT`. This is directly reusable — just change binary names and paths.

2. **`pyproject.toml` structure**: hatchling build system with `packages = ["src/policy_factory"]`, artifact inclusion for `src/policy_factory/static/dist/`, entry point definition. Near-identical structure.

3. **`vite.config.ts`**: The proxy configuration pattern (`/api` → backend, `/ws` → WebSocket backend) and build output (`outDir: "../src/policy_factory/static/dist"`). Nearly identical.

4. **`create_app()` factory pattern**: The FastAPI app factory with lifespan, router registration, WebSocket endpoint, and SPA fallback. The overall shape is directly reusable — Policy Factory needs the same single-binary serving model.

5. **`ConnectionManager` (ws.py)**: The WebSocket connection manager is simple and fully reusable. Policy Factory needs the same broadcast-to-all-clients pattern for cascade streaming.

6. **Dependency injection via `deps.py`**: Module-level singletons with `init_deps()` and getter functions. Simple, works well for a single-process FastAPI app. Policy Factory can use the same pattern, extended with auth-related deps.

7. **`PromptLoader` and prompt file organization**: The `prompts/` directory with categories (e.g., `prompts/agents/`, `prompts/critics/`, `prompts/heartbeat/`) and `load_prompt(category, name, **variables)` is directly reusable. The `str.format()` templating approach is simple and sufficient.

8. **SQLite schema pattern**: `CREATE TABLE IF NOT EXISTS` with WAL mode, migrations via `ALTER TABLE` wrapped in try/except. Straightforward and battle-tested. Policy Factory needs this for users, ideas, scores, cascade state, etc.

9. **Store mixin composition**: `RunStore(BaseRunStore, MixinA, MixinB)` pattern for organizing store methods by domain. Policy Factory's store will have many more domains (auth, ideas, scoring, cascade, heartbeat) — this pattern scales.

10. **`EventEmitter` pub/sub**: The async event emitter with typed dataclass events is directly reusable. Policy Factory needs its own event types (CascadeStarted, LayerUpdated, CriticCompleted, etc.) but the emitter infrastructure is identical.

11. **Frontend theme system**: The design token approach (`theme.ts` with nested objects for colors, spacing, radii, etc.) with styled-components `ThemeProvider` and `styled.d.ts` augmentation. Policy Factory needs a dual-theme version (dark + light) but the token structure is the same.

12. **`useWebSocket` hook**: Auto-reconnect with exponential backoff, event deduplication, REST replay on reconnect. Directly reusable — Policy Factory needs the same resilient WS connection.

13. **Zustand store pattern**: `create<State>()` with fetch logic, polling, and visibility refresh. Reusable pattern for all Policy Factory stores.

14. **Atomic component structure**: atoms/molecules/organisms hierarchy. Reusable organizational approach.

### Adapt Significantly

1. **`ClaudeCodeSession` (cc_session.py)**: The agent wrapper is heavily specific to cc-runner's pipeline (Ralph loops, guardrails, MCP tools for spec building). Policy Factory needs a **simpler wrapper** focused on:
   - Running a prompt to completion
   - Streaming events to WebSocket
   - Per-agent model selection (the `model` parameter on `SessionConfig` is reusable)
   - Retry/error handling (the transient error detection and retry logic is reusable)
   - No Ralph loops, no guardrails, no HITL — these are cc-runner-specific features

2. **`AgentSession` ABC**: The concept of an abstract session interface is useful, but Policy Factory's agents have different concerns. We need something like:
   ```python
   class PolicyAgentSession:
       async def run(prompt: str, cwd: str, model: str) -> AgentResult
       async def stream(prompt: str, cwd: str, model: str) -> AsyncIterator[AgentEvent]
   ```
   Simpler than cc-runner's version — no resume, no HITL, no controller.

3. **Router patterns**: The `APIRouter(prefix=..., tags=...)` structure is standard FastAPI. Policy Factory needs auth middleware on all routes (unlike cc-runner which is single-user local). The pattern of dataclass responses and async handlers is reusable.

4. **Event types**: cc-runner's event types (RunStarted, StepCompleted, PhaseStarted, etc.) map to pipeline steps. Policy Factory needs its own event taxonomy:
   - `CascadeStarted`, `CascadeCompleted`, `CascadeFailed`
   - `LayerGenerationStarted`, `LayerGenerationCompleted`
   - `CriticStarted`, `CriticCompleted`, `SynthesisCompleted`
   - `HeartbeatTierStarted`, `HeartbeatTierCompleted`
   - `IdeaEvaluationStarted`, `IdeaEvaluationCompleted`
   - `AgentChunk` (streamed text from agent)

5. **Spar session management**: The spar concept exists in cc-runner but is for human-AI chat during planning. Policy Factory doesn't have a "spar" feature — but the pattern of managing long-running async AI sessions, streaming their output, and persisting results is relevant to cascade management.

### Not Reusable

1. **cc-runner pipeline logic**: Steps, phases, spec generation, code review, CI monitoring — none of this applies.
2. **Ralph Wiggum loops**: Completion-check loop mechanism — not needed.
3. **HITL (human-in-the-loop) system**: cc-runner's interactive tool permission/question system — not needed for Policy Factory's autonomous agents.
4. **Spec file structure**: tasks/, step files, acceptance criteria — Policy Factory's data model is completely different.
5. **Git integration for code**: cc-runner's git features (branch management, PR creation, diff viewing) — Policy Factory uses git for data versioning, a fundamentally different use case.

---

## Patterns and Conventions

### Backend Patterns

| Pattern | How cc-runner does it | How Policy Factory should do it |
|---------|----------------------|-------------------------------|
| **App factory** | `create_app()` with lifespan, returns FastAPI instance | Same pattern, add auth middleware |
| **Dependency injection** | Module-level singletons, getter functions | Same, extend with auth context (current_user dependency) |
| **Router structure** | `APIRouter(prefix="/api/{domain}", tags=[...])` | Same, all routers get JWT auth dependency except `/api/auth/*` |
| **Store** | Raw sqlite3, mixin composition, dataclass models | Same approach, more domains (users, ideas, scores, cascade, heartbeat) |
| **Schema migrations** | ALTER TABLE wrapped in try/except | Same — simple and sufficient for this scale |
| **Agent sessions** | ABC + factory dispatch, wrapped SDK client | Simpler version — just ClaudeCodeSession with per-agent model config |
| **Prompts** | Markdown files in `prompts/` dir, `str.format()` templating | Same, with categories: `agents/`, `critics/`, `heartbeat/`, `meditation/` |
| **Events** | Typed dataclass events, EventEmitter pub/sub | Same, with Policy Factory-specific event types |
| **WebSocket** | ConnectionManager with broadcast/send_to | Same, add JWT auth on connection |
| **Config** | .env files, multi-location loading | Same pattern |
| **Logging** | Python `logging` module, per-module loggers | Same |

### Frontend Patterns

| Pattern | How cc-runner does it | How Policy Factory should do it |
|---------|----------------------|-------------------------------|
| **App structure** | ThemeProvider → GlobalStyles → BrowserRouter → Routes | Same, add AuthProvider context wrapping routes |
| **Theme** | Single const object with design tokens, dark-only | Dual theme objects (dark + light) + system preference detection |
| **Styling** | styled-components with `${({ theme }) => theme.X}` | Same approach |
| **State** | Zustand `create<State>()` with fetch + polling | Same pattern, more stores (auth, layers, cascade, ideas, activity) |
| **WebSocket** | Custom `useWebSocket` hook with reconnect + dedup | Same, add JWT token in connection URL or first message |
| **Components** | Atomic design (atoms/molecules/organisms) | Same hierarchy |
| **Routing** | react-router-dom v7 with BrowserRouter + Routes | Same, add protected route wrapper |
| **Types** | Separate `types/` directory | Same |
| **Testing** | vitest + @testing-library/react + playwright | Same stack |
| **Storybook** | .stories.tsx files co-located with components | Same approach for design system components |

### Naming Conventions

- **Python packages**: `src/policy_factory/` (snake_case)
- **Python modules**: lowercase with underscores (e.g., `cc_session.py`, `base.py`)
- **Router files**: domain-named (e.g., `health.py`, `spar.py`, `tasks.py`)
- **Frontend files**: PascalCase for components (e.g., `App.tsx`, `RunView.tsx`), camelCase for hooks/stores (e.g., `useWebSocket.ts`, `projectInfoStore.ts`)
- **Style files**: `ComponentName.styles.ts` pattern for co-located styles
- **Test files**: `ComponentName.test.tsx` or `hookName.test.ts` co-located

---

## Risks and Concerns

### Technical Risks

1. **Claude Agent SDK maturity**: cc-runner uses `claude-agent-sdk==0.1.37` — a pre-1.0 package. The SDK API may change. Policy Factory should pin the version and wrap the SDK behind an abstraction layer (like cc-runner's `AgentSession` pattern) to isolate from SDK changes.

2. **Concurrent agent execution**: cc-runner runs one agent at a time per pipeline. Policy Factory needs 6 critics running in parallel plus concurrent idea evaluations. The `ClaudeCodeSession` wrapper was not designed for concurrency — each session spawns a subprocess (`claude` CLI). Running 6+ concurrent Claude CLI processes needs careful resource management (memory, CPU, API rate limits). The retry and error handling in `cc_session.py` (lines 270-580) is battle-tested but was designed for sequential use.

3. **WebSocket authentication**: cc-runner has zero auth — it's a local single-user tool. Policy Factory needs JWT-authenticated WebSocket connections. The `ConnectionManager` needs to be extended to track which user owns each connection, and the WebSocket handshake needs to validate the JWT. This is a well-solved problem (query param token or first-message auth) but it's an addition to the pattern.

4. **Data directory as separate git repo**: cc-runner doesn't have this concept. Auto-committing agent changes to a git repo adds complexity: What if two agents try to commit simultaneously? Solution: the single-writer cascade lock already serializes layer mutations, so git conflicts shouldn't occur. But idea evaluations (read-only) shouldn't trigger commits anyway.

5. **Theme system**: cc-runner is dark-only. Policy Factory needs dual themes. The theme.ts structure needs to be refactored into a `darkTheme` and `lightTheme` object, with a theme switcher in the app and `prefers-color-scheme` media query detection. This is a well-known pattern but means the cc-runner theme isn't directly copy-pasteable — it needs restructuring.

6. **i18n**: cc-runner has zero internationalization. Policy Factory requires all UI strings externalized from day one. This is a significant architectural addition that touches every component. Need to choose an i18n library (react-intl, react-i18next, or a simple custom solution) and set up the extraction/organization workflow.

7. **APScheduler in-process**: Using APScheduler inside the FastAPI process for the heartbeat is simple but means the scheduler dies if the server crashes. For a Docker deployment this is acceptable (Docker restarts the container), but the scheduler state (what was the last heartbeat run?) must be in SQLite, not in memory.

8. **yle.fi scraping**: The heartbeat's Tier 1 needs to read yle.fi. This is a web scraping task that could break if yle.fi changes its markup. Claude Code's native web search capability handles this more robustly than custom scraping code — let the agent read the site using its built-in tools. But we should consider: does yle.fi have an RSS feed or API that's more stable than HTML scraping?

### Architectural Concerns

1. **Agent prompt complexity**: Each Policy Factory agent needs a substantial system prompt: the meditation preamble, layer-specific instructions, the full context of layers below, pending feedback memos, and cross-layer references. These prompts will be large. Need to ensure they fit within Claude's context window alongside the actual file contents the agent reads.

2. **Cascade state management**: cc-runner tracks pipeline state with simple SQLite records. Policy Factory's cascade is more complex: it can pause mid-cascade, queue additional cascades, and resume from failure points. The cascade state machine needs careful design to handle all transitions correctly.

3. **No ORM, raw sqlite3**: cc-runner uses raw sqlite3 with manual Row-to-dataclass conversion. This is fine for a small number of tables but Policy Factory has significantly more tables (users, ideas, scores, cascade_state, feedback_memos, heartbeat_runs, agent_runs, etc.). Consider whether to stick with raw sqlite3 or use a lightweight abstraction. Recommendation: stay with raw sqlite3 for consistency with cc-runner patterns — the mixin composition pattern scales adequately.

4. **Frontend complexity**: cc-runner's frontend is already substantial (~100+ component files). Policy Factory's frontend is comparable in scope (stack overview, layer detail, item editing, idea inbox with radar charts, cascade viewer, activity feed, admin panel, auth flows). The atomic design pattern helps manage this complexity but the build will be substantial.

5. **Bias meditation token cost**: The meditation preamble (10→1 countdown with self-reflection) adds tokens to every agent call. If each line is ~50 tokens, that's ~500 extra tokens per agent invocation. With 6 critics × 5 layers × 2 runs (generation + synthesis) = 60 invocations per full cascade, that's ~30K extra tokens per cascade just for meditation. Acceptable cost for the philosophical value, but worth noting.

### What cc-runner Got Right (and Policy Factory Should Follow)

1. **Single-binary serving**: The pattern of building frontend into the Python package's static directory means deployment is `pip install` + run. No separate frontend server needed. Essential for Docker simplicity.

2. **Event-driven architecture**: The EventEmitter → WebSocket broadcast pattern cleanly decouples agent execution from UI updates. Policy Factory should use this same pattern for cascade streaming.

3. **Prompt files as first-class artifacts**: Storing prompts as markdown files (not inline strings) makes them easy to read, edit, and version. The `load_prompt()` function with `str.format()` templating is simple and effective.

4. **Module-level singleton DI**: While not as sophisticated as dependency injection frameworks, the `deps.py` pattern is pragmatic for a single-process app. It avoids the complexity of DI containers while providing testability through the `init_deps()` initialization pattern.

5. **Typed dataclass events**: Using dataclasses for event types (not dicts) provides type safety and makes the event schema self-documenting. Policy Factory should continue this pattern.

6. **WebSocket resilience**: The `useWebSocket` hook's auto-reconnect with exponential backoff and REST replay on reconnect is production-quality. The event deduplication by ID prevents double-rendering after reconnect.
