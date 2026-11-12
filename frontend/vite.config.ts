import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, searchForWorkspaceRoot } from "vite";

export default defineConfig(({ mode }) => {
  const { A11YRA_DEV_API_PORT = "8000" } = loadEnv(mode, ".", "A11YRA_DEV_");
  const api = `http://127.0.0.1:${A11YRA_DEV_API_PORT}`;
  const email = (loadEnv(mode, ".", "SUPPORT_EMAIL").SUPPORT_EMAIL
    ?? loadEnv(mode, "..", "SUPPORT_EMAIL").SUPPORT_EMAIL ?? "").trim();
  const supportEmail = /^[^\s@?&#]+@[^\s@?&#]+\.[^\s@?&#]+$/.test(email) ? email : "";
  return {
    plugins: [react()],
    define: { __SUPPORT_EMAIL__: JSON.stringify(supportEmail) },
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      fs: { allow: [searchForWorkspaceRoot("."), "../backend/app/product/plan_prices.json"] },
      proxy: {
        "/api": api,
        "/r/": api,
      },
    },
  };
});
