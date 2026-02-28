/**
 * EventItem molecule.
 *
 * Renders a single event in the activity feed. Each event type maps to
 * an icon, description, and contextual details (layer, critic, etc.).
 *
 * The component is reusable outside the activity feed page (e.g., in a
 * sidebar summary or notification area).
 *
 * Event types are rendered via a dispatch on `event_type`:
 * - Cascade lifecycle: started, completed, failed, paused, resumed, cancelled, queued
 * - Layer processing: generation, critics, synthesis
 * - Heartbeat: started, tier completed, completed
 * - Ideas: submitted, evaluation started/completed, generation started/completed
 * - System: user login, user created, lock acquired/released
 *
 * `agent_text_chunk` events are excluded — too high-frequency for the activity feed.
 */
import { useMemo } from "react";
import { useTranslation } from "@/i18n/index.ts";
import { LAYER_NAME_KEYS } from "@/lib/layerConstants.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Badge } from "@/components/atoms/index.ts";
import type { ActivityEvent } from "@/stores/activityStore.ts";
import type { EventCategory } from "@/types/events.ts";
import type { BadgeVariant } from "@/components/atoms/Badge.ts";
import {
  EventItemWrapper,
  EventIcon,
  EventContent,
  EventTopRow,
  EventDescription,
  EventTimestamp,
  EventMeta,
  EventErrorText,
  LayerBadge,
} from "./EventItem.styles.ts";

import { CRITIC_DISPLAY_KEYS } from "@/lib/layerConstants.ts";

// ── Event icons ──────────────────────────────────────────────────────

function getEventIcon(eventType: string): string {
  switch (eventType) {
    // Cascade lifecycle
    case "cascade_started":
      return "\u25B6"; // play
    case "cascade_completed":
      return "\u2713"; // check
    case "cascade_failed":
      return "\u2717"; // cross
    case "cascade_paused":
      return "\u23F8"; // pause
    case "cascade_resumed":
      return "\u25B6"; // play
    case "cascade_cancelled":
      return "\u2715"; // x
    case "cascade_queued":
      return "\u23F0"; // clock
    // Layer processing
    case "layer_generation_started":
      return "\u21BB"; // reload
    case "layer_generation_completed":
      return "\u2713"; // check
    case "critic_started":
      return "\uD83D\uDCAC"; // speech
    case "critic_completed":
      return "\u2713"; // check
    case "synthesis_started":
      return "\u2194"; // merge arrows
    case "synthesis_completed":
      return "\u2713"; // check
    // Heartbeat
    case "heartbeat_started":
      return "\uD83D\uDC93"; // pulse
    case "heartbeat_tier_completed":
      return "\u25C9"; // tier dot
    case "heartbeat_completed":
      return "\u2713"; // check
    // Ideas
    case "idea_submitted":
      return "\uD83D\uDCA1"; // lightbulb
    case "idea_evaluation_started":
      return "\u21BB"; // reload
    case "idea_evaluation_completed":
      return "\u2713"; // check
    case "idea_generation_started":
      return "\u2728"; // sparkle
    case "idea_generation_completed":
      return "\u2713"; // check
    // System
    case "user_login":
      return "\uD83D\uDC64"; // user
    case "user_created":
      return "\uD83D\uDC65"; // user-plus
    case "cascade_lock_acquired":
      return "\uD83D\uDD12"; // lock
    case "cascade_lock_released":
      return "\uD83D\uDD13"; // unlock
    default:
      return "\u2022"; // bullet
  }
}

// ── Category badge mapping ───────────────────────────────────────────

function getCategoryBadgeVariant(category: EventCategory | null): BadgeVariant {
  switch (category) {
    case "cascade":
      return "info";
    case "heartbeat":
      return "warning";
    case "idea":
      return "success";
    case "system":
      return "neutral";
    default:
      return "neutral";
  }
}

function getCategoryLabel(
  category: EventCategory | null,
  t: (key: string) => string,
): string {
  switch (category) {
    case "cascade":
      return t("activity.categoryCascade");
    case "heartbeat":
      return t("activity.categoryHeartbeat");
    case "idea":
      return t("activity.categoryIdeas");
    case "system":
      return t("activity.categorySystem");
    default:
      return t("activity.categorySystem");
  }
}

