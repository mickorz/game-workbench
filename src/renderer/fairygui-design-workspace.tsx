import { useCallback, useEffect, useRef, useState } from "react";
import type { ProjectState, PromptContext } from "../shared/contracts.js";
import { LoaderCircle, RefreshCw } from "./icons.js";
import { WorkspaceBackButton } from "./workspace-shell.js";
import { t } from "./i18n.js";
import "./fairygui-design.css";

/**
 * FairyGUI 工作室的设计页：
 * 左侧包/组件树（编辑器桥 list_packages / list_items），
 * 右侧组件真实渲染截图（focus_component + capture_component，FairyGUI 引擎级保真）
 * 与组件 XML 源码（read_component）。
 * 只读预览；修改走会话 agent（经插件 MCP 的 set_property 等工具）。
 */

const BRIDGE = "http://127.0.0.1:7531/";

interface BridgeResult<T> { ok: boolean; data?: T; error?: string }

async function bridgeCall<T>(cmd: string, args: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(BRIDGE, {
    method: "POST",
    headers: { "Content-Type": "text/plain" }, // 避免 CORS 预检（桥端已带 ACAO *）
    body: JSON.stringify({ cmd, args }),
  });
  const payload = (await response.json()) as BridgeResult<T>;
  if (!payload.ok) throw new Error(payload.error ?? cmd);
  return payload.data as T;
}

interface PkgInfo { id: string; name: string }
interface ItemInfo {
  id: string; name: string; type: string;
  children?: ItemInfo[];
}
interface CaptureResult { png: string; width: number; height: number }

function collectComponents(node: ItemInfo, pkgName: string, out: { pkg: string; name: string }[]): void {
  for (const child of node.children ?? []) {
    if (child.type === "component") out.push({ pkg: pkgName, name: child.name });
    else if (child.type === "folder") collectComponents(child, pkgName, out);
  }
}

