/**
 * Hook that warns the user before closing or navigating away from the page
 * when unsaved changes exist.
 *
 * When the condition is true and the user attempts to close or navigate away,
 * the browser's native "Leave site?" confirmation dialog is shown.
 *
 * The listener is properly cleaned up when the condition changes to false
 * or when the component unmounts.
 *
 * Follows the cc-runner useBeforeUnload.ts pattern.
 *
 * @param shouldWarn - Whether the warning should be active (e.g., isDirty)
 */
import { useEffect } from "react";

export function useBeforeUnload(shouldWarn: boolean): void {
  useEffect(() => {
    if (!shouldWarn) return;

    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };

    window.addEventListener("beforeunload", handler);

    return () => {
      window.removeEventListener("beforeunload", handler);
    };
  }, [shouldWarn]);
}
