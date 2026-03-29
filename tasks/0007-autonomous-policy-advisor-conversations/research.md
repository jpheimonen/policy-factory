# Research

## Related Code

### Agent System
- `src/policy_factory/agent/session.py` — AgentSession wrapper for Claude CLI and Gemini backends. Handles tool integration via MCP, response streaming via EventEmitter, and role-based tool permissions. Single-shot execution model — each `run()` call creates a fresh session with no built-in conversation continuity.
- `src/policy_factory/agent/tools.py` — Sandboxed file tools (list_files, read_file, write_file, delete_file) using MCP protocol. Includes `validate_path` function that enforces sandbox boundaries using path resolution and escape detection. Uses `contextvars.ContextVar` for task-local sandbox isolation.
- `src/policy_factory/agent/config.py` — Maps agent roles to models and tool permissions. Defines TOOL_SET_FULL, TOOL_SET_READ_ONLY, TOOL_SET_NONE.

### Event System & WebSockets
- `src/policy_factory/events.py` — EventEmitter pub/sub system with typed dataclass events (CascadeStarted, AgentTextChunk, etc.).
- `src/policy_factory/server/broadcast.py` — BroadcastHandler subscribes to EventEmitter, persists events to SQLite with sequential db_id, broadcasts via ConnectionManager.
- `src/policy_factory/server/ws.py` — ConnectionManager maintains WebSocket connections, handles authentication.
- `ui/src/hooks/useWebSocket.ts` — Frontend WebSocket hook with deduplication via db_id, reconnection with exponential backoff, missed event replay.
- `ui/src/hooks/useEventDispatch.ts` — Routes events to appropriate Zustand stores based on event type.
- `ui/src/types/events.ts` — TypeScript event type definitions.

### Layer System
- `src/policy_factory/data/layers.py` — LAYERS list with LayerInfo dataclass (slug, display_name, position). Item CRUD functions, narrative summary functions, cross-layer reference resolution.
- `src/policy_factory/cascade/orchestrator.py` — _SLUG_TO_PROMPT mapping, layers_from/layers_below utilities, _gather_generation_context for assembling layer content.
- `src/policy_factory/cascade/content.py` — gather_context_below assembles content from lower layers.
- `ui/src/lib/layerConstants.ts` — LAYER_NAME_KEYS mapping slugs to i18n keys.
- `ui/src/i18n/locales/en.ts` — Translation strings including layer names.

### Database
- `src/policy_factory/store/schema.py` — SQLite schema with tables: users, events, ideas, idea_scores, cascade_runs, cascade_queue, agent_runs, critic_results, synthesis_results, feedback_memos, heartbeat_runs. Uses autocommit mode, WAL journal, Row factory.
- `src/policy_factory/store/__init__.py` — PolicyStore class inheriting from BaseStore and all domain Mixins.
- `src/policy_factory/store/cascade.py` — CascadeStoreMixin with soft locking via is_lock_held(), enqueue_cascade, dequeue_cascade.

### UI Pages
- `ui/src/pages/ItemDetailPage.tsx` — View/Edit modes for individual items. Uses PageWrapper with max-width 800px centered layout. Significant whitespace on sides for sidebar integration.
- `ui/src/pages/ItemDetailPage.styles.ts` — Styled components including PageWrapper, PageHeader, Section.
- `ui/src/pages/LayerDetailPage.tsx` — Layer overview with narrative summary, feedback memos, items list, critic summary.
- `ui/src/components/organisms/AppLayout.tsx` — Root layout with Navigation, MainContent, InputPanel. Outlet renders page content.

### REST API
- `src/policy_factory/server/routers/layers.py` — CRUD endpoints for layers and items (/api/layers/).
- `src/policy_factory/server/routers/cascade.py` — Cascade trigger, status, history, pause/resume/cancel endpoints.

### Prompts
- `src/policy_factory/prompts/generators/values.md` — Values generator with tension-pair requirements, anti-consensus filter, anti-slop standards. Already contains good structure but outputs don't follow it.
- `src/policy_factory/prompts/sections/anti-slop.md` — Writing standards override, banned patterns, voice guidelines. Reusable for conversation agent.
- `src/policy_factory/prompts/critics/*.md` — 6 ideological critic prompts (realist, liberal-institutionalist, nationalist-conservative, social-democratic, libertarian, green-ecological).

## Reuse Opportunities

### AgentSession for Conversations
The existing AgentSession can be reused for conversation turns. Each user message triggers a new `run()` call with conversation history prepended to the prompt. No modification to AgentSession needed — conversation continuity handled at the prompt assembly layer.

