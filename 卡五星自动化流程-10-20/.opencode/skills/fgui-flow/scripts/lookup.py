#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fgui-flow · 定位：关键词 → 包 / 组件 / 节点 / 资源 / 中文备注。

只依赖 Python 标准库。数据来源（按优先级）：
  1) <工作层>/facts.json          —— 扫描器产出的机器可读事实表（主索引）；工作层 = .opencode/work
  2) <工作层>/美术清单.备注.txt    —— 中文说明的唯一来源（中文关键词主要靠它命中）
  3) 命中的组件 XML 本体          —— 只读，仅用于补 facts.json 里缺失的 gear/状态信息

工程根（assets/ + *.fairy）取 workspace.json 的 client_dir，取不到退回"向上找 *.fairy + assets"。

用法（在工作区根执行）：
  python .opencode/skills/fgui-flow/scripts/lookup.py 结算 结果
  python .opencode/skills/fgui-flow/scripts/lookup.py --comp MainResultLayer --nodes
  python .opencode/skills/fgui-flow/scripts/lookup.py --check
  python .opencode/skills/fgui-flow/scripts/lookup.py 头像 --json 命中.json

退出码：
  0  有命中
  1  facts.json 缺失 / 过期（先重跑扫描器）
  3  关键词命中 0 个 —— 会列出候选清单，交给人工确认，**不猜**

硬规矩：本脚本**只读**，不写工程、不改 facts.json。
"""

import argparse
import json
import sys
import time
from pathlib import Path

DOCS_DIR = "fgui文档"
FACTS_NAME = "facts.json"
NOTES_NAME = "美术清单.备注.txt"
SCAN_CMD = "python .opencode/skills/fgui-flow/scripts/scan_fgui.py"

# 命中结果的分类展示顺序
KIND_ORDER = ["包", "组件", "节点", "资源", "备注"]
KIND_TITLE = {
    "包": "包",
    "组件": "组件（要改的文件）",
    "节点": "节点（组件里的元素）",
    "资源": "资源（图片 / 字体 / 附属文件）",
    "备注": "中文备注（美术清单.备注.txt）",
}


def setup_stdout():
    """Windows 控制台默认 GBK，中文会炸；这里强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def find_root(explicit=None):
    """工程根：优先 --root，其次从脚本位置往上找，再退到 cwd 往上找（不绑死目录布局）。"""
    if explicit:
        return Path(explicit).resolve()
    here = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    for cand in list(here.parents)[:8] + [cwd, *list(cwd.parents)]:
        if (cand / DOCS_DIR / FACTS_NAME).exists() or (cand / "assets").is_dir() or any(cand.glob("*.fairy")):
            return cand
    return cwd


def resolve_workspace_paths(explicit_root=None):
    """用 `.opencode/lib/workspace.py` 解析 (工作区根, client 工程根, 工作层 out_root)。

    找不到工作区/库时返回 None —— 调用方退回旧口径（向上找 *.fairy + assets、读 工程根/fgui文档）。
    返回 dict：{"ws": Path, "project": Path|None, "work": Path}。
    """
    import importlib

    lib = Path(__file__).resolve().parents[3] / "lib"
    if not (lib / "workspace.py").is_file():
        return None
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    try:
        W = importlib.import_module("workspace")
    except Exception:
        return None
    try:
        ws = W.find_workspace_root(explicit_root)
    except SystemExit:
        return None
    cfg = W.load_config(ws)
    work = W.get_out_root(ws, cfg)
    project = None
    if explicit_root:
        p = Path(explicit_root).resolve()
        if p.is_dir():
            project = p
    if project is None:
        val = cfg.get("client_dir")
        if val:
            p = W.resolve_path(ws, val)
            if p and p.is_dir():
                project = p
    if project is None:
        project = W.find_fairy_root(explicit_root)
    return {"ws": ws, "project": project, "work": work}


