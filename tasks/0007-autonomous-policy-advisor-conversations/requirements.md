# Requirements

## Problem Statement

The policy factory currently operates as a generation tool — the AI produces content, but users have no way to engage in substantive dialogue with it about individual items or layers. Users cannot challenge, debate, or refine policy content through conversation. Additionally, the system lacks an explicit foundation for *how* it reasons about tradeoffs (political philosophy), and the values layer outputs suffer from "technocratic consensus" bias — producing safe single-topic areas rather than the controversial tension-pairs the system is designed to surface.

This task transforms the policy factory into an **autonomous policy advisor** — an AI co-author with its own intellectual backbone that can hold its ground, push back on human input, and make edits autonomously through conversation.

## Success Criteria

### Conversational AI Interface
- [ ] Users can open a conversation sidebar on any item detail page
- [ ] Users can open a conversation sidebar on any layer overview page
- [ ] The AI has access to the full policy stack (all layers, all items) as context during conversations
- [ ] The AI can read, write, and delete files across any layer during a conversation without human approval
- [ ] All file changes are automatically committed to git after each conversation turn
- [ ] Users can easily revert conversation-driven changes via git history
- [ ] Conversation history is persisted per-item and per-layer in the database
- [ ] Users can return to an item/layer and continue previous conversations
- [ ] AI responses stream to the UI in real-time via WebSocket
- [ ] The item/layer content view updates live when the AI makes edits
- [ ] When conversation edits affect foundational layers (philosophy, values, situational-awareness), a cascade is queued with a notification — the user triggers it when ready
- [ ] Edits to upper layers (strategic, tactical, policies) do not trigger cascades

### AI Behavior — Autonomous Advisor
- [ ] The AI holds firm when it has strong logical or evidence basis — it can "win" arguments
- [ ] The AI pushes back grounded in: internal consistency, logical implications, cross-layer alignment, external knowledge, societal values, and the philosophy layer
- [ ] The AI follows tiered epistemic authority:
  - At the philosophy layer: challenges internal consistency only, not substantive content
  - At the values layer: uses philosophy layer as ground truth for pushback
  - At situational awareness: uses verifiable facts plus philosophy's epistemological commitments
  - At strategic through policies: uses all layers below plus logical derivation
- [ ] The AI's conversation personality is encoded in a carefully designed system prompt

### Political Philosophy Layer
- [ ] A new "philosophy" layer exists at position 1 (bottommost layer in the stack, below values)
- [ ] All existing layers shift up by one position in the cascade hierarchy
- [ ] The philosophy layer contains comprehensive philosophical foundations: epistemological commitments, normative axioms, and tradition/school identification
- [ ] The philosophy layer has a generator prompt for cascade regeneration
- [ ] The philosophy layer can be bootstrapped via a seed prompt that produces a balanced, multi-perspective foundation
- [ ] Users can refine the philosophy layer through the conversation feature
- [ ] The 6 ideological critics evaluate the philosophy layer like any other layer
- [ ] The philosophy layer feeds upward into values and all subsequent layers during cascade runs
- [ ] The UI displays the philosophy layer with appropriate styling (color, i18n, routing)

### Values Layer Prompt Fix
- [ ] The values generator prompt is updated to enforce genuine tension-pair format
- [ ] Tension-pair titles follow explicit "X vs. Y" format
- [ ] The prompt includes concrete examples of good vs. bad tension-pairs
- [ ] The prompt requires strongest arguments from opposing political factions for each tension
- [ ] The prompt reinforces diverse incentives and interests rather than technocratic consensus
- [ ] The prompt references the philosophy layer as grounding for what genuine tensions look like

## Constraints

- **LLM Backend:** Conversations must use Claude CLI (via claude-agent-sdk) for tool-using capability. This is the established pattern in the codebase.
- **Context Size:** Full policy stack as context means potentially large token counts per turn. This is acceptable given Claude CLI plan usage.
- **Existing Infrastructure:** Must integrate with the existing WebSocket event system, EventEmitter pattern, and Zustand stores. Must follow established agent patterns (AgentSession, sandboxed file tools).
- **Git Integration:** All edits must result in git commits. The data directory is already git-tracked.
- **Database:** Conversation persistence uses SQLite via the existing store pattern.

## Non-Goals

- **Multi-user support:** This is a single-user system. No consideration for concurrent conversations or user isolation.
- **Approval workflows:** Edits are auto-applied. No diff review, no staging, no approval gates. Git revert is the undo mechanism.
- **Prompt fixes for layers other than values:** Only the values layer prompt is being updated in this task.
- **Changes to the critic system:** The 6 ideological critics remain unchanged. They simply evaluate the new philosophy layer like any other.
- **Conversation branching or forking:** Conversations are linear. No tree-structured dialogue or alternative conversation paths.
- **Mobile-responsive conversation UI:** The sidebar is designed for desktop use.