### EventEmitter + WebSocket for Streaming
The existing event pipeline (EventEmitter → BroadcastHandler → ConnectionManager → Frontend) can be extended with new event types (e.g., ConversationTextChunk, ConversationFileEdit). No new infrastructure needed — just new event definitions and dispatch handlers.

### File Tools for Conversation Edits
The existing sandboxed file tools (write_file, delete_file) in tools.py are exactly what the conversation agent needs. The validation and sandbox enforcement is already robust.

### Git Integration
The existing `commit_changes` function in `src/policy_factory/data/git.py` (used by cascade generators) can be reused for auto-committing conversation edits.

### Cascade Queue Mechanism
The existing cascade queue (is_lock_held, enqueue_cascade, CascadeQueued event) provides the foundation for "queued cascade notification" when conversation edits affect foundational layers.

### Store Mixin Pattern
New conversations and messages tables should follow the existing Mixin pattern (ConversationStoreMixin) for consistency with idea.py, cascade.py, etc.

### Anti-Slop Prompt Section
The anti-slop.md prompt section can be included in the conversation agent's system prompt to maintain consistent writing quality.

### Layer Constants Pattern
Adding a new layer (philosophy) follows the established pattern: update LAYERS in layers.py, _SLUG_TO_PROMPT in orchestrator.py, LAYER_NAME_KEYS in layerConstants.ts, i18n strings in en.ts.

## Patterns and Conventions

### Agent Roles and Tool Permissions
Agents have roles (generator, critic, heartbeat, etc.) that map to tool permission sets. A new "conversation" role would get TOOL_SET_FULL (all file tools).

### Event Naming
Events use snake_case (cascade_started, agent_text_chunk). New conversation events should follow: conversation_started, conversation_message, conversation_file_edit.

### Database ID Generation
IDs are generated as `str(uuid.uuid4())` in Python before insertion. Timestamps are ISO 8601 strings.

### Frontend Store Updates
Events trigger store updates via useEventDispatch switch statement. New conversation events would route to a new useConversationStore.

### Prompt Template Variables
Generator prompts use `{layer_content}`, `{cross_layer_context}`, `{feedback_memos}` template variables filled by the prompt loader. Conversation prompts could follow similar pattern.

### Page Layout
Pages use styled-components with PageWrapper, PageHeader, Section patterns. Max-width centered content with responsive padding.

### Layer Position Numbering
Position 1 = bottom (values), higher = closer to policies. New philosophy layer at position 0 (or renumber all layers +1).

## Risks and Concerns

### AgentSession Single-Shot Design
AgentSession creates a fresh ClaudeSDKClient for each run() — no built-in session persistence. Multi-turn conversations require replaying full history each turn, which scales linearly with conversation length. Combined with full stack context, token counts could become very large (50-100k+ tokens per turn for long conversations).

### No Conversation Infrastructure
No existing conversation or message tables. No chat UI components. This is net-new infrastructure, not an extension of existing patterns.

### Cascade Queue Assumes Human Trigger
Current cascade queue auto-dequeues when previous cascade completes. For conversation-triggered cascades, we want notification + manual trigger, not auto-dequeue. May need to add a new "pending_conversation_cascade" state or separate notification mechanism.

### Philosophy Layer Ripple Effects
Adding a layer at position 0 affects:
- LAYERS list positions (all shift +1)
- _SLUG_TO_PROMPT mapping
- LAYER_NAME_KEYS
- i18n strings
- UI theme colors for layers
- Cascade context gathering (gather_context_below)
- Classifier prompt (lists available layers)
- Idea helpers (_SLUG_TO_VAR)
- Data directory creation

### Values Prompt Already Has Anti-Consensus Rules
The values generator prompt already contains extensive anti-consensus and tension-pair requirements. The outputs don't follow them. The fix may need to be more aggressive than prompt edits — possibly structural changes to how tension-pairs are enforced, or explicit validation steps.

### Conversation System Prompt Complexity
The conversation agent needs a sophisticated system prompt encoding: tiered epistemic authority, hold-your-ground behavior, cross-layer reasoning, when to edit vs discuss, anti-slop standards, philosophy layer grounding. This prompt is likely 2000+ words and will need careful iteration.

### Git Commit Pollution
Every conversation turn with edits = a git commit. Vigorous 20-turn debates create 20 commits. Git log becomes noisy. Could consider squash-on-session-end, but current design is per-turn commits.
