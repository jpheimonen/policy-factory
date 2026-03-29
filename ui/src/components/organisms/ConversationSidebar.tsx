/**
 * Conversation sidebar — right-aligned sliding panel for conversational AI.
 *
 * Features:
 * - Slides in/out from the right side of the viewport
 * - Conversation selector for switching between threads
 * - Message list with visual distinction between user and assistant
 * - Real-time streaming display with auto-scroll
 * - Input textarea with keyboard shortcut support (Ctrl/Cmd+Enter)
 * - Pending cascade banner when file edits trigger downstream cascades
 * - Loading and error states
 *
 * All visible text uses i18n translation keys.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { useTranslation } from "@/i18n/index.ts";
import { useConversationStore } from "@/stores/conversationStore.ts";
import { useAutoScroll } from "@/hooks/useAutoScroll.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import { Button, IconButton } from "@/components/atoms/index.ts";
import {
  SidebarOverlay,
  SidebarContainer,
  SidebarHeader,
  SidebarTitle,
  SelectorContainer,
  SelectorDropdown,
  NewConversationButton,
  MessageListContainer,
  MessageWrapper,
  MessageBubble,
  MessageMeta,
  MessageContent,
  FilesEditedBadge,
  StreamingBubble,
  StreamingCursor,
  TypingIndicator,
  TypingDot,
  InputContainer,
  InputWrapper,
  InputTextarea,
  InputActions,
  InputHint,
  CascadeBanner,
  CascadeBannerTitle,
  CascadeBannerText,
  CascadeBannerActions,
  LoadingContainer,
  LoadingSpinner,
  LoadingText,
  ErrorContainer,
  ErrorText,
  EmptyState,
  EmptyStateText,
  EmptyStateHint,
} from "./ConversationSidebar.styles.ts";

// ── Types ──────────────────────────────────────────────────────────────

export interface ConversationSidebarProps {
  /** Whether the sidebar is visible */
  isOpen: boolean;
  /** Callback when the sidebar should close */
  onClose: () => void;
  /** Layer context for the conversation */
  layerSlug: string;
  /** Optional item filename (null for layer-level conversations) */
  filename?: string | null;
}

// ── SVG Icons ──────────────────────────────────────────────────────────

function CloseIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

// ── Helper Functions ───────────────────────────────────────────────────

/** Format a timestamp for display */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

/** Format conversation for selector dropdown */
function formatConversationLabel(
  createdAt: string,
  index: number,
  total: number,
): string {
  const date = new Date(createdAt);
  const dateStr = date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `Conversation ${total - index} — ${dateStr}`;
}

// ── Layer Name Mapping ─────────────────────────────────────────────────

const LAYER_NAMES: Record<string, string> = {
  philosophy: "Philosophy",
  values: "Values",
  "situational-awareness": "Situational Awareness",
  "strategic-objectives": "Strategic Objectives",
  "tactical-objectives": "Tactical Objectives",
  policies: "Policies",
};

// ── Component ──────────────────────────────────────────────────────────

