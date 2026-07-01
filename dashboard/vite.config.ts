import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard talks to the local API on :8000. Proxy /api during dev so
// there are no CORS surprises.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
