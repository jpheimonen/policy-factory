/**
 * App layout wrapper for protected pages.
 *
 * Renders the WebSocket provider (global connection), the Navigation header,
 * and the page content (Outlet). Only rendered for authenticated users.
 *
 * The WebSocket provider is placed here (inside the protected route area)
 * so the connection is only established when the user is authenticated
 * and torn down when they log out.
 */
import { Outlet } from "react-router-dom";
import { WebSocketProvider } from "@/hooks/WebSocketProvider.tsx";
import { Navigation } from "./Navigation.tsx";
import { InputPanel } from "./InputPanel.tsx";
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
    <WebSocketProvider>
      <LayoutWrapper>
        <Navigation />
        <MainContent>
          <Outlet />
        </MainContent>
        <InputPanel />
      </LayoutWrapper>
    </WebSocketProvider>
  );
}
