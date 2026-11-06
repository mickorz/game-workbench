#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作区接线脚本：给已注册的类型生成专属工作区组件骨架并接入 project-shell 分支。

前置（缺一不可，否则 typecheck 会用 TS2367 拒绝接线）：
  1. 类型已注册（create-studio 技能的 12 步：PROJECT_TYPE_IDS 等已含 --key）；
  2. 已确认走方案 B（专属工作区），方案 A（canvas 契约定制）不够用。

两种接入形态（--mode）：
  design  整页替换型：仅 hash 带 /design 时渲染（fairygui 模式），
          文件 <key>-design-workspace.tsx，组件 <Key>DesignWorkspace
  full    完全替换型：整个会话页工作区都换（canvas/playable 模式），
          文件 <key>-workspace.tsx，组件 <Key>Workspace

做的事：组件文件从 templates/ 骨架渲染生成 + project-shell.tsx 接线
（import 行 + 分支 JSX；full 模式另改排除分支）。骨架只是接线可编译的最小壳，
内容区全是 TODO——语义步骤（内容区/数据契约/上下文联动）见 create-workspace-flow.md。

保护措施（宁停勿错）：组件文件已存在即报错；project-shell 已含该类型分支即报错
（防重复接线）；锚点在目标文件必须恰好 1 次；全部校验通过才写盘。

用法（仓库根执行）：
  python .claude/skills/create-workspace/scripts/wire.py --key demo --mode design --dry-run
  python .claude/skills/create-workspace/scripts/wire.py --key demo --mode design
  python .claude/skills/create-workspace/scripts/wire.py --key demo --mode full

退出码：0 成功；1 失败（前置未满足 / 锚点漂移 / 已接线）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]   # .claude/skills/create-workspace
REPO_ROOT = SKILL_DIR.parents[2]                  # 仓库根
TEMPLATES = SKILL_DIR / "templates"

# 接线规则：(目标文件, 锚点, 片段来源, 模式)
# 片段来源：("tmpl", 模板文件名) 或 ("inline", 字符串)；
# 模式：after（锚后插）/ before（锚前插）/ replace（整段替换，片段含锚原文）。
IMPORT_ANCHOR = 'import { FairyguiDesignWorkspace } from "./fairygui-design-workspace.js";'

RULES_DESIGN: list[tuple[str, str, tuple[str, str], str]] = [
    ("src/renderer/project-shell.tsx",
     IMPORT_ANCHOR,
     ("inline", '\nimport { {{Component}} } from "./{{key}}-design-workspace.js";'),
     "after"),
    ("src/renderer/project-shell.tsx",
     'project.type === "fairygui" && designOpen ? (',
     ("tmpl", "branch-design.tsx.tmpl"),
     "before"),
]

RULES_FULL: list[tuple[str, str, tuple[str, str], str]] = [
    ("src/renderer/project-shell.tsx",
     IMPORT_ANCHOR,
     ("inline", '\nimport { {{Component}} } from "./{{key}}-workspace.js";'),
     "after"),
    ("src/renderer/project-shell.tsx",
     'project.type !== "interactive-story" && project.type !== "asset-canvas"',
     ("inline", 'project.type !== "interactive-story" && project.type !== "asset-canvas" && project.type !== "{{key}}"'),
     "replace"),
    ("src/renderer/project-shell.tsx",
     '</Suspense> : <PlayableEditorWorkspace',
     ("tmpl", "branch-full.tsx.tmpl"),
     "replace"),
]

MODES = {
    "design": {
        "rules": RULES_DESIGN,
        "component_tpl": "component-design.tsx.tmpl",
        "file": "src/renderer/{key}-design-workspace.tsx",
    },
    "full": {
        "rules": RULES_FULL,
        "component_tpl": "component-full.tsx.tmpl",
        "file": "src/renderer/{key}-workspace.tsx",
    },
}


def render(source: tuple[str, str], values: dict[str, str]) -> str:
    """渲染片段：模板文件或内联字符串，替换 {{占位符}}，去尾换行。"""
    kind, payload = source
    text = (TEMPLATES / payload).read_text(encoding="utf-8") if kind == "tmpl" else payload
    for name, value in values.items():
        text = text.replace("{{" + name + "}}", value)
    return text.rstrip("\n")


