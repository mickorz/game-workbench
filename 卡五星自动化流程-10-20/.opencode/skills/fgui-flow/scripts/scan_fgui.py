#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FGUI 工程扫描器（skill: fgui-flow · s2 备事实底座）

生成两份文档 + 一份事实表，全部落在**工作层** `<工作区根>/.opencode/work/` 下：
  - 工程结构.md      技术 / LLM 用：包 ID、资源 id、导出标记、组件节点、引用关系、异常
  - 美术资源清单.md  美术 / 策划 用：中文说明、图片尺寸、九宫格、被哪些界面引用、没人用的图
  - facts.json       机器可读事实表：供其它技能/脚本快速定位，不必重扫工程

工程根（`assets/` + `settings/` + `*.fairy` 所在层）取 `.opencode/workspace.json` 的 `client_dir`；
取不到时退回"向上找 `*.fairy` + `assets/`"。输出目录默认 = `out_root`（`.opencode/work`）。
中文说明读 `<输出目录>/美术清单.备注.txt`（一行一条：关键词 = 中文说明）。

事实全部来自 package.xml、组件 xml、图片文件头；不做猜测。

用法（在工作区根 = 含 .opencode 的那层执行）：
    python .opencode/skills/fgui-flow/scripts/scan_fgui.py [--root 工程目录] [--out 输出目录] [--json 事实表路径] [--no-art] [--no-struct]
