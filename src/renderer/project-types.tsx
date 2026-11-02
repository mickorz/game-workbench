import { Clapperboard, Gamepad2, Globe2, Image } from "./icons.js";
import { PROJECT_TYPE_IDS, type ProjectType } from "../shared/contracts.js";
import { t } from "./i18n.js";
export { defaultProjectName } from "../shared/project-names.js";

export interface ProjectTypeOption {
  label: string;
  value: ProjectType;
}


export const PROJECT_TYPES: readonly ProjectTypeOption[] = [
  ...PROJECT_TYPE_IDS.filter((value) => value !== "general"),
  "general" as const,
].map((value) => ({ value, label: projectTypeLabel(value) }));

// 当前工具只开放 FairyGUI 与素材画布；其余类型在侧边栏（sidebar-config）与新建入口一并隐藏，恢复时删除该过滤即可
const HIDDEN_PROJECT_TYPE_IDS = new Set(["web-game", "interactive-story", "godot-game", "general"] as const);

export const GAME_PROJECT_TYPES: readonly ProjectTypeOption[] = PROJECT_TYPES.filter(({ value }) => value !== "asset-canvas" && !HIDDEN_PROJECT_TYPE_IDS.has(value));

export function ProjectTypeIcon({ type, size = 14 }: { type: ProjectType; size?: number }) {
  if (type === "general") return <Gamepad2 size={size} aria-hidden="true" />;
  if (type === "web-game") return <Globe2 size={size} aria-hidden="true" />;
  if (type === "interactive-story") return <Clapperboard size={size} aria-hidden="true" />;
  if (type === "asset-canvas") return <Image size={size} aria-hidden="true" />;
  if (type === "fairygui") return <span className="project-type-fairygui-icon" style={{ width: size, height: size }} aria-hidden="true" />;
  return <span className="project-type-godot-icon" style={{ width: size, height: size }} aria-hidden="true" />;
}

export function projectTypeLabel(type: ProjectType): string {
  return PROJECT_TYPE_IDS.includes(type) ? t(`projectType.${type}`) : type;
}
