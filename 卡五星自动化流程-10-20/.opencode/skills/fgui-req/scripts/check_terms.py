#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""需求文档机械检查：错别字 / 用词不统一 / 标签清单交叉核对 / 疑似语义矛盾。

只依赖 Python 标准库。**只读**需求文档，不改任何文件（除非显式给 --json）。

检查项（每项都给行号，方便人工核对）：
  A 错别字 / 异体字：命中 terms.json 里的「变体」
  B 用词不统一：同一份文档里正字与变体并存
  C 标签清单交叉核对：正文提到的【标签】与「正面/负面」清单互相补齐（双向差集）
  D 疑似语义矛盾：同一行里「输分玩家」和「赢分玩家」展示**同一文案**（通常应分「被X」）
  E 计分项字段名：胡分/杠分/漂分/马分/坎分/字分 等写错

退出码：0 = 没问题；4 = 有需要人工确认的项；1 = 用法/文件错误。

用法：
  python .opencode/skills/fgui-req/scripts/check_terms.py .opencode/work/<game_key>/<需求>/需求.md
  python .opencode/skills/fgui-req/scripts/check_terms.py --all
  python .opencode/skills/fgui-req/scripts/check_terms.py 某需求.md --json 检查结果.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK_DIR = Path(".opencode") / "work"     # --all 在此递归找 需求.md
DEFAULT_TERMS = HERE / "terms.json"
SCORE_TAIL = "分"          # 计分项字段名以「分」结尾
TAG_RE = re.compile(r"【([^】]{1,12})】")
TAG_CLEAN = re.compile(r"[*`\s]")          # 去掉加粗/空格：**【捉炮**胡】 → 捉炮胡
ARROW_SPLIT = re.compile(r"[，,、;；/／\s]+")
CHECK_OFF = "<!-- check:off -->"            # 这对标记之间的内容不检查（用于写自己的批注）
CHECK_ON = "<!-- check:on -->"


