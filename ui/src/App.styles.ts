/**
 * Root styled components for the App shell.
 */
import styled from "styled-components";

export const AppContainer = styled.div`
  height: 100%;
  min-height: 100vh;
  overflow-x: hidden;
  background-color: ${({ theme }) => theme.colors.bg.primary};
  color: ${({ theme }) => theme.colors.text.primary};
  transition: background-color ${({ theme }) => theme.transitions.normal},
              color ${({ theme }) => theme.transitions.normal};
`;
