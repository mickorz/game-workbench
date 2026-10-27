import type { ParseKeys } from "i18next";
import brandMark from "../shared/assets/ohmygame-mark-v2.svg";
import type { SidebarPage } from "./routes.js";

/** 侧边栏导航图标（与 NavigationItem 的 icon 联合类型保持一致） */
export type SidebarIcon =
  | "home"
  | "project"
  | "library"
  | "general"
  | "web-game"
  | "interactive-story"
  | "godot"
  | "fairygui"
  | "asset-canvas"
  | "community"
  | "plugins";

/** 侧边栏导航分组：主导航 / 工作室 */
export type SidebarGroup = "main" | "studios";

/** 品牌配置：改这里即可换侧边栏品牌名与图标
 *  mark 填图片 URL（如 "./assets/ohmygame-mark-v2.svg"、"/my-logo.png" 或 data URI）
 */
export const SIDEBAR_BRAND = {
  /** 品牌名，同时用于文字展示与图标 alt */
  name: "xc-ui-flow",
  /** 品牌图标 URL；换图标改这里，不用改组件 */
  mark: brandMark as string,
} as const;

export interface SidebarItemConfig {
  /** 跳转目标页面 id（routes.ts 的 SidebarPage 成员） */
  id: SidebarPage;
  /** i18n 文案 key（如 "sidebar.home"，受 i18next 字面量联合类型约束） */
  labelKey: ParseKeys<"translation">;
  /** 图标 */
  icon: SidebarIcon;
  /** 分组；studios 组会带「工作室」分组标题 */
  group: SidebarGroup;
  /** 显示开关；false 时该项不渲染（路由仍可达） */
  visible?: boolean;
}

/** 侧边栏主导航配置：想增删改导航项、调整顺序或临时隐藏，只改这个数组 */
export const SIDEBAR_ITEMS: SidebarItemConfig[] = [
  { id: "home", labelKey: "sidebar.home", icon: "home", group: "main" },
  { id: "projects", labelKey: "sidebar.projects", icon: "project", group: "main" },
  { id: "library", labelKey: "sidebar.library", icon: "library", group: "main" },
  { id: "plugins", labelKey: "sidebar.plugins", icon: "plugins", group: "main" },
  { id: "community", labelKey: "sidebar.community", icon: "community", group: "main", visible: false },
  { id: "web-game", labelKey: "projectType.web-game", icon: "web-game", group: "studios" },
  { id: "interactive-story", labelKey: "projectType.interactive-story", icon: "interactive-story", group: "studios" },
  { id: "godot", labelKey: "projectType.godot-game", icon: "godot", group: "studios" },
  { id: "fairygui", labelKey: "projectType.fairygui", icon: "fairygui", group: "studios" },
  { id: "asset-canvas", labelKey: "projectType.asset-canvas", icon: "asset-canvas", group: "studios" },
  { id: "general", labelKey: "projectType.general", icon: "general", group: "studios" },
];
