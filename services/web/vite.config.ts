import { defineConfig, loadEnv } from "vite";
import solid from "vite-plugin-solid";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_BASE_URL ?? "http://localhost:8000";

  return {
    plugins: [solid()],
    resolve: {
      alias: [
        {
          find: "solid-js/web",
          replacement: fileURLToPath(new URL("./src/solid-compat/web.ts", import.meta.url)),
        },
        {
          find: "solid-js/store",
          replacement: fileURLToPath(new URL("./src/solid-compat/store.ts", import.meta.url)),
        },
        {
          find: "solid-js",
          replacement: fileURLToPath(new URL("./src/solid-compat/solid.ts", import.meta.url)),
        },
      ],
    },
    server: {
      port: 5173,
      strictPort: false,
      fs: {
        allow: ["../.."],
      },
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 4173,
    },
    build: {
      sourcemap: true,
      target: "es2022",
    },
  };
});