仅依赖 Python 标准库。
"""

import argparse
import datetime
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

STRUCT_OUT = "工程结构.md"
ART_OUT = "美术资源清单.md"
NOTES_FILE = "美术清单.备注.txt"
DOCS_DIR = "fgui文档"          # 兜底输出目录（正常走 out_root = .opencode/work）
FACTS_OUT = "facts.json"       # 机器可读事实表（供 lookup 等快速定位，不必重扫）

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
SPINE_EXT = {".json"}

RES_TYPE_ZH = {
    "image": "图片",
    "component": "组件",
    "spine": "Spine 动画",
    "font": "位图字体",
    "misc": "附属文件",
    "sound": "音效",
    "movieclip": "序列帧动画",
    "folder": "目录",
}

NODE_TYPE_ZH = {
    "image": "图片",
    "text": "文本",
    "richtext": "富文本",
    "inputtext": "输入框",
    "loader": "装载器（代码换图）",
    "loader3D": "Spine/3D 装载器",
    "component": "子元件",
    "list": "列表",
    "group": "组",
    "graph": "图形",
    "movieclip": "序列帧动画",
    "tree": "树",
    "label": "标签",
}

DIR_ROLE = {
    "atlas": "打进本包图集的图片（发布时合并成图集）",
    "alone": "单独图集（package.xml 标记 atlas，不并入主图集、非 2 次幂）",
    "effect": "Spine 动画目录（.json + .atlas + .png 三件套，必须同名同改）",
    "fnt": "位图字体目录（.fnt + 同名字模 png 子目录）",
    "component": "可复用子元件目录",
    "image": "散图目录（不进图集）",
}

# 通用中文词表：按文件名里的英文/拼音片段给自动提示，命中的会标记为「自动推断」
TOKEN_ZH = [
    ("touxiangkuang", "头像框"), ("touxiang", "头像"), ("zhuang", "庄家"), ("qipao", "气泡"),
    ("biaoqian", "标签"), ("zimo", "自摸"), ("fengexian", "分隔线"), ("jiantou", "箭头"),
    ("arrow", "箭头"), ("paizhuo", "牌桌"), ("chupai", "出牌"), ("duogang", "多杠"),
    ("fanxing", "牌型"), ("lsxq", "历史详情"), ("hu", "胡"), ("gui", "鬼/赖子"),
    ("lai", "赖子"), ("zimo", "自摸"), ("background", "背景"), ("bg", "背景"),
    ("title", "标题"), ("back", "返回/背面"), ("box", "框"), ("btn", "按钮"), ("bnt", "按钮"),
    ("icon", "图标"), ("ico", "图标"), ("close", "关闭"), ("head", "头像"), ("mah", "麻将牌"),
    ("fnt", "位图字体"), ("win", "赢"), ("lose", "输"), ("emoji", "表情"), ("emotion", "表情"),
    ("clock", "时钟"), ("chat", "聊天"), ("money", "分数"), ("name", "名字"), ("corner", "角标"),
    ("value", "牌值"), ("desk", "桌面"), ("start", "开局"), ("combo", "连击/牌型"),
    ("btn", "按钮"), ("main", "主界面"), ("result", "结算"), ("player", "玩家/座位"),
    ("self", "自己"), ("hand", "手牌"), ("score", "得分"), ("flow", "流水"), ("item", "条目"),
    ("layer", "层"), ("black", "黑色"), ("bottom", "底部"), ("handler", "按钮容器"),
    ("effect", "特效"), ("ting", "听牌"), ("chi", "吃"), ("gang", "杠"), ("peng", "碰"),
]

TOPLEVEL_SKIP = {".objs", ".opencode", ".xflow", ".git", "node_modules", ".agents"}


# ----------------------------------------------------------------------------- 基础工具


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_xml(path: Path):
    try:
        return ET.parse(str(path)).getroot()
    except (ET.ParseError, OSError):
        return None


def parse_kv_list(value: str):
    """FGUI 的 '0,a,1,b' 页列表 -> [(0,'a'), (1,'b')]"""
    parts = [p for p in (value or "").split(",")]
    out = []
    for i in range(0, len(parts) - 1, 2):
        out.append((parts[i], parts[i + 1]))
    return out


def parse_scale9(value: str):
    if not value:
        return None
    try:
        nums = [int(x) for x in value.split(",")]
    except ValueError:
        return None
    return nums if len(nums) == 4 else None


def png_size(path: Path):
    try:
        with path.open("rb") as fh:
            head = fh.read(26)
    except OSError:
        return None
    if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        return w, h
    return None


def jpeg_size(path: Path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    i, n = 2, len(data)
    while i < n - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xD9 or i + 1 >= n:
            break
        seg_len = struct.unpack(">H", data[i:i + 2])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if i + 7 <= n:
                h, w = struct.unpack(">HH", data[i + 3:i + 7])
                return w, h
            return None
        i += seg_len
    return None


def image_size(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".png":
        return png_size(path)
    if suffix in (".jpg", ".jpeg"):
        return jpeg_size(path)
    return None


def cell(value) -> str:
    """Markdown 表格单元格转义"""
    if value is None or value == "":
        return "-"
    text = str(value).replace("|", "\\|").replace("\n", "<br>")
    return text


def tokenize(name: str):
    """把文件名/节点名拆成小写词：img_bg_gxhs -> [img, bg, gxhs]，XxxMahResultView -> [xxx, mah, result, view]"""
    stem = Path(name).stem
    parts = re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", stem)
    out = []
    for part in parts:
        if not part:
            continue
        for chunk in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+|[\u4e00-\u9fff]+", part):
            out.append(chunk.lower())
    return out


def zh_hint(name: str):
    """按通用词表给中文提示。

    先按整词匹配（避免 'chupai' 里的 'hu' 被当成「胡」），
    没命中再对长度 >= 6 的长词做包含匹配（如 touxiangkuang）。
    置信度低，调用方需标记为自动推断。
    """
    tokens = tokenize(name)
    hits = []
    for token, zh in TOKEN_ZH:
        if token in tokens:
            if zh not in hits:
                hits.append(zh)
        elif len(token) >= 6 and any(token in t for t in tokens):
            if zh not in hits:
                hits.append(zh)
        if len(hits) >= 3:
            break
    return "".join(hits) if hits else ""


# ----------------------------------------------------------------------------- 备注文件


class Notes:
    def __init__(self, path: Path):
        self.path = path
        self.items = {}
        if path.exists():
            for raw in read_text(path).splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key and value:
                    self.items[key.lower()] = value

    def lookup(self, *keys):
        for key in keys:
            if not key:
                continue
            got = self.items.get(str(key).lower().replace("\\", "/"))
            if got:
                return got
        return None

    def describe(self, *keys):
        """返回 (说明, 是否待补充)。带 * 前缀表示脚本按文件名自动推断。"""
        got = self.lookup(*keys)
        if got:
            return got, False
        for key in keys:
            if not key:
                continue
            guess = zh_hint(Path(str(key)).stem)
            if guess:
                return "*" + guess, False
        return "待补充", True


# ----------------------------------------------------------------------------- 解析工程


class Scanner:
    def __init__(self, root: Path, notes_path: Path = None):
        self.root = root
        # 备注文件放在工作层目录（main 会显式传入）；没传就退回工程根目录
        self.notes_path = Path(notes_path) if notes_path else (root / NOTES_FILE)
        self.notes = Notes(self.notes_path)
        self.fairy = None
        self.settings = {}
        self.packages = []          # 每个包的原始信息
        self.res_index = {}         # (pkgdir, resid) -> resource dict
        self.comp_index = {}        # (pkgdir, relpath) -> component dict
        self.usage = {}             # (pkgdir, resid) -> [引用处]
        self.anomalies = []

    # ---------- 顶层

    def scan_fairy(self):
        fairs = sorted(self.root.glob("*.fairy"))
        if not fairs:
            return
        # 用 XML 解析而不是正则：文件头部的 <?xml version="1.0"?> 会抢走 version 匹配
        info = {"file": fairs[0].name, "id": "", "type": "", "version": ""}
        root = parse_xml(fairs[0])
        if root is not None:
            info["id"] = root.get("id", "")
            info["type"] = root.get("type", "")
            info["version"] = root.get("version", "")
        self.fairy = info

    def scan_settings(self):
        sdir = self.root / "settings"
        if not sdir.is_dir():
            return
        for path in sorted(sdir.glob("*.json")):
            try:
                self.settings[path.name] = json.loads(read_text(path))
            except json.JSONDecodeError:
                self.settings[path.name] = {"__error__": "JSON 解析失败"}

    # ---------- 包

    def scan_packages(self):
        assets = self.root / "assets"
        if not assets.is_dir():
            raise SystemExit(f"找不到 assets 目录：{assets}")
        for pkg_dir in sorted(p for p in assets.iterdir() if p.is_dir()):
            pkg_xml = pkg_dir / "package.xml"
            if not pkg_xml.exists():
                continue
            root = parse_xml(pkg_xml)
            if root is None:
                self.anomalies.append(("包描述解析失败", f"assets/{pkg_dir.name}/package.xml"))
                continue
            pkg = {
                "dir": pkg_dir.name,
                "path": f"assets/{pkg_dir.name}",
                "id": root.get("id", ""),
                "resources": [],
                "publish": {},
                "components": [],
                "disk_files": [],
                "empty_dirs": [],
            }
            publish = root.find("publish")
            if publish is not None:
                pkg["publish"] = {
                    "path": publish.get("path", ""),
                    "packageCount": publish.get("packageCount", ""),
                }
            for res in root.findall("./resources/*"):
                item = {
                    "tag": res.tag,
                    "type": RES_TYPE_ZH.get(res.tag, res.tag),
                    "id": res.get("id", ""),
                    "name": res.get("name", ""),
                    "path": res.get("path", "/"),
                    "exported": res.get("exported") == "true",
                    "scale9grid": parse_scale9(res.get("scale9grid")),
                    "atlas": res.get("atlas") or "",
                }
                if res.tag == "spine":
                    item.update({
                        "require": res.get("require", ""),
                        "atlasNames": res.get("atlasNames", ""),
                        "anchor": res.get("anchor", ""),
                        "width": res.get("width", ""),
                        "height": res.get("height", ""),
                    })
                rel = (item["path"].strip("/") + "/" + item["name"]).lstrip("/")
                item["relpath"] = rel
                fpath = pkg_dir / rel
                item["exists"] = fpath.exists()
                if item["exists"] and fpath.suffix.lower() in IMAGE_EXT:
                    size = image_size(fpath)
                    item["dims"] = size
                pkg["resources"].append(item)
                self.res_index[(pkg["dir"], item["id"])] = item
            self.packages.append(pkg)

        # 磁盘文件清单（用于查未登记文件 / 空目录）
        for pkg in self.packages:
            pdir = self.root / pkg["path"]
            registered = {r["relpath"] for r in pkg["resources"]}
            for dirpath, dirnames, filenames in os_walk(pdir):
                rel_dir = Path(dirpath).relative_to(pdir)
                if not dirnames and not filenames:
                    pkg["empty_dirs"].append(str(rel_dir).replace("\\", "/"))
                for fn in filenames:
                    rel = str((rel_dir / fn)).replace("\\", "/")
                    pkg["disk_files"].append(rel)
                    if rel == "package.xml":
                        continue
                    if rel not in registered:
                        self.anomalies.append((
                            "文件未登记进 package.xml（FGUI 索引不到）",
                            f"{pkg['path']}/{rel}",
                        ))
            for res in pkg["resources"]:
                if not res["exists"]:
                    self.anomalies.append((
                        "package.xml 登记了但磁盘上没有这个文件",
                        f"{pkg['path']}/{res['relpath']}",
                    ))

    # ---------- 组件

    def scan_components(self):
        for pkg in self.packages:
            pdir = self.root / pkg["path"]
            for xml_path in sorted(pdir.rglob("*.xml")):
                if xml_path.name == "package.xml":
                    continue
                root = parse_xml(xml_path)
                if root is None or root.tag != "component":
                    continue
                rel = str(xml_path.relative_to(pdir)).replace("\\", "/")
                comp = {
                    "pkg": pkg["dir"],
                    "relpath": rel,
                    "file": xml_path.name,
                    "size": root.get("size", ""),
                    "extention": root.get("extention", ""),
                    "initName": root.get("initName", ""),
                    "remark": root.get("remark", ""),
                    "controllers": [],
                    "nodes": [],
                    "refs": [],          # (pkgdir, resid, kind)
                    "spines": [],
                }
                for ctrl in root.findall("controller"):
                    comp["controllers"].append({
                        "name": ctrl.get("name", ""),
                        "exported": ctrl.get("exported") == "true",
                        "pages": parse_kv_list(ctrl.get("pages", "")),
                        "remarks": {
                            r.get("page"): r.get("value")
                            for r in ctrl.findall("remark")
                        },
                        "actions": len(ctrl.findall("action")),
                    })
                display = root.find("displayList")
                if display is not None:
                    for el in display:
                        comp["nodes"].append(self._parse_node(pkg, comp, el))
                self.comp_index[(pkg["dir"], rel)] = comp
                pkg["components"].append(comp)

    def _parse_node(self, pkg, comp, el):
        node = {
            "tag": el.tag,
            "type": NODE_TYPE_ZH.get(el.tag, el.tag),
            "name": el.get("name", ""),
            "id": el.get("id", ""),
            "size": el.get("size", ""),
            "xy": el.get("xy", ""),
            "visible": el.get("visible", ""),
            "hidden": el.get("visible") == "false",
            "text": el.get("text", ""),
            "controller": el.get("controller", ""),
            "group": el.get("group", ""),
            "gears": sorted(k for k in el.attrib if k.startswith("gear")),
            "items": len(el.findall("item")),
            "src_name": "",
            "src_rel": "",
            "src_kind": "",
            "src_pkg": "",
            "url": "",
            "url_desc": "",
            "url_all": "",
            "urls": [],
            "extra": [c.tag for c in el if c.tag in ("Button", "Label", "ProgressBar", "customProperty")],
        }
        # 1) src 属性：可能落在本包，也可能用 pkg="其它包名/包ID" 指向别的包
        src = el.get("src", "")
        if src and not src.startswith("ui://"):
            target_pkg = self._pkgdir_for(el.get("pkg")) if el.get("pkg") else pkg["dir"]
            res = self.res_index.get((target_pkg, src))
            if res is None:
                res = self.res_index.get((pkg["dir"], src))
                target_pkg = pkg["dir"]
            if res:
                node["src_name"] = res["name"]
                node["src_rel"] = res["relpath"]
                node["src_kind"] = res["tag"]
                node["src_pkg"] = target_pkg
                self._add_usage(target_pkg, src, pkg["dir"], comp["relpath"], node["name"])
                comp["refs"].append((target_pkg, src, res["tag"]))
            else:
                node["src_name"] = f"未知资源 id {src}"
                self.anomalies.append((
                    "节点 src 引用解析不到资源",
                    f"{pkg['path']}/{comp['relpath']} 节点 {node['name']} -> src={src}"
                    + (f" pkg={el.get('pkg')}" if el.get("pkg") else ""),
                ))
        # 2) ui:// 引用：节点自身 url / defaultItem，以及子元素里的 gearIcon、Button icon、item url 等
        found = []
        for sub in el.iter():
            for attr, value in sub.attrib.items():
                for match in re.finditer(r"ui://[A-Za-z0-9_]+", value):
                    found.append((match.group(0), f"{sub.tag}@{attr}"))
        pairs = []
        seen = set()
        for url, origin in found:
            if url in seen:
                continue
            seen.add(url)
            pairs.append((url, origin, self._resolve_ui(url, pkg, comp, node)))
        if pairs:
            node["url"] = pairs[0][0]
            node["url_desc"] = pairs[0][2]
            node["urls"] = [{"url": u, "from": o, "desc": d} for u, o, d in pairs]
            node["url_all"] = "、".join(dict.fromkeys(d for _, _, d in pairs))
        return node

    def _pkgdir_for(self, ref):
        """pkg="..." 里写的可能是包 ID（如 xmahcomm），也可能是包目录名（如 xxx_mah_common）"""
        if not ref:
            return None
        for cand in self.packages:
            if cand["id"] == ref or cand["dir"] == ref:
                return cand["dir"]
        return ref

    def _resolve_ui(self, url, pkg, comp, node):
        """ui://<包ID><资源ID> -> '包目录/文件名'，并登记引用"""
        target = url[5:]
        for cand in self.packages:
            pid = cand["id"]
            if not pid or not target.startswith(pid):
                continue
            resid = target[len(pid):]
            res = self.res_index.get((cand["dir"], resid))
            if res:
                self._add_usage(cand["dir"], resid, pkg["dir"], comp["relpath"], node["name"])
                comp["refs"].append((cand["dir"], resid, res["tag"]))
                if res["tag"] == "spine":
                    comp["spines"].append(res["name"])
                label = f"{cand['dir']}/{res['name']}"
                return label
            self.anomalies.append(("ui:// 引用找不到目标资源", f"{pkg['path']}/{comp['relpath']} 节点 {node['name']} -> {url}"))
            return f"未找到 {url}"
        self.anomalies.append(("ui:// 引用不属于任何已扫描的包", f"{pkg['path']}/{comp['relpath']} 节点 {node['name']} -> {url}"))
        return f"未知包 {url}"

    def _add_usage(self, pkgdir, resid, from_pkg, from_comp, node_name):
        self.usage.setdefault((pkgdir, resid), []).append({
            "pkg": from_pkg,
            "comp": from_comp,
            "node": node_name,
        })

    # ---------- 交叉分析

    def cross_checks(self):
        # 同名图片重复（字模、Spine 附属文件不算，它们本来就同名）
        by_name = {}
        for pkg in self.packages:
            attached = self.attached_resources(pkg)
            for res in pkg["resources"]:
                if res["tag"] != "image" or res["id"] in attached:
                    continue
                by_name.setdefault(res["name"].lower(), []).append(f"{pkg['path']}/{res['relpath']}")
        for name, locs in sorted(by_name.items()):
            if len(locs) > 1:
                self.anomalies.append(("同名图片在多个包里各有一份（改图要确认是否都要同步）", " / ".join(locs)))

        # 未登记 / 空目录
        for pkg in self.packages:
            for d in pkg["empty_dirs"]:
                self.anomalies.append(("空目录", f"{pkg['path']}/{d}"))

    # ---------- 界面归组（给美术清单）

    def build_screens(self):
        """以各包的顶层视图组件为「界面」，递归收集其用到的图片"""
        screens = []
        claimed = set()
        anchors = []
        for pkg in self.packages:
            view_ids = [r["id"] for r in pkg["resources"]
                        if r["tag"] == "component" and r["path"] == "/"]
            for comp in pkg["components"]:
                if comp["relpath"] in ("", None):
                    continue
                resid = self._comp_resid(pkg, comp["relpath"])
                if resid and resid in view_ids:
                    anchors.append((pkg, comp))
        for pkg, comp in anchors:
            imgs, comps, spines = self._collect(pkg, comp)
            claimed.update(imgs)
            screens.append({
                "pkg": pkg,
                "comp": comp,
                "images": sorted(imgs, key=lambda k: (k[0], k[1])),
                "components": sorted(comps),
                "spines": sorted(spines),
            })
        # 其它图片（既没被任何界面用到，也不是字模/Spine 附属文件）
        others = []
        for pkg in self.packages:
            attached = self.attached_resources(pkg)
            for res in pkg["resources"]:
                if res["tag"] != "image":
                    continue
                if res["id"] in attached:
                    continue
                if (pkg["dir"], res["id"]) in claimed:
                    continue
                others.append((pkg, res))
        return screens, others

    def _comp_resid(self, pkg, relpath):
        for res in pkg["resources"]:
            if res["tag"] == "component" and res["relpath"] == relpath:
                return res["id"]
        return None

    def _collect(self, pkg, comp):
        """从组件出发，递归收集图片 key / 子元件 / Spine"""
        images, comps, spines = set(), set(), set()
        seen = set()
        stack = [(pkg, comp)]
        while stack:
            cur_pkg, cur = stack.pop()
            if (cur_pkg["dir"], cur["relpath"]) in seen:
                continue
            seen.add((cur_pkg["dir"], cur["relpath"]))
            comps.add(f"{cur_pkg['dir']}/{cur['relpath']}")
            for node in cur["nodes"]:
                if node["src_kind"] == "image":
                    images.add((node["src_pkg"], self._resid_of(node["src_pkg"], node["src_rel"])))
                elif node["src_kind"] == "component":
                    key = self._find_comp(node["src_pkg"], node["src_rel"])
                    if key:
                        stack.append(key)
                elif node["src_kind"] == "spine":
                    spines.add(node["src_name"])
                for ref in node.get("urls", []):
                    resolved = self._resolve_key(ref["url"])
                    if not resolved:
                        continue
                    kind, rpkg, res = resolved
                    if kind == "image":
                        images.add((rpkg["dir"], res["id"]))
                    elif kind == "component":
                        key = self._find_comp(rpkg["dir"], res["relpath"])
                        if key:
                            stack.append(key)
                    elif kind == "spine":
                        spines.add(res["name"])
        images.discard((None, None))
        images = {k for k in images if k[1]}
        return images, comps, spines

    def _resid_of(self, pkgdir, relpath):
        for (pdir, rid), res in self.res_index.items():
            if pdir == pkgdir and res["relpath"] == relpath:
                return rid
        return None

    def attached_resources(self, pkg):
        """返回不属于「界面图片」的资源 id：
        - 位图字体的字模小图
        - Spine 的贴图 / atlas 描述（由 spine 的 require 指定）
        同时给资源打上 glyph_dir 标记，供美术清单生成字模说明。
        """
        attached = {}   # resid -> 原因
        glyph_prefixes = []
        for res in pkg["resources"]:
            if res["tag"] != "font":
                continue
            parent = str(Path(res["relpath"]).parent).replace("\\", "/")
            parent = "" if parent == "." else parent
            glyph_prefixes.append((parent + "/" + Path(res["name"]).stem).lstrip("/"))
        for res in pkg["resources"]:
            if res["tag"] != "image":
                continue
            for prefix in glyph_prefixes:
                if res["relpath"].startswith(prefix + "/"):
                    attached[res["id"]] = "位图字体字模"
                    res["glyph_dir"] = prefix
                    res["glyph"] = Path(res["name"]).stem
        for res in pkg["resources"]:
            if res["tag"] != "spine":
                continue
            for rid in (res.get("require") or "").split(","):
                rid = rid.strip()
                if rid:
                    attached[rid] = f"Spine 附属文件（{res['name']}）"
        for res in pkg["resources"]:
            for rid, why in attached.items():
                if res["id"] == rid:
                    res["attached_to"] = why
        return attached

    def _find_comp(self, pkgdir, relpath):
        for pkg in self.packages:
            if pkg["dir"] != pkgdir:
                continue
            for comp in pkg["components"]:
                if comp["relpath"] == relpath:
                    return (pkg, comp)
        return None

    def _resolve_key(self, url):
        target = url[5:]
        for cand in self.packages:
            pid = cand["id"]
            if pid and target.startswith(pid):
                res = self.res_index.get((cand["dir"], target[len(pid):]))
                if res:
                    return res["tag"], cand, res
        return None


