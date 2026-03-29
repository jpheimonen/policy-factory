/**
 * Item Detail page.
 *
 * Route: /layers/:slug/:item
 *
 * Displays the full detail view for a single layer item:
 * - View mode: frontmatter fields, rendered markdown body, cross-layer references,
 *   attribution, and header with layer identity color accent.
 * - Edit mode: inline editing of frontmatter fields and markdown body with
 *   dirty detection, unsaved-changes warning, and save/cancel workflow.
 * - Delete: confirmation modal, API call, and redirect to layer detail.
 * - Conversation sidebar: integrated AI chat with file edit detection.
 *
 * Pattern follows LayerDetailPage.tsx and cc-runner's DocsPanel inline-edit pattern.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { isValidLayerSlug } from "@/stores/layerStore.ts";
import { useConversationStore } from "@/stores/conversationStore.ts";
import { LAYER_NAME_KEYS } from "@/lib/layerConstants.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Badge, Button, Input, Select, Markdown } from "@/components/atoms/index.ts";
import { LoadingState, ErrorState } from "@/components/molecules/index.ts";
import { FormField } from "@/components/molecules/FormField.tsx";
import { ConfirmModal } from "@/components/molecules/ConfirmModal.tsx";
import { ConversationSidebar } from "@/components/organisms/ConversationSidebar.tsx";
import { useBeforeUnload } from "@/hooks/useBeforeUnload.ts";
import {
  PageContainer,
  PageWrapper,
  PageHeader,
  HeaderLeft,
  HeaderRight,
  BackLink,
  LayerSubtitle,
  ItemTitleHeading,
  SaveIndicator,
  Section,
  SectionTitle,
  FieldGrid,
  FieldItem,
  FieldLabel,
  FieldValue,
  BodyWrapper,
  EmptyBody,
  ReferenceGroup,
  ReferenceGroupTitle,
  ReferenceLink,
  ReferenceLayerTag,
  AttributionBar,
  AttributionItem,
  EditBody,
  ErrorBanner,
  ReadOnlyValue,
  ConversationToggle,
  ConflictBanner,
  ConflictBannerIcon,
  ConflictBannerContent,
  ConflictBannerTitle,
  ConflictBannerText,
  ConflictBannerActions,
} from "./ItemDetailPage.styles.ts";

// ── Types ─────────────────────────────────────────────────────────────

interface ItemData {
  frontmatter: Record<string, unknown>;
  body: string;
}

interface Reference {
  layer_slug: string;
  filename: string;
  title: string;
}

interface ReferencesData {
  forward: Reference[];
  backward: Reference[];
}

// ── Constants ─────────────────────────────────────────────────────────

/** Known frontmatter fields that get special treatment */
const KNOWN_FIELDS = [
  "title",
  "status",
  "created_at",
  "last_modified",
  "last_modified_by",
  "references",
];

/** Read-only fields that cannot be edited */
const READ_ONLY_FIELDS = ["created_at", "last_modified", "last_modified_by"];

/** Status options for the select dropdown */
const STATUS_OPTIONS = ["active", "draft", "archived", "deprecated"];

/** Status-to-badge-variant mapping */
const STATUS_BADGE_MAP: Record<string, "success" | "neutral" | "info" | "warning" | "error"> = {
  active: "success",
  draft: "neutral",
  archived: "neutral",
  deprecated: "warning",
};

// ── Icons ─────────────────────────────────────────────────────────────