def setup_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_terms(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    terms = []
    for t in data.get("terms", []):
        canon = t.get("正字")
        if not canon:
            continue
        variants = [v for v in t.get("变体", []) if v and v != canon]
        terms.append({"canon": canon, "variants": variants, "note": t.get("说明", "")})
    return {
        "terms": terms,
        "label_ignore": set(data.get("label_ignore", [])),
        "list_prefixes": data.get("list_line_prefixes", ["正面", "负面"]),
        "score_fields": data.get("score_fields", []),
    }


def strip_md(line):
    s = line.strip()
    while s[:1] in (">", "-", "*", "#", "|"):
        s = s[1:].strip()
    s = s.rstrip("|").strip()
    return s


def check_text(text, cfg):
    lines = text.splitlines()
    issues = {"A": [], "B": [], "C": [], "D": [], "E": []}

    # 0) check:off / check:on 之间的内容是自己写的批注，不参与机械检查
    skipping = False
    checked = []
    for raw in lines:
        if CHECK_OFF in raw:
            skipping = True
        checked.append("" if skipping else raw)
        if CHECK_ON in raw:
            skipping = False
    lines = checked
    text = "\n".join(lines)

    # A / B —— 变体与不统一
    for t in cfg["terms"]:
        canon = t["canon"]
        hit_canon = [i + 1 for i, l in enumerate(lines) if canon in l]
        for v in t["variants"]:
            hit = [i + 1 for i, l in enumerate(lines) if v in l]
            if hit:
                issues["A"].append(
                    {"行": hit, "命中": v, "建议正字": canon, "说明": t["note"]})
                if hit_canon:
                    issues["B"].append(
                        {"正字": canon, "正字行": hit_canon, "变体": v, "变体行": hit})
        # 正字本身一次都没出现，但变体出现了 —— 也值得提醒
        if not hit_canon:
            for v in t["variants"]:
                if any(v in l for l in lines):
                    issues["E"].append(
                        {"行": [i + 1 for i, l in enumerate(lines) if v in l],
                         "命中": v, "建议正字": canon,
                         "说明": f"全文没有出现正字「{canon}」，疑似整体写错"})

    # C —— 标签清单交叉核对（同一个标签只报一次，列出全部行号）
    doc_tags, list_tags, list_where = {}, {}, {}
    for idx, raw in enumerate(lines, 1):
        for tag in TAG_RE.findall(raw):
            tag = TAG_CLEAN.sub("", tag)
            if tag:
                doc_tags.setdefault(tag, []).append(idx)
        s = strip_md(raw)
        for pref in cfg["list_prefixes"]:
            if s.startswith(pref):
                body = s[len(pref):].lstrip("：: ")
                for tok in ARROW_SPLIT.split(body):
                    tok = TAG_CLEAN.sub("", tok).strip("【】")
                    if tok:
                        list_tags.setdefault(tok, []).append(idx)
                        list_where.setdefault(tok, pref)
                break

    if list_tags:
        for tag, rows in doc_tags.items():
            if tag in cfg["label_ignore"] or tag in list_tags:
                continue
            if any(x.startswith(tag) or tag.startswith(x) for x in list_tags):
                continue
            issues["C"].append({
                "类型": "正文有、清单没有",
                "标签": tag, "行": rows,
                "说明": f"正文提到【{tag}】，但「正面/负面」清单里都没有它 —— 漏写，还是这个标签不用出现？"})
        for tag, rows in list_tags.items():
            if tag in doc_tags or tag in cfg["label_ignore"]:
                continue
            issues["C"].append({
                "类型": "清单有、正文没提",
                "标签": tag, "行": rows,
                "说明": f"{list_where.get(tag, '')}清单里的「{tag}」在正文规则里没有出现 —— 疑似错别字或规则漏写"})

    # D —— 同一行输分/赢分展示同一文案
    for idx, raw in enumerate(lines, 1):
        if "输分" in raw and "赢分" in raw:
            tags = [TAG_CLEAN.sub("", t) for t in TAG_RE.findall(raw)]
            tags = [t for t in tags if t]
            if len(tags) >= 2 and len(set(tags)) < len(tags):
                dup = [x for x in set(tags) if tags.count(x) > 1]
                issues["D"].append({
                    "行": [idx], "重复文案": dup,
                    "说明": "同一行里输分玩家和赢分玩家展示完全相同的文案 —— 通常应该分「被X」两种，请确认"})

    # E —— 计分项字段名
    for field in cfg["score_fields"]:
        if field in text:
            continue
        for t in cfg["terms"]:
            if field in t["variants"]:
                for idx, raw in enumerate(lines, 1):
                    if field in raw:
                        issues["E"].append({"行": [idx], "命中": field, "建议正字": t["canon"],
                                            "说明": "计分项字段名写错"})
    return issues


TITLES = {
    "A": "错别字 / 异体字",
    "B": "用词不统一（同一份文档里两种写法并存）",
    "C": "标签清单交叉核对",
    "D": "疑似语义矛盾",
    "E": "其它用词问题",
}


def format_report(path, issues):
    total = sum(len(v) for v in issues.values())
    out = [f"检查文件：{path}", f"结论：{'✅ 未发现需要确认的项' if not total else f'⚠ 发现 {total} 处需要人工确认'}"]
    for key in ("A", "B", "C", "D", "E"):
        items = issues.get(key) or []
        if not items:
            continue
        out.append(f"\n【{key}】{TITLES[key]}（{len(items)}）")
        for it in items:
            line = "、".join(str(x) for x in it.get("行", []))
            if key == "A":
                out.append(f"  行 {line}：「{it['命中']}」→ 建议「{it['建议正字']}」（{it['说明']}）")
            elif key == "B":
                out.append(f"  「{it['正字']}」行 {it['正字行']} 与「{it['变体']}」行 {it['变体行']} 并存 → 统一成一种写法")
            elif key == "C":
                out.append(f"  行 {line}：{it['类型']} —— {it['说明']}")
            elif key == "D":
                out.append(f"  行 {line}：{'、'.join(it['重复文案'])} —— {it['说明']}")
            else:
                out.append(f"  行 {line}：「{it['命中']}」→ 建议「{it['建议正字']}」（{it['说明']}）")
    out.append("\n提醒：这里只做机械检查（用词、清单一致性）；"
               "「这句需求到底是什么意思」要靠人确认，脚本不替你判断。")
    return "\n".join(out)


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(description="需求文档机械检查：错别字 / 清单一致性 / 疑似矛盾")
    ap.add_argument("files", nargs="*", help="要检查的需求 md")
    ap.add_argument("--all", action="store_true", help="检查 fgui文档/需求/ 下所有 md")
    ap.add_argument("--terms", default=str(DEFAULT_TERMS), help="术语表路径（默认技能自带 terms.json）")
    ap.add_argument("--json", dest="json_out", help="把结果写成 JSON")
    args = ap.parse_args(argv)

    cfg = load_terms(args.terms)
    targets = []
    if args.all:
        base = Path.cwd() / WORK_DIR
        if not base.is_dir():
            print(f"❌ 找不到需求目录：{base}")
            return 1
        targets = sorted(base.rglob("需求.md"))
    targets += [Path(p) for p in args.files]
    if not targets:
        ap.print_help()
        print("\n至少要给一个文件，或加 --all")
        return 1

    payload, bad = {}, 0
    for path in targets:
        if not path.exists():
            print(f"❌ 文件不存在：{path}")
            return 1
        issues = check_text(path.read_text(encoding="utf-8-sig"), cfg)
        print(format_report(path, issues))
        print()
        payload[str(path)] = issues
        bad += sum(len(v) for v in issues.values())

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结果已写入：{out}")
    return 4 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