export function ConversationSidebar({
  isOpen,
  onClose,
  layerSlug,
  filename,
}: ConversationSidebarProps) {
  const { t } = useTranslation();

  // ── Local state ────────────────────────────────────────────────────
  const [closing, setClosing] = useState(false);
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);
  const [triggeringCascade, setTriggeringCascade] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Store state ────────────────────────────────────────────────────
  const {
    conversations,
    conversationsLoading,
    conversationsError,
    activeConversationId,
    messages,
    messagesLoading,
    messagesError,
    isStreaming,
    streamingText,
    pendingCascade,
    fetchConversations,
    fetchConversation,
    createConversation,
    sendMessage,
    setActiveConversation,
    clearPendingCascade,
    setContext,
  } = useConversationStore();

  // ── Auto-scroll for message list ───────────────────────────────────
  // Track total content length (messages + streaming) for auto-scroll
  const scrollDependency =
    messages.length + streamingText.length + (isStreaming ? 1 : 0);
  const { ref: messageListRef } = useAutoScroll<HTMLDivElement>(scrollDependency);

  // ── Effects ────────────────────────────────────────────────────────

  // Set context and fetch conversations when sidebar opens
  useEffect(() => {
    if (isOpen) {
      setContext(layerSlug, filename ?? undefined);
      fetchConversations(layerSlug, filename ?? undefined);
    }
  }, [isOpen, layerSlug, filename, setContext, fetchConversations]);

  // Focus input when sidebar opens or streaming ends
  useEffect(() => {
    if (isOpen && !isStreaming && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen, isStreaming]);

  // ── Handlers ───────────────────────────────────────────────────────

  const handleClose = useCallback(() => {
    setClosing(true);
    // Wait for slide-out animation before calling onClose
    setTimeout(() => {
      setClosing(false);
      onClose();
    }, 200);
  }, [onClose]);

  // Handle Escape key to close
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleClose]);

  const handleConversationChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const conversationId = e.target.value;
      if (conversationId) {
        setActiveConversation(conversationId);
      }
    },
    [setActiveConversation],
  );

  const handleNewConversation = useCallback(async () => {
    const conversationId = await createConversation(
      layerSlug,
      filename ?? undefined,
    );
    if (conversationId) {
      // Conversation is automatically set as active by createConversation
      inputRef.current?.focus();
    }
  }, [createConversation, layerSlug, filename]);

  const handleSendMessage = useCallback(async () => {
    if (!inputText.trim() || isStreaming || !activeConversationId) return;

    setSending(true);
    try {
      await sendMessage(activeConversationId, inputText.trim());
      setInputText("");
    } finally {
      setSending(false);
    }
  }, [inputText, isStreaming, activeConversationId, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Ctrl+Enter or Cmd+Enter to send
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSendMessage();
      }
    },
    [handleSendMessage],
  );

  const handleTriggerCascade = useCallback(async () => {
    if (!pendingCascade) return;

    setTriggeringCascade(true);
    try {
      await apiRequest("/api/cascade/trigger-pending", { method: "POST" });
      clearPendingCascade();
    } catch {
      // Error handling — could show a toast or error state
    } finally {
      setTriggeringCascade(false);
    }
  }, [pendingCascade, clearPendingCascade]);

  const handleDismissCascade = useCallback(() => {
    clearPendingCascade();
  }, [clearPendingCascade]);

  // ── Don't render if not open ───────────────────────────────────────
  if (!isOpen && !closing) {
    return null;
  }

  // ── Render helpers ─────────────────────────────────────────────────

  const renderConversationSelector = () => {
    if (conversationsLoading) {
      return (
        <SelectorContainer>
          <LoadingText>{t("common.loading")}</LoadingText>
        </SelectorContainer>
      );
    }

    if (conversationsError) {
      return (
        <SelectorContainer>
          <ErrorText>{conversationsError}</ErrorText>
        </SelectorContainer>
      );
    }

    return (
      <SelectorContainer>
        {conversations.length > 0 ? (
          <SelectorDropdown
            value={activeConversationId || ""}
            onChange={handleConversationChange}
          >
            <option value="" disabled>
              {t("conversations.selectConversation")}
            </option>
            {conversations.map((conv, index) => (
              <option key={conv.id} value={conv.id}>
                {formatConversationLabel(
                  conv.created_at,
                  index,
                  conversations.length,
                )}
              </option>
            ))}
          </SelectorDropdown>
        ) : null}
        <NewConversationButton onClick={handleNewConversation}>
          <PlusIcon />
          {t("conversations.newConversation")}
        </NewConversationButton>
      </SelectorContainer>
    );
  };

  const renderMessageList = () => {
    // Loading state
    if (messagesLoading && messages.length === 0) {
      return (
        <LoadingContainer>
          <LoadingSpinner />
          <LoadingText>{t("conversations.loadingMessages")}</LoadingText>
        </LoadingContainer>
      );
    }

    // Error state
    if (messagesError && messages.length === 0) {
      return (
        <ErrorContainer>
          <ErrorText>{messagesError}</ErrorText>
          <Button
            $variant="secondary"
            $size="sm"
            onClick={() =>
              activeConversationId && fetchConversation(activeConversationId)
            }
          >
            {t("common.refresh")}
          </Button>
        </ErrorContainer>
      );
    }

    // No active conversation
    if (!activeConversationId) {
      return (
        <EmptyState>
          <EmptyStateText>{t("conversations.noConversation")}</EmptyStateText>
          <EmptyStateHint>{t("conversations.startHint")}</EmptyStateHint>
        </EmptyState>
      );
    }

    // No messages yet
    if (messages.length === 0 && !isStreaming) {
      return (
        <EmptyState>
          <EmptyStateText>{t("conversations.noMessages")}</EmptyStateText>
          <EmptyStateHint>{t("conversations.sendFirstMessage")}</EmptyStateHint>
        </EmptyState>
      );
    }

    return (
      <MessageListContainer ref={messageListRef}>
        {messages.map((message) => (
          <MessageWrapper key={message.id} $role={message.role}>
            <MessageBubble $role={message.role}>
              <MessageContent>
                {message.content.split("\n").map((line, i) => (
                  <p key={i}>{line || "\u00A0"}</p>
                ))}
              </MessageContent>
            </MessageBubble>
            <MessageMeta $role={message.role}>
              <span>{formatTimestamp(message.created_at)}</span>
              {message.files_edited && message.files_edited.length > 0 && (
                <FilesEditedBadge>
                  <EditIcon />
                  {message.files_edited.length}{" "}
                  {message.files_edited.length === 1 ? "file" : "files"} edited
                </FilesEditedBadge>
              )}
            </MessageMeta>
          </MessageWrapper>
        ))}

        {/* Streaming response */}
        {isStreaming && (
          <MessageWrapper $role="assistant">
            <StreamingBubble $role="assistant">
              {streamingText ? (
                <MessageContent>
                  {streamingText.split("\n").map((line, i) => (
                    <p key={i}>{line || "\u00A0"}</p>
                  ))}
                  <StreamingCursor />
                </MessageContent>
              ) : (
                <TypingIndicator>
                  <TypingDot $delay={0} />
                  <TypingDot $delay={150} />
                  <TypingDot $delay={300} />
                </TypingIndicator>
              )}
            </StreamingBubble>
          </MessageWrapper>
        )}
      </MessageListContainer>
    );
  };

  const renderPendingCascadeBanner = () => {
    if (!pendingCascade) return null;

    const layerName =
      LAYER_NAMES[pendingCascade.starting_layer] ||
      pendingCascade.starting_layer;

    return (
      <CascadeBanner>
        <CascadeBannerTitle>
          <AlertIcon />
          {t("conversations.cascadePending")}
        </CascadeBannerTitle>
        <CascadeBannerText>
          {t("conversations.cascadePendingDescription", { layer: layerName })}
        </CascadeBannerText>
        <CascadeBannerActions>
          <Button
            $variant="primary"
            $size="sm"
            onClick={handleTriggerCascade}
            disabled={triggeringCascade}
            $loading={triggeringCascade}
          >
            {t("conversations.triggerCascade")}
          </Button>
          <Button
            $variant="ghost"
            $size="sm"
            onClick={handleDismissCascade}
            disabled={triggeringCascade}
          >
            {t("conversations.dismissCascade")}
          </Button>
        </CascadeBannerActions>
      </CascadeBanner>
    );
  };

  const renderInput = () => {
    const canSend =
      inputText.trim().length > 0 && !isStreaming && activeConversationId;

    return (
      <InputContainer>
        <InputWrapper>
          <InputTextarea
            ref={inputRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("conversations.inputPlaceholder")}
            disabled={isStreaming || !activeConversationId}
            rows={3}
          />
          <InputActions>
            <InputHint>{t("conversations.sendHint")}</InputHint>
            <Button
              $variant="primary"
              $size="sm"
              onClick={handleSendMessage}
              disabled={!canSend}
              $loading={sending}
            >
              <SendIcon />
              {t("conversations.send")}
            </Button>
          </InputActions>
        </InputWrapper>
      </InputContainer>
    );
  };

  // ── Main render ────────────────────────────────────────────────────

  return (
    <>
      <SidebarOverlay $closing={closing} onClick={handleClose} />
      <SidebarContainer $closing={closing}>
        <SidebarHeader>
          <SidebarTitle>{t("conversations.title")}</SidebarTitle>
          <IconButton
            $variant="ghost"
            $size="sm"
            onClick={handleClose}
            aria-label={t("common.close")}
          >
            <CloseIcon />
          </IconButton>
        </SidebarHeader>

        {renderConversationSelector()}
        {renderMessageList()}
        {renderPendingCascadeBanner()}
        {renderInput()}
      </SidebarContainer>
    </>
  );
}
