/**
 * Input panel — floating action button (FAB) for submitting free-text input.
 *
 * A persistent UI element visible on every authenticated page. When activated,
 * it expands to reveal a text area and submit button. Submitting sends the
 * text to POST /api/cascade/trigger, which classifies the input to a layer
 * and triggers a cascade.
 *
 * Placement: fixed position bottom-right corner (FAB pattern).
 * State is managed locally — no zustand store needed.
 *
 * All visible text uses i18n translation keys.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { apiRequest, isApiError } from "@/lib/apiClient.ts";
import { Button, IconButton } from "@/components/atoms/index.ts";
import {
  FabButton,
  PanelOverlay,
  PanelContainer,
  PanelHeader,
  PanelTitle,
  PanelBody,
  PanelTextarea,
  PanelActions,
  ResultDisplay,
  ResultLink,
} from "./InputPanel.styles.ts";

// ── Types ──────────────────────────────────────────────────────────────

interface TriggerResponse {
  classification?: {
    layer: string;
    layer_name?: string;
    explanation?: string;
  };
  cascade_id?: string;
  queued?: boolean;
  queue_position?: number;
}

// Map layer slugs to human-readable names
const LAYER_NAMES: Record<string, string> = {
  values: "Values",
  "situational-awareness": "Situational Awareness",
  "strategic-objectives": "Strategic Objectives",
  "tactical-objectives": "Tactical Objectives",
  policies: "Policies",
};

function getLayerDisplayName(layer: string, layerName?: string): string {
  return layerName || LAYER_NAMES[layer] || layer;
}

// ── SVG icons ──────────────────────────────────────────────────────────

/** Plus icon for the FAB trigger */
function PlusIcon() {
  return (
    <svg
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

/** Close icon (X) */
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

// ── Component ──────────────────────────────────────────────────────────

export function InputPanel() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Panel state
  const [isOpen, setIsOpen] = useState(false);
  const [closing, setClosing] = useState(false);
  const [inputText, setInputText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{
    type: "success" | "error";
    message: string;
    layerName?: string;
    explanation?: string;
    queued?: boolean;
    queuePosition?: number;
  } | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea when panel opens
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isOpen]);

  // ── Open / close handlers ───────────────────────────────────────────

  const handleOpen = useCallback(() => {
    setIsOpen(true);
    setClosing(false);
    setResult(null);
  }, []);

  const handleClose = useCallback(() => {
    setClosing(true);
    // Wait for fade-out animation before removing
    setTimeout(() => {
      setIsOpen(false);
      setClosing(false);
      // Don't clear result on close — it auto-dismisses
    }, 150);
  }, []);

  // Close on Escape key
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

  // ── Submit handler ──────────────────────────────────────────────────

  const handleSubmit = async () => {
    if (!inputText.trim() || submitting) return;

    setSubmitting(true);
    setResult(null);

    try {
      const response = await apiRequest<TriggerResponse>(
        "/api/cascade/trigger",
        {
          method: "POST",
          body: { input: inputText.trim() },
        },
      );

      const layerName = response.classification
        ? getLayerDisplayName(
            response.classification.layer,
            response.classification.layer_name,
          )
        : undefined;

      const explanation = response.classification?.explanation;

      // Build result message
      let message = t("input.submitSuccess");
      if (layerName) {
        message = t("input.classifiedAs", { layerName });
      }

      setResult({
        type: "success",
        message,
        layerName,
        explanation,
        queued: response.queued,
        queuePosition: response.queue_position,
      });

      // Clear input on success
      setInputText("");

      // Auto-dismiss result and close after 5 seconds
      setTimeout(() => {
        setResult(null);
        handleClose();
      }, 5000);
    } catch (err) {
      const detail = isApiError(err)
        ? err.detail
        : t("input.submitError");
      setResult({
        type: "error",
        message: detail,
      });
      // Keep input text on error so user can retry
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Ctrl+Enter to submit
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // ── Navigate to cascade viewer ──────────────────────────────────────

  const handleViewCascade = () => {
    handleClose();
    navigate("/cascade");
  };

  // ── Render ──────────────────────────────────────────────────────────

  // Show FAB when panel is closed
  if (!isOpen) {
    return (
      <FabButton
        onClick={handleOpen}
        title={t("input.triggerTooltip")}
        aria-label={t("input.triggerLabel")}
      >
        <PlusIcon />
      </FabButton>
    );
  }

  // Show expanded panel
  return (
    <>
      {/* Clicking outside the panel closes it */}
      <PanelOverlay onClick={handleClose} />

      <PanelContainer $closing={closing}>
        <PanelHeader>
          <PanelTitle>{t("input.heading")}</PanelTitle>
          <IconButton
            $variant="ghost"
            $size="sm"
            onClick={handleClose}
            aria-label={t("input.closePanel")}
          >
            <CloseIcon />
          </IconButton>
        </PanelHeader>

        <PanelBody>
          <PanelTextarea
            ref={textareaRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("input.placeholder")}
            rows={3}
            disabled={submitting}
          />

          {result && (
            <ResultDisplay $variant={result.type}>
              <span>{result.message}</span>
              {result.explanation && (
                <span>{result.explanation}</span>
              )}
              {result.queued && result.queuePosition != null && (
                <span>
                  {t("input.cascadeQueued", {
                    position: String(result.queuePosition),
                  })}
                </span>
              )}
              {result.type === "success" && (
                <ResultLink onClick={handleViewCascade}>
                  {t("input.viewCascade")}
                </ResultLink>
              )}
            </ResultDisplay>
          )}

          <PanelActions>
            <Button
              $variant="primary"
              $size="sm"
              onClick={handleSubmit}
              disabled={!inputText.trim() || submitting}
              $loading={submitting}
            >
              {submitting ? t("input.submitting") : t("input.submitButton")}
            </Button>
          </PanelActions>
        </PanelBody>
      </PanelContainer>
    </>
  );
}
