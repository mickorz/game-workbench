#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新增工作室脚手架：读 templates/ 渲染片段，按锚点插入目标文件。

覆盖 add-studio-flow.md 12 步中全部机械插入点（步骤 1~9、11 + 双图标 SVG）：
类型契约 / 工作室条目 / 双语文案 / 路由 / 侧边栏 / CSS mask / 页面分发 /
类型图标分支 / 发布边界 / daemon 文案。不做语义步骤：文案打磨、图标选型、
验收、commit——见 add-studio-flow.md。

插入语义统一：锚点文本原样保留，片段插在锚点之后（片段自带前缀换行/空格）。
锚点基准：全部锚定 fairygui（PROJECT_TYPE_IDS 只加不减，fairygui 永在，
锚不随新增漂移）；新工作室统一插在 fairygui 之后（顺序无功能影响）。
保护措施（宁停勿错，错误完整暴露）：
  - 锚点在目标文件必须恰好出现 1 次，漂移即报错中止；
  - 目标文件已含新 key 时报错退出（防重复脚手架）；
  - 全部校验通过才写盘，不写半截。

用法（仓库根执行）：
  python .claude/skills/create-studio/scripts/scaffold.py --key demo --zh 演示 --en Demo --dry-run
  python .claude/skills/create-studio/scripts/scaffold.py --key demo --zh 演示 --en Demo
  python .claude/skills/create-studio/scripts/scaffold.py --key demo --zh 演示 --en Demo \
      --title-zh "要演示什么？" --title-en "What to demo?" \
      --placeholder-zh "描述…" --placeholder-en "Describe..." \
      --new-zh "新建演示项目" --new-en "New demo project" \
      --icon path/to/icon.svg

缺省文案草案（交付后可改，改法见 add-studio-flow.md「修改已有工作室」）：
  title = 类型中/英文名；placeholder = "描述你的<名>…" / "Describe your <en>..."；
  new = "新建<名>项目" / "New <en> project"。图标缺省复制 templates/icon.svg 占位。

退出码：0 成功；1 失败（锚点漂移 / key 已存在 / 文件缺失）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]   # .claude/skills/create-studio
REPO_ROOT = SKILL_DIR.parents[2]                  # 仓库根
TEMPLATES = SKILL_DIR / "templates"

# 每条规则：(目标文件, 锚点, 插入片段来源)
# 片段来源：("tmpl", 模板文件名) 读 templates/ 渲染；("inline", 字符串) 直接渲染。
# 片段自带前缀（换行/空格），渲染后统一去掉尾部换行。
EDIT_RULES: list[tuple[str, str, tuple[str, str]]] = [
    # 步骤 1：类型契约（PROJECT_TYPE_IDS 末尾追加）
    ("src/shared/contracts.ts",
     '"godot-game", "fairygui"',
     ("inline", ', "{{key}}"')),
    # 步骤 2：工作室条目（GAME_STUDIOS 末尾，接在 fairygui 条目后）
    ("src/renderer/studios.ts",
     '    newLabel: t("studio.fairygui.new"),\n  },',
     ("tmpl", "studio-entry.ts.tmpl")),
    # 步骤 3：双语文案（projectType 块 + studio 块，两个 locales 同 commit）
    ("src/renderer/locales/zh-CN.ts",
     '    fairygui: "FairyGUI",',
     ("inline", '\n    "{{key}}": "{{zh}}",')),
    ("src/renderer/locales/zh-CN.ts",
     '      bridgeOffline: "编辑器桥：未连接（启动编辑器或检查插件）",\n    },',
     ("tmpl", "locale-studio-block-zh.tmpl")),
    ("src/renderer/locales/en.ts",
     '    fairygui: "FairyGUI",',
     ("inline", '\n    "{{key}}": "{{en}}",')),
    ("src/renderer/locales/en.ts",
     '      bridgeOffline: "Editor bridge: offline (start the editor or check the plugin)",\n    },',
     ("tmpl", "locale-studio-block-en.tmpl")),
    # 步骤 4：路由（SidebarPage 联合 + SIDEBAR_PAGES 白名单）
    ("src/renderer/routes.ts",
     '  | "fairygui"',
     ("inline", '\n  | "{{key}}"')),
    ("src/renderer/routes.ts",
     '"godot", "fairygui",',
     ("inline", ' "{{key}}",')),
    # 步骤 5：侧边栏（SidebarIcon 联合 + SIDEBAR_ITEMS 条目，默认可见）
    ("src/renderer/sidebar-config.ts",
     '  | "fairygui"',
     ("inline", '\n  | "{{key}}"')),
    ("src/renderer/sidebar-config.ts",
     '{ id: "fairygui", labelKey: "projectType.fairygui", icon: "fairygui", group: "studios" },',
     ("inline", '\n  { id: "{{key}}", labelKey: "projectType.{{key}}", icon: "{{key}}", group: "studios" },')),
    # 步骤 7：页面分发（key 与类型同名，直接走 route.page）
    ("src/renderer/app.tsx",
     'route.page === "fairygui"',
     ("inline", ' || route.page === "{{key}}"')),
    # 步骤 8：项目类型图标分支
    ("src/renderer/project-types.tsx",
     '  if (type === "fairygui") return <span className="project-type-fairygui-icon" style={{ width: size, height: size }} aria-hidden="true" />;',
     ("inline", '\n  if (type === "{{key}}") return <span className="project-type-{{key}}-icon" style={{ width: size, height: size }} aria-hidden="true" />;')),
    # 步骤 9：发布边界
    ("src/renderer/coding-workspace.tsx",
     'project?.type === "fairygui" ||',
     ("inline", ' project?.type === "{{key}}" ||')),
    # 步骤 6/8 的 CSS：两处图标类（接在 fairygui 对应块后）
    ("src/renderer/styles.css",
     '-webkit-mask-image: url("./assets/sidebar/fairygui.svg");\n}',
     ("tmpl", "home-nav-icon.css.tmpl")),
    ("src/renderer/styles.css",
     'mask: url("./assets/fairygui.svg") center / contain no-repeat;\n}',
     ("tmpl", "project-type-icon.css.tmpl")),
    # 步骤 11：daemon 文案（projectTypes 合法值清单）
    ("src/daemon/plugin-authoring.ts",
     "asset-canvas, fairygui",
     ("inline", ", {{key}}")),
]


