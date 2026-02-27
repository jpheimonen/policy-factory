/**
 * Registration page.
 *
 * Route: /register
 * Only accessible when no users exist in the system (first-user flow).
 * If users exist and visitor is unauthenticated, redirects to /login.
 *
 * Same visual design as the login page — centered card with the app name.
 * Includes an info note indicating this is the first admin account.
 */
import { useState, useCallback, useEffect, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Input } from "@/components/atoms/index.ts";
import { useTranslation } from "@/i18n/index.ts";
import { useAuthStore } from "@/stores/authStore.ts";
import {
  AuthWrapper,
  AuthCard,
  AuthBrand,
  AuthSubtitle,
  AuthForm,
  FormField,
  FieldLabel,
  FieldError,
  FormError,
  InfoNote,
} from "./AuthPage.styles.ts";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const register = useAuthStore((s) => s.register);
  const loading = useAuthStore((s) => s.loading);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const hasUsers = useAuthStore((s) => s.hasUsers);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  // Redirect to login if users already exist and not authenticated
  useEffect(() => {
    if (hasUsers === true && !isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [hasUsers, isAuthenticated, navigate]);

  // Redirect to home if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const validate = useCallback((): boolean => {
    let valid = true;
    setEmailError(null);
    setPasswordError(null);
    setConfirmError(null);

    if (!email.trim()) {
      setEmailError(t("auth.errorEmailRequired"));
      valid = false;
    } else if (!email.includes("@")) {
      setEmailError(t("auth.errorEmailInvalid"));
      valid = false;
    }

    if (!password) {
      setPasswordError(t("auth.errorPasswordRequired"));
      valid = false;
    }

    if (password && confirmPassword && password !== confirmPassword) {
      setConfirmError(t("auth.errorPasswordMismatch"));
      valid = false;
    }

    return valid;
  }, [email, password, confirmPassword, t]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const success = await register(email, password);
    if (success) {
      navigate("/", { replace: true });
    }
  };

  const handleInputChange = () => {
    if (error) clearError();
  };

  // Don't render if users exist (redirect will fire)
  if (hasUsers === true && !isAuthenticated) {
    return null;
  }

  return (
    <AuthWrapper>
      <AuthCard>
        <AuthBrand>
          <h1>{t("nav.appName")}</h1>
        </AuthBrand>
        <AuthSubtitle>{t("auth.registerTitle")}</AuthSubtitle>

        <InfoNote>{t("auth.registerDescription")}</InfoNote>

        {error && <FormError>{error}</FormError>}

        <AuthForm onSubmit={handleSubmit}>
          <FormField>
            <FieldLabel htmlFor="register-email">
              {t("auth.emailLabel")}
            </FieldLabel>
            <Input
              id="register-email"
              type="email"
              placeholder={t("auth.emailPlaceholder")}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setEmailError(null);
                handleInputChange();
              }}
              $error={!!emailError}
              autoComplete="email"
              autoFocus
            />
            {emailError && <FieldError>{emailError}</FieldError>}
          </FormField>

          <FormField>
            <FieldLabel htmlFor="register-password">
              {t("auth.passwordLabel")}
            </FieldLabel>
            <Input
              id="register-password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setPasswordError(null);
                handleInputChange();
              }}
              $error={!!passwordError}
              autoComplete="new-password"
            />
            {passwordError && <FieldError>{passwordError}</FieldError>}
          </FormField>

          <FormField>
            <FieldLabel htmlFor="register-confirm-password">
              {t("auth.confirmPasswordLabel")}
            </FieldLabel>
            <Input
              id="register-confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setConfirmError(null);
                handleInputChange();
              }}
              $error={!!confirmError}
              autoComplete="new-password"
            />
            {confirmError && <FieldError>{confirmError}</FieldError>}
          </FormField>

          <Button
            type="submit"
            $variant="primary"
            $size="lg"
            $fullWidth
            $loading={loading}
            disabled={loading}
          >
            {loading ? t("auth.registering") : t("auth.registerButton")}
          </Button>
        </AuthForm>
      </AuthCard>
    </AuthWrapper>
  );
}
