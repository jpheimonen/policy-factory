/**
 * Navigation styled components.
 *
 * Horizontal top bar with app name, nav links, cascade status indicator,
 * user info, and actions.
 * Follows the Linear/Notion aesthetic with subtle borders and muted colors.
 */
import styled, { css, keyframes } from "styled-components";
import { NavLink as RouterNavLink } from "react-router-dom";

export const NavBar = styled.header`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.lg};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.xl};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border.default};
  min-height: 48px;
  position: sticky;
  top: 0;
  z-index: ${({ theme }) => theme.zIndices.sticky};

  @media (max-width: 768px) {
    gap: ${({ theme }) => theme.spacing.sm};
    padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
    flex-wrap: wrap;
  }
`;

export const NavBrand = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.base};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  white-space: nowrap;
  margin-right: ${({ theme }) => theme.spacing.md};

  @media (max-width: 768px) {
    margin-right: ${({ theme }) => theme.spacing.sm};
  }
`;

export const NavLinks = styled.nav`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  flex: 1;

  @media (max-width: 768px) {
    order: 3;
    flex-basis: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
`;

export const NavLink = styled(RouterNavLink)`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.secondary};
  padding: ${({ theme }) => theme.spacing.xs} ${({ theme }) => theme.spacing.sm};
  border-radius: ${({ theme }) => theme.radii.md};
  text-decoration: none;
  white-space: nowrap;
  transition: color ${({ theme }) => theme.transitions.fast},
    background ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.text.primary};
    background: ${({ theme }) => theme.colors.bg.tertiary};
  }

  &.active {
    color: ${({ theme }) => theme.colors.text.primary};
    background: ${({ theme }) => theme.colors.bg.elevated};
  }
`;

export const NavRight = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  margin-left: auto;

  @media (max-width: 768px) {
    gap: ${({ theme }) => theme.spacing.sm};
  }
`;

export const UserEmail = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;

  @media (max-width: 768px) {
    display: none;
  }
`;

export const NavDivider = styled.div`
  width: 1px;
  height: 20px;
  background: ${({ theme }) => theme.colors.border.default};

  @media (max-width: 768px) {
    display: none;
  }
`;

// ── Cascade status indicator ─────────────────────────────────────────

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
`;

export type CascadeIndicatorStatus = "idle" | "running" | "paused" | "failed";

export const CascadeStatusWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  padding: 2px ${({ theme }) => theme.spacing.sm};
  border-radius: ${({ theme }) => theme.radii.xl};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  white-space: nowrap;
`;

export const CascadeStatusDot = styled.span<{ $status: CascadeIndicatorStatus }>`
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;

  ${({ $status, theme }) =>
    $status === "running" &&
    css`
      background: ${theme.colors.status.active.text};
      animation: ${pulse} 1.5s ease-in-out infinite;
    `}

  ${({ $status, theme }) =>
    $status === "paused" &&
    css`
      background: ${theme.colors.status.warning.text};
    `}

  ${({ $status, theme }) =>
    $status === "failed" &&
    css`
      background: ${theme.colors.status.error.text};
    `}

  ${({ $status, theme }) =>
    $status === "idle" &&
    css`
      background: ${theme.colors.text.muted};
      opacity: 0.5;
    `}
`;

export const CascadeStatusText = styled.span<{ $status: CascadeIndicatorStatus }>`
  ${({ $status, theme }) =>
    $status === "running" &&
    css`
      color: ${theme.colors.status.active.text};
    `}

  ${({ $status, theme }) =>
    $status === "paused" &&
    css`
      color: ${theme.colors.status.warning.text};
    `}

  ${({ $status, theme }) =>
    $status === "failed" &&
    css`
      color: ${theme.colors.status.error.text};
    `}

  ${({ $status, theme }) =>
    $status === "idle" &&
    css`
      color: ${theme.colors.text.muted};
    `}
`;
