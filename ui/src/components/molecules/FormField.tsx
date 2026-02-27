/**
 * FormField molecule.
 *
 * Wraps a form input (Input, Textarea, Select, or any child) with a label
 * above it and optional error text below. Used in edit forms across the app:
 * item editing (step 011), admin panel (step 023), idea submission (step 021).
 *
 * Follows the cc-runner FormField.tsx pattern.
 */
import type { ReactNode } from "react";
import styled from "styled-components";

export interface FormFieldProps {
  /** Label displayed above the input */
  label: string;
  /** The form input element(s) */
  children: ReactNode;
  /** Error message displayed below the input in error styling */
  error?: string;
  /** Help text displayed below the label in muted styling */
  helpText?: string;
  /** Shows a required indicator (*) next to the label */
  required?: boolean;
  /** For accessibility — links the label to the input via `for` attribute */
  htmlFor?: string;
}

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};

  & + & {
    margin-top: ${({ theme }) => theme.spacing.md};
  }
`;

const LabelRow = styled.div`
  display: flex;
  align-items: baseline;
  gap: ${({ theme }) => theme.spacing.sm};
`;

const Label = styled.label`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.primary};
`;

const RequiredIndicator = styled.span`
  color: ${({ theme }) => theme.colors.accent.red};
  font-weight: 500;
`;

const HelpText = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
`;

const ErrorText = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.accent.red};
`;

export function FormField({
  label,
  children,
  error,
  helpText,
  required,
  htmlFor,
}: FormFieldProps) {
  return (
    <Container>
      <LabelRow>
        <Label htmlFor={htmlFor}>
          {label}
          {required && <RequiredIndicator> *</RequiredIndicator>}
        </Label>
        {helpText && <HelpText>{helpText}</HelpText>}
      </LabelRow>
      {children}
      {error && <ErrorText>{error}</ErrorText>}
    </Container>
  );
}
