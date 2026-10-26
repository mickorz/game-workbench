#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""动态加载 `.opencode/knowledge/*.md` —— 知识库会持续更新，所以技能不复制它的内容，
每次要用时现读（本脚本就是那条"现读"的通道）。

用法（在工作区根 = 含 .opencode 的那层跑）：

    python .opencode/skills/fgui-flow/scripts/knowledge.py              # 同 --list
    python .opencode/skills/fgui-flow/scripts/knowledge.py --list       # 知识库索引：每个文件的标题树
    python .opencode/skills/fgui-flow/scripts/knowledge.py --files      # 只印文件名（给脚本用）
    python .opencode/skills/fgui-flow/scripts/knowledge.py --topic 复用  # 按关键词取相关小节（可多次）
    python .opencode/skills/fgui-flow/scripts/knowledge.py --topic 九宫格 --topic 拉伸
    python .opencode/skills/fgui-flow/scripts/knowledge.py --path 复用技巧   # 印整个文件（按名字片段匹配）
    python .opencode/skills/fgui-flow/scripts/knowledge.py --check      # 自检：目录/文件/标题是否可检索

知识库位置（**唯一一份**）：<工作区根>/.opencode/knowledge/*.md。

退出码：0 正常；1 没命中（关键词/文件名）；3 知识库目录不存在或为空。
只用标准库；输出一律 UTF-8（Windows 控制台默认 GBK，已在启动时纠正）。
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

KB_SUBDIR = (".opencode", "knowledge")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
# 从 ## 标题里抽"可检索关键词"用：去掉编号前缀、截到第一个标点
ENUM_RE = re.compile(r"^\s*(?:[0-9]+[.、)）]|[〇零一二三四五六七八九十]+[、.．)）])\s*")
TOPIC_SPLIT_RE = re.compile(r"[：:（(、，,/|｜]")


def setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def find_root(explicit: str | None) -> Path:
    """定位工作区根（含 .opencode 的目录）：优先 --root，其次从脚本位置/cwd 往上找。"""
    if explicit:
        return Path(explicit).expanduser().resolve()

    here = Path(__file__).resolve()
    for base in [*list(here.parents), Path.cwd().resolve(), *list(Path.cwd().resolve().parents)]:
        if (base / ".opencode").is_dir():
            return base
    return Path.cwd().resolve()


def kb_dir(root: Path) -> Path:
    d = root / KB_SUBDIR[0] / KB_SUBDIR[1]
    if d.is_dir():
        return d
    # 兜底：按脚本位置（.opencode/skills/<技能>/scripts -> .opencode/knowledge）
    bundled = Path(__file__).resolve().parents[3] / "knowledge"
    return bundled if bundled.is_dir() else d


def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def split_sections(path: Path) -> tuple[str, list[dict]]:
    """把 md 拆成小节：每个标题 + 直到下一个同级或更高级标题之前的内容。

    代码块（``` / ~~~）里的 `#` 行不算标题 —— 知识库里常有示例代码，不能让它污染索引。
    """
    text = read_text(path)
    lines = text.splitlines()
    marks: list[tuple[int, int, str]] = []  # (行号, 级别, 标题)
    in_fence = False
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            marks.append((idx, len(m.group(1)), m.group(2)))

    sections: list[dict] = []
    if not marks:
        sections.append({"level": 0, "title": path.name, "start": 0, "end": len(lines), "lines": lines})
        return text, sections

    # 文件头（第一个标题之前）算一个无标题小节
    if marks[0][0] > 0:
        sections.append({"level": 0, "title": "(文件开头)", "start": 0, "end": marks[0][0], "lines": lines})

    for pos, (idx, level, title) in enumerate(marks):
        end = len(lines)
        for nxt_idx, nxt_level, _ in marks[pos + 1:]:
            if nxt_level <= level:
                end = nxt_idx
                break
        sections.append({"level": level, "title": title, "start": idx, "end": end, "lines": lines})
    return text, sections


def load_all(root: Path) -> list[tuple[Path, str, list[dict]]]:
    d = kb_dir(root)
    if not d.is_dir():
        return []
    out = []
    for path in sorted(d.glob("*.md")):
        text, sections = split_sections(path)
        out.append((path, text, sections))
    return out


def topic_keywords(docs: list[tuple[Path, str, list[dict]]], limit: int = 28) -> list[str]:
    """从各知识库文件的 ## 小节标题里，抽出可直接当 --topic 用的关键词。

    为什么要这个：技能（和 AGENTS.md）里写的 `--topic 复用 --topic 九宫格` 只是**例子**，
    知识库随时会多出新文件/新小节（例如后来补的"对齐与成组"）。让索引自己把
    "现在能查哪些词"报出来，就不依赖谁记得去改技能。
    """
    out: list[str] = []
    for _, _, sections in docs:
        for s in sections:
            if s["level"] != 2:
                continue
            head = TOPIC_SPLIT_RE.split(ENUM_RE.sub("", s["title"]))[0]
            head = re.sub(r"[`*\"'“”《》]", "", head).strip()
            if 2 <= len(head) <= 16 and head not in out:
                out.append(head)
    return out[:limit]


def fmt_date(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def cmd_list(root: Path, files_only: bool, quiet: bool) -> int:
    docs = load_all(root)
    d = kb_dir(root)
    if not docs:
        print(f"✗ 知识库为空或不存在：{d}", file=sys.stderr)
        print("  （知识库文档放在 .opencode/knowledge/*.md；没有就说明还没建）", file=sys.stderr)
        return 3
    if files_only:
        for path, _, _ in docs:
            print(path.name)
        return 0
    print(f"知识库目录：{d}")
    print(f"共 {len(docs)} 个文件（内容随文件实时变化，用 --topic / --path 取细节）\n")
    for path, text, sections in docs:
        size_kb = len(text.encode("utf-8")) / 1024
        print(f"■ {path.name}   {size_kb:.1f} KB   改于 {fmt_date(path.stat().st_mtime)}")
        headings = [s for s in sections if s["level"] > 0]
        if not headings:
            print("    ⚠ 没有 ## 标题，无法按主题检索（建议给知识库文件加标题）")
        for s in headings:
            print("    " + "  " * (s["level"] - 1) + "· " + s["title"])
        print()
    if not quiet:
        kws = topic_keywords(docs)
        if kws:
            print("▸ 可当 --topic 用的关键词（从各文件 ## 标题自动提取，知识库一变它就变）：")
            print("  " + "、".join(kws))
            print("  ⚠ 技能/AGENTS.md 里写的 --topic 例子只是**例子** —— 取词以本次索引为准，")
            print("    尤其别忘了排版那条线（对齐 / 成组 / 留白 / 间距 / 居中 / 锚点）。\n")
        print("提示：本索引由文件实时生成 —— 知识库更新后重跑本命令即可，技能里不复制其内容。")
    return 0


def cmd_files(root: Path) -> int:
    return cmd_list(root, files_only=True, quiet=True)


def cmd_topic(root: Path, topics: list[str], limit: int, max_chars: int) -> int:
    docs = load_all(root)
    if not docs:
        print(f"✗ 知识库为空或不存在：{kb_dir(root)}", file=sys.stderr)
        return 3
    hits = 0
    emitted = 0
    for topic in topics:
        needle = topic.lower()
        matched: list[tuple[int, Path, dict, str]] = []
        for path, _, sections in docs:
            # 只按"小节"检索：一级标题（文件大标题）覆盖全文，命中它等于倒出整份文件
            candidates = [s for s in sections if s["level"] >= 2]
            if not candidates:  # 该文件没有小节 → 退回整份（按标题/正文匹配）
                candidates = [s for s in sections if s["level"] == 0]
            for s in candidates:
                body = "\n".join(s["lines"][s["start"]:s["end"]])
                title_hit = needle in s["title"].lower()
                body_hit = needle in body.lower()
                if title_hit or body_hit:
                    rank = 0 if title_hit else 1  # 标题命中优先
                    matched.append((rank, path, s, body))
        if not matched:
            print(f"—— 主题「{topic}」：知识库里没命中 ——")
            print("   （要么这块还没写进知识库，要么换个词；先 --list 看索引）\n")
            continue
        matched.sort(key=lambda item: (item[0], item[1].name, item[2]["start"]))
        print(f"====== 主题「{topic}」：命中 {len(matched)} 节（标题命中优先）======")
        shown = 0
        for rank, path, s, body in matched:
            if shown >= limit or emitted >= max_chars:
                break
            mark = "◆" if rank == 0 else "·"
            print(f"\n--- {mark} {path.name} → {s['title']} ---")
            print(body.strip())
            emitted += len(body)
            shown += 1
            hits += 1
        if shown < len(matched):
            print(
                f"\n…（本主题还有 {len(matched) - shown} 节未印；用 --limit / --max-chars 调大，"
                f"或 --path <文件名> 看整份）"
            )
        print()
    return 0 if hits else 1


def cmd_path(root: Path, name: str) -> int:
    docs = load_all(root)
    if not docs:
        print(f"✗ 知识库为空或不存在：{kb_dir(root)}", file=sys.stderr)
        return 3
    needle = name.lower()
    exact = [d for d in docs if d[0].name.lower() == needle]
    partial = [d for d in docs if needle in d[0].name.lower() or needle in d[1].lower()[:200]]
    pick = exact or partial
    if not pick:
        print(f"✗ 没找到知识库文件：{name}", file=sys.stderr)
        print("  现有文件：" + "、".join(p.name for p, _, _ in docs), file=sys.stderr)
        return 1
    path, text, _ = pick[0]
    print(f"<!-- 来源：{path}（{fmt_date(path.stat().st_mtime)}）—— 以文件当前内容为准 -->")
    print(text)
    return 0


def cmd_check(root: Path) -> int:
    d = kb_dir(root)
    print(f"工作区根：{root}")
    print(f"知识库：{d}")
    if not d.is_dir():
        print("✗ 知识库目录不存在 → 技能无法加载知识库（第 0 步会失败）")
        return 3
    docs = load_all(root)
    if not docs:
        print("✗ 知识库目录存在但没有 .md 文件")
        return 3
    bad = 0
    print(f"✓ 找到 {len(docs)} 个知识库文件")
    for path, text, sections in docs:
        headings = [s for s in sections if s["level"] > 0]
        flag = "✓"
        if not headings:
            flag = "⚠ 无 ## 标题（不可按主题检索）"
            bad += 1
        print(f"  {flag} {path.name}  {len(text.encode('utf-8'))/1024:.1f} KB  {len(headings)} 个标题")
    kws = topic_keywords(docs)
    if kws:
        shown = "、".join(kws[:14]) + (" …" if len(kws) > 14 else "")
        print(f"  ✓ 可检索关键词 {len(kws)} 个：{shown}")
    print("\n结论：" + ("可以加载（有文件缺标题，建议补）" if bad else "可以加载"))
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(
        description="动态加载 .opencode/knowledge/*.md（技能不复制知识库内容，每次现读）",
    )
    ap.add_argument("--root", help="工作区根目录（含 .opencode；默认按脚本位置/当前目录推断）")
    ap.add_argument("--list", action="store_true", help="印知识库索引（文件 + 标题树）")
    ap.add_argument("--files", action="store_true", help="只印知识库文件名")
    ap.add_argument("--topic", action="append", default=[], help="按关键词取相关小节，可多次")
    ap.add_argument("--path", help="印整个知识库文件（按文件名片段匹配）")
    ap.add_argument("--check", action="store_true", help="自检知识库是否可加载/可检索")
    ap.add_argument("--limit", type=int, default=6, help="每个主题最多印几节（默认 6）")
    ap.add_argument("--max-chars", type=int, default=9000, help="总输出字符上限（默认 9000）")
    args = ap.parse_args(argv)

    root = find_root(args.root)

    if args.check:
        return cmd_check(root)
    if args.files:
        return cmd_files(root)
    if args.path:
        return cmd_path(root, args.path)
    if args.topic:
        return cmd_topic(root, args.topic, args.limit, args.max_chars)
    return cmd_list(root, files_only=False, quiet=False)


if __name__ == "__main__":
    raise SystemExit(main())
