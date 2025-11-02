import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { copyFileSync } from "fs";

export default defineConfig({
  plugins: [
    react(),
    {
      // Ensures Netlify/Render redirects are included in production build
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
    outDir: "dist", // This is what Render deploys
  },
  server: {
    historyApiFallback: true, // Enable client-side routing
  },
});
