# Testing Plan

## Unit Tests

### Layer System (Philosophy Layer Addition)
- [ ] LAYERS list contains philosophy at position 1 with correct slug and display_name
- [ ] All existing layers have positions incremented by 1 (values=2, situational-awareness=3, etc.)
- [ ] get_layer returns correct LayerInfo for philosophy slug
- [ ] validate_layer_slug accepts philosophy as valid
- [ ] layers_from("philosophy") returns all 6 layers in order
- [ ] layers_below("values") returns only philosophy
- [ ] layers_below("philosophy") returns empty list

### Cascade Orchestrator (Philosophy Integration)
- [ ] _SLUG_TO_PROMPT contains mapping for philosophy
- [ ] _gather_generation_context for values layer includes philosophy content
- [ ] _gather_generation_context for philosophy layer returns empty context (no layers below)

### Database Schema (Conversation Tables)
- [ ] conversations table is created with expected columns
- [ ] messages table is created with expected columns
- [ ] Foreign key relationship between messages and conversations is enforced
- [ ] Conversations can be created for item-level (layer_slug + filename)
- [ ] Conversations can be created for layer-level (layer_slug only, filename null)
- [ ] Messages store role, content, and timestamp correctly
- [ ] Messages can store file_edits metadata for assistant messages

### Conversation Store Mixin
- [ ] create_conversation returns new conversation ID
- [ ] get_conversation returns conversation with all fields
- [ ] list_conversations_for_item returns only conversations matching layer_slug and filename
- [ ] list_conversations_for_layer returns only conversations matching layer_slug with null filename
- [ ] add_message creates message with correct conversation_id and role
- [ ] get_messages returns messages in chronological order
- [ ] delete_conversation removes conversation and all associated messages

### Conversation Runner
- [ ] Assembles prompt with system prompt, stack context, history, and user message
- [ ] Creates AgentSession with "conversation" role
- [ ] Extracts file edits from tool call results
- [ ] Commits changes to git after successful turn
- [ ] Detects foundational layer edits (philosophy, values, situational-awareness)
- [ ] Emits ConversationCascadePending event for foundational layer edits
- [ ] Does not emit cascade event for upper layer edits (strategic, tactical, policies)
- [ ] Handles agent timeout gracefully with error message storage
- [ ] Truncates old messages when conversation history exceeds context limit

### Pending Cascade Tracking
- [ ] Pending cascade record is created when foundational layer is edited
- [ ] Multiple edits to same foundational layer do not create duplicate pending cascades
- [ ] Edits to lower foundational layer update pending cascade starting_layer
- [ ] Pending cascade persists until explicitly triggered or dismissed
- [ ] Triggering pending cascade clears the pending record
- [ ] Dismissing pending cascade clears the pending record without running cascade

### Agent Configuration
- [ ] "conversation" role exists in agent config
- [ ] "conversation" role has TOOL_SET_FULL permissions
- [ ] "conversation" role uses Claude CLI backend (not Gemini)

### Event Definitions
- [ ] ConversationStarted event has conversation_id field
- [ ] ConversationTextChunk event has conversation_id and text fields
- [ ] ConversationFileEdit event has conversation_id, layer_slug, filename, action fields
- [ ] ConversationTurnComplete event has conversation_id, message_id, files_edited fields
- [ ] ConversationCascadePending event has conversation_id and starting_layer fields

### Prompt Loading
- [ ] philosophy.md generator prompt loads successfully
- [ ] philosophy.md seed prompt loads successfully
- [ ] conversation/system.md prompt loads successfully
- [ ] Updated values.md prompt loads successfully

## Integration Tests

### Conversation API Endpoints
- [ ] POST /api/conversations creates conversation and returns ID
- [ ] POST /api/conversations requires authentication
- [ ] GET /api/conversations returns conversations filtered by layer_slug and filename
- [ ] GET /api/conversations/{id} returns conversation with messages
- [ ] GET /api/conversations/{id} returns 404 for non-existent conversation
- [ ] POST /api/conversations/{id}/messages creates user message and triggers agent
- [ ] POST /api/conversations/{id}/messages streams response via WebSocket events
- [ ] DELETE /api/conversations/{id} removes conversation and messages
- [ ] DELETE /api/conversations/{id} returns 404 for non-existent conversation

