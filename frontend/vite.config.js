import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { copyFileSync } from "fs";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "copy-redirects",
      closeBundle() {
        try {
          copyFileSync(
            resolve(__dirname, "public/_redirects"),
            resolve(__dirname, "dist/_redirects")
          );
          console.log("✅ _redirects file copied to dist/");
        } catch (err) {
          console.warn("⚠️ Could not copy _redirects file:", err);
        }
      },
    },
  ],
  build: {
    outDir: "dist",
  },
  server: {
    port: 5173,
    open: true,
    // Enable React Router support locally
    historyApiFallback: true,
  },
  preview: {
    port: 4173,
    open: true,
    // Make sure preview also supports routes
    historyApiFallback: true,
  },
});
