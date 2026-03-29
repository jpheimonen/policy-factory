# Architecture

## Components Affected

### Backend: Layer System
- **layers.py** — Add philosophy layer at position 1 (bottom), renumber all existing layers +1. Add to LAYERS list with slug "philosophy", display name "Philosophy".
- **orchestrator.py** — Add philosophy to _SLUG_TO_PROMPT mapping. The layers_from and layers_below utilities automatically adapt via the LAYERS list.
- **content.py** — gather_context_below automatically includes philosophy content when generating values and above.
- **classifier.py** — The classifier prompt template already pulls from LAYERS, so it will include philosophy in layer selection.
- **ideas/helpers.py** — Add philosophy to _SLUG_TO_VAR mapping for idea evaluation context.

### Backend: Database (New Tables)
- **conversations** — Stores conversation metadata. Each conversation belongs to either an item (layer_slug + filename) or a layer (layer_slug only). Tracks creation time and last activity.
- **messages** — Stores individual messages within a conversation. Each message has a role (user or assistant), content, timestamp, and optional metadata about file edits made during that turn.

### Backend: Agent System
- **config.py** — Add new "conversation" agent role with TOOL_SET_FULL permissions (all file tools).
- **session.py** — No changes needed. Conversation turns use existing AgentSession.run() with conversation history prepended to the prompt.

### Backend: Conversation Runner (New)
- **conversation/runner.py** — New module that orchestrates a single conversation turn. Assembles the system prompt, conversation history, full stack context, and user message into a prompt. Calls AgentSession.run(). Detects file edits from tool calls. Commits changes to git. Checks if edited layers are foundational and queues cascade notification if so.

### Backend: Event System
- **events.py** — Add new event types: ConversationStarted, ConversationMessage (with streaming text chunks), ConversationFileEdit (when the agent modifies a file), ConversationCascadePending (when edits to foundational layers queue a cascade).

### Backend: REST API (New Router)
- **routers/conversations.py** — New router with endpoints for: creating a conversation (POST), listing conversations for an item or layer (GET), retrieving a conversation with its messages (GET), sending a message and receiving the response (POST with streaming via WebSocket events), deleting a conversation (DELETE).

### Backend: Cascade Integration
- **store/cascade.py** — Add mechanism for "pending conversation cascade" that differs from the normal queue. This pending cascade shows a notification to the user but does not auto-trigger. User explicitly triggers it via existing cascade endpoints.

### Frontend: Conversation Store (New)
- **stores/useConversationStore.ts** — New Zustand store tracking: active conversation ID, messages list, streaming state, pending cascade notification flag.

### Frontend: Event Dispatch
- **hooks/useEventDispatch.ts** — Add cases for new conversation event types, routing them to the conversation store.

### Frontend: Conversation Sidebar (New)
- **components/organisms/ConversationSidebar.tsx** — Right-aligned sliding panel containing: conversation history selector, message list with streaming support, input textarea with send button, pending cascade banner (when applicable).

### Frontend: Page Integration
- **pages/ItemDetailPage.tsx** — Add toggle button to open conversation sidebar. Adjust layout so content shifts left when sidebar is open. Refetch item content when conversation emits file edit events.
- **pages/LayerDetailPage.tsx** — Same sidebar integration as ItemDetailPage. Conversations at layer level discuss the entire layer rather than a specific item.

### Frontend: Layer UI
- **lib/layerConstants.ts** — Add philosophy to LAYER_NAME_KEYS.
- **i18n/locales/en.ts** — Add translation for philosophy layer name.
- **theme.ts** — Add theme color for philosophy layer (existing pattern has layer-specific colors).

### Prompts (New and Modified)
- **prompts/generators/philosophy.md** — New generator prompt for philosophy layer. Instructs AI to produce epistemological commitments, normative axioms, and philosophical tradition identification. Emphasizes balanced, multi-perspective foundation.
- **prompts/seed/philosophy.md** — New seed prompt for bootstrapping philosophy layer with initial content.
- **prompts/conversation/system.md** — New system prompt for conversation agent. Encodes: tiered epistemic authority model, hold-your-ground behavior, full stack awareness, when to edit vs discuss, anti-slop writing standards, philosophy layer as reasoning foundation.
- **prompts/generators/values.md** — Updated to fix technocratic consensus bias. Adds concrete good/bad tension-pair examples, enforces explicit "X vs. Y" title format, strengthens the requirement for presenting genuinely opposed positions.

