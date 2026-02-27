/**
 * Protected route wrapper.
 *
 * Wraps routes that require authentication. Checks the auth store
 * for a valid token — redirects to /login if absent.
 *
 * Used in App.tsx to guard all routes except /login and /register.
 */
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore.ts";

export function ProtectedRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