### Conversation with Mocked Agent
- [ ] Full conversation turn with mocked agent response stores both user and assistant messages
- [ ] Agent file write triggers ConversationFileEdit event
- [ ] Agent file delete triggers ConversationFileEdit event
- [ ] Multiple file edits in single turn are all recorded
- [ ] Git commit is created after turn with file edits
- [ ] Git commit message references conversation context

### Cascade Integration
- [ ] Conversation edit to philosophy layer queues pending cascade
- [ ] Conversation edit to values layer queues pending cascade
- [ ] Conversation edit to situational-awareness layer queues pending cascade
- [ ] Conversation edit to strategic-objectives layer does not queue cascade
- [ ] POST /api/cascade/trigger-pending starts cascade from pending record
- [ ] Pending cascade is cleared after triggering
- [ ] Pending cascade notification persists across multiple conversation turns

### Philosophy Layer in Cascade
- [ ] Full cascade starting from philosophy generates all 6 layers
- [ ] Philosophy content appears in context when generating values
- [ ] Critics evaluate philosophy layer with all 6 ideological perspectives
- [ ] Synthesis is generated for philosophy layer

### WebSocket Event Flow
- [ ] ConversationStarted event broadcasts when turn begins
- [ ] ConversationTextChunk events stream during agent response
- [ ] ConversationFileEdit events broadcast for each file operation
- [ ] ConversationTurnComplete event broadcasts when turn finishes
- [ ] ConversationCascadePending event broadcasts for foundational edits
- [ ] Events include correct db_id for deduplication

### Values Prompt Fix Verification
- [ ] Values generator with updated prompt produces items with "X vs. Y" title format
- [ ] Generated values include arguments from opposing political perspectives
- [ ] Generated values avoid single-topic consensus items

## Browser/E2E Tests

### Conversation Sidebar UI
- [ ] Conversation toggle button appears on item detail page
- [ ] Clicking toggle opens right sidebar panel
- [ ] Clicking toggle again closes sidebar
- [ ] Sidebar displays "Start new conversation" when no conversations exist
- [ ] Creating new conversation shows empty message list
- [ ] Typing in input and pressing send creates user message bubble
- [ ] Assistant response streams into assistant message bubble
- [ ] Conversation history persists when closing and reopening sidebar
- [ ] Multiple conversations for same item appear in conversation selector
- [ ] Switching conversations loads correct message history

### Layer-Level Conversations
- [ ] Conversation toggle button appears on layer detail page
- [ ] Layer conversation sidebar functions identically to item conversation
- [ ] Layer conversation shows layer name in header (not item name)

### Philosophy Layer UI
- [ ] Philosophy layer appears in layer navigation
- [ ] Philosophy layer has distinct theme color
- [ ] Philosophy layer detail page loads successfully
- [ ] Philosophy items display in item list
- [ ] Philosophy item detail page loads successfully
- [ ] Conversation sidebar works on philosophy items

### File Edit Feedback
- [ ] When agent edits current item, content view updates automatically
- [ ] When agent edits different item, notification appears in sidebar
- [ ] File edit events show which files were modified

### Pending Cascade Notification
- [ ] Banner appears in sidebar when foundational layer is edited
- [ ] Banner shows "Cascade pending" with affected starting layer
- [ ] "Trigger Cascade" button in banner initiates cascade
- [ ] Banner disappears after cascade is triggered
- [ ] "Dismiss" option clears banner without running cascade

### Conversation Streaming
- [ ] Long responses stream incrementally (not all at once)
- [ ] Streaming text appears in real-time
- [ ] User can scroll while streaming continues
- [ ] Final message matches complete streamed content

### Error Handling
- [ ] Network error during send shows error message
- [ ] Agent error shows error state in message bubble
- [ ] Retry button appears after error
- [ ] Clicking retry resends the message

## Manual Testing

**None** - all verification must be automated.
