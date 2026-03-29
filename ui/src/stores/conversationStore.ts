/**
 * Conversation zustand store.
 *
 * Manages conversation state for the conversational AI sidebar.
 * Combines REST-based CRUD actions with WebSocket event handlers
 * for real-time streaming.
 *
 * Updated by two sources:
 * 1. REST (CRUD operations via apiRequest)
 * 2. WebSocket events dispatched by the central event dispatcher
 *
 * The WebSocket event handlers update the store in real-time, enabling
 * live streaming of AI responses without polling.
 */
import { create } from "zustand";
import { apiRequest } from "@/lib/apiClient.ts";
import type {
  ConversationStartedEvent,
  ConversationTextChunkEvent,
  ConversationFileEditEvent,
  ConversationTurnCompleteEvent,
  ConversationTurnErrorEvent,
  ConversationCascadePendingEvent,
} from "@/types/events.ts";

// ── Types ────────────────────────────────────────────────────────────

/** Conversation summary as returned by GET /api/conversations */
export interface ConversationSummary {
  id: string;
  layer_slug: string;
  filename: string | null;
  created_at: string;
  last_active_at: string;
}

/** Message as returned by GET /api/conversations/:id */
export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  files_edited?: string[];
}

/** Pending cascade info from ConversationCascadePending event */
export interface PendingCascade {
  starting_layer: string;
  conversation_id: string;
}

/** File edit info from ConversationFileEdit event */
export interface FileEdit {
  layer_slug: string;
  filename: string;
  action: "write" | "delete";
}

// ── API Response Types ───────────────────────────────────────────────

interface ConversationListResponse {
  conversations: ConversationSummary[];
}

interface ConversationDetailResponse {
  conversation: ConversationSummary;
  messages: ConversationMessage[];
}

interface CreateConversationResponse {
  id: string;
  layer_slug: string;
  filename: string | null;
  created_at: string;
  last_active_at: string;
}

interface SendMessageResponse {
  message_id: string;
}

// ── Helper Functions ─────────────────────────────────────────────────

/** Extract error detail from API errors */
function extractErrorDetail(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "detail" in err) {
    return String((err as { detail: string }).detail);
  }
  return fallback;
}

// ── Store definition ─────────────────────────────────────────────────

interface ConversationState {
  // ── Conversation List State ──────────────────────────────────────
  /** List of conversation summaries for the current item/layer */
  conversations: ConversationSummary[];
  /** True during list loading */
  conversationsLoading: boolean;
  /** Error from list fetch */
  conversationsError: string | null;

  // ── Active Conversation State ────────────────────────────────────
  /** Currently active conversation ID */
  activeConversationId: string | null;
  /** Active conversation detail */
  activeConversation: ConversationSummary | null;
  /** Messages for the active conversation */
  messages: ConversationMessage[];
  /** True during messages loading */
  messagesLoading: boolean;
  /** Error from messages fetch */
  messagesError: string | null;

  // ── Streaming State ──────────────────────────────────────────────
  /** True if AI is currently responding */
  isStreaming: boolean;
  /** Accumulated streamed text buffer */
  streamingText: string;
  /** ID of the message being streamed */
  streamingMessageId: string | null;

  // ── Pending Cascade State ────────────────────────────────────────
  /** Pending cascade info (shows when conversation edits triggered a cascade) */
  pendingCascade: PendingCascade | null;

  // ── Context State ────────────────────────────────────────────────
  /** Current layer slug (what layer/item we're viewing conversations for) */
  currentLayerSlug: string | null;
  /** Current filename (null for layer-level) */
  currentFilename: string | null;

  // ── File Edit Tracking ───────────────────────────────────────────
  /** File edits from the current streaming response */
  pendingFileEdits: FileEdit[];

  // ── REST Actions ─────────────────────────────────────────────────

  /** Fetch conversations for an item or layer */
  fetchConversations: (layerSlug: string, filename?: string) => Promise<void>;
  /** Fetch a single conversation with its messages */
  fetchConversation: (conversationId: string) => Promise<void>;
  /** Create a new conversation */
  createConversation: (layerSlug: string, filename?: string) => Promise<string | null>;
  /** Send a user message */
  sendMessage: (conversationId: string, content: string) => Promise<void>;
  /** Delete a conversation */
  deleteConversation: (conversationId: string) => Promise<void>;

  // ── WebSocket Event Handlers ─────────────────────────────────────

  /** Handle conversation started event */
  handleConversationStarted: (event: ConversationStartedEvent) => void;
  /** Handle text chunk event (streaming) */
  handleConversationTextChunk: (event: ConversationTextChunkEvent) => void;
  /** Handle file edit event */
  handleConversationFileEdit: (event: ConversationFileEditEvent) => void;
  /** Handle turn complete event */
  handleConversationTurnComplete: (event: ConversationTurnCompleteEvent) => void;
  /** Handle turn error event */
  handleConversationTurnError: (event: ConversationTurnErrorEvent) => void;
  /** Handle cascade pending event */
  handleConversationCascadePending: (event: ConversationCascadePendingEvent) => void;

