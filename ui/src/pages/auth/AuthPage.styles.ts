/**
 * Shared styled components for login and registration pages.
 *
 * Centered card layout with Notion/Linear aesthetic:
 * generous whitespace, subtle card border, professional feel.
 */
import styled from "styled-components";

/** Full-viewport centered wrapper. */
export const AuthWrapper = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: ${({ theme }) => theme.spacing.xl};
  background-color: ${({ theme }) => theme.colors.bg.primary};
`;

/** The centered card containing the auth form. */
export const AuthCard = styled.div`
  width: 100%;
  max-width: 400px;
  padding: ${({ theme }) => theme.spacing.xxl};
  background: ${({ theme }) => theme.colors.bg.elevated};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.xl};
  box-shadow: ${({ theme }) => theme.shadows.md};
`;

/** App name / branding at the top of the card. */
export const AuthBrand = styled.div`
  text-align: center;
  margin-bottom: ${({ theme }) => theme.spacing.xl};

  h1 {
    font-family: ${({ theme }) => theme.fonts.sans};
    font-size: ${({ theme }) => theme.fontSizes.xl};
    font-weight: 600;
    color: ${({ theme }) => theme.colors.text.primary};
    margin-bottom: ${({ theme }) => theme.spacing.xs};
  }
`;

/** Subtitle / description text under the brand. */
export const AuthSubtitle = styled.p`
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.secondary};
  text-align: center;
  margin-bottom: ${({ theme }) => theme.spacing.xl};
  line-height: 1.5;
`;

/** Form container with vertical gap between fields. */
export const AuthForm = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.lg};
`;

/** Individual form field: label + input + optional error. */
export const FormField = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
`;

/** Field label. */
export const FieldLabel = styled.label`
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.secondary};
`;

/** Inline validation error below a field. */
export const FieldError = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.status.error.text};
  line-height: 1.4;
`;

/** Top-level form error (e.g., wrong credentials). */
export const FormError = styled.div`
  padding: ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.status.error.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.error.border};
  border-radius: ${({ theme }) => theme.radii.md};
  color: ${({ theme }) => theme.colors.status.error.text};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  text-align: center;
`;

/** Info note (e.g., "first admin account" message). */
export const InfoNote = styled.div`
  padding: ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.status.active.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.active.border};
  border-radius: ${({ theme }) => theme.radii.md};
  color: ${({ theme }) => theme.colors.status.active.text};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  text-align: center;
  margin-bottom: ${({ theme }) => theme.spacing.lg};
`;
