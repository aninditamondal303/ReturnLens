import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The API base URL is read at runtime from VITE_API_BASE_URL (see .env.example).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, host: "127.0.0.1" },
  preview: { port: 4173, host: "127.0.0.1" },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