def os_walk(path: Path):
    for dirpath, dirnames, filenames in __import__("os").walk(path):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules"}]
        yield dirpath, dirnames, filenames


# ----------------------------------------------------------------------------- 文档一：工程结构


def render_tree(sc: Scanner) -> str:
    """带标注的嵌套文件树：导出标记、未登记文件、图片尺寸、空目录、目录用途"""
    import os as _os

    L = ["## 二、完整文件树（assets + settings）\n"]
    L.append("> 标注含义：`✅` 已导出（可被其它包/代码引用）｜`⚠未登记` 磁盘上有但 package.xml 里没有（编辑器看不到、不会发布）｜")
    L.append("> `空目录` 下面没有任何文件。图片后面括起来的是当前像素尺寸。\n")
    L.append("```")

    lines = []

    def emit(dirpath, rel_prefix, indent, pkg):
        try:
            names = sorted(_os.listdir(dirpath))
        except OSError:
            return
        entries = []
        for name in names:
            full = _os.path.join(dirpath, name)
            entries.append((_os.path.isdir(full), name, full))
        entries.sort(key=lambda t: (not t[0], t[1].lower()))
        for idx, (is_dir, name, full) in enumerate(entries):
            last = idx == len(entries) - 1
            branch = "└── " if last else "├── "
            rel = f"{rel_prefix}{name}"
            child_indent = indent + ("    " if last else "│   ")
            if is_dir:
                note = ""
                if not _os.listdir(full):
                    note = "   ← 空目录"
                elif name in DIR_ROLE:
                    note = "   ← " + DIR_ROLE[name]
                lines.append(f"{indent}{branch}{name}/{note}")
                emit(full, rel + "/", child_indent, pkg)
            else:
                marks, dims = [], None
                if pkg is not None and rel != "package.xml":
                    res = next((r for r in pkg["resources"] if r["relpath"] == rel), None)
                    if res is None:
                        marks.append("⚠未登记")
                    else:
                        if res["exported"]:
                            marks.append("✅导出")
                        dims = res.get("dims")
                suffix = f"  ({dims[0]}×{dims[1]})" if dims else ""
                mark = ("   " + " ".join(marks)) if marks else ""
                lines.append(f"{indent}{branch}{name}{suffix}{mark}")

    lines.append("assets/")
    for pkg in sc.packages:
        lines.append(f"├── {pkg['dir']}/    # 包 ID {pkg['id']}，{len(pkg['disk_files'])} 个文件")
        emit(str(sc.root / pkg["path"]), "", "│   ", pkg)
    lines.append("└── (以上为 6 个 UI 包)")
    lines.append("")
    lines.append("settings/")
    sdir = sc.root / "settings"
    if sdir.is_dir():
        names = sorted(p.name for p in sdir.glob("*.json"))
        for idx, name in enumerate(names):
            branch = "└── " if idx == len(names) - 1 else "├── "
            desc, _ = sc.notes.describe(name)
            if desc != "待补充":
                short = desc.split("。")[0]
                if len(short) > 36:
                    short = short[:36] + "…"
                lines.append(f"{branch}{name}   ← {short}")
            else:
                lines.append(f"{branch}{name}")
    L.extend(lines)
    L.append("```")
    L.append("")
    return "\n".join(L)


