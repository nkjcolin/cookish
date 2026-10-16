import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the browser talks to Vite only; Vite forwards API calls to the backend.
// This matches production, where the frontend and API Gateway share one origin.
const backend = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";
// /ai goes to the ai service when one is running; otherwise the backend's stand-in answers.
const ai = process.env.VITE_AI_PROXY_TARGET ?? backend;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": backend,
      "/ai": ai,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
