import { useEffect, useState } from "react";
import { t } from "./i18n.js";

/**
 * FairyGUI 工作室的编辑器桥连接状态角标。
 * 轮询编辑器内 agent-bridge 插件的 HTTP 端点（默认 localhost:7531），
 * 显示「已连接 / 未连接」，帮助用户在开工前发现编辑器未启动或插件未安装。
 */
export function FairyguiBridgeStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll(): Promise<void> {
      try {
        // content-type 用 text/plain 避免 CORS 预检；桥端支持任意 Origin
        const response = await fetch("http://127.0.0.1:7531/", {
          method: "POST",
          headers: { "Content-Type": "text/plain" },
          body: JSON.stringify({ cmd: "ping" }),
        });
        const payload = await response.json();
        if (!cancelled) setOnline(Boolean(payload?.ok));
      } catch {
        if (!cancelled) setOnline(false);
      }
    }
    void poll();
    const timer = window.setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <p className={`fairygui-bridge-status ${online ? "is-online" : "is-offline"}`} role="status">
      {online
        ? t("studio.fairygui.bridgeConnected")
        : t("studio.fairygui.bridgeOffline")}
    </p>
  );
}
