import { isValidElement, memo, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Box, Check, Copy, FileCode2, FileText, Film, Image, Music2, type IconComponent } from "./icons.js";
import { t } from "./i18n.js";

export type WorkspaceFileIconKind = "code" | "text" | "image" | "video" | "audio" | "model" | "file";

const FILE_ICON_COMPONENTS: Record<WorkspaceFileIconKind, IconComponent> = {
  code: FileCode2,
  text: FileText,
  image: Image,
  video: Film,
  audio: Music2,
  model: Box,
  file: FileText,
};

const FILE_ICON_EXTENSIONS: Record<Exclude<WorkspaceFileIconKind, "file">, ReadonlySet<string>> = {
  code: new Set(["c", "cc", "cpp", "cs", "css", "cxx", "gd", "glsl", "go", "h", "hpp", "html", "htm", "java", "js", "jsx", "kt", "kts", "less", "lua", "mjs", "cjs", "php", "py", "rb", "rs", "sass", "scss", "shader", "sh", "sql", "svelte", "swift", "ts", "tscn", "tsx", "vue", "wgsl"]),
  text: new Set(["conf", "config", "csv", "env", "ini", "json", "jsonc", "lock", "md", "markdown", "text", "toml", "txt", "xml", "yaml", "yml"]),
  image: new Set(["avif", "bmp", "gif", "ico", "jpeg", "jpg", "png", "svg", "webp"]),
  video: new Set(["m4v", "mov", "mp4", "webm"]),
  audio: new Set(["aac", "flac", "m4a", "mp3", "ogg", "wav"]),
  model: new Set(["blend", "dae", "fbx", "glb", "gltf", "obj", "stl"]),
};

/** FGUI 组件名特征：大写开头、长度 >= 4、含内部大写或下划线（KW_BTN_ACTIVITY / C_LoginBtn / AwardBoxView），排除文件路径样式 */
const COMPONENT_NAME_BODY = "[A-Z][A-Za-z0-9_]{3,}";

/**
 * 把 agent 回复里的组件名统一替换为 fgui:// 伪链接，供 a: 分支拦截成可点击元素。
 * 覆盖三种源形态：[`NAME`](任意url)、[NAME](任意url)、`NAME`；围栏代码块内不动。
 */
const FENCED_CODE_RE = /\n```[\s\S]*?\n```|\n~~~[\s\S]*?\n~~~/g;
const LINKED_NAME_RE = new RegExp("\\[(`?(" + COMPONENT_NAME_BODY + ")`?)\\]\\(([^)]*)\\)", "g");
const NON_COMPONENT_URL_RE = /\\.(png|jpe?g|gif|webp|svg|md|pdf|zip|mp4|mp3|wav|json)$/i;
const BARE_TICK_NAME_RE = new RegExp("`(" + COMPONENT_NAME_BODY + ")`(?!\\]\\(fgui)", "g");

function linkifyComponentNames(text: string): string {
  return text
    .split(FENCED_CODE_RE)
    .map((part, index) => {
      if (index % 2 === 1) return part;
      let out = part.replace(LINKED_NAME_RE, (match: string, name: string, url: string) => {
        if (url.startsWith("fgui://") || NON_COMPONENT_URL_RE.test(url)) return match;
        return "[`" + name + "`](fgui://component/" + name + ")";
      });
      out = out.replace(BARE_TICK_NAME_RE, (match: string, name: string) => {
        if (/[.\\/]/.test(name)) return match;
        return "[`" + name + "`](fgui://component/" + name + ")";
      });
      return out;
    })
    .join("");
}

/** 放行自定义协议（react-markdown 默认 urlTransform 会把非 http 协议清洗成空串） */
function actionUrlTransform(url: string): string {
  return url;
}

