import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    historyApiFallback: true, // enable local routing
  },
  build: {
    outDir: "dist", // ensure output folder matches Render’s publish directory
  },
});