def render_structure(sc: Scanner) -> str:
    L = []
    name = sc.fairy["file"] if sc.fairy else sc.root.name
    L.append(f"# {name} 工程结构（自动生成）\n")
    L.append("> 本文档由 skill `fgui-flow` 的 `scan_fgui.py` 自动生成，**不要手改**。")
    L.append("> 要补充说明，请写进 `<工作层>/美术清单.备注.txt` 后重新生成。")
    L.append(f"> 生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M}　扫描根：`{sc.root}`")
    L.append("> 重新生成：`python .opencode/skills/fgui-flow/scripts/scan_fgui.py`（输出都在 `.opencode/work/`）")
    L.append("> 配套文档：`美术资源清单.md`（给美术/策划看的中文清单）、`facts.json`（机器可读事实表）\n")

    # 一、定位索引
    L.append("## 一、定位索引（先在这里找该改哪个文件）\n")
    L.append("| 你要改的东西 | 关键词（可直接 Ctrl+F 搜） | 文件 |")
    L.append("|---|---|---|")
    rows = []
    if sc.fairy:
        rows.append(("工程本身", sc.fairy["file"], f"`{sc.fairy['file']}`（id `{sc.fairy['id']}`，`{sc.fairy['type']}`）"))
    for pkg in sc.packages:
        desc, _ = sc.notes.describe(pkg["dir"])
        kw = f"{pkg['dir']} / 包 ID {pkg['id']}"
        rows.append((desc, kw, f"`{pkg['path']}/`"))
    for pkg in sc.packages:
        for comp in pkg["components"]:
            desc, _ = sc.notes.describe(comp["file"], comp["relpath"])
            node_kw = " ".join(n["name"] for n in comp["nodes"] if n["name"])[:90]
            rows.append((desc, f"{comp['file']} / {node_kw}", f"`{pkg['path']}/{comp['relpath']}`"))
    for label, key, value in rows:
        L.append(f"| {cell(label)} | {cell(key)} | {cell(value)} |")
    L.append("")

    # 二、文件树
    L.append(render_tree(sc))

    # 三、工程与设置
    L.append("## 三、工程与全局设置\n")
    if sc.fairy:
        L.append(f"- 工程文件：`{sc.fairy['file']}`（id `{sc.fairy['id']}`，类型 `{sc.fairy['type']}`，版本 `{sc.fairy['version']}`）")
    add = sc.settings.get("Adaptation.json") or {}
    if add:
        L.append(f"- 设计分辨率：**{add.get('designResolutionX')} × {add.get('designResolutionY')}**，{add.get('scaleMode')} / {add.get('screenMathMode')}")
        devices = add.get("devices") or []
        if devices:
            L.append("- 预置机型：" + "、".join(f"{d.get('name')}({d.get('resolutionX')}×{d.get('resolutionY')})" for d in devices))
    pub = sc.settings.get("Publish.json") or {}
    if pub:
        L.append(f"- 发布：输出 `{pub.get('path')}`，格式 `{pub.get('fileExtension')}`，`packageCount={pub.get('packageCount')}`，描述压缩 `{pub.get('compressDesc')}`")
        atlas = pub.get("atlasSetting") or {}
        if atlas:
            L.append(f"- 图集：最大 {atlas.get('maxSize')}、{atlas.get('sizeOption')}、分页 {atlas.get('paging')}、允许旋转 {atlas.get('allowRotation')}")
        code = pub.get("codeGeneration") or {}
        if code:
            L.append(f"- 代码生成：{'开启' if code.get('allowGenCode') else '关闭'}，输出 `{code.get('codePath')}`")
    custom = sc.settings.get("CustomProperties.json") or {}
    if custom:
        L.append("- 自定义属性：" + "、".join(f"`{k}`=`{v}`" for k, v in custom.items()))
    i18n = sc.settings.get("i18n.json")
    if i18n is not None:
        L.append(f"- 多语言：{'未启用（langFiles 为空）' if not i18n.get('langFiles') else i18n.get('langFiles')}")
    groups = sc.settings.get("PackageGroup.json")
    if isinstance(groups, list):
        L.append(f"- 分包分组（{len(groups)} 组）：" + "、".join(str(g.get("name")) for g in groups))
        pkg_ids = {p["id"] for p in sc.packages}
        listed = set()
        for g in groups:
            listed.update(g.get("pkgs") or [])
        missing = sorted(i for i in pkg_ids if i not in listed)
        if missing:
            L.append(f"  - ⚠ 本工程有 {len(missing)} 个包的 id 未出现在任何分组：`{'`, `'.join(missing)}`")
    L.append("")

    # 四、包清单
    L.append("## 四、包清单\n")
    L.append("| 包目录 | 包 ID | 文件数 | 组件数 | 图片数 | 导出组件 | 说明 |")
    L.append("|---|---|---|---|---|---|---|")
    for pkg in sc.packages:
        exported = [c["file"] for c in pkg["components"]
                    if any(r["relpath"] == c["relpath"] and r["exported"] for r in pkg["resources"])]
        n_img = sum(1 for r in pkg["resources"] if r["tag"] == "image")
        desc, _ = sc.notes.describe(pkg["dir"])
        L.append(f"| `{pkg['dir']}` | `{pkg['id']}` | {len(pkg['disk_files'])} | {len(pkg['components'])} "
                 f"| {n_img} | {cell('、'.join(exported) if exported else '-')} | {cell(desc)} |")
    L.append("")

    # 五、逐包明细
    L.append("## 五、逐包明细\n")
    for pkg in sc.packages:
        desc, _ = sc.notes.describe(pkg["dir"])
        L.append(f"### {pkg['dir']}（id `{pkg['id']}`）— {desc}\n")
        if pkg["publish"]:
            L.append(f"- 发布目标：`{pkg['publish'].get('path')}`（packageCount={pkg['publish'].get('packageCount')}）")
        L.append(f"- 目录：`{pkg['path']}/`，共 {len(pkg['disk_files'])} 个文件\n")

        L.append("**资源登记表**（`src` / `ui://` 引用的就是这里的 id）\n")
        L.append("| id | 文件 | 类型 | 导出 | 尺寸 | 九宫格 | 被引用处 |")
        L.append("|---|---|---|---|---|---|---|")
        for res in pkg["resources"]:
            if res["tag"] == "folder":
                continue
            dims = f"{res['dims'][0]}×{res['dims'][1]}" if res.get("dims") else "-"
            s9 = ",".join(str(x) for x in res["scale9grid"]) if res.get("scale9grid") else "-"
            users = sc.usage.get((pkg["dir"], res["id"]), [])
            user_txt = "、".join(sorted({f"{u['comp'].split('/')[-1]}·{u['node']}" for u in users})) or "-"
            mark = "" if res["exists"] else " ⚠文件缺失"
            L.append(f"| `{res['id']}` | `{res['relpath']}`{mark} | {res['type']} | "
                     f"{'✅' if res['exported'] else '-'} | {dims} | {s9} | {cell(user_txt)} |")
        L.append("")

        for comp in pkg["components"]:
            cdesc, _ = sc.notes.describe(comp["file"], f"{pkg['dir']}/{comp['relpath']}")
            L.append(f"**组件 `{comp['relpath']}`**（{comp['size'] or '?'}，{cdesc}）\n")
            if comp["extention"]:
                L.append(f"- 扩展类型：`{comp['extention']}`" + (f"，initName `{comp['initName']}`" if comp["initName"] else ""))
            if comp["remark"]:
                L.append(f"- 组件备注：`{comp['remark']}`")
            if comp["controllers"]:
                for ctrl in comp["controllers"]:
                    pages = "、".join(
                        f"{p}({ctrl['remarks'].get(p) or name})" if (ctrl['remarks'].get(p) or name) else p
                        for p, name in ctrl["pages"]
                    )
                    L.append(f"- 控制器 `{ctrl['name']}`{'（导出）' if ctrl['exported'] else ''}：{pages or '无页'}"
                             + (f"，{ctrl['actions']} 条跳转动作" if ctrl["actions"] else ""))
            if comp["nodes"]:
                L.append("")
                L.append("| 节点名 | 类型 | 尺寸/位置 | 引用 | 其它 |")
                L.append("|---|---|---|---|---|")
                for node in comp["nodes"]:
                    ref = node["src_rel"] or node["url_all"] or node["url_desc"] or "-"
                    if node["src_kind"] == "component" and node["src_rel"]:
                        owner = node["src_pkg"] if node["src_pkg"] and node["src_pkg"] != pkg["dir"] else ""
                        ref = f"子元件 `{(owner + '/') if owner else ''}{node['src_rel']}`"
                        if owner:
                            ref += "（跨包）"
                    elif node["src_rel"]:
                        owner = node["src_pkg"] if node["src_pkg"] and node["src_pkg"] != pkg["dir"] else ""
                        ref = f"`{(owner + '/') if owner else ''}{node['src_rel']}`"
                        if owner:
                            ref += "（跨包）"
                    extra = []
                    if node["hidden"]:
                        extra.append("默认隐藏")
                    if node["group"]:
                        extra.append(f"属组 {node['group']}")
                    if node["items"]:
                        extra.append(f"{node['items']} 个列表项")
                    if node["gears"]:
                        extra.append("、".join(g.replace("gear", "状态") for g in node["gears"]))
                    if node["controller"]:
                        extra.append(f"控制器 {node['controller']}")
                    if node["text"]:
                        extra.append(f"文案「{node['text'][:24]}」")
                    if node["extra"]:
                        extra.append("扩展 " + "/".join(node["extra"]))
                    L.append(f"| `{cell(node['name'])}` | {node['type']} | {cell(node['xy'])} / {cell(node['size'])} "
                             f"| {cell(ref)} | {cell('；'.join(extra))} |")
            L.append("")

    # 六、引用关系
    L.append("## 六、引用关系\n")
    cross = []
    for (pdir, rid), users in sc.usage.items():
        res = sc.res_index.get((pdir, rid))
        if not res:
            continue
        for u in users:
            if u["pkg"] != pdir:
                cross.append((f"{u['pkg']}/{u['comp']}", f"{u['node']}", f"{pdir}/{res['name']}"))
    if cross:
        L.append("**跨包引用**（改右侧资源会影响左侧界面）\n")
        L.append("| 引用方（包/组件） | 节点 | 被引用资源 |")
        L.append("|---|---|---|")
        for a, b, c in sorted(set(cross)):
            L.append(f"| `{a}` | `{b}` | `{c}` |")
        L.append("")
    multi = []
    for (pdir, rid), users in sc.usage.items():
        res = sc.res_index.get((pdir, rid))
        if res and len({u["comp"] for u in users}) > 1:
            multi.append((f"{pdir}/{res['name']}", sorted({f"{u['comp']}·{u['node']}" for u in users})))
    if multi:
        L.append("**被多处复用的资源**（换图会同时影响多个位置）\n")
        L.append("| 资源 | 用在哪 |")
        L.append("|---|---|")
        for name, users in sorted(multi):
            L.append(f"| `{name}` | {cell('、'.join(users))} |")
        L.append("")
    if not cross and not multi:
        L.append("（没有跨包引用，也没有被多处复用的资源）\n")

    # 七、异常
    L.append("## 七、异常与待确认\n")
    if sc.anomalies:
        L.append("| 类型 | 位置 |")
        L.append("|---|---|")
        for kind, where in sc.anomalies:
            L.append(f"| {cell(kind)} | {cell(where)} |")
    else:
        L.append("（未发现异常）")
    L.append("")
    L.append("> 说明：「文件未登记进 package.xml」= 磁盘上有这个文件，但 FGUI 的资源索引里没有它，")
    L.append("> 在编辑器里看不到、也不会发布；新增图片必须登记。\n")

    # 八、顶层目录
    L.append("## 八、顶层目录与文件（事实清单）\n")
    L.append("| 名称 | 类型 | 文件数 | 说明 |")
    L.append("|---|---|---|---|")
    for entry in sorted(sc.root.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if entry.name.startswith(".") and entry.name not in (".objs", ".opencode", ".xflow"):
            continue
        if entry.name in TOPLEVEL_SKIP and entry.name != ".objs":
            desc, _ = sc.notes.describe(entry.name)
            L.append(f"| `{entry.name}` | 目录 | {count_files(entry)} | {cell(desc)} |")
            continue
        if entry.is_dir():
            desc, _ = sc.notes.describe(entry.name)
            L.append(f"| `{entry.name}` | 目录 | {count_files(entry)} | {cell(desc)} |")
        else:
            desc, _ = sc.notes.describe(entry.name)
            L.append(f"| `{entry.name}` | 文件 | {entry.stat().st_size} B | {cell(desc)} |")
    L.append("")
    return "\n".join(L)


def count_files(path: Path) -> int:
    n = 0
    for _, _, filenames in os_walk(path):
        n += len(filenames)
    return n


# ----------------------------------------------------------------------------- 文档二：美术资源清单


def render_art(sc: Scanner) -> str:
    screens, others = sc.build_screens()
    L = []
    name = sc.fairy["file"] if sc.fairy else sc.root.name
    L.append(f"# {name} 美术资源清单\n")
    L.append(f"> 自动生成于 {datetime.datetime.now():%Y-%m-%d %H:%M}。事实（路径、尺寸、九宫格、引用关系）来自工程文件本身；")
    L.append("> 「说明」列优先取 `美术清单.备注.txt`，带 `*` 的是按文件名自动推断，写「待补充」的需要人工确认。\n")
    L.append("## 怎么用\n")
    L.append("1. **要改某个界面** → 在「一、界面总览」找到它，按里面的文件路径打开（用 FairyGUI 编辑器打开 `工程目录` 即可）。")
    L.append("2. **要换某张图** → 在「二、界面图片明细」里找到它，**按表格里的尺寸和九宫格边界出图**，然后覆盖同名文件；如果这张图出现在多个界面里，一次会改到多处。")
    L.append("3. **要加新图** → 放到对应包的 `atlas/`（要进图集）或 `image/`（不进图集），**必须在 FairyGUI 编辑器里导入/登记**，否则不会发布。见「六、改图注意」。\n")

    # 一、界面总览
    L.append("## 一、界面总览\n")
    L.append("| 界面 / 用途 | 打开这个文件 | 图片数 | 用到的其它元件 |")
    L.append("|---|---|---|---|")
    for scn in screens:
        pkg, comp = scn["pkg"], scn["comp"]
        desc, _ = sc.notes.describe(comp["file"], f"{pkg['dir']}/{comp['relpath']}")
        others_txt = "、".join(Path(c).name.replace(".xml", "") for c in scn["components"] if c != f"{pkg['dir']}/{comp['relpath']}")
        L.append(f"| {cell(desc)} | `{pkg['path']}/{comp['relpath']}` | {len(scn['images'])} | {cell(others_txt)} |")
    L.append("")
    L.append("> 「用途」优先取 `美术清单.备注.txt`；带 `*` 的是按文件名自动推断的，请核对。\n")

    # 二、每个界面的图片
    L.append("## 二、界面图片明细\n")
    for scn in screens:
        pkg, comp = scn["pkg"], scn["comp"]
        desc, _ = sc.notes.describe(comp["file"], f"{pkg['dir']}/{comp['relpath']}")
        L.append(f"### {desc}\n")
        L.append(f"- 打开：`{pkg['path']}/{comp['relpath']}`（画布 {comp['size'] or '?'}）")
        if scn["spines"]:
            L.append(f"- 用到的动画：{'、'.join('`' + s + '`' for s in scn['spines'])}")
        L.append("")
        if scn["images"]:
            L.append("| 图片 | 尺寸 | 九宫格 | 说明 |")
            L.append("|---|---|---|---|")
            for pdir, rid in scn["images"]:
                res = sc.res_index.get((pdir, rid))
                if not res:
                    continue
                dims = f"{res['dims'][0]}×{res['dims'][1]}" if res.get("dims") else "-"
                s9 = ",".join(str(x) for x in res["scale9grid"]) if res.get("scale9grid") else "-"
                rdesc, _ = sc.notes.describe(res["name"], f"{pdir}/{res['relpath']}")
                L.append(f"| `{pdir}/{res['relpath']}` | {dims} | {s9} | {cell(rdesc)} |")
            L.append("")
        else:
            L.append("（这个界面没有直接用到图片，画面由动画/代码组成）\n")

    # 三、其它图片
    L.append("## 三、其它图片（没有出现在上面任何界面里）\n")
    if others:
        L.append("> 这些图没有被组件引用，可能是代码里动态加载的，也可能已经废弃 —— **删之前请先问开发**。\n")
        L.append("| 图片 | 尺寸 | 九宫格 | 导出 | 说明 |")
        L.append("|---|---|---|---|---|")
        for pkg, res in others:
            dims = f"{res['dims'][0]}×{res['dims'][1]}" if res.get("dims") else "-"
            s9 = ",".join(str(x) for x in res["scale9grid"]) if res.get("scale9grid") else "-"
            rdesc, _ = sc.notes.describe(res["name"], f"{pkg['dir']}/{res['relpath']}")
            L.append(f"| `{pkg['dir']}/{res['relpath']}` | {dims} | {s9} | {'✅' if res['exported'] else '-'} | {cell(rdesc)} |")
        L.append("")
    else:
        L.append("（没有孤立图片）\n")

    # 四、动画特效
    L.append("## 四、动画特效（Spine）\n")
    L.append("> 每个动画是 **3 个同名文件**：`.json`（骨骼数据）+ `.atlas`（图集描述）+ `.png`（贴图）。")
    L.append("> 改动时三个文件要一起换、名字必须保持一致，否则动画会丢。\n")
    L.append("| 动画 | 文件位置 | 贴图尺寸 | 被用在哪 | 说明 |")
    L.append("|---|---|---|---|---|")
    for pkg in sc.packages:
        for res in pkg["resources"]:
            if res["tag"] != "spine":
                continue
            png = next((r for r in pkg["resources"]
                        if r["tag"] == "image" and Path(r["name"]).stem == Path(res["name"]).stem), None)
            dims = f"{png['dims'][0]}×{png['dims'][1]}" if png and png.get("dims") else "-"
            users = sc.usage.get((pkg["dir"], res["id"]), [])
            user_txt = "、".join(sorted({f"{u['pkg']}/{u['comp'].split('/')[-1]}·{u['node']}" for u in users})) or "-"
            rdesc, _ = sc.notes.describe(res["name"], f"{pkg['dir']}/{res['relpath']}")
            L.append(f"| `{res['name']}` | `{pkg['path']}/{res['relpath']}` | {dims} | {cell(user_txt)} | {cell(rdesc)} |")
    L.append("")

    # 五、位图字体
    L.append("## 五、位图字体（特殊数字样式）\n")
    L.append("> 位图字体 = `.fnt` 描述文件 + 一个装着每个字符小图的同名目录。数字/符号的样式就是这些小图。\n")
    fonts = [(pkg, res) for pkg in sc.packages for res in pkg["resources"] if res["tag"] == "font"]
    if fonts:
        L.append("| 字体 | 字体文件 | 字模目录 | 包含字符 | 说明 |")
        L.append("|---|---|---|---|---|")
        for pkg, res in fonts:
            sc.attached_resources(pkg)
            parent = str(Path(res["relpath"]).parent).replace("\\", "/")
            parent = "" if parent == "." else parent + "/"
            stem = Path(res["name"]).stem
            glyph_dir = f"{pkg['path']}/{parent}{stem}"
            glyphs = sorted((r for r in pkg["resources"] if r.get("glyph_dir") == (parent + stem).lstrip("/")),
                            key=lambda r: r.get("glyph", ""))
            chars = "、".join(f"`{g.get('glyph')}`" for g in glyphs)
            rdesc, _ = sc.notes.describe(res["name"], f"{pkg['dir']}/{res['relpath']}")
            L.append(f"| `{res['name']}` | `{pkg['path']}/{res['relpath']}` | `{glyph_dir}/` | {cell(chars)} | {cell(rdesc)} |")
        L.append("")
    else:
        L.append("（工程里没有位图字体）\n")

    # 六、改图注意
    L.append("## 六、改图注意（工程现状检查）\n")
    step = 0

    def head(title):
        nonlocal step
        step += 1
        L.append(f"**{step}. {title}**\n")

    s9_list = []
    for pkg in sc.packages:
        for res in pkg["resources"]:
            if res.get("scale9grid"):
                s9_list.append((f"{pkg['dir']}/{res['relpath']}",
                                ",".join(str(x) for x in res["scale9grid"]),
                                f"{res['dims'][0]}×{res['dims'][1]}" if res.get("dims") else "-"))
    if s9_list:
        head("下面这些图是九宫格拉伸图，出图时尺寸和九宫格边界不能变")
        L.append("| 图片 | 九宫格边界(左,上,右,下) | 当前尺寸 |")
        L.append("|---|---|---|")
        for p, s9, dims in sorted(s9_list):
            L.append(f"| `{p}` | {s9} | {dims} |")
        L.append("")
    head("新增图片必须登记")
    L.append("把图拷进 `atlas/` 或 `image/` 目录后，要在 FairyGUI 编辑器里导入（或把资源配置写进该包的 `package.xml`），否则发布包里不会有它。\n")
    unreg = [a for a in sc.anomalies if a[0].startswith("文件未登记")]
    if unreg:
        L.append("当前扫描发现以下文件在磁盘上但没登记：\n")
        for _, where in unreg:
            L.append(f"- `{where}`")
        L.append("")
    missing = [a for a in sc.anomalies if a[0].startswith("package.xml 登记了")]
    if missing:
        head("登记了但文件不见了")
        for _, where in missing:
            L.append(f"- `{where}`")
        L.append("")
    dupes = [a for a in sc.anomalies if a[0].startswith("同名图片")]
    if dupes:
        head("同名图在多个包里各有一份（改的时候要确认是不是都要同步）")
        for _, where in dupes:
            L.append(f"- {where}")
        L.append("")
    if others:
        head(f"没人引用的图共 {len(others)} 张")
        L.append("清单见上面「三、其它图片」。这些图不在任何界面里，可能是代码动态加载的，也可能已经废弃 —— **删之前先问开发**。\n")
    glyph_total = sum(1 for pkg in sc.packages for res in pkg["resources"] if res.get("glyph_dir"))
    if glyph_total:
        head("位图字体字模按字符逐个存放")
        L.append(f"本工程有 {glyph_total} 张字模小图（在 `fnt/win/`、`fnt/lose/` 里）。改数字样式要按字符逐张替换，")
        L.append("并且不同字体的字符集不一样（见上面「五、位图字体」），漏一张就会少一个字符。\n")
    empty = [a for a in sc.anomalies if a[0] == "空目录"]
    if empty:
        head("空目录")
        for _, where in empty:
            L.append(f"- `{where}`")
        L.append("")
    pending_comps = [(pkg, comp) for pkg in sc.packages for comp in pkg["components"]
                     if sc.notes.describe(comp["file"], f"{pkg['dir']}/{comp['relpath']}")[1]]
    if pending_comps:
        head(f"还没写说明的组件共 {len(pending_comps)} 个（需要人确认用途）")
        for pkg, comp in pending_comps:
            L.append(f"- `{pkg['path']}/{comp['relpath']}`")
        L.append("")
    return "\n".join(L)


# ----------------------------------------------------------------------------- 主流程


def find_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(6):
        if list(cur.glob("*.fairy")) and (cur / "assets").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()


def resolve_workspace_paths(explicit_root=None):
    """用 `.opencode/lib/workspace.py` 解析 (工作区根, client 工程根, 工作层 out_root)。

    找不到工作区/库时返回 None —— 调用方退回旧口径（向上找 *.fairy + assets、输出到工程根）。
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


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")   # 报错信息也要能被中文控制台读出来
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="扫描 FairyGUI 工程，生成工程结构与美术资源清单")
    ap.add_argument("--root", default=None,
                    help="工程根目录（默认取 workspace.json 的 client_dir；再退回向上找 .fairy + assets）")
    ap.add_argument("--out", default=None,
                    help="文档输出目录（默认取 out_root = <工作区根>/.opencode/work）")
    ap.add_argument("--json", default=None, help=f"事实表输出路径（默认 输出目录/{FACTS_OUT}）")
    ap.add_argument("--no-art", action="store_true", help="不生成 美术资源清单.md")
    ap.add_argument("--no-struct", action="store_true", help="不生成 工程结构.md")
    args = ap.parse_args(argv)

    paths = resolve_workspace_paths(args.root)
    if args.root:
        root = Path(args.root).resolve()
    elif paths and paths.get("project"):
        root = paths["project"]
    else:
        root = find_root(Path.cwd())
    if not (root / "assets").is_dir():
        raise SystemExit(f"在 {root} 下找不到 assets/；请先跑 s0 定位 client 工程，或用 --root 指定工程根目录")

    if args.out:
        out_dir = Path(args.out).resolve()
    elif paths and paths.get("work"):
        out_dir = paths["work"]
    else:
        out_dir = root / DOCS_DIR
    notes_path = out_dir / NOTES_FILE
    out_dir.mkdir(parents=True, exist_ok=True)

    sc = Scanner(root, notes_path=notes_path)
    sc.scan_fairy()
    sc.scan_settings()
    sc.scan_packages()
    sc.scan_components()
    sc.cross_checks()

    written = []
    # 先写事实表，再渲染文档：这样文档里的顶层目录文件数才把 facts.json 算进去
    facts = {
        "root": str(root),
        "fairy": sc.fairy,
        "settings": sc.settings,
        "packages": [
            {k: v for k, v in pkg.items() if k != "components"} for pkg in sc.packages
        ],
        "components": [
            {**{k: v for k, v in c.items() if k not in ("nodes", "refs")},
             "nodes": [{k: v for k, v in n.items() if k != "extra"} for n in c["nodes"]]}
            for pkg in sc.packages for c in pkg["components"]
        ],
        "usage": [
            {"pkg": pdir, "id": rid, "used_by": users}
            for (pdir, rid), users in sc.usage.items()
        ],
        "anomalies": [{"type": k, "where": w} for k, w in sc.anomalies],
    }
    facts_path = Path(args.json).resolve() if args.json else (out_dir / FACTS_OUT)
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    written.append(str(facts_path.relative_to(root)) if facts_path.is_relative_to(root) else str(facts_path))

    if not args.no_struct:
        out = out_dir / STRUCT_OUT
        out.write_text(render_structure(sc), encoding="utf-8", newline="\n")
        written.append(str(out.relative_to(root)) if out.is_relative_to(root) else str(out))
    if not args.no_art:
        out = out_dir / ART_OUT
        out.write_text(render_art(sc), encoding="utf-8", newline="\n")
        written.append(str(out.relative_to(root)) if out.is_relative_to(root) else str(out))

    print(f"工程根：{root}")
    print(f"包：{len(sc.packages)} 个 | 组件：{sum(len(p['components']) for p in sc.packages)} 个 "
          f"| 资源登记：{len(sc.res_index)} 条 | 异常：{len(sc.anomalies)} 条")
    print("已生成：" + "、".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
