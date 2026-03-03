/**
 * Time formatting utilities.
 *
 * Provides human-readable relative time formatting used throughout
 * the UI for timestamps on items, events, cascades, and ideas.
 */

/**
 * Format the duration between two ISO timestamps as a compact string.
 *
 * Returns "42s" for sub-minute durations, or "3m 12s" for longer durations.
 */
export function formatDuration(start: string, end: string): string {
  const diffMs = new Date(end).getTime() - new Date(start).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  const sec = diffSec % 60;
  return `${min}m ${sec}s`;
}

/**
 * Format an ISO timestamp as a human-readable relative time string.
 *
 * Returns simple labels like "just now", "5m ago", "3h ago",
 * "yesterday", "12d ago", or a locale date for older timestamps.
 */
export function formatRelativeTime(isoTimestamp: string): string {
  if (!isoTimestamp) return "";

  try {
    const date = new Date(isoTimestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "yesterday";
    if (diffDays < 30) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  } catch {
    return "";
  }
}
