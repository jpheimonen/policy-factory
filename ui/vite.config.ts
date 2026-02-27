/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Backend port: use VITE_BACKEND_PORT env var if set, otherwise default to 8765.
// The `make dev` target auto-detects an available port and passes it here,
// so the proxy always points at the correct backend even when multiple
// instances are running.
const backendPort = process.env.VITE_BACKEND_PORT || "8765";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    // Setup files run before each test file
    setupFiles: ["./src/test-setup.ts"],
  },
  server: {
    // Proxy API and WebSocket requests to FastAPI backend during development
    proxy: {
      "/api": {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
      },
      "/ws": {
        target: `ws://localhost:${backendPort}`,
        ws: true,
      },
    },
  },
  build: {
    // Output directly to Python package static directory
    outDir: "../src/policy_factory/static/dist",
    emptyOutDir: true,
  },
});