function MessageSquareIcon() {
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
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function AlertTriangleIcon() {
  return (
    <svg
      width="18"
      height="18"
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

// ── Helpers ───────────────────────────────────────────────────────────

function formatDate(isoTimestamp: string): string {
  if (!isoTimestamp) return "";
  try {
    return new Date(isoTimestamp).toLocaleString();
  } catch {
    return isoTimestamp;
  }
}

function filenameToSlug(filename: string): string {
  return filename.replace(/\.md$/, "");
}

function slugToFilename(slug: string): string {
  return slug.endsWith(".md") ? slug : `${slug}.md`;
}

/** Get a human-readable label for a frontmatter field key */
function fieldKeyToLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Page component ────────────────────────────────────────────────────

export function ItemDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { slug, item: itemSlug } = useParams<{ slug: string; item: string }>();

  // ── Data state ──────────────────────────────────────────────────
  const [itemData, setItemData] = useState<ItemData | null>(null);
  const [references, setReferences] = useState<ReferencesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Edit mode state ─────────────────────────────────────────────
  const [isEditMode, setIsEditMode] = useState(false);
  const [editedFrontmatter, setEditedFrontmatter] = useState<Record<string, unknown>>({});
  const [editedBody, setEditedBody] = useState("");
  const [originalFrontmatter, setOriginalFrontmatter] = useState<Record<string, unknown>>({});
  const [originalBody, setOriginalBody] = useState("");

  // ── Save state ──────────────────────────────────────────────────
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const saveSuccessTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Delete state ────────────────────────────────────────────────
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // ── Discard changes state ───────────────────────────────────────
  const [showDiscardModal, setShowDiscardModal] = useState(false);

  // ── Conversation sidebar state ─────────────────────────────────
  const [isConversationOpen, setIsConversationOpen] = useState(false);

  // ── AI conflict detection state ────────────────────────────────
  const [aiConflictDetected, setAiConflictDetected] = useState(false);

  // ── Store subscriptions ────────────────────────────────────────
  const pendingFileEdits = useConversationStore((s) => s.pendingFileEdits);
  const isStreaming = useConversationStore((s) => s.isStreaming);

  // ── Derived values ──────────────────────────────────────────────
  const filename = itemSlug ? slugToFilename(itemSlug) : "";
  const layerDisplayName = slug ? t(LAYER_NAME_KEYS[slug] ?? slug) : "";

  // ── Dirty detection ─────────────────────────────────────────────
  const isDirty = (() => {
    if (!isEditMode) return false;
    if (editedBody !== originalBody) return true;
    const editedKeys = Object.keys(editedFrontmatter);
    const originalKeys = Object.keys(originalFrontmatter);
    if (editedKeys.length !== originalKeys.length) return true;
    return editedKeys.some(
      (key) => String(editedFrontmatter[key] ?? "") !== String(originalFrontmatter[key] ?? ""),
    );
  })();

  // ── Unsaved changes warning ─────────────────────────────────────
  useBeforeUnload(isDirty);

  // ── Data fetching ───────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    if (!slug || !itemSlug) return;

    setLoading(true);
    setError(null);

    try {
      const [itemResult, refsResult] = await Promise.allSettled([
        apiRequest<ItemData>(`/api/layers/${slug}/items/${filename}`),
        apiRequest<ReferencesData>(`/api/layers/${slug}/items/${filename}/references`),
      ]);

      if (itemResult.status === "rejected") {
        throw itemResult.reason;
      }

      setItemData(itemResult.value);

      if (refsResult.status === "fulfilled") {
        setReferences(refsResult.value);
      } else {
        // References endpoint might fail — non-fatal
        setReferences({ forward: [], backward: [] });
      }
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : t("items.loadError");
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [slug, itemSlug, filename, t]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Cleanup save success timer ──────────────────────────────────

  useEffect(() => {
    return () => {
      if (saveSuccessTimer.current) {
        clearTimeout(saveSuccessTimer.current);
      }
    };
  }, []);

  // ── AI edit detection ─────────────────────────────────────────────
  // Subscribe to file edit events from the conversation store.
  // When AI edits the current item:
  // - If user has unsaved changes: show conflict banner
  // - Otherwise: auto-refresh the item data

  // Track the previous streaming state and file edits to detect completion
  const prevStreamingRef = useRef(isStreaming);
  const prevFileEditsRef = useRef(pendingFileEdits);

  useEffect(() => {
    // Check if streaming just ended (AI turn complete)
    const streamingJustEnded = prevStreamingRef.current && !isStreaming;
    prevStreamingRef.current = isStreaming;

    // Check if we had file edits during this turn that affected current item
    const hadRelevantEdits = prevFileEditsRef.current.some(
      (edit) => edit.layer_slug === slug && edit.filename === filename
    );
    prevFileEditsRef.current = pendingFileEdits;

    // Only act when streaming ends and we had relevant edits
    if (streamingJustEnded && hadRelevantEdits) {
      if (isDirty) {
        // User has unsaved changes - show conflict banner
        setAiConflictDetected(true);
      } else {
        // No unsaved changes - auto-refresh
        fetchData();
      }
    }
  }, [isStreaming, pendingFileEdits, slug, filename, isDirty, fetchData]);

  // Also listen for real-time file edits during streaming
  useEffect(() => {
    // Check if the current item is being edited by AI right now
    const currentItemBeingEdited = pendingFileEdits.some(
      (edit) => edit.layer_slug === slug && edit.filename === filename
    );

    if (currentItemBeingEdited && isDirty && !aiConflictDetected) {
      // Show conflict banner immediately when we detect AI editing our file
      setAiConflictDetected(true);
    }
  }, [pendingFileEdits, slug, filename, isDirty, aiConflictDetected]);

  // ── Handlers ────────────────────────────────────────────────────

  const handleBack = useCallback(() => {
    if (slug) {
      navigate(`/layers/${slug}`);
    } else {
      navigate("/");
    }
  }, [navigate, slug]);

  const handleEnterEditMode = useCallback(() => {
    if (!itemData) return;
    const fm = { ...itemData.frontmatter };
    setEditedFrontmatter(fm);
    setOriginalFrontmatter(fm);
    setEditedBody(itemData.body);
    setOriginalBody(itemData.body);
    setSaveError(null);
    setSaveSuccess(false);
    setIsEditMode(true);
  }, [itemData]);

  const handleCancelEdit = useCallback(() => {
    if (isDirty) {
      setShowDiscardModal(true);
    } else {
      setIsEditMode(false);
    }
  }, [isDirty]);

  const handleConfirmDiscard = useCallback(() => {
    setShowDiscardModal(false);
    setIsEditMode(false);
    setSaveError(null);
  }, []);

  const handleSave = useCallback(async () => {
    if (!slug || !filename) return;

    setSaving(true);
    setSaveError(null);

    try {
      // Build frontmatter for the save — exclude read-only fields
      const frontmatterToSave = { ...editedFrontmatter };
      for (const key of READ_ONLY_FIELDS) {
        delete frontmatterToSave[key];
      }

      const result = await apiRequest<ItemData>(`/api/layers/${slug}/items/${filename}`, {
        method: "PUT",
        body: {
          frontmatter: frontmatterToSave,
          body: editedBody,
        },
      });

      // Update item data with server response
      setItemData(result);
      setIsEditMode(false);
      setSaveSuccess(true);

      // Clear success indicator after 2 seconds
      if (saveSuccessTimer.current) {
        clearTimeout(saveSuccessTimer.current);
      }
      saveSuccessTimer.current = setTimeout(() => {
        setSaveSuccess(false);
      }, 2000);
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : t("items.saveError");
      setSaveError(detail);
    } finally {
      setSaving(false);
    }
  }, [slug, filename, editedFrontmatter, editedBody, t]);

  const handleDelete = useCallback(async () => {
    if (!slug || !filename) return;

    setDeleting(true);
    setDeleteError(null);

    try {
      await apiRequest(`/api/layers/${slug}/items/${filename}`, {
        method: "DELETE",
      });

      // Navigate back to layer detail
      navigate(`/layers/${slug}`);
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "detail" in err
          ? String((err as { detail: string }).detail)
          : t("items.deleteError");
      setDeleteError(detail);
      setShowDeleteModal(false);
    } finally {
      setDeleting(false);
    }
  }, [slug, filename, navigate, t]);

  const handleReferenceClick = useCallback(
    (ref: Reference) => {
      navigate(`/layers/${ref.layer_slug}/${filenameToSlug(ref.filename)}`);
    },
    [navigate],
  );

  const handleFrontmatterChange = useCallback((key: string, value: unknown) => {
    setEditedFrontmatter((prev) => ({ ...prev, [key]: value }));
  }, []);

  // ── Conversation handlers ───────────────────────────────────────

  const handleToggleConversation = useCallback(() => {
    setIsConversationOpen((prev) => !prev);
  }, []);

  const handleCloseConversation = useCallback(() => {
    setIsConversationOpen(false);
  }, []);

  // ── AI conflict handlers ────────────────────────────────────────

  const handleConflictRefresh = useCallback(() => {
    // Discard user changes and refresh from server
    setIsEditMode(false);
    setAiConflictDetected(false);
    fetchData();
  }, [fetchData]);

  const handleConflictKeepEditing = useCallback(() => {
    // Dismiss the banner and keep user's changes
    setAiConflictDetected(false);
  }, []);

  // ── Invalid slug / item ─────────────────────────────────────────

  if (!slug || !isValidLayerSlug(slug) || !itemSlug) {
    return (
      <PageContainer $sidebarOpen={false}>
        <PageWrapper>
          <ErrorState
            message={t("layers.invalidLayer", { slug: slug ?? "" })}
            onRetry={handleBack}
          />
        </PageWrapper>
      </PageContainer>
    );
  }

  // ── Loading state ───────────────────────────────────────────────

  if (loading) {
    return (
      <PageContainer $sidebarOpen={false}>
        <PageWrapper>
          <LoadingState />
        </PageWrapper>
      </PageContainer>
    );
  }

  // ── Error state ─────────────────────────────────────────────────

  if (error || !itemData) {
    return (
      <PageContainer $sidebarOpen={false}>
        <PageWrapper>
          <PageHeader $layerSlug={slug}>
            <HeaderLeft>
              <BackLink onClick={handleBack}>
                &larr; {t("items.backToLayer", { layer: layerDisplayName })}
              </BackLink>
            </HeaderLeft>
          </PageHeader>
          <ErrorState message={error ?? t("items.loadError")} onRetry={fetchData} />
        </PageWrapper>
      </PageContainer>
    );
  }

  // ── Computed values ─────────────────────────────────────────────

  const fm = isEditMode ? editedFrontmatter : itemData.frontmatter;
  const body = isEditMode ? editedBody : itemData.body;
  const itemTitle = String(fm.title ?? itemSlug);
  const itemStatus = String(fm.status ?? "");
  const createdAt = String(fm.created_at ?? "");
  const lastModified = String(fm.last_modified ?? "");
  const lastModifiedBy = String(fm.last_modified_by ?? "");

  // Collect unknown/extra frontmatter fields
  const extraFields = Object.keys(fm).filter(
    (key) => !KNOWN_FIELDS.includes(key),
  );

  const hasForwardRefs = references && references.forward.length > 0;
  const hasBackwardRefs = references && references.backward.length > 0;
  const hasAnyRefs = hasForwardRefs || hasBackwardRefs;

  // ── Render ──────────────────────────────────────────────────────

  return (
    <PageContainer $sidebarOpen={isConversationOpen}>
      <PageWrapper $sidebarOpen={isConversationOpen}>
        {/* ── Page header ──────────────────────────────────────────── */}
        <PageHeader $layerSlug={slug}>
          <HeaderLeft>
            <BackLink onClick={handleBack}>
              &larr; {t("items.backToLayer", { layer: layerDisplayName })}
            </BackLink>
            <LayerSubtitle $layerSlug={slug}>{layerDisplayName}</LayerSubtitle>
            <ItemTitleHeading>{itemTitle}</ItemTitleHeading>
          </HeaderLeft>
          <HeaderRight>
            {saveSuccess && <SaveIndicator>{t("items.saved")}</SaveIndicator>}
            {isEditMode ? (
              <>
                <Button
                  $variant="secondary"
                  $size="sm"
                  onClick={handleCancelEdit}
                  disabled={saving}
                >
                  {t("items.cancelEdit")}
                </Button>
                <Button
                  $variant="primary"
                  $size="sm"
                  $loading={saving}
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? t("items.saving") : t("items.saveButton")}
                </Button>
              </>
            ) : (
              <>
                <Button
                  $variant="primary"
                  $size="sm"
                  onClick={handleEnterEditMode}
                >
                  {t("items.editButton")}
                </Button>
                <Button
                  $variant="ghost"
                  $size="sm"
                  onClick={() => setShowDeleteModal(true)}
                >
                  {t("items.deleteButton")}
                </Button>
              </>
            )}
            <ConversationToggle
              $active={isConversationOpen}
              onClick={handleToggleConversation}
              aria-label={t("items.conversationToggle")}
              title={t("items.conversationToggle")}
            >
              <MessageSquareIcon />
              {t("items.conversationToggle")}
            </ConversationToggle>
          </HeaderRight>
        </PageHeader>

        {/* ── AI conflict banner ─────────────────────────────────── */}
        {aiConflictDetected && (
          <ConflictBanner>
            <ConflictBannerIcon>
              <AlertTriangleIcon />
            </ConflictBannerIcon>
            <ConflictBannerContent>
              <ConflictBannerTitle>
                {t("items.aiConflictTitle")}
              </ConflictBannerTitle>
              <ConflictBannerText>
                {t("items.aiConflictMessage")}
              </ConflictBannerText>
            </ConflictBannerContent>
            <ConflictBannerActions>
              <Button
                $variant="secondary"
                $size="sm"
                onClick={handleConflictKeepEditing}
              >
                {t("items.aiConflictKeepEditing")}
              </Button>
              <Button
                $variant="primary"
                $size="sm"
                onClick={handleConflictRefresh}
              >
                {t("items.aiConflictRefresh")}
              </Button>
            </ConflictBannerActions>
          </ConflictBanner>
        )}

        {/* ── Save error banner ────────────────────────────────────── */}
        {saveError && <ErrorBanner>{saveError}</ErrorBanner>}

        {/* ── Delete error banner ──────────────────────────────────── */}
        {deleteError && <ErrorBanner>{deleteError}</ErrorBanner>}

        {/* ── Frontmatter fields section ───────────────────────────── */}
        <Section>
          <SectionTitle>
            {isEditMode ? t("common.edit") : t("items.title")}
          </SectionTitle>

          {isEditMode ? (
            /* ── Edit mode: form fields ─────────────────────────────── */
            <div>
              <FormField label={t("items.title")} htmlFor="field-title" required>
                <Input
                  id="field-title"
                  value={String(editedFrontmatter.title ?? "")}
                  onChange={(e) => handleFrontmatterChange("title", e.target.value)}
                />
              </FormField>

              <FormField label={t("items.status")} htmlFor="field-status">
                <Select
                  id="field-status"
                  value={String(editedFrontmatter.status ?? "")}
                  onChange={(e) =>
                    handleFrontmatterChange("status", e.target.value)
                  }
                >
                  <option value="">&mdash;</option>
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {t(`items.status${opt.charAt(0).toUpperCase() + opt.slice(1)}`)}
                    </option>
                  ))}
                </Select>
              </FormField>

              {/* Read-only fields */}
              <FormField
                label={t("items.createdAt")}
                helpText={t("items.readOnlyField")}
              >
                <ReadOnlyValue>{formatDate(createdAt)}</ReadOnlyValue>
              </FormField>

              <FormField
                label={t("items.lastModified")}
                helpText={t("items.readOnlyField")}
              >
                <ReadOnlyValue>
                  {lastModified ? formatRelativeTime(lastModified) : "—"}
                </ReadOnlyValue>
              </FormField>

              <FormField
                label={t("items.lastModifiedBy", { user: "" }).replace(" by ", "")}
                helpText={t("items.readOnlyField")}
              >
                <ReadOnlyValue>{lastModifiedBy || "—"}</ReadOnlyValue>
              </FormField>

              {/* References — read-only in edit mode */}
              {fm.references != null && (
                <FormField
                  label={t("items.crossReferences")}
                  helpText={t("items.readOnlyField")}
                >
                  <ReadOnlyValue>
                    {Array.isArray(fm.references)
                      ? (fm.references as string[]).join(", ")
                      : String(fm.references)}
                  </ReadOnlyValue>
                </FormField>
              )}

              {/* Extra/unknown fields — editable */}
              {extraFields.map((key) => (
                <FormField
                  key={key}
                  label={fieldKeyToLabel(key)}
                  htmlFor={`field-extra-${key}`}
                >
                  <Input
                    id={`field-extra-${key}`}
                    value={String(editedFrontmatter[key] ?? "")}
                    onChange={(e) =>
                      handleFrontmatterChange(key, e.target.value)
                    }
                  />
                </FormField>
              ))}
            </div>
          ) : (
            /* ── View mode: labelled key-value pairs ────────────────── */
            <FieldGrid>
              <FieldItem>
                <FieldLabel>{t("items.status")}</FieldLabel>
                {itemStatus ? (
                  <Badge $variant={STATUS_BADGE_MAP[itemStatus] ?? "info"}>
                    {itemStatus}
                  </Badge>
                ) : (
                  <FieldValue>—</FieldValue>
                )}
              </FieldItem>

              <FieldItem>
                <FieldLabel>{t("items.createdAt")}</FieldLabel>
                <FieldValue>{createdAt ? formatDate(createdAt) : "—"}</FieldValue>
              </FieldItem>

              <FieldItem>
                <FieldLabel>{t("items.lastModified")}</FieldLabel>
                <FieldValue>
                  {lastModified ? formatRelativeTime(lastModified) : "—"}
                </FieldValue>
              </FieldItem>

              <FieldItem>
                <FieldLabel>
                  {t("items.lastModifiedBy", { user: "" }).replace(" by ", "")}
                </FieldLabel>
                <FieldValue>{lastModifiedBy || "—"}</FieldValue>
              </FieldItem>

              {/* Extra/unknown frontmatter fields */}
              {extraFields.map((key) => (
                <FieldItem key={key}>
                  <FieldLabel>{fieldKeyToLabel(key)}</FieldLabel>
                  <FieldValue>{String(fm[key] ?? "—")}</FieldValue>
                </FieldItem>
              ))}
            </FieldGrid>
          )}
        </Section>

        {/* ── Body section ─────────────────────────────────────────── */}
        <Section>
          <SectionTitle>{t("items.body")}</SectionTitle>
          {isEditMode ? (
            <EditBody
              value={editedBody}
              onChange={(e) => setEditedBody(e.target.value)}
              placeholder={t("items.body")}
            />
          ) : (
            <BodyWrapper>
              {body ? (
                <Markdown content={body} />
              ) : (
                <EmptyBody>{t("items.noContent")}</EmptyBody>
              )}
            </BodyWrapper>
          )}
        </Section>

        {/* ── Cross-layer references section ───────────────────────── */}
        {hasAnyRefs && (
          <Section>
            <SectionTitle>{t("items.crossReferences")}</SectionTitle>

            {hasForwardRefs && (
              <ReferenceGroup>
                <ReferenceGroupTitle>
                  {t("items.referencesForward")}
                </ReferenceGroupTitle>
                {references!.forward.map((ref) => (
                  <ReferenceLink
                    key={`${ref.layer_slug}/${ref.filename}`}
                    $layerSlug={ref.layer_slug}
                    onClick={() => handleReferenceClick(ref)}
                  >
                    <ReferenceLayerTag $layerSlug={ref.layer_slug}>
                      {t(LAYER_NAME_KEYS[ref.layer_slug] ?? ref.layer_slug)}
                    </ReferenceLayerTag>
                    <span>{ref.title || ref.filename}</span>
                  </ReferenceLink>
                ))}
              </ReferenceGroup>
            )}

            {hasBackwardRefs && (
              <ReferenceGroup>
                <ReferenceGroupTitle>
                  {t("items.referencesBackward")}
                </ReferenceGroupTitle>
                {references!.backward.map((ref) => (
                  <ReferenceLink
                    key={`${ref.layer_slug}/${ref.filename}`}
                    $layerSlug={ref.layer_slug}
                    onClick={() => handleReferenceClick(ref)}
                  >
                    <ReferenceLayerTag $layerSlug={ref.layer_slug}>
                      {t(LAYER_NAME_KEYS[ref.layer_slug] ?? ref.layer_slug)}
                    </ReferenceLayerTag>
                    <span>{ref.title || ref.filename}</span>
                  </ReferenceLink>
                ))}
              </ReferenceGroup>
            )}
          </Section>
        )}

        {/* ── Attribution section ──────────────────────────────────── */}
        {!isEditMode && (lastModifiedBy || lastModified) && (
          <AttributionBar>
            {lastModifiedBy && (
              <AttributionItem>
                {t("items.lastModifiedBy", { user: lastModifiedBy })}
              </AttributionItem>
            )}
            {lastModified && (
              <AttributionItem title={formatDate(lastModified)}>
                {t("items.lastModifiedAt", {
                  time: formatRelativeTime(lastModified),
                })}
              </AttributionItem>
            )}
          </AttributionBar>
        )}

        {/* ── Delete confirmation modal ────────────────────────────── */}
        <ConfirmModal
          isOpen={showDeleteModal}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteModal(false)}
          title={t("items.deleteConfirmTitle")}
          message={t("items.deleteConfirmMessage")}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
          variant="danger"
          loading={deleting}
        />

        {/* ── Discard changes confirmation modal ───────────────────── */}
        <ConfirmModal
          isOpen={showDiscardModal}
          onConfirm={handleConfirmDiscard}
          onCancel={() => setShowDiscardModal(false)}
          title={t("items.discardChangesTitle")}
          message={t("items.discardChangesMessage")}
          confirmLabel={t("items.discardChanges")}
          cancelLabel={t("items.keepEditing")}
          variant="warning"
        />
      </PageWrapper>

      {/* ── Conversation sidebar ───────────────────────────────────── */}
      <ConversationSidebar
        isOpen={isConversationOpen}
        onClose={handleCloseConversation}
        layerSlug={slug}
        filename={filename}
      />
    </PageContainer>
  );
}