### Filesystem
- **data/philosophy/** — New directory for philosophy layer items.
- **data/philosophy/README.md** — Narrative summary for philosophy layer.

## New Entities/Endpoints

### Database Entities

**Conversation**
- Belongs to an item (identified by layer_slug + filename) OR a layer (identified by layer_slug only, filename null)
- Tracks when created and when last active
- Has many messages

**Message**
- Belongs to a conversation
- Has role (user or assistant)
- Has text content
- Has timestamp
- Optionally tracks which files were edited during this turn (for assistant messages)

### REST Endpoints

**POST /api/conversations**
- Creates a new conversation for an item or layer
- Request includes layer_slug and optional filename (if item-level)
- Returns conversation ID

**GET /api/conversations**
- Lists conversations for an item or layer
- Query params: layer_slug, filename (optional)
- Returns list of conversation summaries (ID, created_at, last_message_preview)

**GET /api/conversations/{id}**
- Retrieves full conversation with all messages
- Returns conversation metadata and message list

**POST /api/conversations/{id}/messages**
- Sends a user message and triggers AI response
- Request includes message text
- AI response streams via WebSocket events
- Returns message ID (response content delivered via events)

**DELETE /api/conversations/{id}**
- Deletes a conversation and all its messages

**POST /api/cascade/trigger-pending**
- Triggers a pending cascade that was queued by conversation edits
- Separate from normal cascade trigger to distinguish conversation-initiated cascades

### WebSocket Events

**conversation_started**
- Emitted when a new conversation turn begins processing
- Includes conversation_id

**conversation_text_chunk**
- Emitted during streaming response
- Includes conversation_id and text fragment

**conversation_file_edit**
- Emitted when the agent writes or deletes a file
- Includes conversation_id, layer_slug, filename, action (write/delete)

**conversation_turn_complete**
- Emitted when the agent finishes its turn
- Includes conversation_id, message_id, files_edited list

**conversation_cascade_pending**
- Emitted when conversation edits to foundational layers queue a cascade
- Includes conversation_id and starting_layer for the pending cascade

## Integration Points

### Conversation → Agent System
The conversation runner creates an AgentSession with the "conversation" role. It assembles a prompt containing: the conversation system prompt, full policy stack content (all layers, all items), conversation history (all previous messages), and the current user message. The AgentSession executes this as a single-shot run, streaming response chunks via EventEmitter.

### Conversation → File System
The agent uses existing file tools (write_file, delete_file) sandboxed to the data directory. After the agent turn completes, the conversation runner inspects which files were modified by examining tool call results. It then commits all changes to git with a message indicating the conversation context.

### Conversation → Cascade System
After committing file changes, the conversation runner checks if any edited files belong to foundational layers (philosophy, values, situational-awareness). If so, it emits a ConversationCascadePending event and stores a pending cascade record. This record differs from the normal cascade queue — it persists until the user explicitly triggers it or dismisses it.

### Frontend → Conversation Sidebar
The sidebar component manages its own state via the conversation store. When opened on an item or layer page, it fetches existing conversations and displays them. When the user sends a message, it posts to the API and then listens for WebSocket events to display the streaming response. File edit events trigger a refetch of the parent page's item/layer content.

### Frontend → Cascade Notification
When a conversation_cascade_pending event arrives, the conversation store sets a flag that causes the sidebar (or a global notification) to display a banner. The banner explains that edits to foundational layers were made and offers a button to trigger the cascade. Clicking the button calls the trigger-pending endpoint.

### Philosophy Layer → Cascade
The philosophy layer integrates into the cascade like any other layer. When philosophy content changes (via conversation or cascade), it triggers regeneration of all layers above. The gather_context_below function automatically includes philosophy content when building context for values generation and above. Critics evaluate philosophy content using the same 6 ideological perspectives.

### Conversation System Prompt → AI Behavior
The conversation system prompt defines the AI's personality and reasoning approach. It instructs the AI to: always read the full policy stack context before responding, use the philosophy layer as foundational axioms for reasoning, apply tiered epistemic authority (only challenge philosophy on consistency grounds, use philosophy as ground truth for other layers), hold firm when evidence/logic supports its position, and follow anti-slop writing standards from the shared prompt section.

## Failure Modes

### Agent Timeout or Error
If the AgentSession fails mid-turn (timeout, API error, tool error), the conversation runner catches the exception, stores a partial message with an error flag, and emits a conversation_turn_error event. The UI displays the error and allows the user to retry or continue.

### Git Commit Failure
If git commit fails after file edits, the conversation runner logs the error but does not roll back file changes (they're already on disk). The UI shows a warning that changes were made but not committed. User can manually commit or the next successful turn will commit the accumulated changes.

### Cascade Already Running
If conversation edits queue a cascade but another cascade is already running, the pending cascade notification waits. The UI shows "Cascade pending (another cascade in progress)". When the running cascade completes, the pending cascade remains in notification state — it does not auto-start.

### Context Too Large
If the assembled prompt (system prompt + full stack + conversation history) exceeds 150,000 tokens, the conversation runner truncates older messages from conversation history until under 120,000 tokens, keeping the most recent exchanges. A warning is logged. If the stack content alone exceeds these limits, this is a fatal error that cannot be recovered through truncation.

### Philosophy Layer Conflicts
If a conversation on a non-philosophy item tries to edit philosophy content, the edit proceeds (cross-item editing is allowed). However, this could create confusion if multiple conversations are happening simultaneously. Since this is a single-user system, simultaneous conversations are not expected, but the UI should indicate when the AI is editing items outside the current conversation's scope.

### Conversation Store Stale State
If the user has the conversation sidebar open and another process (e.g., a cascade) modifies the item being discussed, the sidebar's view of the item becomes stale. The file edit events from cascades should also trigger item refetch on the parent page, keeping the view synchronized.

### Pending Cascade Accumulation
If the user makes multiple conversation edits to foundational layers without triggering the pending cascade, only one pending cascade should exist. Additional edits to foundational layers update the pending cascade's scope (e.g., if philosophy was edited, then values was edited, the pending cascade starts from philosophy). The pending cascade record tracks the lowest affected layer as its starting point.