def render(source: tuple[str, str], values: dict[str, str]) -> str:
    """渲染插入片段：模板文件或内联字符串，替换 {{占位符}}，去尾换行。"""
    kind, payload = source
    text = (TEMPLATES / payload).read_text(encoding="utf-8") if kind == "tmpl" else payload
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    return text.rstrip("\n")


def fail(message: str) -> None:
    print(f"[失败] {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="新增工作室脚手架（机械插入自动化）")
    parser.add_argument("--key", required=True, help="类型 id（小写连字符，如 requirement-check）")
    parser.add_argument("--zh", required=True, help="类型中文名（如 需求检查）")
    parser.add_argument("--en", required=True, help="类型英文名（如 Requirement Check）")
    parser.add_argument("--title-zh"), parser.add_argument("--title-en")
    parser.add_argument("--placeholder-zh"), parser.add_argument("--placeholder-en")
    parser.add_argument("--new-zh"), parser.add_argument("--new-en")
    parser.add_argument("--icon", help="单色镂空 SVG 路径；缺省用 templates/icon.svg 占位")
    parser.add_argument("--dry-run", action="store_true", help="只打印预览，不写盘")
    args = parser.parse_args()

    values = {
        "key": args.key,
        "zh": args.zh,
        "en": args.en,
        "title_zh": args.title_zh or args.zh,
        "title_en": args.title_en or args.en,
        "placeholder_zh": args.placeholder_zh or f"描述你的{args.zh}…",
        "placeholder_en": args.placeholder_en or f"Describe your {args.en}...",
        "new_zh": args.new_zh or f"新建{args.zh}项目",
        "new_en": args.new_en or f"New {args.en} project",
    }

    # 先全量读文件 + 校验（锚点唯一、key 未存在），任一失败即中止，不写半截。
    # 同文件多条规则递进应用（后一条在前一条的结果上 replace），
    # 幂等检查基于原始文本（防同文件后续规则误判 key 已存在）。
    current: dict[Path, str] = {}
    orig: dict[Path, str] = {}
    for relpath, anchor, source in EDIT_RULES:
        path = REPO_ROOT / relpath
        if path not in current:
            if not path.exists():
                fail(f"目标文件不存在：{relpath}")
            text = path.read_text(encoding="utf-8")
            current[path] = orig[path] = text
        marker = f'"{args.key}"'
        if marker in orig[path]:
            fail(f"{relpath} 已含 {marker}，key 可能已脚手架过；重复执行请先回滚")
        count = current[path].count(anchor)
        if count != 1:
            fail(f"{relpath} 锚点出现 {count} 次（要求恰好 1 次），锚点已漂移：\n  {anchor[:70]}...")
        current[path] = current[path].replace(anchor, anchor + render(source, values))

    # 图标两处（内容相同，文件名 = key）
    icon_src = Path(args.icon).resolve() if args.icon else TEMPLATES / "icon.svg"
    if not icon_src.exists():
        fail(f"图标文件不存在：{icon_src}")
    icon_targets = [REPO_ROOT / f"src/renderer/assets/sidebar/{args.key}.svg",
                    REPO_ROOT / f"src/renderer/assets/{args.key}.svg"]
    for target in icon_targets:
        if target.exists():
            fail(f"图标目标已存在：{target}")

    for path, new in current.items():
        relpath = path.relative_to(REPO_ROOT).as_posix()
        if args.dry_run:
            print(f"[预览] {relpath}（未写盘）")
        else:
            path.write_text(new, encoding="utf-8", newline="\n")
            print(f"[写入] {relpath}")
    for target in icon_targets:
        if args.dry_run:
            print(f"[预览] 图标 {target.relative_to(REPO_ROOT)}（未写盘）")
        else:
            shutil.copyfile(icon_src, target)
            icon_note = "占位图标" if not args.icon else "用户图标"
            print(f"[写入] 图标 {target.relative_to(REPO_ROOT)}（{icon_note}）")

    print()
    print("机械插入完成。剩余语义步骤（见 add-studio-flow.md）：")
    print("  1. bun run typecheck（护航报错清零才算结构完整）")
    print("  2. 文案打磨：改 src/renderer/locales/{zh-CN,en}.ts 的 studio.<key> 块（双语同改）")
    print("  3. 图标换真 SVG（可选）：替换两处 svg 文件，选型法见流程步骤 6")
    print("  4. 验收：daemon 重启 + 浏览器实测（流程文档「验收」节）")
    print("  5. commit：feat: add <key> studio (project type + sidebar + boundaries)")


if __name__ == "__main__":
    main()