export const MarkdownContent = memo(function MarkdownContent({ text, className = "", workspacePath, baseDir, onOpenWorkspaceFile, onComponentClick, onConfirmAction, renderImage }: {
  text: string;
  className?: string;
  workspacePath?: string;
  baseDir?: string;
  onOpenWorkspaceFile?: (path: string) => void;
  /** 启用后，code span 中的 FGUI 组件名（如 `KW_BTN_ACTIVITY`）变为可点击，回调收到组件名 */
  onComponentClick?: (name: string) => void;
  /** 启用后，requirement-check:// 确认链接变为可点击，回调收到确认动作 */
  onConfirmAction?: (action: string) => void;
  renderImage?: (src: string | undefined, alt: string | undefined) => ReactNode;
}) {
  // Stable component types keep loaded images mounted when only Markdown text changes.
  const components = useMemo<Components>(() => ({
    ...(renderImage ? { img: ({ src, alt }: { src?: string; alt?: string }) => renderImage(src, alt) } : {}),
    a: ({ href, children }) => {
      if (onComponentClick && href?.startsWith("fgui://component/")) {
        const componentName = decodeURIComponent(href.slice("fgui://component/".length));
        return <a className="fgui-component-link" href={href} title={`${t("fairyguiDesign.openComponent")}: ${componentName}`} onClick={(event) => {
          event.preventDefault();
          onComponentClick(componentName);
        }}>{children}</a>;
      }
      if (onConfirmAction && href?.startsWith("requirement-check://confirm/")) {
        const action = decodeURIComponent(href.slice("requirement-check://confirm/".length));
        return <a className="requirement-confirm-link" href={href} title={t("requirementPanel.confirmLinkTitle")} onClick={(event) => {
          event.preventDefault();
          onConfirmAction(action);
        }}>{children}</a>;
      }
      const filePath = onOpenWorkspaceFile ? workspaceLinkPath(href, workspacePath, baseDir) : undefined;
      if (filePath) {
        const iconKind = workspaceFileIconKind(filePath);
        const FileIcon = FILE_ICON_COMPONENTS[iconKind];
        return <a className="workspace-file-link" data-file-kind={iconKind} href={href} title={t("markdown.openInCode", { path: filePath })} onClick={(event) => {
          event.preventDefault();
          onOpenWorkspaceFile?.(filePath);
        }}><FileIcon size={13} aria-hidden="true" />{children}</a>;
      }
      return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
    },
    pre: MarkdownCodeBlock,
  }), [workspacePath, baseDir, onOpenWorkspaceFile, onComponentClick, onConfirmAction, renderImage]);

  const linkedText = useMemo(() => (onComponentClick ? linkifyComponentNames(text) : text), [text, onComponentClick]);
  return (
    <div className={`markdown-content${className ? ` ${className}` : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} urlTransform={onComponentClick || onConfirmAction ? actionUrlTransform : undefined}>
        {linkedText}
      </ReactMarkdown>
    </div>
  );
});

export function workspaceFileIconKind(filePath: string): WorkspaceFileIconKind {
  const name = filePath.split("/").at(-1)?.toLocaleLowerCase() ?? "";
  const extension = name.includes(".") ? name.split(".").at(-1) ?? "" : "";
  for (const [kind, extensions] of Object.entries(FILE_ICON_EXTENSIONS) as Array<[Exclude<WorkspaceFileIconKind, "file">, ReadonlySet<string>]>) {
    if (extensions.has(extension)) return kind;
  }
  return "file";
}

/** `baseDir` is the workspace-relative folder that relative links resolve against. */
export function workspaceLinkPath(href: string | undefined, workspacePath?: string, baseDir?: string): string | undefined {
  if (!href || href.startsWith("#")) return undefined;
  let value = href;
  if (/^file:/i.test(value)) {
    try {
      value = new URL(value).pathname;
    } catch {
      return undefined;
    }
  } else if (/^[a-z][a-z\d+.-]*:/i.test(value)) {
    return undefined;
  }
  value = value.split(/[?#]/, 1)[0];
  try {
    value = decodeURIComponent(value);
  } catch {
    return undefined;
  }
  value = value.replaceAll("\\", "/");
  value = value.replace(/:\d+(?::\d+)?$/, "");
  const root = workspacePath?.replaceAll("\\", "/").replace(/\/$/, "");
  if (/^\/[A-Za-z]:\//.test(value)) value = value.slice(1);
  const absolute = value.startsWith("/") || /^[A-Za-z]:\//.test(value);
  if (absolute) {
    if (!root || !pathWithinRoot(value, root)) return undefined;
    value = value.slice(root.length).replace(/^\/+/, "");
  }
  const parts: string[] = [];
  for (const part of [...(absolute || !baseDir ? [] : baseDir.split("/")), ...value.split("/")]) {
    if (!part || part === ".") continue;
    if (part !== "..") parts.push(part);
    else if (baseDir === undefined || !parts.pop()) return undefined;
  }
  if (parts.length === 0) return undefined;
  const filePath = parts.join("/");
  return looksLikeWorkspaceFile(filePath) ? filePath : undefined;
}

const EXTENSIONLESS_WORKSPACE_FILES = new Set(["agents.md", "dockerfile", "gemfile", "license", "makefile", "procfile", "rakefile"]);
const OTHER_WORKSPACE_FILE_EXTENSIONS = new Set(["data", "gitignore", "pdf", "wasm", "zip"]);

function looksLikeWorkspaceFile(filePath: string): boolean {
  const name = filePath.split("/").at(-1) ?? "";
  if (!name || name.endsWith("/")) return false;
  if (EXTENSIONLESS_WORKSPACE_FILES.has(name.toLocaleLowerCase())) return true;
  if (name.startsWith(".") && name.length > 1) return true;
  const extension = name.includes(".") ? name.split(".").at(-1)?.toLocaleLowerCase() : undefined;
  if (!extension) return false;
  return filePath.includes("/") || OTHER_WORKSPACE_FILE_EXTENSIONS.has(extension) ||
    Object.values(FILE_ICON_EXTENSIONS).some((extensions) => extensions.has(extension));
}

function pathWithinRoot(value: string, root: string): boolean {
  const insensitive = /^[A-Za-z]:\//.test(root);
  const candidate = insensitive ? value.toLocaleLowerCase() : value;
  const base = insensitive ? root.toLocaleLowerCase() : root;
  return candidate.startsWith(`${base}/`);
}

function MarkdownCodeBlock({ children }: { children?: ReactNode }) {
  const [copiedCode, setCopiedCode] = useState<string>();
  const code = nodeText(children).replace(/\n$/, "");
  const copied = copiedCode === code;
  const language = isValidElement<{ className?: string }>(children)
    ? children.props.className?.match(/language-([^\s]+)/)?.[1]
    : undefined;

  return (
    <div className="markdown-code-block">
      <div className="markdown-code-header">
        <span>{language ?? t("markdown.code")}</span>
        <button type="button" onClick={() => {
          void navigator.clipboard.writeText(code).then(() => setCopiedCode(code));
        }}>
          {copied ? <Check size={12} /> : <Copy size={12} />}
          <span>{copied ? t("common.copied") : t("common.copy")}</span>
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return nodeText(node.props.children);
  return "";
}
