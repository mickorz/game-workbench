#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《施工单》骨架：需求原文 → 施工依据文档（结构统一 + 自动塞入机械检查结果）。

只依赖 Python 标准库。脚本负责"结构与机械检查"，**语义解析（拆 A1/A2、资源分类、冲突判断）由模型填** ——
不替人做判断，不编造内容。

它会：
  1. 读需求原文 md，跑 check_terms.py 的检查，把结果填进《施工单》第一节；
  2. 把需求原文里的 `| A1 | … |` 条目表**原样搬**过来（缺列补空），省掉手工复制；
  3. 按固定结构生成骨架，人/模型只填 {{...}} 位置。

默认输出：与需求原文**同目录**的 `施工单.md`（即 `.opencode/work/<game_key>/<需求>/施工单.md`）。
已存在的文件**默认不覆盖**（避免抹掉已填的内容），要重生成得加 --force。

用法：
  python .opencode/skills/fgui-req/scripts/build_guide.py .opencode/work/<game_key>/<需求>/需求.md
  python .opencode/skills/fgui-req/scripts/build_guide.py 某需求.md --out 自定义路径.md --force
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True   # 别在技能目录里留 __pycache__
sys.path.insert(0, str(HERE))

import check_terms  # noqa: E402  （同目录，直接复用检查逻辑）

TEMPLATE = HERE / "施工单模板.md"
ITEM_ROW = re.compile(r"^\|\s*(A\d+)\s*\|(.+?)\|\s*$")


def setup_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def carry_item_rows(text):
    """把需求原文里的 | A1 | … | 行搬过来，并补上"负责人/新资源/验收点"三列。"""
    rows = []
    for raw in text.splitlines():
        m = ITEM_ROW.match(raw.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        while len(cells) < 4:
            cells.append("")
        rows.append((m.group(1), cells[:4]))
    if not rows:
        return "（需求原文里没有 `| A1 | … |` 形式的条目表，需要人工补）"
    out = ["| 编号 | 需求 | 影响文件/节点（实测） | 负责 | 新资源 | 验收点 |",
           "|---|---|---|---|---|---|"]
    for num, cells in rows:
        out.append(f"| {num} | {cells[0]} | {cells[1]} | 待填 | 待填 | 待填 |")
    return "\n".join(out)


def summarize_issues(issues):
    total = sum(len(v) for v in issues.values())
    if not total:
        return "✅ 未发现需要确认的项。"
    lines = []
    for key in ("A", "B", "C", "D", "E"):
        items = issues.get(key) or []
        if not items:
            continue
        lines.append(f"**【{key}】{check_terms.TITLES[key]}（{len(items)}）**")
        for it in items:
            rows = "、".join(str(x) for x in it.get("行", []))
            if key == "C":
                lines.append(f"- 行 {rows}：{it['说明']}")
            elif key == "D":
                lines.append(f"- 行 {rows}：{'、'.join(it['重复文案'])} —— {it['说明']}")
            elif key == "B":
                lines.append(f"- 「{it['正字']}」与「{it['变体']}」并存（行 {it['正字行']} / {it['变体行']}）→ 统一")
            else:
                lines.append(f"- 行 {rows}：「{it['命中']}」→ 建议「{it['建议正字']}」（{it['说明']}）")
        lines.append("")
    lines.append(f"> 合计 {total} 处，需要人工/策划确认后写进第五节。")
    return "\n".join(lines)


def guess_scope(text):
    """从需求原文里找"范围/不动"的表述：只取**最短**的一句，取不到就留占位让模型填。"""
    best = ""
    for raw in text.splitlines():
        s = raw.strip()
        if not any(k in s for k in ("禁止修改", "只改", "只动", "不相关")):
            continue
        s = re.sub(r"^[>#*\-\s]+", "", s)
        s = re.sub(r"^\d+[、.]\s*", "", s)
        s = s.replace("**", "").replace("`", "").strip("；;。 ")
        if s and (not best or len(s) < len(best)):
            best = s
    return best[:160] if best else "（需求里没写范围 → 待确认，见第五节）"


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(description="生成《施工单》骨架（结构 + 机械检查 + 条目搬运）")
    ap.add_argument("req", help="需求原文 md")
    ap.add_argument("--out", help="输出路径（默认 需求原文同目录的 施工单.md）")
    ap.add_argument("--terms", default=str(HERE / "terms.json"), help="术语表路径")
    ap.add_argument("--force", action="store_true", help="允许覆盖已存在的施工单")
    args = ap.parse_args(argv)

    req = Path(args.req)
    if not req.exists():
        print(f"❌ 需求原文不存在：{req}")
        return 1
    if not TEMPLATE.exists():
        print(f"❌ 模板不存在：{TEMPLATE}")
        return 1

    text = req.read_text(encoding="utf-8-sig")
    # 需求名：标准名 `需求.md` 时取所在目录名；否则取文件名
    name = req.parent.name if req.name == "需求.md" else req.stem
    out = Path(args.out) if args.out else req.with_name("施工单.md")
    if out.exists() and not args.force:
        print(f"❌ 已存在，拒绝覆盖：{out}")
        print("   要重新生成加 --force（会抹掉已填内容）")
        return 1

    cfg = check_terms.load_terms(args.terms)
    issues = check_terms.check_text(text, cfg)
    today = datetime.now().strftime("%Y-%m-%d")

    doc = TEMPLATE.read_text(encoding="utf-8-sig")
    replace = {
        "{{需求名}}": name,
        "{{需求原文路径}}": str(req).replace("\\", "/"),
        "{{来源}}": "需求截图/文档（原文见上述文件，逐条抄录）",
        "{{日期}}": today,
        "{{范围}}": guess_scope(text),
        "{{机械检查结果}}": summarize_issues(issues),
        "{{条目表}}": carry_item_rows(text),
        "{{资源清单路径}}": "（待填：资源清单的路径）",
        "{{复用摘要}}": "（待填：能直接用的资源 + 尺寸）",
        "{{生图摘要}}": "（待填：资源名，并在同一行补 尺寸/透明底/九宫格/数量/命名/依赖项）",
        "{{文字摘要}}": "（待填：程序填的文字内容 + 位置）",
        "{{冲突表}}": "| # | 冲突 | 处理口径 |\n|---|---|---|\n| — | （待填） | 以美术需求为准 |",
        "{{待确认表}}": "（待填：要拍什么）",
        "{{不做清单}}": "- （待填：明确不动的文件/包）",
        "{{影响面}}": "（待填：实测的节点/坐标/连带组件，例如「改了这里谁跟着要改」）",
    }
    for key, val in replace.items():
        doc = doc.replace(key, val)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")

    total = sum(len(v) for v in issues.values())
    print(f"✅ 已生成施工单：{out}")
    print(f"   需求原文：{req}（{len(text.splitlines())} 行）")
    print(f"   机械检查：{total} 处需要确认" + ("（明细已写进文档第一节）" if total else ""))
    left = [k for k in ("{{",) if k in doc]
    print(f"   待填占位：{'还有未替换的 ' + str(left) if left else '无（全部分配）'}")
    print("   下一步：填第三节资源清单（含 AI 生图规格）、第四节冲突口径、第五节决定清单（建议 + 不定会怎样）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
