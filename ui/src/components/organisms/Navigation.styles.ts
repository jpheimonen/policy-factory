/**
 * Navigation styled components.
 *
 * Horizontal top bar with app name, nav links, user info, and actions.
 * Follows the Linear/Notion aesthetic with subtle borders and muted colors.
 */
import styled from "styled-components";
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
`;

export const NavBrand = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.base};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  white-space: nowrap;
  margin-right: ${({ theme }) => theme.spacing.md};
`;

export const NavLinks = styled.nav`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  flex: 1;
`;

export const NavLink = styled(RouterNavLink)`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.secondary};
  padding: ${({ theme }) => theme.spacing.xs} ${({ theme }) => theme.spacing.sm};
  border-radius: ${({ theme }) => theme.radii.md};
  text-decoration: none;
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
`;

export const UserEmail = styled.span`
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;
`;

export const NavDivider = styled.div`
  width: 1px;
  height: 20px;
  background: ${({ theme }) => theme.colors.border.default};
`;