  // ── Utility Actions ──────────────────────────────────────────────

  /** Set the active conversation (triggers fetch if not loaded) */
  setActiveConversation: (conversationId: string) => void;
  /** Clear active conversation state */
  clearActiveConversation: () => void;
  /** Clear pending cascade flag */
  clearPendingCascade: () => void;
  /** Set context (layer/item we're viewing) */
  setContext: (layerSlug: string, filename?: string) => void;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  // ── Conversation List State ────────────────────────────────────────
  conversations: [],
  conversationsLoading: false,
  conversationsError: null,

  // ── Active Conversation State ──────────────────────────────────────
  activeConversationId: null,
  activeConversation: null,
  messages: [],
  messagesLoading: false,
  messagesError: null,

  // ── Streaming State ────────────────────────────────────────────────
  isStreaming: false,
  streamingText: "",
  streamingMessageId: null,

  // ── Pending Cascade State ──────────────────────────────────────────
  pendingCascade: null,

  // ── Context State ──────────────────────────────────────────────────
  currentLayerSlug: null,
  currentFilename: null,

  // ── File Edit Tracking ─────────────────────────────────────────────
  pendingFileEdits: [],

  // ── REST Actions ───────────────────────────────────────────────────

  fetchConversations: async (layerSlug: string, filename?: string) => {
    set({ conversationsLoading: true, conversationsError: null });

    try {
      const params = new URLSearchParams();
      params.set("layer_slug", layerSlug);
      if (filename) {
        params.set("filename", filename);
      }

      const data = await apiRequest<ConversationListResponse>(
        `/api/conversations?${params.toString()}`,
      );

      set({
        conversations: data.conversations,
        conversationsLoading: false,
        conversationsError: null,
      });
    } catch (err: unknown) {
      const detail = extractErrorDetail(err, "Failed to fetch conversations");
      set({ conversationsLoading: false, conversationsError: detail });
    }
  },

  fetchConversation: async (conversationId: string) => {
    set({ messagesLoading: true, messagesError: null });

    try {
      const data = await apiRequest<ConversationDetailResponse>(
        `/api/conversations/${conversationId}`,
      );

      set({
        activeConversationId: conversationId,
        activeConversation: data.conversation,
        messages: data.messages,
        messagesLoading: false,
        messagesError: null,
      });
    } catch (err: unknown) {
      const detail = extractErrorDetail(err, "Failed to fetch conversation");
      set({ messagesLoading: false, messagesError: detail });
    }
  },

  createConversation: async (layerSlug: string, filename?: string) => {
    try {
      const body: { layer_slug: string; filename?: string } = { layer_slug: layerSlug };
      if (filename) {
        body.filename = filename;
      }

      const data = await apiRequest<CreateConversationResponse>(
        "/api/conversations",
        { method: "POST", body },
      );

      // Add the new conversation to the list
      const newConversation: ConversationSummary = {
        id: data.id,
        layer_slug: data.layer_slug,
        filename: data.filename,
        created_at: data.created_at,
        last_active_at: data.last_active_at,
      };

      set((state) => ({
        conversations: [newConversation, ...state.conversations],
        activeConversationId: data.id,
        activeConversation: newConversation,
        messages: [],
      }));

      return data.id;
    } catch {
      return null;
    }
  },

