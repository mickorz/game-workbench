import type { ThreadItem } from "../shared/contracts.js";
import { mcpServerName } from "./mcp-tool-presentation.js";
import { t } from "./i18n.js";

export type ToolItem = Extract<ThreadItem, { type: "dynamicToolCall" | "mcpToolCall" }>;
export type ThinkingItem = Extract<ThreadItem, { type: "reasoning" }>;

export type WorkDisplayItem =
  | { kind: "item"; item: ThreadItem }
  | { kind: "tool-group"; id: string; tools: ToolItem[] }
  | { kind: "thinking"; item: ThinkingItem }
  | { kind: "waiting" };

export function projectWorkItems(items: ThreadItem[], { waiting = false }: { waiting?: boolean } = {}): WorkDisplayItem[] {
  const projected: WorkDisplayItem[] = [];
  let tools: ToolItem[] = [];

  function flushTools() {
    if (tools.length === 0) return;
    projected.push({ kind: "tool-group", id: tools[0].id, tools });
    tools = [];
  }

  for (const item of items) {
    if (item.type === "dynamicToolCall" || item.type === "mcpToolCall") {
      tools.push(item);
      continue;
    }
    flushTools();
    if (item.type === "reasoning") projected.push({ kind: "thinking", item });
    else projected.push({ kind: "item", item });
  }
  flushTools();
  // 排队占位：代理看似空闲（无进行中工具与思考）时显示等待动效。
  if (waiting) projected.push({ kind: "waiting" });
  return projected;
}

export function toolGroupSummary(tools: ToolItem[]): string {
  const categories = new Map<string, ToolItem[]>();
  for (const tool of tools.filter((item) => item.status !== "failed")) {
    const category = toolCategory(tool);
    categories.set(category, [...(categories.get(category) ?? []), tool]);
  }

  const phrases = [...categories]
    .sort(([left], [right]) => categoryOrder(left) - categoryOrder(right))
    .map(([category, items]) => categoryPhrase(category, items));
  const failed = tools.filter((item) => item.status === "failed").length;
  if (failed > 0) phrases.push(failed === 1 ? t("timeline.summary.actionFailed") : t("timeline.summary.actionsFailed"));
  if (phrases.length === 0) return t("timeline.summary.usedTools");
  const summary = phrases.join(t("timeline.summary.separator"));
  return summary[0].toUpperCase() + summary.slice(1);
}

function toolCategory(tool: ToolItem): string {
  if (tool.type === "mcpToolCall") return `mcp:${tool.server ?? ""}`;
  const toolName = tool.tool;
  if (toolName === "edit" || toolName === "write") return "edit";
  if (toolName === "read" || toolName === "grep" || toolName === "find" || toolName === "ls") return "read";
  if (toolName === "bash") return "command";
  if (toolName === "web_search") return "web-search";
  if (toolName === "game_use") return "playtest";
  return `tool:${toolName}`;
}

function categoryOrder(category: string): number {
  if (category === "edit") return 0;
  if (category === "read") return 1;
  if (category === "command") return 2;
  return 3;
}

function categoryPhrase(category: string, tools: ToolItem[]): string {
  if (category === "edit") return editedFilesPhrase(tools);
  if (category === "read") return tools.length === 1 ? t("timeline.summary.readFile") : t("timeline.summary.readFiles");
  if (category === "command") return tools.length === 1 ? t("timeline.summary.ranCommand") : t("timeline.summary.ranCommands");
  if (category === "web-search") return tools.length === 1 ? t("timeline.summary.searchedWeb") : t("timeline.summary.searchedWebMultiple");
  if (category === "playtest") return t("timeline.summary.playtested");
  if (category.startsWith("mcp:")) {
    const name = singularToolName(mcpServerName(category.slice("mcp:".length) || undefined));
    return usedToolsPhrase(name, tools.length);
  }
  return usedToolsPhrase(category.slice("tool:".length), tools.length);
}

function usedToolsPhrase(name: string, count: number): string {
  if (count !== 1) return t("timeline.summary.usedToolsNamed", { name });
  return indefiniteArticle(name) === "an" ? t("timeline.summary.usedToolAn", { name }) : t("timeline.summary.usedToolA", { name });
}

function editedFilesPhrase(tools: ToolItem[]): string {
  const targets = new Set(tools.map(toolTarget).filter(Boolean));
  const count = targets.size || tools.length;
  return count === 1 ? t("timeline.summary.editedFile") : t("timeline.summary.editedFiles");
}

function indefiniteArticle(value: string): "a" | "an" {
  const firstWord = value.trim().split(/\s+/, 1)[0] ?? "";
  if (/^[A-Z]{2,}$/.test(firstWord)) return /^[AEFHILMNORSX]/.test(firstWord) ? "an" : "a";
  return /^[aeiou]/i.test(firstWord) ? "an" : "a";
}

function singularToolName(value: string): string {
  return value.replace(/\s+tools?$/i, "");
}

function toolTarget(tool: ToolItem): string {
  const args = record(tool.arguments);
  return text(args?.path) || text(args?.file_path);
}

function record(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}