// ── Time formatting helpers ──────────────────────────────────────────

function formatFullTimestamp(isoTimestamp: string): string {
  if (!isoTimestamp) return "";

  try {
    const date = new Date(isoTimestamp);
    return date.toLocaleString();
  } catch {
    return "";
  }
}

// ── Props ────────────────────────────────────────────────────────────

export interface EventItemProps {
  /** The activity event to render. */
  event: ActivityEvent;
  /** Whether this is a newly arrived event (triggers fade-in animation). */
  isNew?: boolean;
}

// ── Component ────────────────────────────────────────────────────────

export function EventItem({ event, isNew = false }: EventItemProps) {
  const { t } = useTranslation();

  const layerName = useMemo(() => {
    if (!event.layer_slug) return null;
    const key = LAYER_NAME_KEYS[event.layer_slug];
    return key ? t(key) : event.layer_slug;
  }, [event.layer_slug, t]);

  const description = useMemo(() => {
    const data = event.data;

    switch (event.event_type) {
      // ── Cascade lifecycle ────────────────────────────────────────
      case "cascade_started": {
        const startingLayer =
          data.starting_layer as string | undefined;
        const lName = startingLayer
          ? t(LAYER_NAME_KEYS[startingLayer] ?? startingLayer)
          : "";
        return t("activity.cascadeStarted", { layerName: lName });
      }
      case "cascade_completed":
        return t("activity.cascadeCompleted");
      case "cascade_failed": {
        const failedLayer =
          data.failed_layer as string | undefined;
        const fName = failedLayer
          ? t(LAYER_NAME_KEYS[failedLayer] ?? failedLayer)
          : "";
        const step = (data.failed_step as string) ?? "";
        return t("activity.cascadeFailed", { layerName: fName, step });
      }
      case "cascade_paused": {
        const pausedLayer =
          data.paused_layer as string | undefined;
        const pName = pausedLayer
          ? t(LAYER_NAME_KEYS[pausedLayer] ?? pausedLayer)
          : "";
        const pStep = (data.paused_step as string) ?? "";
        return t("activity.cascadePaused", { layerName: pName, step: pStep });
      }
      case "cascade_resumed":
        return t("activity.cascadeResumed");
      case "cascade_cancelled":
        return t("activity.cascadeCancelled");
      case "cascade_queued": {
        const pos = (data.queue_position as number) ?? 0;
        return t("activity.cascadeQueued", { position: pos });
      }

      // ── Layer processing ─────────────────────────────────────────
      case "layer_generation_started": {
        const lSlug = data.layer_slug as string | undefined;
        const ln = lSlug
          ? t(LAYER_NAME_KEYS[lSlug] ?? lSlug)
          : "";
        return t("activity.layerGenerationStarted", { layerName: ln });
      }
      case "layer_generation_completed": {
        const lSlug = data.layer_slug as string | undefined;
        const ln = lSlug
          ? t(LAYER_NAME_KEYS[lSlug] ?? lSlug)
          : "";
        return t("activity.layerGenerationCompleted", { layerName: ln });
      }
      case "critic_started": {
        const lSlug = data.layer_slug as string | undefined;
        const ln = lSlug
          ? t(LAYER_NAME_KEYS[lSlug] ?? lSlug)
          : "";
        const critic = data.critic_archetype as string | undefined;
        const cName = critic
          ? t(CRITIC_DISPLAY_KEYS[critic] ?? critic)
          : "";
        return t("activity.criticStarted", {
          criticName: cName,
          layerName: ln,
        });
      }
      case "critic_completed": {
        const lSlug = data.layer_slug as string | undefined;
        const ln = lSlug
          ? t(LAYER_NAME_KEYS[lSlug] ?? lSlug)
          : "";
        const critic = data.critic_archetype as string | undefined;
        const cName = critic
          ? t(CRITIC_DISPLAY_KEYS[critic] ?? critic)
          : "";
        return t("activity.criticCompleted", {
          criticName: cName,
          layerName: ln,
        });
      }
      case "synthesis_started": {
        const lSlug = data.layer_slug as string | undefined;
        const ln = lSlug
          ? t(LAYER_NAME_KEYS[lSlug] ?? lSlug)
          : "";
        return t("activity.synthesisStarted", { layerName: ln });
      }
      case "synthesis_completed": {
        const lSlug = data.layer_slug as string | undefined;
        const ln = lSlug
          ? t(LAYER_NAME_KEYS[lSlug] ?? lSlug)
          : "";
        return t("activity.synthesisCompleted", { layerName: ln });
      }

      // ── Heartbeat ────────────────────────────────────────────────
      case "heartbeat_started":
        return t("activity.heartbeatStarted");
      case "heartbeat_tier_completed": {
        const tier = (data.tier as number) ?? 0;
        const outcome = (data.outcome as string) ?? "";
        const escalated = data.escalated as boolean | undefined;
        let desc = t("activity.heartbeatTierCompleted", {
          tier,
          outcome,
        });
        if (escalated) {
          desc += t("activity.heartbeatTierEscalating", {
            nextTier: tier + 1,
          });
        }
        return desc;
      }
      case "heartbeat_completed": {
        const tier = (data.highest_tier as number) ?? 0;
        return t("activity.heartbeatCompleted", { tier });
      }

      // ── Ideas ────────────────────────────────────────────────────
      case "idea_submitted": {
        const source = data.source as string | undefined;
        const srcLabel = source === "human"
          ? t("activity.sourceHuman")
          : source === "ai"
            ? t("activity.sourceAI")
            : "";
        return srcLabel
          ? `${t("activity.ideaSubmitted")} (${srcLabel})`
          : t("activity.ideaSubmitted");
      }
      case "idea_evaluation_started":
        return t("activity.ideaEvaluationStarted");
      case "idea_evaluation_completed":
        return t("activity.ideaEvaluationCompleted");
      case "idea_generation_started":
        return t("activity.ideaGenerationStarted");
      case "idea_generation_completed": {
        const count = (data.count as number) ?? 0;
        return t("activity.ideaGenerationCompleted", { count });
      }

      // ── System ───────────────────────────────────────────────────
      case "user_login": {
        const email = (data.email as string) ?? "";
        return t("activity.userLogin", { email });
      }
      case "user_created": {
        const email = (data.email as string) ?? "";
        const role = (data.role as string) ?? "";
        return t("activity.userCreated", { email, role });
      }
      case "cascade_lock_acquired":
        return t("activity.cascadeLockAcquired");
      case "cascade_lock_released":
        return t("activity.cascadeLockReleased");

      default:
        return event.event_type;
    }
  }, [event, t]);

  // Extract error text for failed/paused events
  const errorText = useMemo(() => {
    if (
      event.event_type === "cascade_failed" ||
      event.event_type === "cascade_paused"
    ) {
      return (event.data.error as string) ?? null;
    }
    return null;
  }, [event]);

  const icon = getEventIcon(event.event_type);
  const relativeTime = formatRelativeTime(event.timestamp);
  const fullTimestamp = formatFullTimestamp(event.timestamp);

  return (
    <EventItemWrapper $category={event.category} $isNew={isNew}>
      <EventIcon $category={event.category}>{icon}</EventIcon>
      <EventContent>
        <EventTopRow>
          <EventDescription>{description}</EventDescription>
          <EventTimestamp title={fullTimestamp}>{relativeTime}</EventTimestamp>
        </EventTopRow>
        <EventMeta>
          <Badge $variant={getCategoryBadgeVariant(event.category)}>
            {getCategoryLabel(event.category, t)}
          </Badge>
          {event.layer_slug && layerName && (
            <LayerBadge $layerSlug={event.layer_slug}>{layerName}</LayerBadge>
          )}
        </EventMeta>
        {errorText && <EventErrorText>{errorText}</EventErrorText>}
      </EventContent>
    </EventItemWrapper>
  );
}