def pick_facts(work_dirs, name):
    """在候选目录里挑第一个存在的文件（工作层优先，退回工程根/fgui文档）。"""
    for d in work_dirs:
        p = d / name
        if p.exists():
            return p
    return (work_dirs[0] / name) if work_dirs else Path(name)


def fmt_time(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def load_notes(path):
    """备注文件：一行一条 <关键词> = <中文说明>，与扫描器同一套解析规则。"""
    items = []
    if not path.exists():
        return items
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            items.append((key, value))
    return items


def notes_map(items):
    return {k.lower().replace("\\", "/"): v for k, v in items}


def note_of(nmap, *keys):
    for key in keys:
        if not key:
            continue
        got = nmap.get(str(key).lower().replace("\\", "/"))
        if got:
            return got
    return ""


def newest_source(root):
    """assets/ 与 settings/ 里最新的文件 —— 用来判断 facts.json 是否过期。"""
    newest = (0.0, "")
    for sub in ("assets", "settings"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            try:
                if p.is_file():
                    m = p.stat().st_mtime
                    if m > newest[0]:
                        newest = (m, str(p))
            except OSError:
                continue
    return newest


def read_component_xml(path):
    """直读组件 XML，取控制器与节点的 gear（facts.json 的 gears 字段是空的，见 --check 报告）。"""
    import xml.etree.ElementTree as ET

    root = ET.parse(str(path)).getroot()
    controllers = []
    for c in root.findall("controller"):
        raw = (c.get("pages") or "").split(",")
        pages = [(raw[i], raw[i + 1] if i + 1 < len(raw) else "") for i in range(0, len(raw), 2)]
        controllers.append(
            {
                "name": c.get("name", ""),
                "pages": pages,
                "selected": c.get("selected", ""),
                "actions": len(c.findall("action")),
                "exported": c.get("exported", "") == "true",
            }
        )
    nodes = []
    display = root.find("displayList")
    for el in (display if display is not None else []):
        gears = []
        for g in el:
            if g.tag.startswith("gear"):
                gears.append(
                    {
                        "kind": g.tag,
                        "controller": g.get("controller", ""),
                        "pages": g.get("pages", ""),
                        "values": g.get("values", ""),
                        "default": g.get("default", ""),
                    }
                )
        nodes.append(
            {
                "tag": el.tag,
                "name": el.get("name", ""),
                "id": el.get("id", ""),
                "xy": el.get("xy", ""),
                "size": el.get("size", ""),
                "visible": el.get("visible", ""),
                "group": el.get("group", ""),
                "controller": el.get("controller", ""),
                "src": el.get("src", ""),
                "fileName": el.get("fileName", ""),
                "url": el.get("url", ""),
                "text": el.get("text", ""),
                "gears": gears,
                "extra": [c.tag for c in el if c.tag in ("Button", "Label", "ProgressBar", "customProperty")],
            }
        )
    return {"size": root.get("size", ""), "controllers": controllers, "nodes": nodes}


class Index:
    """把 facts.json + 备注文件拍平成一堆可搜索条目。"""

    def __init__(self, facts, notes, root):
        self.facts = facts
        self.root = root
        self.notes = notes
        self.nmap = notes_map(notes)
        self.entries = []
        self.xml_cache = {}
        self._build()

    # ---------- 索引

    def _add(self, kind, key, blob_parts, payload):
        blob = " | ".join(str(p) for p in blob_parts if p)
        self.entries.append({"kind": kind, "key": key, "blob": blob.lower(), "payload": payload})

    def _build(self):
        facts = self.facts
        for pkg in facts.get("packages", []):
            desc = note_of(self.nmap, pkg.get("dir"), pkg.get("path"))
            self._add(
                "包",
                pkg.get("dir", ""),
                [pkg.get("dir"), pkg.get("id"), pkg.get("path"), desc],
                {"pkg": pkg.get("dir"), "id": pkg.get("id"), "path": pkg.get("path"), "note": desc},
            )
            for res in pkg.get("resources", []):
                rel = f"{pkg.get('dir')}/{res.get('relpath')}"
                rdesc = note_of(self.nmap, res.get("name"), rel)
                self._add(
                    "资源",
                    res.get("name", ""),
                    [res.get("name"), res.get("id"), res.get("path"), rel, res.get("type"), rdesc],
                    {
                        "pkg": pkg.get("dir"),
                        "name": res.get("name"),
                        "id": res.get("id"),
                        "type": res.get("type"),
                        "tag": res.get("tag"),
                        "relpath": res.get("relpath"),
                        "abs": f"{pkg.get('path')}/{res.get('relpath')}",
                        "dims": res.get("dims"),
                        "scale9grid": res.get("scale9grid"),
                        "exported": res.get("exported"),
                        "exists": res.get("exists"),
                        "atlas": res.get("atlas"),
                        "note": rdesc,
                    },
                )
        usage = {}
        for u in facts.get("usage", []):
            usage[(u.get("pkg"), u.get("id"))] = u.get("used_by", [])
        self.usage = usage

        for comp in facts.get("components", []):
            pkg = comp.get("pkg")
            rel = comp.get("relpath")
            desc = note_of(self.nmap, comp.get("file"), f"{pkg}/{rel}")
            ctrl = " ".join(c.get("name", "") for c in comp.get("controllers", []))
            self._add(
                "组件",
                f"{pkg}/{rel}",
                [comp.get("file"), pkg, rel, comp.get("initName"), comp.get("remark"), ctrl, desc],
                {"pkg": pkg, "file": comp.get("file"), "relpath": rel, "size": comp.get("size"),
                 "controllers": comp.get("controllers", []), "remark": comp.get("remark"),
                 "nodes_count": len(comp.get("nodes", [])), "note": desc},
            )
            for node in comp.get("nodes", []):
                ndesc = note_of(self.nmap, node.get("src_name"))
                self._add(
                    "节点",
                    f"{comp.get('file')} :: {node.get('name')}",
                    [node.get("name"), node.get("id"), node.get("tag"), node.get("type"),
                     node.get("src_name"), node.get("url_desc"), node.get("url_all"),
                     node.get("text"), node.get("controller"), node.get("group"), ndesc],
                    {"pkg": pkg, "comp": comp.get("file"), "relpath": rel, "node": node, "note": ndesc},
                )
        for key, value in self.notes:
            self._add("备注", key, [key, value], {"key": key, "value": value})

    # ---------- 搜索

    def search(self, keywords, limit):
        kws = [k.lower() for k in keywords]
        hits = []
        for e in self.entries:
            if all(k in e["blob"] for k in kws):
                score = 0
                for k in kws:
                    key = e["key"].lower()
                    name = Path(e["key"]).name.lower()
                    if k == key or k == name or k == Path(key).stem:
                        score += 3
                    elif key.startswith(k) or name.startswith(k):
                        score += 2
                    else:
                        score += 1
                hits.append((score, e))
        hits.sort(key=lambda x: (-x[0], KIND_ORDER.index(x[1]["kind"]), len(x[1]["key"])))
        out = {}
        for _, e in hits:
            out.setdefault(e["kind"], []).append(e)
        return {k: v[:limit] for k, v in out.items()}, sum(1 for _ in hits)

    def per_keyword(self, keywords, limit):
        """AND 命中为空时的兜底：每个关键词各自命中什么（只报告，不替人做决定）。"""
        out = []
        for kw in keywords:
            hits, total = self.search([kw], limit)
            out.append((kw, hits, total))
        return out

    # ---------- 组件详情

    def xml_of(self, pkg, relpath):
        key = (pkg, relpath)
        if key not in self.xml_cache:
            path = self.root / "assets" / pkg / relpath
            self.xml_cache[key] = read_component_xml(path) if path.exists() else None
        return self.xml_cache[key]

    def find_components(self, name, limit=5):
        name_l = name.lower().strip()
        if name_l.endswith(".xml"):
            name_l = name_l[:-4]
        found = []
        for comp in self.facts.get("components", []):
            stem = Path(comp.get("file", "")).stem.lower()
            if name_l in (stem, comp.get("file", "").lower(), comp.get("initName", "").lower()):
                found.append((3, comp))
            elif name_l and (name_l in stem or name_l in comp.get("relpath", "").lower()):
                found.append((1, comp))
        found.sort(key=lambda x: -x[0])
        return [c for _, c in found[:limit]]


# ----------------------------------------------------------------------------- 打印


def gear_pages_text(gear, controllers):
    """把 gearDisplay pages="3,4" 翻译成「控制器 C 的页 3,4」。"""
    pages = [p for p in (gear.get("pages") or "").split(",") if p != ""]
    name = gear.get("controller", "")
    page_names = {}
    for c in controllers or []:
        if c.get("name") == name:
            page_names = dict(c.get("pages", []))
    parts = []
    for p in pages:
        label = page_names.get(p, "")
        parts.append(f"{p}{'(' + label + ')' if label else ''}")
    return name, ",".join(parts)


def print_hits(idx, results, keywords, args):
    if not results:
        return
    print(f"\n== 关键词 {'  '.join(keywords)} —— 命中摘要 ==")
    for kind in KIND_ORDER:
        items = results.get(kind)
        if not items:
            continue
        print(f"\n---- {KIND_TITLE[kind]}（{len(items)}）----")
        for i, e in enumerate(items, 1):
            p = e["payload"]
            if kind == "包":
                print(f"[{i}] {p['pkg']}   包id={p['id']}")
                print(f"    目录：{p['path']}")
                if p["note"]:
                    print(f"    备注：{p['note']}")
            elif kind == "组件":
                ctrls = "、".join(f"{c.get('name')}({len(c.get('pages', []))}页)" for c in p["controllers"])
                print(f"[{i}] {p['pkg']}/{p['relpath']}   画布 {p['size'] or '未标注'}   节点 {p['nodes_count']}")
                print(f"    文件：assets/{p['pkg']}/{p['relpath']}")
                if ctrls:
                    print(f"    控制器：{ctrls}")
                if p["note"]:
                    print(f"    备注：{p['note']}")
                if not args.no_gears:
                    print_component_detail(idx, p["pkg"], p["relpath"], args, brief=True)
            elif kind == "节点":
                n = p["node"]
                pos = f"xy={n.get('xy') or '—'}"
                size = f"尺寸={n.get('size') or '继承/未标注'}"
                print(f"[{i}] {p['comp']} :: {n.get('name')}   ({n.get('type')}, {pos}, {size})")
                ref = n.get("src_name") or n.get("url_desc") or ""
                if ref:
                    print(f"    引用：{ref}")
                if n.get("text"):
                    print(f"    文本：{n['text']}")
                if p["note"]:
                    print(f"    备注：{p['note']}")
                detail = idx.xml_of(p["pkg"], p["relpath"])
                if detail:
                    for node in detail["nodes"]:
                        if node["name"] == n.get("name") or (node["id"] and node["id"] == n.get("id")):
                            for g in node["gears"]:
                                cname, pages = gear_pages_text(g, detail["controllers"])
                                print(f"    状态（gear 来自组件 XML）：{g['kind']} → 控制器 {cname} 页 {pages}")
                            if node.get("controller"):
                                print(f"    节点级控制器：{node['controller']}（属性写法「控制器名,页」= 设计期固定到该页）")
            elif kind == "资源":
                dims = "×".join(str(x) for x in p["dims"]) if p.get("dims") else "未记录"
                print(f"[{i}] {p['pkg']}/{p['relpath']}   {p['type']}   id={p['id']}   像素 {dims}")
                if p.get("scale9grid"):
                    print(f"    九宫格：{p['scale9grid']}")
                if p.get("note"):
                    print(f"    备注：{p['note']}")
                used = idx.usage.get((p["pkg"], p["id"]), [])
                if used:
                    head = "；".join(f"{u['comp']}::{u['node']}" for u in used[:4])
                    more = f" 等 {len(used)} 处" if len(used) > 4 else ""
                    print(f"    被引用：{head}{more}")
                else:
                    print("    被引用：无（组件 XML 里没有引用；代码侧动态引用本脚本看不到）")
            elif kind == "备注":
                print(f"[{i}] {p['key']} = {p['value']}")


def print_component_detail(idx, pkg, relpath, args, brief=False):
    detail = idx.xml_of(pkg, relpath)
    if not detail:
        print("    （读不到组件 XML 文件，可能已被移动或删除）")
        return
    if brief and not args.nodes and not detail["controllers"]:
        return
    print(f"    --- 组件 XML 直读：{pkg}/{relpath} 画布 {detail['size']} ---")
    for c in detail["controllers"]:
        pages = "、".join(f"{pid}{'(' + nm + ')' if nm else ''}" for pid, nm in c["pages"])
        extra = f" selected={c['selected']}" + (f" actions={c['actions']}" if c["actions"] else "")
        print(f"    控制器 {c['name']}：{len(c['pages'])} 页 [{pages}]{extra}")
    nodes = detail["nodes"]
    if brief and not args.nodes:
        return
    print(f"    节点 {len(nodes)} 个：")
    for n in nodes:
        size = n["size"] or ("继承" if n["tag"] in ("component", "loader") else "—")
        vis = "隐藏" if n["visible"] == "false" else ""
        print(f"      {n['name']:<22} {n['tag']:<10} xy={n['xy'] or '—':<12} size={size:<10} {vis}")
        for g in n["gears"]:
            cname, pages = gear_pages_text(g, detail["controllers"])
            vals = f"  values={g['values']}" if g["values"] else ""
            print(f"        状态 {g['kind']} → 控制器 {cname} 页 {pages}{vals}")
        if n["controller"]:
            print(f"        固定控制器：{n['controller']}")
        ref = n["src"] or n["url"] or ""
        if ref:
            print(f"        引用：{n['fileName'] or ref}")
        if n["text"]:
            print(f"        文本：{n['text']}")
        if n["extra"]:
            print(f"        扩展：{'、'.join(n['extra'])}")


def print_candidates(idx, args):
    print("\n== 关键词一个都没命中 —— 下面是候选清单，请人工指认（我不猜）==")
    comps = idx.facts.get("components", [])
    print(f"\n6 个包 / {len(comps)} 个组件：")
    cur = None
    for c in comps:
        if c["pkg"] != cur:
            cur = c["pkg"]
            print(f"  [{cur}]")
        note = note_of(idx.nmap, c.get("file"), f"{cur}/{c.get('relpath')}")
        print(f"    {c['relpath']:<30} 画布 {c.get('size') or '—':<12} {note}")
    print("\n备注文件里的关键词（可用来搜中文）：")
    keys = [k for k, _ in load_notes(idx.root / DOCS_DIR / NOTES_NAME)]
    print("  " + "、".join(keys[:40]) + (f" …共 {len(keys)} 条" if len(keys) > 40 else ""))
    print(f"\n提示：单个关键词分开搜、或换成文件里的英文名（如 MainResultLayer / ResultItem）再试。")


def print_gears_bug_report(idx):
    empty = sum(1 for c in idx.facts.get("components", []) for n in c.get("nodes", []) if not n.get("gears"))
    total = sum(len(c.get("nodes", [])) for c in idx.facts.get("components", []))
    xml_gears = 0
    for c in idx.facts.get("components", []):
        detail = idx.xml_of(c["pkg"], c["relpath"])
        if detail:
            xml_gears += sum(len(n["gears"]) for n in detail["nodes"])
    print("\n== 自查：facts.json 的 gears 字段 ==")
    print(f"  facts.json 里节点 {total} 个，其中 gears 非空的 {total - empty} 个 —— 字段实际为空")
    print(f"  组件 XML 里真实存在的 gear 元素：{xml_gears} 个")
    if xml_gears and total - empty == 0:
        print("  结论：扫描器（.opencode/skills/fgui-flow/scripts/scan_fgui.py 第 446 行）只看了节点的**属性**，")
        print("        而 FGUI 的 gear 是节点的**子元素**（<gearDisplay>/<gearIcon>…），所以字段恒为空。")
        print("        本脚本已改为定位时直读组件 XML 补状态信息（计划 02 §八 已记录）。")


# ----------------------------------------------------------------------------- 主流程


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(
        description="FGUI 工程关键词定位（只读）：关键词 → 包/组件/节点/资源/中文备注",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("keywords", nargs="*", help="关键词，可多个（要求同一个条目里全部出现）")
    ap.add_argument("--root", help="工程根目录（默认按脚本位置推断）")
    ap.add_argument("--comp", help="看某个组件的全部细节（接受 MainResultLayer / MainResultLayer.xml / 节点名）")
    ap.add_argument("--nodes", action="store_true", help="打印被命中组件的完整节点表")
    ap.add_argument("--no-gears", action="store_true", help="不直读组件 XML（只查 facts.json）")
    ap.add_argument("--check", action="store_true", help="只做事实表新鲜度与内容自查")
    ap.add_argument("--force", action="store_true", help="事实表过期也继续（默认拒绝）")
    ap.add_argument("--limit", type=int, default=8, help="每类最多显示几条（默认 8）")
    ap.add_argument("--json", dest="json_out", help="把命中结果写成 JSON 文件")
    args = ap.parse_args(argv)

    paths = resolve_workspace_paths(args.root)
    if args.root:
        root = Path(args.root).resolve()
    elif paths and paths.get("project"):
        root = paths["project"]
    else:
        root = find_root(None)

    cand_dirs = []
    if paths and paths.get("work"):
        cand_dirs.append(paths["work"])
    cand_dirs += [root / DOCS_DIR, root]
    facts_path = pick_facts(cand_dirs, FACTS_NAME)
    notes_path = pick_facts(cand_dirs, NOTES_NAME)

    print(f"工程根：{root}")
    if not facts_path.exists():
        print(f"❌ 找不到事实表：{facts_path}")
        print(f"   请先跑一次扫描器：{SCAN_CMD}")
        return 1

    facts_mtime = facts_path.stat().st_mtime
    src_mtime, src_file = newest_source(root)
    print(f"事实表：{facts_path.name}  生成于 {fmt_time(facts_mtime)}  大小 {facts_path.stat().st_size} B")
    if src_file:
        print(f"最新源文件：{src_file}  {fmt_time(src_mtime)}")
    stale = src_mtime > facts_mtime
    if stale and not args.force:
        print("❌ 事实表已过期（assets/ 或 settings/ 里有文件比它新）")
        print(f"   请先重跑扫描器：{SCAN_CMD}")
        print("   （确实要用旧数据，加 --force）")
        return 1
    print("事实表新鲜度：" + ("⚠ 已过期（--force 强制继续）" if stale else "✅ 未过期"))

    facts = json.loads(facts_path.read_text(encoding="utf-8-sig"))
    notes = load_notes(notes_path)
    if not notes:
        print(f"⚠ 读不到备注文件：{notes_path}（中文说明会缺失，定位中文关键词容易漏）")
    idx = Index(facts, notes, root)
    print(f"索引：{len(facts.get('packages', []))} 包 / {len(facts.get('components', []))} 组件 / "
          f"{len(facts.get('usage', []))} 条引用记录 / 备注 {len(notes)} 条")

    if args.check:
        print_gears_bug_report(idx)
        print("\n== 结论：事实表可用 ==")
        return 0

    if args.comp:
        comps = idx.find_components(args.comp)
        if not comps:
            print(f"\n❌ 找不到组件：{args.comp}")
            print_candidates(idx, args)
            return 3
        print(f"\n== 组件详情：{args.comp} ==")
        for c in comps:
            note = note_of(idx.nmap, c.get("file"), f"{c['pkg']}/{c.get('relpath')}")
            print(f"\n[{c['pkg']}/{c['relpath']}]  画布 {c.get('size') or '—'}")
            print(f"  文件：assets/{c['pkg']}/{c['relpath']}")
            if note:
                print(f"  备注：{note}")
            print_component_detail(idx, c["pkg"], c["relpath"], args)
            _print_uses(idx, c)
        return 0

    if not args.keywords:
        ap.print_help()
        return 0

    results, total = idx.search(args.keywords, args.limit)
    if not total:
        print(f"\n❌ 关键词 {'  '.join(args.keywords)}：命中 0 个")
        print("\n== 分开单搜的结果（仅供参考）==")
        best = None
        for kw, hits, kw_total in idx.per_keyword(args.keywords, 3):
            names = [f"{k}:{len(v)}" for k, v in hits.items()]
            print(f"  「{kw}」命中 {kw_total} 条  {'、'.join(names) if names else '（无）'}")
            if kw_total and (best is None or kw_total > best[1]):
                best = (kw, kw_total)
        if best:
            print(f"\n提示：这些词不是同时出现的；只想用命中最多的那个，就单独搜「{best[0]}」（{best[1]} 条）。")
        print_candidates(idx, args)
        return 3

    print_hits(idx, results, args.keywords, args)
    print(f"\n== 总命中 {total} 条（每类最多显示 {args.limit} 条）==")
    print("提醒：本脚本只能看到组件 XML 里的引用，代码侧的动态引用看不到（计划 02 §一 已声明）。")

    if args.json_out:
        payload = {
            "keywords": args.keywords,
            "generated_at": fmt_time(time.time()),
            "facts_mtime": fmt_time(facts_mtime),
            "hits": {k: [e["key"] for e in v] for k, v in results.items()},
        }
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"命中清单已写入：{out}")
    return 0


def _print_uses(idx, comp):
    """① 本组件引用了什么 ② 谁引用了本组件（影响面线索，来自 facts.json 的 usage 表）。"""
    refs = []
    for c in idx.facts.get("components", []):
        if c.get("pkg") == comp["pkg"] and c.get("relpath") == comp["relpath"]:
            for n in c.get("nodes", []):
                target = n.get("src_name") or n.get("url_desc") or ""
                if target:
                    refs.append(f"{n.get('name')} → {target}")
    if refs:
        print("  本组件引用的资源 / 子元件：")
        for r in dict.fromkeys(refs):
            print(f"    {r}")

    my_id = None
    for pkg in idx.facts.get("packages", []):
        if pkg.get("dir") != comp["pkg"]:
            continue
        for res in pkg.get("resources", []):
            if res.get("relpath") == comp["relpath"]:
                my_id = res.get("id")
    users = idx.usage.get((comp["pkg"], my_id), []) if my_id else []
    if users:
        print(f"  谁引用了本组件（影响面，共 {len(users)} 处）：")
        for u in users[:12]:
            print(f"    {u.get('pkg')}/{u.get('comp')} :: {u.get('node')}")
        if len(users) > 12:
            print(f"    …还有 {len(users) - 12} 处")
    else:
        print("  谁引用了本组件：组件 XML 里没有别处引用（可能由代码动态创建 / 或它就是根界面）")


if __name__ == "__main__":
    sys.exit(main())
