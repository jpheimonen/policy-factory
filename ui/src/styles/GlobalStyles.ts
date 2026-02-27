/**
 * Global styles for Policy Factory.
 *
 * CSS reset, base typography, scrollbar styling, and full-height layout.
 * All values reference theme tokens so both dark and light themes are
 * supported automatically.
 */
import { createGlobalStyle } from "styled-components";

export const GlobalStyles = createGlobalStyle`
  /* CSS Reset */
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  /* Full-height layout */
  html, body, #root {
    height: 100%;
  }

  /* Base typography and colors */
  body {
    font-family: ${({ theme }) => theme.fonts.sans};
    font-size: ${({ theme }) => theme.fontSizes.base};
    line-height: 1.6;
    color: ${({ theme }) => theme.colors.text.primary};
    background-color: ${({ theme }) => theme.colors.bg.primary};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    transition: background-color ${({ theme }) => theme.transitions.normal},
                color ${({ theme }) => theme.transitions.normal};
  }

  /* Scrollbar styling (Webkit / Chrome / Edge / Safari) */
  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: transparent;
  }

  ::-webkit-scrollbar-thumb {
    background-color: ${({ theme }) => theme.colors.border.default};
    border-radius: 4px;

    &:hover {
      background-color: ${({ theme }) => theme.colors.text.muted};
    }
  }

  /* Firefox scrollbar */
  * {
    scrollbar-width: thin;
    scrollbar-color: ${({ theme }) => theme.colors.border.default} transparent;
  }

  /* Anchor reset */
  a {
    color: inherit;
    text-decoration: none;
  }

  /* Button reset */
  button {
    font-family: inherit;
    cursor: pointer;
    border: none;
    background: none;
    color: inherit;
  }

  /* Input/textarea/select reset */
  input, textarea, select {
    font-family: inherit;
    font-size: inherit;
    color: inherit;
  }

  /* List reset */
  ul, ol {
    list-style: none;
  }

  /* Image defaults */
  img {
    max-width: 100%;
    display: block;
  }
`;