def fail(message: str) -> None:
    print(f"[失败] {message}", file=sys.stderr)
    sys.exit(1)


def pascal(key: str) -> str:
    """key 连字符转 PascalCase：requirement-check -> RequirementCheck"""
    return "".join(part.capitalize() for part in key.split("-"))


def main() -> None:
    parser = argparse.ArgumentParser(description="专属工作区接线（组件骨架 + project-shell 分支）")
    parser.add_argument("--key", required=True, help="目标类型 id（必须已注册，create-studio 12 步已完成）")
    parser.add_argument("--mode", required=True, choices=["design", "full"],
                        help="design=整页替换型（仅 /design）；full=完全替换型（整个会话页）")
    parser.add_argument("--zh", default="", help="类型中文名（组件头注释用，缺省用 key）")
    parser.add_argument("--dry-run", action="store_true", help="只打印预览，不写盘")
    args = parser.parse_args()

    values = {
        "key": args.key,
        "Component": pascal(args.key) + ("DesignWorkspace" if args.mode == "design" else "Workspace"),
        "zh": args.zh or args.key,
    }
    spec = MODES[args.mode]
    shell_path = REPO_ROOT / "src/renderer/project-shell.tsx"
    component_path = REPO_ROOT / spec["file"].format(key=args.key)

    # 前置校验：类型已注册（contracts 里能查到，否则接线后 typecheck 必炸 TS2367）
    contracts = (REPO_ROOT / "src/shared/contracts.ts").read_text(encoding="utf-8")
    if f'"{args.key}"' not in contracts:
        fail(f'contracts.ts 不含类型 "{args.key}"——先跑 create-studio 技能完成类型注册，再来接线')

    # 校验：组件文件不存在、project-shell 未接线、锚点唯一
    if component_path.exists():
        fail(f"组件文件已存在：{component_path.relative_to(REPO_ROOT)}（已生成过？改内容直接编辑它）")
    shell = shell_path.read_text(encoding="utf-8")
    if f'"{args.key}"' in shell:
        fail(f'project-shell.tsx 已含 "{args.key}"（已接线？重复执行请先回滚）')

    # 同文件多规则递进应用（同 scaffold.py 的教训：后一条不能覆盖前一条）
    for relpath, anchor, source, mode in spec["rules"]:
        count = shell.count(anchor)
        if count != 1:
            fail(f"{relpath} 锚点出现 {count} 次（要求恰好 1 次），锚点已漂移：\n  {anchor[:70]}...")
        snippet = render(source, values)
        if mode == "after":
            shell = shell.replace(anchor, anchor + snippet)
        elif mode == "before":
            shell = shell.replace(anchor, snippet + anchor)
        else:  # replace
            shell = shell.replace(anchor, snippet)

    component = render(("tmpl", spec["component_tpl"]), values)

    if args.dry_run:
        print(f"[预览] 生成 {component_path.relative_to(REPO_ROOT)}（未写盘）")
        print(f"[预览] 接线 src/renderer/project-shell.tsx（{len(spec['rules'])} 处，未写盘）")
    else:
        component_path.write_text(component, encoding="utf-8", newline="\n")
        print(f"[写入] 生成 {component_path.relative_to(REPO_ROOT)}（骨架，内容区 TODO）")
        shell_path.write_text(shell, encoding="utf-8", newline="\n")
        print(f"[写入] 接线 src/renderer/project-shell.tsx（{len(spec['rules'])} 处）")

    print()
    print("接线完成（骨架只保证可编译）。剩余语义步骤（见 create-workspace-flow.md）：")
    print("  1. bun run typecheck（应零报错；TS2367 说明类型未注册）")
    print("  2. 填内容区：组件树 / 预览 / 专属 UI（模板里的 TODO 位）")
    print("  3. 数据契约接线（复用 canvas/ 或自定义并同步 agent 侧）")
    print("  4. 设计上下文联动（onContextChange 上报选中态）")
    print("  5. 验收：分支命中实测 + 回归四类既有工作区（flow 文档第 5 步）")


if __name__ == "__main__":
    main()
