import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const modulePath = id.replaceAll("\\", "/");
          if (!modulePath.includes("/node_modules/")) return;
          if (
            modulePath.includes("/node_modules/react/") ||
            modulePath.includes("/node_modules/react-dom/") ||
            modulePath.includes("/node_modules/scheduler/")
          )
            return "react-vendor";
          if (
            modulePath.includes("/node_modules/@xyflow/") ||
            modulePath.includes("/node_modules/@dagrejs/")
          )
            return "graph-vendor";
          return "vendor";
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:7842",
      "/ws": { target: "ws://127.0.0.1:7842", ws: true },
    },
  },
});
