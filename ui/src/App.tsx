/**
 * Root application component.
 *
 * Wraps the app in ThemeProvider with the resolved theme from the theme store.
 * Renders GlobalStyles and the root AppContainer.
 */
import { ThemeProvider } from "styled-components";
import { GlobalStyles } from "@/styles/GlobalStyles.ts";
import { useThemeStore } from "@/stores/themeStore.ts";
import { AppContainer } from "@/App.styles.ts";

export function App() {
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);

  return (
    <ThemeProvider theme={resolvedTheme}>
      <GlobalStyles />
      <AppContainer>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
          }}
        >
          <h1>Policy Factory</h1>
        </div>
      </AppContainer>
    </ThemeProvider>
  );
}
