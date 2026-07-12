import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발 시 /api → FastAPI(8000) 프록시 (PRD_Phase1 §4.2)
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
});
