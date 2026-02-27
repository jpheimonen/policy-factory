/**
 * Login page.
 *
 * Route: /login
 * Centered card with email + password fields, using design system atoms
 * and i18n translation keys for all visible text.
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
} from "./AuthPage.styles.ts";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const loading = useAuthStore((s) => s.loading);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const hasUsers = useAuthStore((s) => s.hasUsers);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Redirect to register if no users exist (first-user flow)
  useEffect(() => {
    if (hasUsers === false) {
      navigate("/register", { replace: true });
    }
  }, [hasUsers, navigate]);

  // Redirect to home if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const validate = useCallback((): boolean => {
    let valid = true;
    setEmailError(null);
    setPasswordError(null);

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

    return valid;
  }, [email, password, t]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const success = await login(email, password);
    if (success) {
      navigate("/", { replace: true });
    }
  };

  const handleInputChange = () => {
    if (error) clearError();
  };

  return (
    <AuthWrapper>
      <AuthCard>
        <AuthBrand>
          <h1>{t("nav.appName")}</h1>
        </AuthBrand>
        <AuthSubtitle>{t("auth.loginTitle")}</AuthSubtitle>

        {error && <FormError>{t("auth.errorInvalidCredentials")}</FormError>}

        <AuthForm onSubmit={handleSubmit}>
          <FormField>
            <FieldLabel htmlFor="login-email">
              {t("auth.emailLabel")}
            </FieldLabel>
            <Input
              id="login-email"
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
            <FieldLabel htmlFor="login-password">
              {t("auth.passwordLabel")}
            </FieldLabel>
            <Input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setPasswordError(null);
                handleInputChange();
              }}
              $error={!!passwordError}
              autoComplete="current-password"
            />
            {passwordError && <FieldError>{passwordError}</FieldError>}
          </FormField>

          <Button
            type="submit"
            $variant="primary"
            $size="lg"
            $fullWidth
            $loading={loading}
            disabled={loading}
          >
            {loading ? t("auth.loggingIn") : t("auth.loginButton")}
          </Button>
        </AuthForm>
      </AuthCard>
    </AuthWrapper>
  );
}
