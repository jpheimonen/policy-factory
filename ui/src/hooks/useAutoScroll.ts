/**
 * Smart auto-scroll hook for scrollable containers.
 *
 * Adapted from cc-runner's useAutoScroll pattern.
 *
 * Behaviour:
 * - Auto-scrolls to the bottom when the dependency value changes
 * - Only scrolls if the user is already near the bottom (within threshold)
 * - If the user scrolls up to read earlier content, auto-scrolling pauses
 * - Auto-scrolling resumes when the user scrolls back to the bottom
 *
 * Used by the cascade viewer's streaming text panel.
 */
import { useEffect, useRef, useCallback, type RefObject } from "react";

/** If the user is within this many pixels of the bottom, auto-scroll */
const SCROLL_THRESHOLD = 100;

/**
 * @param dependency - Value that triggers scroll check (e.g., text length or event count)
 * @returns ref to attach to the scrollable container, plus utility functions
 */
export function useAutoScroll<T extends HTMLElement>(dependency: number): {
  ref: RefObject<T | null>;
  scrollToBottom: () => void;
  isAtBottom: () => boolean;
} {
  const ref = useRef<T>(null);
  // Start true so that initial content scrolls into view
  const isUserAtBottom = useRef(true);

  /** Check if the user is within threshold of the bottom. */
  const isAtBottom = useCallback((): boolean => {
    if (!ref.current) return true;
    const { scrollTop, scrollHeight, clientHeight } = ref.current;
    return scrollHeight - scrollTop - clientHeight <= SCROLL_THRESHOLD;
  }, []);

  /** Programmatically scroll to the bottom. */
  const scrollToBottom = useCallback(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, []);

  /** Track user scroll position. */
  const handleScroll = useCallback(() => {
    isUserAtBottom.current = isAtBottom();
  }, [isAtBottom]);

  // Attach scroll listener
  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    element.addEventListener("scroll", handleScroll, { passive: true });
    return () => element.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Auto-scroll when dependency changes, only if user is at the bottom
  useEffect(() => {
    if (ref.current && isUserAtBottom.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [dependency]);

  return { ref, scrollToBottom, isAtBottom };
}
