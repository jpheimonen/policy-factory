/**
 * App layout wrapper for protected pages.
 *
 * Renders the Navigation header followed by the page content (Outlet).
 * Only rendered for authenticated users.
 */
import { Outlet } from "react-router-dom";
import { Navigation } from "./Navigation.tsx";
import styled from "styled-components";

const LayoutWrapper = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 100vh;
`;

const MainContent = styled.main`
  flex: 1;
  padding: ${({ theme }) => theme.spacing.xl};
`;

export function AppLayout() {
  return (
    <LayoutWrapper>
      <Navigation />
      <MainContent>
        <Outlet />
      </MainContent>
    </LayoutWrapper>
  );
}
