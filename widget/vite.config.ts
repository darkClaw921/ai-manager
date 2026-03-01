import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  build: {
    target: "es2015",
    outDir: "dist",
    rollupOptions: {
      input: {
        widget: "index.html",
        embed: "embed.js",
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  server: {
    port: 3001,
  },
  preview: {
    port: 3001,
  },
});