  sendMessage: async (conversationId: string, content: string) => {
    // Optimistic update: add user message immediately
    const optimisticMessage: ConversationMessage = {
      id: `__optimistic_${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };

    set((state) => ({
      messages: [...state.messages, optimisticMessage],
      isStreaming: true,
      streamingText: "",
      streamingMessageId: null,
      pendingFileEdits: [],
    }));

    try {
      const data = await apiRequest<SendMessageResponse>(
        `/api/conversations/${conversationId}/messages`,
        { method: "POST", body: { content } },
      );

      // Update the optimistic message with the real ID
      set((state) => ({
        messages: state.messages.map((msg) =>
          msg.id === optimisticMessage.id
            ? { ...msg, id: data.message_id }
            : msg,
        ),
      }));

      // AI response will come via WebSocket events
    } catch (err: unknown) {
      // Remove optimistic message on failure
      const detail = extractErrorDetail(err, "Failed to send message");
      set((state) => ({
        messages: state.messages.filter((msg) => msg.id !== optimisticMessage.id),
        isStreaming: false,
        messagesError: detail,
      }));
    }
  },

  deleteConversation: async (conversationId: string) => {
    try {
      await apiRequest<void>(
        `/api/conversations/${conversationId}`,
        { method: "DELETE" },
      );

      // Remove from conversations list
      set((state) => {
        const isActive = state.activeConversationId === conversationId;
        return {
          conversations: state.conversations.filter((c) => c.id !== conversationId),
          // Clear active state if deleted conversation was active
          ...(isActive
            ? {
                activeConversationId: null,
                activeConversation: null,
                messages: [],
                isStreaming: false,
                streamingText: "",
                streamingMessageId: null,
              }
            : {}),
        };
      });
    } catch {
      // Silently fail — could add error state if needed
    }
  },

  // ── WebSocket Event Handlers ───────────────────────────────────────

  handleConversationStarted: (event) => {
    const { activeConversationId } = get();
    if (event.conversation_id !== activeConversationId) return;

    // Confirm streaming is starting
    set({
      isStreaming: true,
      streamingText: "",
    });
  },

  handleConversationTextChunk: (event) => {
    const { activeConversationId } = get();
    // Only process if this is for the active conversation
    if (event.conversation_id !== activeConversationId) return;

    set((state) => ({
      streamingText: state.streamingText + event.text,
    }));
  },

  handleConversationFileEdit: (event) => {
    const { activeConversationId } = get();
    if (event.conversation_id !== activeConversationId) return;

    // Track file edits for display in UI
    const fileEdit: FileEdit = {
      layer_slug: event.layer_slug,
      filename: event.filename,
      action: event.action,
    };

    set((state) => ({
      pendingFileEdits: [...state.pendingFileEdits, fileEdit],
    }));
  },

  handleConversationTurnComplete: (event) => {
    const { activeConversationId, streamingText } = get();
    if (event.conversation_id !== activeConversationId) return;

    // Create the final assistant message from the streaming buffer
    const assistantMessage: ConversationMessage = {
      id: event.message_id,
      role: "assistant",
      content: streamingText,
      created_at: new Date().toISOString(),
      files_edited: event.files_edited.length > 0 ? event.files_edited : undefined,
    };

    set((state) => ({
      messages: [...state.messages, assistantMessage],
      isStreaming: false,
      streamingText: "",
      streamingMessageId: null,
      pendingFileEdits: [],
    }));
  },

  handleConversationTurnError: (event) => {
    const { activeConversationId, streamingText } = get();
    if (event.conversation_id !== activeConversationId) return;

    // If there's partial streaming text, we could show it with an error indicator
    // For now, create an error message
    if (streamingText) {
      const errorMessage: ConversationMessage = {
        id: `error_${Date.now()}`,
        role: "assistant",
        content: `${streamingText}\n\n[Error: ${event.error_message}]`,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        messages: [...state.messages, errorMessage],
        isStreaming: false,
        streamingText: "",
        streamingMessageId: null,
        pendingFileEdits: [],
        messagesError: event.error_message,
      }));
    } else {
      set({
        isStreaming: false,
        streamingText: "",
        streamingMessageId: null,
        pendingFileEdits: [],
        messagesError: event.error_message,
      });
    }
  },

  handleConversationCascadePending: (event) => {
    // Set pending cascade regardless of active conversation
    // This allows showing the notification even if user navigates away
    set({
      pendingCascade: {
        starting_layer: event.starting_layer,
        conversation_id: event.conversation_id,
      },
    });
  },

  // ── Utility Actions ────────────────────────────────────────────────

  setActiveConversation: (conversationId: string) => {
    const { activeConversationId } = get();

    // Already active — no action needed
    if (activeConversationId === conversationId) return;

    set({
      activeConversationId: conversationId,
      activeConversation: null,
      messages: [],
      messagesError: null,
      isStreaming: false,
      streamingText: "",
      streamingMessageId: null,
      pendingFileEdits: [],
    });

    // Fetch the conversation details
    get().fetchConversation(conversationId);
  },

  clearActiveConversation: () => {
    set({
      activeConversationId: null,
      activeConversation: null,
      messages: [],
      messagesLoading: false,
      messagesError: null,
      isStreaming: false,
      streamingText: "",
      streamingMessageId: null,
      pendingFileEdits: [],
    });
  },

  clearPendingCascade: () => {
    set({ pendingCascade: null });
  },

  setContext: (layerSlug: string, filename?: string) => {
    const { currentLayerSlug, currentFilename } = get();

    // If context hasn't changed, no action needed
    if (
      currentLayerSlug === layerSlug &&
      currentFilename === (filename ?? null)
    ) {
      return;
    }

    // Clear existing state and set new context
    set({
      currentLayerSlug: layerSlug,
      currentFilename: filename ?? null,
      conversations: [],
      conversationsLoading: false,
      conversationsError: null,
      activeConversationId: null,
      activeConversation: null,
      messages: [],
      messagesLoading: false,
      messagesError: null,
      isStreaming: false,
      streamingText: "",
      streamingMessageId: null,
      pendingFileEdits: [],
    });
  },
}));