export function FairyguiDesignWorkspace({ project, onContextChange, onLeave, initialComponent }: {
  project: ProjectState;
  onContextChange?: (context: PromptContext | undefined) => void;
  onLeave?: () => void;
  /** 从会话文本组件名点击进入时携带的目标；token 变化即重新选中 */
  initialComponent?: { pkg: string; name: string; token: number };
}) {
  const [packages, setPackages] = useState<PkgInfo[]>([]);
  // 包内组件按需加载：只有用户展开某包时才拉它的资源树，
  // 避免挂载时串行打满桥的单线程队列，导致会话里的 agent 工具调用排队超时
  const [pkgComponents, setPkgComponents] = useState<Record<string, { names: string[]; error?: string }>>({});
  const [expanded, setExpanded] = useState<string>();
  const [selected, setSelected] = useState<{ pkg: string; name: string }>();
  const [treePhase, setTreePhase] = useState<"loading" | "ready" | "error">("loading");
  const [treeError, setTreeError] = useState<string>();
  const [xml, setXml] = useState<string>();
  const [png, setPng] = useState<string>();
  const [detailPhase, setDetailPhase] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [detailError, setDetailError] = useState<string>();
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const loadTree = useCallback(async (): Promise<void> => {
    setTreePhase("loading");
    setTreeError(undefined);
    try {
      setPackages(await bridgeCall<PkgInfo[]>("list_packages"));
      setTreePhase("ready");
    } catch (cause) {
      setTreeError(cause instanceof Error ? cause.message : String(cause));
      setTreePhase("error");
    }
  }, []);

  useEffect(() => { void loadTree(); }, [loadTree]);

  // 从会话组件名点击进入：直接选中目标组件（并展开其所在包）
  useEffect(() => {
    if (!initialComponent) return;
    setSelected({ pkg: initialComponent.pkg, name: initialComponent.name });
    setExpanded(initialComponent.pkg);
    setPkgComponents((current) => current[initialComponent.pkg] ? current : { ...current, [initialComponent.pkg]: { names: [] } });
    void (async () => {
      try {
        const root = await bridgeCall<ItemInfo>("list_items", { pkg: initialComponent.pkg, depth: 2 });
        const out: { pkg: string; name: string }[] = [];
        collectComponents(root, initialComponent.pkg, out);
        setPkgComponents((current) => ({ ...current, [initialComponent.pkg]: { names: out.map((item) => item.name) } }));
      } catch { /* 树加载失败不影响主预览 */ }
    })();
  }, [initialComponent?.token]);

  const togglePackage = useCallback(async (pkgName: string): Promise<void> => {
    if (expanded === pkgName) { setExpanded(undefined); return; }
    setExpanded(pkgName);
    setSelected(undefined);
    if (pkgComponents[pkgName]) return;
    try {
      const root = await bridgeCall<ItemInfo>("list_items", { pkg: pkgName, depth: 2 });
      const out: { pkg: string; name: string }[] = [];
      collectComponents(root, pkgName, out);
      setPkgComponents((current) => ({ ...current, [pkgName]: { names: out.map((item) => item.name) } }));
    } catch (cause) {
      setPkgComponents((current) => ({ ...current, [pkgName]: { names: [], error: cause instanceof Error ? cause.message : String(cause) } }));
    }
  }, [expanded, pkgComponents]);

  // 选中组件：打开文档 → 截图 → 读 XML
  useEffect(() => {
    if (!selected) { setDetailPhase("idle"); return; }
    let cancelled = false;
    const target = selected;
    setDetailPhase("loading");
    setDetailError(undefined);
    setPng(undefined);
    setXml(undefined);
    (async () => {
      try {
        // focus_component：关掉编辑器里其它已开文档，保持「单一工作目标」
        await bridgeCall("focus_component", { pkg: target.pkg, name: target.name });
        const capture = await bridgeCall<CaptureResult>("capture_component", { scale: 1 });
        if (cancelled) return;
        setPng(`data:image/png;base64,${capture.png}`);
        const detail = await bridgeCall<{ xml: string }>("read_component", { pkg: target.pkg, name: target.name });
        if (!cancelled) { setXml(detail.xml); setDetailPhase("ready"); }
      } catch (cause) {
        if (!cancelled) { setDetailError(cause instanceof Error ? cause.message : String(cause)); setDetailPhase("error"); }
      }
    })();
    return () => { cancelled = true; };
  }, [selected]);

  // 设计上下文：选中组件即成为发消息的 chip，agent 能感知当前在看哪个组件
  useEffect(() => {
    onContextChange?.(selected ? { kind: "canvas-board", label: `${selected.pkg}/${selected.name}`, text: `FairyGUI 组件 ${selected.pkg}/${selected.name}` } : undefined);
  }, [selected, onContextChange]);

  useEffect(() => () => onContextChange?.(undefined), [onContextChange]);

  return (
    <section className="viewer-pane fairygui-design" aria-label={t("fairyguiDesign.title")}>
      {onLeave ? <div className="fairygui-design-back"><WorkspaceBackButton onClick={onLeave} label={t("fairyguiDesign.backToWorkspace")} /></div> : null}
      <div className="fairygui-design-tree">
        <h2 className="fairygui-design-tree-title">
          {t("fairyguiDesign.components")}
          <button className="icon-button" type="button" onClick={() => void loadTree()} title={t("common.refresh")} aria-label={t("common.refresh")}>
            {treePhase === "loading" ? <LoaderCircle className="spin" size={13} /> : <RefreshCw size={13} />}
          </button>
        </h2>
        {treePhase === "error" ? <p className="fairygui-design-error">{t("fairyguiDesign.bridgeOffline")}<br />{treeError}</p> : null}
        {treePhase === "ready" ? <ul className="fairygui-design-list">
          {packages.map((pkg) => {
            const entry = pkgComponents[pkg.name];
            const isOpen = expanded === pkg.name;
            return <li key={pkg.id} className="fairygui-design-pkg">
              <button type="button" className="fairygui-design-pkg-toggle" aria-expanded={isOpen} onClick={() => void togglePackage(pkg.name)}>
                <span className="fairygui-design-pkg-arrow" aria-hidden="true">{isOpen ? "▾" : "▸"}</span> {pkg.name}
              </button>
              {isOpen ? entry?.error ? <p className="fairygui-design-error">{entry.error}</p> : <ul>
                {(entry?.names ?? []).map((name) => {
                  const active = selected?.pkg === pkg.name && selected?.name === name;
                  return <li key={name}>
                    <button type="button" className={active ? "active" : ""} onClick={() => setSelected({ pkg: pkg.name, name })}>{name}</button>
                  </li>;
                })}
                {!entry ? <li className="fairygui-design-status">…</li> : null}
                {entry && !entry.names.length ? <li className="fairygui-design-status">{t("fairyguiDesign.noComponents")}</li> : null}
              </ul> : null}
            </li>;
          })}
        </ul> : null}
        {treePhase === "loading" ? <p className="fairygui-design-status">{t("fairyguiDesign.loadingTree")}</p> : null}
      </div>
      <div className="fairygui-design-detail">
        {detailPhase === "idle" ? <p className="fairygui-design-status">{t("fairyguiDesign.selectPrompt")}</p> : null}
        {detailPhase === "loading" ? <p className="fairygui-design-status"><LoaderCircle className="spin" size={14} /> {t("fairyguiDesign.loadingComponent")}</p> : null}
        {detailPhase === "error" ? <p className="fairygui-design-error">{detailError}</p> : null}
        {png ? <div className="fairygui-design-preview">
          <img src={png} alt={`${selected?.pkg}/${selected?.name}`} />
        </div> : null}
        {xml ? <details className="fairygui-design-xml" open>
          <summary>{t("fairyguiDesign.xmlSource")}</summary>
          <pre>{xml}</pre>
        </details> : null}
      </div>
    </section>
  );
}
