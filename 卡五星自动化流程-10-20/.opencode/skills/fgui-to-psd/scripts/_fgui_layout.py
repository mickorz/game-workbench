# -*- coding: utf-8 -*-
"""FGUI 界面 XML -> 布局还原清单（manifest JSON）。第 1 步：只解析，不开 PhotoCraft。

为什么要有这一步
----------------
FGUI 里节点的坐标是**相对父组件**的，组件还能层层嵌套
（XxxMahXuanZiView -> btnZi / Button9Scale），而且还有控制器 + gear 决定
"用哪张图 / 什么颜色 / 显不显示"。PSD 要的是"每个节点一层、绝对坐标摆好"。
这些换算必须在一处算清、并且**不依赖 Photopea 就能核对**，所以单独成脚本：
    _fgui_layout.py  ->  manifest.json  ->  _pc_build.py（在 PhotoCraft 里合成 PSD）

三条从 XML 实测确认的口径（写代码前先验证过的，不是猜的）
--------------------------------------------------------
1. **anchor="true" 时 xy 是 pivot 点的位置，不是左上角**。
   证据：`XxxMahXuanZiView.xml` 画布 1334 宽，`KW_Tip` 写 `xy="667,234" pivot="0.5,0.5" anchor="true"`
   —— 667 正是画布中轴；`btnZi.xml` 的 `title` 写 `xy="88,43"`，而组件 176×86 的中心就是 (88,43)。
   anchor 缺省(false)时 xy 才是左上角（如 `KW_Block xy="0,0" size="1334,750"`）。
2. **displayList 的书写顺序 = 从下到上**（第一个在最底）。
   证据：`btnZi.xml` 里 `icon`(卡面) 在 `title`(文字) 之前；视图里 `KW_Block`(压黑遮罩) 排第一，
   它必须在所有东西**下面**才讲得通。
3. **relation 是"增量"语义，不是"吸到父级中心"**。
   FGUI 的 XML 只存 sidePair（不存 offset），偏移量是加载时按**设计态几何**现算的：
       新值 = 设计值 + (父级新尺寸 - 父级设计尺寸) × 系数
   证据：`Button9Scale.xml` 组件设计 100×20，title 设计中心 y=9（父级中心是 10，即它本来偏上 1px），
   而实例 `KW_BTN_OK` 是 223×81。按增量口径：
       center_y = 9 + (81-20)/2 = 39.5
   而不是"吸到中心"的 81/2 = 40.5。两者差 1px —— 本脚本按**增量**（忠于 FGUI），
   并把这类 >0 的偏差记进 warnings，免得后面有人以为是算错了。
4. **`scale` 是渲染缩放，和 `size` 两码事，而且是累乘的**（2026-02 补）。
   节点的画布几何 = 局部几何 × 父级累计 scale；节点自己的 scale 再累乘后传给子节点。
   证据：`ResultItem.xml` 的 `KW_Mah_Hu xy="850,74" scale="0.484,0.484"`（组件设计 94×141），
   不乘 scale 这张牌高到 74+141=215，**越出 161 高的那一排**盖到下一排；
   `KW_Head size="120,120" scale="0.9"` 实际 108×108（gearSize 也写 0.9，互为印证）。
   以前脚本**完全忽略 scale**（全仓 `xxx_mah_xuanzi` 一个 `scale=` 都没有，所以一直没暴露）。
5. **`<list>` 要按 `<item>` 展开**（2026-02 补）。见 `expand_list()`：
   item 尺寸 = `defaultItem` 组件的设计尺寸，间距 = `colGap`/`lineGap`，在**列表局部单位**里排，
   再统一乘列表的累计缩放。不展开的症状是**整批牌不见了**。

用法
----
    python _fgui_layout.py <view.xml> [--assets DIR] [--out manifest.json]
                                  [--reuse 文件1,文件2] [--state-default C=页]
                                  [--state 节点名=C:页] [--quiet]

    # 例：把某界面还原成清单（--assets 不给时，从界面 XML 或当前目录向上找 *.fairy + assets/）
    python _fgui_layout.py "assets/<包名>/XxxView.xml" ^
      --reuse img_zi_check.png,img_xuanzi_btn_ok.png ^
      --state-default C_ZiState=0 ^
      --state KW_BTN_Zi_1=C_ZiState:1 --state KW_BTN_Zi_2=C_ZiState:2
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def find_project_root(start: Path):
    """从 start 向上找含 *.fairy + assets/ 的工程根（不写死任何本机路径）。"""
    cur = start.resolve()
    for _ in range(8):
        if list(cur.glob("*.fairy")) and (cur / "assets").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def resolve_assets(view: Path, assets_arg):
    """决定用哪个 assets/ 根目录。

    优先级：显式 --assets > 从界面 XML 位置向上找工程根 > 从当前目录向上找工程根。
    显式 --assets 既接受指向 assets/ 本身，也接受指向工程根。
    """
    if assets_arg:
        p = Path(assets_arg).resolve()
        if p.is_dir() and p.name == "assets":
            return p
        if (p / "assets").is_dir():
            return p / "assets"
        raise SystemExit(f"!! --assets 目录不存在或不是 assets/：{p}")
    root = find_project_root(view.parent) if view else None
    if root is None:
        root = find_project_root(Path.cwd())
    if root:
        return (root / "assets").resolve()
    raise SystemExit(
        "!! 找不到 FGUI 工程根（含 *.fairy 和 assets/ 的那层目录）。\n"
        "   请在工程根执行，或用 --assets 显式指定 assets/ 目录。"
    )


REUSE_PREFIX = "复用_"

# relation 里我们能正确解算的八种；其余一律告警（宁可吵，也不能静默算错）
SUPPORTED_RELATIONS = {
    ("width", "width"), ("height", "height"),
    ("center", "center"), ("middle", "middle"),
    ("left", "left"), ("top", "top"),
    ("right", "right"), ("bottom", "bottom"),
}

# 同一条轴上出现两个定位约束 = 自相矛盾（如 middle-middle + bottom-bottom），必须报出来
AXIS_OF_POSITION = {
    "left-left": "h", "center-center": "h", "right-right": "h",
    "top-top": "v", "middle-middle": "v", "bottom-bottom": "v",
}

WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print(f"   !! {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- 2D 仿射
#
# 节点的 scale / rotation / skew / 镜像 在 FGUI 里就是一套 2D 变换
# （TRS，绕 pivot 做，顺序：先 scale、再 skew、最后 rotation）。
# 统一用 2×3 仿射矩阵表示：(a, b, c, d, e, f)
#     X = a*x + c*y + e
#     Y = b*x + d*y + f
# 角度用**度数**；屏幕坐标 y 向下，所以正角在屏幕上是**顺时针**。
# 父级矩阵左乘子级矩阵（子级坐标先变到父级，再一路变到画布）。

def mat_identity():
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(m1, m2):
    """m1 ∘ m2（先作用 m2，再作用 m1）"""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def mat_apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def mat_translate(tx, ty):
    return (1.0, 0.0, 0.0, 1.0, float(tx), float(ty))


def mat_trs(rot_deg, skew_deg, sx, sy):
    """FGUI 顺序：scale -> skew -> rotation。skew=(kx,ky) 度数。"""
    kx = math.tan(math.radians(skew_deg[0])) if skew_deg[0] else 0.0
    ky = math.tan(math.radians(skew_deg[1])) if skew_deg[1] else 0.0
    th = math.radians(rot_deg)
    cs, sn = math.cos(th), math.sin(th)
    S = (float(sx), 0.0, 0.0, float(sy), 0.0, 0.0)
    K = (1.0, ky, kx, 1.0, 0.0, 0.0)          # x' = x + tan(kx)*y ; y' = y + tan(ky)*x
    R = (cs, sn, -sn, cs, 0.0, 0.0)           # 屏幕坐标下的顺时针旋转
    return mat_mul(R, mat_mul(K, S))


def aabb_of(m, w, h):
    """[0,w]×[0,h] 四角经 m 映射后的轴对齐包围盒 -> (l, t, r, b)"""
    pts = [mat_apply(m, 0, 0), mat_apply(m, w, 0),
           mat_apply(m, 0, h), mat_apply(m, w, h)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- 基础解析

def parse_pair(s, default=(0.0, 0.0)):
    """'176,86' -> (176.0, 86.0)"""
    if s is None or str(s).strip() == "":
        return default
    parts = [p for p in re.split(r"[,\s]+", str(s).strip()) if p != ""]
    try:
        v = [float(p) for p in parts]
    except ValueError:
        warn(f"坐标解析失败 {s!r}，按 {default} 处理")
        return default
    while len(v) < 2:
        v.append(0.0)
    return (v[0], v[1])


def parse_color(c):
    """FGUI 颜色：'#RRGGBB'（文字）或 '#AARRGGBB'（graph 填充）-> dict"""
    if not c:
        return None
    h = str(c).strip().lstrip("#")
    try:
        if len(h) == 8:                      # AARRGGBB
            a, r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
        elif len(h) == 6:                    # RRGGBB
            a = 255
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        elif len(h) == 3:                    # RGB
            a = 255
            r, g, b = (int(ch * 2, 16) for ch in h)
        else:
            warn(f"颜色位数不认识 {c!r}")
            return None
    except ValueError:
        warn(f"颜色解析失败 {c!r}")
        return None
    return {"hex": "#%02X%02X%02X" % (r, g, b), "a": a, "alpha": round(a / 255.0, 4)}


def is_true(el, key, default=False):
    v = el.get(key)
    if v is None:
        return default
    return str(v).strip().lower() == "true"


def node_scale(el):
    """节点的 `scale="0.464,0.464"` —— FGUI 的**渲染缩放**，和 `size` 是两码事。

    实测口径（结算 UI `ResultItem.xml`）：`KW_Mah_Hu xy="850,74" scale="0.484,0.484"`
    而组件设计尺寸是 94×141 —— 画出来是 45.5×68.2。按未缩放算（94×141）这张牌
    会高到 74+141=215，**越出 161 高的那一排**、盖到下一排去。
    同理 `KW_Head size="120,120" scale="0.9"` 实际是 108×108（gearSize 也写 0.9，互为印证）。

    scale 是**累乘**的：父级缩放会连同子节点位置/尺寸一起缩。
    """
    sx, sy = parse_pair(el.get("scale"), (1.0, 1.0))
    if not sx:
        sx = 1.0
    if not sy:
        sy = 1.0
    return sx, sy


def node_rotation(el):
    """`rotation="90"` —— 度数，屏幕上是顺时针。以前整条流水线**完全没解析**它，
    症状是上/下/对家的手牌牌面全部朝上、摆在未旋转的框里。"""
    v = el.get("rotation")
    if v is None or str(v).strip() == "":
        return 0.0
    try:
        return float(v)
    except ValueError:
        warn(f"rotation 解析失败 {v!r}（节点 {el.get('name')}），按 0 处理")
        return 0.0


def node_skew(el):
    """`skew="0,19"` —— (skewX, skewY) 度数。"""
    return parse_pair(el.get("skew"), (0.0, 0.0))


def rect_of(el, parent, deviations, size_override=None, xy_override=None,
            size_gear=None, design_out=None):
    """算出节点在**父级坐标系**里的矩形（左上角 + 宽高）。

    parent = {"w","h","dw","dh"}：父级的实际尺寸与实际尺寸对应的**设计尺寸**。
    两者不同（组件被实例放大/缩小）时，relation 按文件头第 3 条的增量口径解算。

    size_override：XML **没写 `size`** 时用来兜底的尺寸（如 `<image>` 的源图尺寸）。
    FGUI 里 `<image>` 不写 size 就等于源图尺寸，兜不上会算成 0×0，
    再经 anchor/pivot 换算位置也会跟着错。

    xy_override / size_gear：gearXY / gearSize 在**当前控制器页**下的值
    （空值 = 用该 gear 的 `default`，没有 gear = 用静态属性）。
    size_gear 是 4 个数 `w,h,scaleX,scaleY`（FGUI 的 GearSize 连缩放一起存）。

    design_out：把本次用到的**设计尺寸**写回给调用方 —— pivot 点要用它算。
    """
    x, y = parse_pair(xy_override if xy_override is not None else el.get("xy"), (0.0, 0.0))
    if size_gear is not None:
        dw, dh = float(size_gear[0]), float(size_gear[1])
    elif el.get("size") is None and size_override is not None:
        dw, dh = float(size_override[0]), float(size_override[1])
    else:
        dw, dh = parse_pair(el.get("size"), (0.0, 0.0))
    if design_out is not None:
        design_out[:] = [dw, dh]
    px, py = parse_pair(el.get("pivot"), (0.0, 0.0))

    if is_true(el, "anchor"):
        left, top = x - px * dw, y - py * dh
    else:
        left, top = x, y

    w, h = dw, dh
    rel_el = el.find("relation")
    if rel_el is None:
        return [left, top, w, h]

    pairs = [p.strip() for p in (rel_el.get("sidePair") or "").split(",") if p.strip()]
    seen_axis = {}
    for p in pairs:
        key = tuple(p.split("-")) if "-" in p else None
        if key not in SUPPORTED_RELATIONS:
            warn(f"暂不支持的 relation {p!r}（节点 {el.get('name')}）—— 该节点位置可能不对")
            continue
        ax = AXIS_OF_POSITION.get(p)
        if ax:
            if ax in seen_axis:
                warn(f"节点 {el.get('name')} 同一条轴上有两个定位约束 "
                     f"{seen_axis[ax]!r} + {p!r} —— 以 {p!r} 为准")
            seen_axis[ax] = p

    if "width-width" in pairs:
        w = dw + (parent["w"] - parent["dw"])
    if "height-height" in pairs:
        h = dh + (parent["h"] - parent["dh"])

    # 居中类：设计中心 + 父级尺寸变化的一半，再减掉自己（可能已被拉伸）的一半
    if "center-center" in pairs:
        new_cx = (left + dw / 2.0) + (parent["w"] - parent["dw"]) / 2.0
        if abs((new_cx - w / 2.0) - left) > 0.01:
            deviations.append(
                f"{el.get('name')} 的 center-center 按增量口径修正了 "
                f"{left:g} -> {new_cx - w / 2.0:g}（父级 {parent['dw']:g}->{parent['w']:g}）")
        left = new_cx - w / 2.0
    if "middle-middle" in pairs:
        new_cy = (top + dh / 2.0) + (parent["h"] - parent["dh"]) / 2.0
        if abs((new_cy - h / 2.0) - top) > 0.01:
            deviations.append(
                f"{el.get('name')} 的 middle-middle 按增量口径修正了 "
                f"{top:g} -> {new_cy - h / 2.0:g}（父级 {parent['dh']:g}->{parent['h']:g}）")
        top = new_cy - h / 2.0

    # 贴右边 / 贴下边：到父级右边（下边）的距离不变 —— 父级变宽（变高）多少就整体平移多少（系数 1）
    # 注意和 center/middle 的差别：那两个是自己拉到父级中心（系数 1/2），这两个是被父级边缘推着走。
    if "right-right" in pairs:
        new_left = left + (parent["w"] - parent["dw"])
        if abs(new_left - left) > 0.01:
            deviations.append(
                f"{el.get('name')} 的 right-right 按增量口径修正了 "
                f"{left:g} -> {new_left:g}（父级 {parent['dw']:g}->{parent['w']:g}）")
        left = new_left
    if "bottom-bottom" in pairs:
        new_top = top + (parent["h"] - parent["dh"])
        if abs(new_top - top) > 0.01:
            deviations.append(
                f"{el.get('name')} 的 bottom-bottom 按增量口径修正了 "
                f"{top:g} -> {new_top:g}（父级 {parent['dh']:g}->{parent['h']:g}）")
        top = new_top

    return [left, top, w, h]


# ---------------------------------------------------------------- 资源包索引

def scan_packages(assets_root: Path):
    """扫所有 package.xml：包 id -> {dir, res:{resid:{type,name,path,file}}}"""
    pkgs = {}
    for pxml in sorted(assets_root.rglob("package.xml")):
        try:
            root = ET.parse(pxml).getroot()
        except ET.ParseError as e:
            warn(f"package.xml 解析失败 {pxml}: {e}")
            continue
        pkgid = root.get("id")
        if not pkgid:
            continue
        res = {}
        res_el = root.find("resources")
        for e in (res_el if res_el is not None else []):
            res[e.get("id")] = {
                "type": e.tag,
                "name": e.get("name"),
                "path": e.get("path") or "/",
                "exported": e.get("exported") == "true",
                "id": e.get("id"),
                # 九宫格：`scale="9grid" scale9grid="左,上,右,下"`（单位 = 源图像素）
                "scale": e.get("scale"),
                "scale9grid": e.get("scale9grid"),
            }
        pkgs[pkgid] = {"dir": pxml.parent, "res": res, "xml": pxml}
    return pkgs


class Assets:
    def __init__(self, assets_root: Path):
        self.root = assets_root
        self.pkgs = scan_packages(assets_root)
        self._px_cache = {}

    def resolve_ui_url(self, url: str):
        """ui://xmahxuanxz002 -> 资源记录（pkgid 8 位 + resid 5 位）"""
        if not url:
            return None
        body = url[5:] if url.startswith("ui://") else url
        if "/" in body:
            pkgid, resid = body.split("/", 1)
        else:
            pkgid, resid = body[:8], body[8:]
        pkg = self.pkgs.get(pkgid)
        if not pkg:
            warn(f"找不到包 {pkgid}（来自 {url}）")
            return None
        r = pkg["res"].get(resid)
        if not r:
            warn(f"包 {pkgid} 里没有资源 {resid}（来自 {url}）")
            return None
        r = dict(r)
        r["ui"] = url
        r["pkg_id"] = pkgid
        r["file"] = str(Path(pkg["dir"]) / r["path"].strip("/") / r["name"])
        return self.enrich(r)

    def enrich(self, asset):
        """补上图片真实像素尺寸并检查文件在不在（PSD 里要不要缩放看它）"""
        if not asset or asset.get("type") not in ("image", "misc"):
            return asset
        f = asset["file"]
        if f in self._px_cache:
            asset["px"] = self._px_cache[f]
            return asset
        p = Path(f)
        if not p.exists():
            warn(f"图片文件不存在：{p}")
            asset["px"] = None
        else:
            try:
                from PIL import Image
                with Image.open(p) as im:
                    asset["px"] = [im.width, im.height]
            except Exception as e:
                warn(f"读不出图片尺寸 {p}：{e}")
                asset["px"] = None
        self._px_cache[f] = asset["px"]
        return asset

    def component_path(self, pkgid, resid):
        pkg = self.pkgs.get(pkgid)
        if not pkg:
            warn(f"找不到包 {pkgid}")
            return None
        r = pkg["res"].get(resid)
        if not r or r["type"] != "component":
            warn(f"包 {pkgid} 里 {resid} 不是组件")
            return None
        return Path(pkg["dir"]) / r["path"].strip("/") / r["name"]


# ---------------------------------------------------------------- 组件定义

class ComponentDef:
    """一个 component XML 的静态定义（尺寸 + 控制器默认页 + displayList）"""

    _cache = {}

    @classmethod
    def load(cls, path: Path):
        key = str(path)
        if key in cls._cache:
            return cls._cache[key]
        root = ET.parse(path).getroot()
        self = cls()
        self.path = path
        self.tag = root.tag
        self.w, self.h = parse_pair(root.get("size"), (0.0, 0.0))
        self.controllers = {}
        for c in root.findall("controller"):
            toks = [t for t in (c.get("pages") or "").split(",") if t != ""]
            pages = [(toks[i], toks[i + 1]) for i in range(0, len(toks) - 1, 2)]
            self.controllers[c.get("name")] = {
                "pages": pages,
                "selected": c.get("selected") or (pages[0][0] if pages else "0"),
            }
        self.display_list = root.find("displayList")
        self.button_ext = root.find("Button") is not None
        cls._cache[key] = self
        return self

    def default_state(self):
        return {n: c["selected"] for n, c in self.controllers.items()}

    def page_label(self, ctrl, page):
        c = self.controllers.get(ctrl)
        if not c:
            return None
        for pid, label in c["pages"]:
            if pid == page:
                return label
        return None


# ---------------------------------------------------------------- gear 解算

def gear_value(node_el, gear_tag, ctrl_name, state):
    """取该节点上某个 gear 在**当前页**下的值（没有对应页就返回 None = 用默认）"""
    for g in node_el.findall(gear_tag):
        if g.get("controller") != ctrl_name:
            continue
        pages = [p.strip() for p in (g.get("pages") or "").split(",")]
        vals = (g.get("values") or "").split("|")
        if len(vals) != len(pages):
            warn(f"{gear_tag} 的 pages/values 个数不匹配（{node_el.get('name')}）")
        cur = state.get(ctrl_name)
        for i, p in enumerate(pages):
            if p == cur and i < len(vals):
                return vals[i]
    return None


def gear_cur(node_el, gear_tag, state):
    """该 gear 在**当前控制器页**下的有效值串；没有这个 gear 就返回 None。

    FGUI 口径：当前页在 `pages` 里 -> 用 `values` 里对应的那一项（那一项可以是**空串**）；
    当前页不在 `pages` 里、或那一项是空串 -> 用 gear 自己的 `default`。
    （证据：`mahHandSelf.xml` 的 `KW_Value` 静态 `xy="2,21"` = pages="0,4,5" 里页 0 的
    值 `2,21`，而 `default="2,13"` 正是"不在 0/4/5 这三页时"的值。）
    """
    for g in node_el.findall(gear_tag):
        ctrl = g.get("controller")
        if ctrl not in state:
            continue
        v = gear_value(node_el, gear_tag, ctrl, state)
        if v is None or v.strip() == "":
            v = g.get("default")
        if v is not None and v.strip() != "":
            return v
    return None


def gear_xy_size(node_el, state):
    """gearXY / gearSize 在当前页下的值 -> (xy 串, [w,h,sx,sy] 或 None)"""
    xy = gear_cur(node_el, "gearXY", state)
    size = None
    raw = gear_cur(node_el, "gearSize", state)
    if raw:
        nums = []
        for t in raw.split(","):
            t = t.strip()
            if t == "":
                continue
            try:
                nums.append(float(t))
            except ValueError:
                warn(f"gearSize 的值不是数字：{raw!r}（节点 {node_el.get('name')}）")
                nums = []
                break
        if len(nums) >= 2:
            size = nums
    return xy, size


def resolve_visual(node_el, state):
    """把 gear 叠加到节点的 url / color / visible 上，得到"这一页实际长什么样"。

    gearLook 的取值串是 4 个数。实测 btnZi.xml：`pages="1" values="1,0,1,0"`
    对比默认 `default="1,0,0,1"` —— 差异正好在第 3 位（0->1）和第 4 位（1->0）。
    按 FGUI 语义第 3 位是 grayed（变灰）、第 4 位是 touchable（可点）；
    「他人已选」变灰且不可点，逻辑吻合。这里只取 grayed/alpha 用于出图。
    """
    out = {"visible": not (node_el.get("visible") == "false")}
    for tag in ("url", "color", "icon", "fontSize", "text"):
        if node_el.get(tag) is not None:
            out[tag] = node_el.get(tag)

    # 还没实现的 gear 一律吵出来 —— 静默忽略 = 位置/文字悄悄算错
    # （gearXY / gearSize / gearDisplay2 已实现，见 gear_xy_size / 下面那段）
    for tag in ("gearText", "gearFontSize", "gearAni", "gearIcon2", "gearColor2"):
        if node_el.findall(tag):
            warn(f"节点 {node_el.get('name')} 用了暂不支持的 <{tag}> —— 位置/文字可能不对")

    for ctrl, st in state.items():
        v = gear_value(node_el, "gearIcon", ctrl, state)
        if v is not None:
            for piece in v.split(","):
                if piece.startswith("ui://"):
                    out["url"] = piece

        v = gear_value(node_el, "gearColor", ctrl, state)
        if v is not None:
            out["color"] = v.split(",")[0]        # "色,描边色" 取第一个

        # gearDisplay 只写 pages（没有 values）：当前页**在**列表里 = 显示，不在 = 隐藏。
        # 注意两个方向都要写 —— KW_Check 自身 `visible="false"`，只有把页 2 判成 True
        # 它才会在"自己选中"时露出来（漏掉这一步的典型症状：对勾在所有状态都不显示）。
        for g in node_el.findall("gearDisplay"):
            if g.get("controller") != ctrl:
                continue
            pages = [p.strip() for p in (g.get("pages") or "").split(",")]
            out["visible"] = st in pages

        # gearDisplay2 = 「显示控制2」：**带条件的**显隐（FGUI Editor 里的"显示条件"）。
        # condition=0 -> 只在 `pages` 里那几页显示，其它页**隐藏**；
        # condition=1 -> 反过来（只在不是那几页时显示）。
        # 实测（comboLeft.xml，C_BuGang 页 id "1"=非、"0"=补杠）：
        #   `n5`(ImgBu 补杠图标) 用 gearDisplay pages="0"     -> 补杠时显示
        #   `n4`(arrow)/`n6`(icon_zimo) 用 gearDisplay2 pages="1" condition="0"
        #   -> 只显示在"非"，与 ImgBu 正好互斥；否则补杠态会两个图标一起叠着出。
        for g in node_el.findall("gearDisplay2"):
            if g.get("controller") != ctrl:
                continue
            pages = [p.strip() for p in (g.get("pages") or "").split(",") if p.strip()]
            try:
                cond = int(g.get("condition") or 0)
            except ValueError:
                warn(f"gearDisplay2 的 condition 不是整数（{node_el.get('name')}），按 0 处理")
                cond = 0
            inp = st in pages
            out["visible"] = inp if cond == 0 else (not inp)

        v = gear_value(node_el, "gearLook", ctrl, state)
        if v is not None:
            nums = [x.strip() for x in v.split(",")]
            for idx, key, conv in ((0, "alpha", float), (2, "grayed", lambda x: float(x) > 0.5)):
                if len(nums) > idx:
                    try:
                        out[key] = conv(nums[idx])
                    except ValueError:
                        pass
    return out


# ---------------------------------------------------------------- 展开

def node_transform(el, parent, ctx, size_override=None):
    """把一个节点的**画布几何**一次算清（位置/尺寸/缩放/镜像/旋转/斜切/gear 全算完）。

    返回 dict：
      rect    画布上的**轴对齐包围盒** [x, y, w, h]（w/h 恒为正）
      xf_box  盒内局部坐标 ([0,lw]×[0,lh]) -> 画布 的 2×3 仿射（子节点继承这个）
      xf_unit 单位盒 ([0,1]²) -> 画布（组装阶段贴图用：含旋转/斜切/镜像/缩放）
      box     节点未变换的局部盒尺寸 [lw, lh]
      M       父级设计空间 -> 画布

    变换口径（FGUI）：绕 **pivot** 做 TRS —— 先 scale（带符号 = 镜像）、再 skew、
    最后 rotation；anchor="true" 时 xy 就是 pivot 的位置，否则 xy 是左上角，
    pivot 是相对左上角的偏移（px*dw, py*dh）。
    pivot=(0,0)（FGUI 的默认值）时，这套公式退化成"按左上角缩放"，与旧版逐像素一致。
    """
    gxy, gsz = gear_xy_size(el, ctx["state"])
    design = [0.0, 0.0]
    r = rect_of(el, parent, ctx["deviations"], size_override=size_override,
                xy_override=gxy, size_gear=gsz, design_out=design)
    lx, ly, lw, lh = r
    sx, sy = node_scale(el)
    if gsz is not None and len(gsz) >= 4:
        # GearSize 的值是 `w,h,scaleX,scaleY`（实测 mahHandSelf.xml 的 KW_Value：
        # `94,118,1,1|92,115,1,1|92,100,1,1`，其中的 94×118 正是静态 size）
        sx, sy = gsz[2], gsz[3]
    rot = node_rotation(el)
    skew = node_skew(el)
    px, py = parse_pair(el.get("pivot"), (0.0, 0.0))
    dw, dh = design
    piv = (lx + px * dw, ly + py * dh)
    lin = mat_trs(rot, skew, sx, sy)
    local = mat_mul(mat_translate(piv[0], piv[1]),
                    mat_mul(lin, mat_translate(-piv[0], -piv[1])))
    M = mat_mul(ctx["xf"], local)
    xf_box = mat_mul(M, mat_translate(lx, ly))
    l, t, rr, b = aabb_of(xf_box, lw, lh)
    xf_unit = mat_mul(xf_box, (lw, 0.0, 0.0, lh, 0.0, 0.0))
    return {
        "rect": [round(l, 2), round(t, 2), round(rr - l, 2), round(b - t, 2)],
        "xf_box": xf_box,
        "xf_unit": xf_unit,
        "box": [lw, lh],
        "M": M,
        "sx": sx, "sy": sy, "rot": rot, "skew": skew,
        "design": [dw, dh], "gxy": gxy, "gsz": gsz,
        # 累计缩放（旋转不变）：文字字号要按它乘
        "ax": math.hypot(M[0], M[1]), "ay": math.hypot(M[2], M[3]),
    }


def expand_display_list(dl, parent, ctx, out_children):
    """把一个 displayList 展开成 out_children。

    FGUI 的 `<group>`（布局组）不是画面元素，但它是个真实节点，
    这里保留成 PSD 的图层组；组内成员靠子节点的 `group="n8_xz01"` 归属。
    """
    group_nodes = {}
    for el in dl:
        if el.tag == "group":
            geo = node_transform(el, parent, ctx)
            gvis = resolve_visual(el, ctx["state"])
            group_nodes[el.get("id")] = {
                "name": el.get("name") or el.get("id"),
                "kind": "group",
                "rect": geo["rect"],
                "xf": [round(v, 6) for v in geo["xf_unit"]],
                "box": [round(geo["box"][0], 4), round(geo["box"][1], 4)],
                "scale": [round(geo["sx"], 4), round(geo["sy"], 4)],
                "rotation": geo["rot"],
                "skew": [geo["skew"][0], geo["skew"][1]],
                "layout": el.get("layout"),
                "colGap": el.get("colGap"),
                "rowGap": el.get("rowGap"),
                "fgui_id": el.get("id"),
                "visible": gvis.get("visible", True),
                "alpha": gvis.get("alpha", 1.0),
                "grayed": gvis.get("grayed", False),
                "children": [],
            }

    final = []
    for el in dl:
        if el.tag == "group":
            final.append(group_nodes[el.get("id")])
            continue
        node = expand_node(el, parent, ctx)
        if node is None:
            continue
        gid = el.get("group")
        if gid and gid in group_nodes:
            group_nodes[gid]["children"].append(node)
        else:
            final.append(node)
    out_children.extend(final)
    return final


def expand_node(el, parent, ctx):
    """单个节点 -> manifest 节点（None = 不画）"""
    vis = resolve_visual(el, ctx["state"])
    name = el.get("name") or el.get("id")

    # 图/loader 的资源要**先**解析：`<image>` 不写 size 时尺寸就是源图尺寸，
    # 而 rect（尤其 anchor 的 pivot 换算）必须先知道尺寸才算得对。
    asset = None
    url = None
    if el.tag in ("image", "loader", "movieclip"):
        url = vis.get("url")
        asset = ctx["assets"].resolve_ui_url(url) if url else None
        if el.tag == "image" and not asset and el.get("src"):
            # `src` 是**本包内**的资源号；跨包引用时 XML 会带 `pkg="<包id>"`
            # （例：btnKouPai.xml 的 KW_Back src="ivlvo" pkg="n3dx31ny"）。
            # 不认这个属性就会去本包里找，报「包里没有资源」。
            asset = ctx["assets"].resolve_ui_url(
                "ui://%s%s" % (el.get("pkg") or ctx["pkg_id"], el.get("src")))

    size_ov = None
    if asset and asset.get("px") and el.get("size") is None:
        size_ov = (asset["px"][0], asset["px"][1])

    # `<component>` 实例不写 `size` 时尺寸 = **组件设计尺寸**（FGUI 口径）——
    # 和 `<image>` 不写 size = 源图尺寸（坑 12）是同一类兜底。
    # 不兜底就按 0×0 算：子节点的 relation 会全部吃到 (0 − 设计尺寸) 的增量。
    # 实测 playerHead 设计 88×116 被当成 0×0，`KW_Chat_Back`（XML 明写 size="179,52"）
    # 被算成 179−88=91 × 52−116=**−64**（负高度），而且**静默出错、日志里不提**。
    if el.tag == "component" and el.get("size") is None:
        cs = component_design_size(el, ctx)
        if cs:
            size_ov = cs

    geo = node_transform(el, parent, ctx, size_override=size_ov)
    lw, lh = geo["box"]
    ax, ay = geo["ax"], geo["ay"]
    base = {
        "name": name,
        "rect": geo["rect"],
        # xf：单位盒 [0,1]² -> 画布 的仿射（含缩放/镜像/旋转/斜切）——
        # 组装阶段按它贴图，旋转和镜像才落得下来。
        "xf": [round(v, 6) for v in geo["xf_unit"]],
        "box": [round(lw, 4), round(lh, 4)],
        "fgui_id": el.get("id"),
        "visible": vis.get("visible", True),
        "alpha": vis.get("alpha", 1.0),
        "grayed": vis.get("grayed", False),
        "scale": [round(geo["sx"], 4), round(geo["sy"], 4)],
        "rotation": geo["rot"],
        "skew": [geo["skew"][0], geo["skew"][1]],
    }

    if el.tag == "component":
        return expand_component(el, geo, ctx, base)

    if el.tag == "list":
        return expand_list(el, geo, ctx, base)

    if el.tag == "text":
        # 字号也走 scale：FGUI 里 `fontSize` 是**未缩放**值，编辑器/运行时看到的是
        # fontSize × 节点累计缩放（实测 KW_Score XML 32px、scale 0.77 → 画出来 24.64px；
        # KW_Nickname 22px、scale 0.9 → 19.8px）。两个值都留在清单里，好对账。
        fs_xml = float(el.get("fontSize") or 12)
        return dict(base, kind="text",
                    text=el.get("text") or "",
                    fontSize=round(fs_xml * ay, 2),
                    fontSize_xml=fs_xml,
                    fontScale=round(ay, 4),
                    color=parse_color(vis.get("color")),
                    bold=is_true(el, "bold"),
                    italic=is_true(el, "italic"),
                    align=el.get("align") or "left",
                    valign=el.get("vAlign") or "top",
                    singleLine=is_true(el, "singleLine"),
                    strokeColor=parse_color(el.get("strokeColor")),
                    strokeSize=float(el.get("strokeSize") or 0))

    if el.tag in ("image", "loader", "movieclip"):
        # 没有图源的 loader **不能在这儿就丢掉**：Button 扩展属性
        # （`<Button icon="ui://..."/>`）是**展开之后**才盖到子节点 `icon` 上的，
        # 这里返回 None 会让覆盖命中不到子节点（症状：两个按钮的底图整层消失）。
        # 真正的剔除在 build_manifest 末尾统一做（prune_empty_images）。
        return dict(base, kind="image",
                    asset=asset,
                    fit=el.get("fill") or "none",
                    align=el.get("align") or "left",
                    valign=el.get("vAlign") or "top",
                    src=el.get("src"),
                    url=url,
                    # `<image color="#ffc4c4">` 是**染色**（FGUI 口径：与纹理相乘，不是不透明覆盖）。
                    # 不认它的症状实测：`njiesuan` 的 `n33`（color="#000000"）本该是黑色 35% 的
                    # 遮罩条，产物里变成原图的浅粉圆角块，正好压在「本家」上。
                    tint=parse_color(vis.get("color")),
                    # `<image blend="multiply">` 是图层混合模式（FGUI 运行时改的是 blendMode）。
                    # 不认它的症状实测：`mahHandSelf` 的 `mask` 本该正片叠底压在牌面上，
                    # 产物里按普通模式盖上去，把 `8B.png`（八条）整张糊白。
                    blend=el.get("blend"),
                    # FGUI 的九宫格标记（package.xml 里 `scale="9grid" scale9grid="l,t,r,b"`）：
                    # atlas 图被拉到节点框尺寸时**只拉中间**，四角保持原像素，
                    # 不认它就整图缩放 —— 圆角会被横向拉变形。
                    scale9=bool(asset and asset.get("scale") == "9grid"),
                    scale9grid=(asset or {}).get("scale9grid"))

    if el.tag == "graph":
        return dict(base, kind="rect",
                    shape=el.get("type") or "rect",
                    fill=parse_color(el.get("fillColor")),
                    lineSize=float(el.get("lineSize") or 0),
                    lineColor=parse_color(el.get("lineColor")))

    warn(f"暂不支持的节点类型 <{el.tag}> name={name}")
    return None


def component_design_size(el, ctx):
    """组件实例不写 `size` 时的兜底尺寸 = 那个 component XML 头上的 `size`。

    解析不出来就返回 None（`expand_component` 那边会照常报「组件文件不存在」，
    这里不重复吵）。
    """
    resid = el.get("src")
    if not resid:
        return None
    pkgid = el.get("pkg") or ctx["pkg_id"]
    cpath = ctx["assets"].component_path(pkgid, resid)
    if not cpath or not Path(cpath).exists():
        return None
    comp = ComponentDef.load(Path(cpath))
    if not comp.w and not comp.h:
        return None
    return (comp.w, comp.h)


def expand_component(el, geo, ctx, base):
    """展开组件实例：加载定义，套实例覆盖，再递归展开它的 displayList。

    实例可以覆盖组件内部属性（FGUI 的"扩展"机制）：
      * `controller="C_ZiState,1"`  指定控制器页值
      * `<Button title=.. titleColor=.. titleFontSize=.. icon=.. />` Button 扩展属性，
        分别落到子节点 `title`(文字) 与 `icon`(图) 上

    子节点坐标相对实例的**局部**盒（未变换的左上角），实例自己的整套变换
    （缩放/镜像/旋转/斜切/gear）通过 `ctx["xf"]` 一路传下去 —— 所以旋转的实例
    里每个子节点都会跟着转，位置也对。
    """
    pkgid = el.get("pkg") or ctx["pkg_id"]
    resid = el.get("src")
    if not resid:
        warn(f"component {base['name']} 没有 src，跳过")
        return dict(base, kind="group", children=[])
    cpath = ctx["assets"].component_path(pkgid, resid)
    if not cpath or not Path(cpath).exists():
        # 跨包引用没解析出来（如快照只含本轮包、缺被引用的包）时**不能崩**：
        # 返回一个空的 group 节点占位，`print_tree` / 组装阶段照常走。
        warn(f"组件文件不存在：{cpath}")
        return dict(base, kind="group", children=[])

    comp = ComponentDef.load(Path(cpath))

    # ---- 页值优先级：组件默认 < 实例 controller 属性 < --state-default < --state
    state = dict(comp.default_state())
    ctrl_attr = el.get("controller")
    if ctrl_attr:
        toks = [t.strip() for t in ctrl_attr.split(",")]
        for i in range(0, len(toks) - 1, 2):
            state[toks[i]] = toks[i + 1]

    ctx["_used_ctrl"].add(base["name"])
    for k, v in ctx["state_default"].items():
        # 只覆盖**这个组件真的有的**控制器，否则会把无关控制器塞进每一层
        if k in comp.controllers:
            state[k] = v
            ctx["_hit_ctrl"].add(k)
    for k, v in ctx["state_over"].get(base["name"], {}).items():
        if k in comp.controllers:
            state[k] = v
            ctx["_hit_ctrl"].add(k)
        else:
            warn(f"--state {base['name']}={k}:{v} —— 组件 {Path(cpath).name} 没有控制器 {k}")

    child_ctx = dict(ctx)
    child_ctx["state"] = state
    child_ctx["pkg_id"] = pkgid
    child_ctx["xf"] = geo["xf_box"]

    w, h = geo["box"]
    children = []
    if comp.display_list is not None:
        # 子节点坐标相对**实例**；relation 要同时知道实例尺寸和组件设计尺寸
        child_parent = {"w": w, "h": h, "dw": comp.w, "dh": comp.h}
        if abs(w - comp.w) > 0.01 or abs(h - comp.h) > 0.01:
            ctx["deviations"].append(
                f"组件 {Path(cpath).name} 设计 {comp.w:g}×{comp.h:g}，"
                f"实例 {base['name']} 实为 {w:g}×{h:g} —— 子节点按 relation 增量重算")
        expand_display_list(comp.display_list, child_parent, child_ctx, children)

    # ---- Button 扩展属性覆盖到子节点
    def find_child(nodes, nm):
        for n in nodes:
            if n["name"] == nm:
                return n
            if n.get("children"):
                got = find_child(n["children"], nm)
                if got:
                    return got
        return None

    btn = el.find("Button")
    if btn is not None:
        overrides = {}
        if btn.get("title") is not None:
            overrides.setdefault("title", {})["text"] = btn.get("title")
        if btn.get("titleColor") is not None:
            overrides.setdefault("title", {})["color"] = parse_color(btn.get("titleColor"))
        if btn.get("titleFontSize") is not None:
            overrides.setdefault("title", {})["fontSize"] = float(btn.get("titleFontSize"))
            overrides["title"]["fontSize_xml"] = float(btn.get("titleFontSize"))
        if btn.get("icon") is not None:
            overrides.setdefault("icon", {})["url"] = btn.get("icon")
        for cname, props in overrides.items():
            node = find_child(children, cname)
            if node is None:
                warn(f"Button 覆盖属性命中不到子节点 {cname!r}（实例 {base['name']}）")
                continue
            if "url" in props:
                node["asset"] = ctx["assets"].resolve_ui_url(props["url"])
                node["url"] = props["url"]
            for k in ("text", "color", "fontSize"):
                if k in props:
                    if k == "fontSize":
                        # 实例上的 titleFontSize 也是**未缩放**值：节点若在缩放过的父级里，
                        # 画出来的字号还要再乘一次累计缩放（本界面按钮没缩放，
                        # 但口径不能只对本界面成立）。
                        node["fontSize"] = round(props[k] * node.get("fontScale", 1.0), 2)
                        node["fontSize_xml"] = props.get("fontSize_xml", props[k])
                    else:
                        node[k] = props[k]

    zi = comp.page_label("C_ZiState", state.get("C_ZiState")) if "C_ZiState" in comp.controllers else None
    is_common = bool(el.get("pkg") and el.get("pkg") != ctx.get("root_pkg_id"))
    base.update(kind="group",
                is_component=True,
                is_common_pkg=is_common,
                component=str(cpath),
                component_size=[comp.w, comp.h],
                controller_state=state,
                state_label=zi,
                children=children)
    return base


def expand_list(el, geo, ctx, base):
    """展开 `<list>`：按 `defaultItem` 把 XML 里那些 `<item>` 实例化出来，再按 layout 排。

    以前脚本直接 `warn("暂不支持的节点类型 <list>")` 整块跳过 —— 症状是**整批牌不见了**
    （`ResultItem.xml` 每排 8 张 ×3 排 + `MainResultLayer.xml` 6 张 = 38 张）。
    这些 `<item controllers="state,5"/>` 是**设计态**就摆在编辑器里的列表项，
    FGUI 加载时会照 `defaultItem` 建对象，所以它们是界面的一部分，不是运行时数据。

    item 的尺寸 = `defaultItem` 那个组件的设计尺寸，间距 = `colGap` / `lineGap`，
    全在**列表的局部单位**里算，最后统一乘列表自己的变换（`geo["xf_box"]`）
    —— 牌的间距必须这么算，否则 scale 0.464 的列表会被摆成 2 倍宽。

    layout 口径（FGUI 的 ListLayoutType 序列化名）：
      `row` 单行 / `column` 单列 / `flow_hz` 水平流式（超宽换行）/ `flow_vt` 垂直流式。
    """
    name = base["name"]
    items = el.findall("item")
    if not items:
        # 运行时才 addItemFromPool 的列表，设计态本来就是空的（如 ScoreFlow 的流水列表）
        return None

    url = el.get("defaultItem")
    if not url:
        warn(f"list {name} 有 {len(items)} 个 item，但没写 defaultItem —— 实例化不了，整块跳过")
        return None
    a = ctx["assets"].resolve_ui_url(url)
    if not a or a.get("type") != "component":
        warn(f"list {name} 的 defaultItem {url} 不是组件 —— 整块跳过")
        return None
    cpath = Path(a["file"])
    if not cpath.exists():
        warn(f"list {name} 的 defaultItem 组件文件不存在：{cpath} —— 整块跳过")
        return None
    comp = ComponentDef.load(cpath)
    if not comp.w and not comp.h:
        warn(f"list {name} 的 defaultItem 组件 {cpath.name} 没有尺寸 —— 整块跳过")
        return None

    layout = (el.get("layout") or "row").strip()
    col_gap = parse_pair(el.get("colGap"), (0.0, 0.0))[0]
    row_gap = parse_pair(el.get("lineGap") or el.get("rowGap"), (0.0, 0.0))[0]
    lw, lh = parse_pair(el.get("size"), (0.0, 0.0))
    step_x, step_y = comp.w + col_gap, comp.h + row_gap

    per_row = per_col = 1
    if layout == "row":
        per_row = len(items)                    # 单行：一行到底，不换行（overflow=scroll）
    elif layout == "flow_hz":
        per_row = max(1, int((lw + col_gap) // step_x)) if step_x > 0 else 1
    elif layout == "column":
        per_col = len(items)                    # 单列：一列到底
    elif layout == "flow_vt":
        per_col = max(1, int((lh + row_gap) // step_y)) if step_y > 0 else 1
    else:
        warn(f"list {name} 的 layout={layout!r} 暂不支持 —— 整块跳过")
        return None

    kids = []
    for i, it in enumerate(items):
        if layout in ("row", "flow_hz"):
            ix, iy = (i % per_row) * step_x, (i // per_row) * step_y
        else:
            ix, iy = (i // per_col) * step_x, (i % per_col) * step_y
        sub = ET.Element("component")
        sub.set("id", "%s_item_%d" % (el.get("id") or name, i))
        # 图层名：列表名 + 序号（FGUI 里这些 item 没有自己的节点名，只有 defaultItem 的组件名）
        sub.set("name", "%s_%d" % (name, i))
        sub.set("src", a["id"])
        sub.set("pkg", a["pkg_id"])
        sub.set("xy", "%g,%g" % (ix, iy))
        sub.set("size", "%g,%g" % (comp.w, comp.h))
        if it.get("controllers"):
            sub.set("controller", it.get("controllers"))
        item_ctx = dict(ctx)
        item_ctx["xf"] = geo["xf_box"]
        node = expand_node(sub, {"w": lw, "h": lh, "dw": lw, "dh": lh}, item_ctx)
        if node is not None:
            kids.append(node)

    if not kids:
        return None

    # 单行/单列放不下时 FGUI 是滚动（overflow="scroll"），坐标照原样摆，但要报出来
    total_x = (len(kids) - 1) * step_x + comp.w if layout in ("row", "flow_hz") else comp.w
    if layout == "row" and total_x > lw + 0.5:
        ctx["deviations"].append(
            f"list {name}（单行）：{len(kids)} 项共 {total_x:g} 宽 > 列表框 {lw:g} —— "
            f"FGUI 里这排会横向滚动，这里照 FGUI 的坐标原样摆（右边会超出列表框）")
    if layout == "flow_hz" and per_row * step_x - col_gap > lw + 0.5:
        ctx["deviations"].append(
            f"list {name}（水平流式）：一行放 {per_row} 项共 "
            f"{per_row * step_x - col_gap:g} 宽 > 列表框 {lw:g}")

    base.update(kind="group",
                is_list=True,
                list_layout=layout,
                list_item=Path(cpath).name,
                list_item_size=[comp.w, comp.h],
                children=kids)
    return base


# ---------------------------------------------------------------- 美术规范标签推导（遵照 .opencode/knowledge/psd-art-spec.md）

def apply_art_spec_tags(nodes, reuse_names=None, scale9_names=None, root_pkg_id=None):
    """根据 psd-art-spec.md 规范自动推导 PSD 图层与组的初始结构标签。
    严禁提前注入【新】标签。
    """
    reuse_names = set(reuse_names or [])
    scale9_names = set(scale9_names or [])
    hits = []

    def walk(ns):
        for n in ns:
            if n.get("children") is not None:
                walk(n["children"])

            name = n.get("name") or "Layer"
            kind = n.get("kind")
            prefix = ""

            # 1. 结构与容器标签
            if kind == "group":
                if n.get("is_list"):
                    prefix = "【列表】"
                elif n.get("is_common_pkg"):
                    prefix = "【common】"
                elif n.get("is_component"):
                    prefix = "【group】"
            elif kind == "rect":
                # 遮罩或大底板
                if "block" in name.lower() or "mask" in name.lower() or "bg" in name.lower():
                    prefix = "【ignore】"

            # 2. 切片资源标签（九宫格 / 复用）
            a = n.get("asset") or {}
            fname = a.get("name") or n.get("file") or ""
            is_reused = bool((fname and fname in reuse_names) or (name in reuse_names) or n.get("reused"))
            if is_reused:
                n["reused"] = True
                n["reuse_reason"] = f"复用工程现有资源 {fname or name}"
                hits.append((name, fname or name))

            is_scale9 = bool(n.get("scale9") or (fname and fname in scale9_names) or (name in scale9_names))
            if is_scale9:
                prefix = prefix + "【九宫】"

            if is_reused:
                prefix = prefix + "复用_"

            n["layer"] = (prefix + name) if prefix else name

    walk(nodes)
    return hits


# 兼容旧名
mark_reuse = apply_art_spec_tags


# ---------------------------------------------------------------- 主流程

def prune_unrenderable(nodes, dropped):
    """剔掉**文字内容为空串**的节点（FGUI 里就不显示任何字）。

    `Button9Scale` 的 `title` 就是这种：按钮上的字是**烤进按钮图里**的，
    XML 的 `title` 留空。这种节点出一个空文字层毫无意义，直接摘掉并记一笔。
    """
    kept = []
    for n in nodes:
        kids = n.get("children")
        if kids is not None:                     # 组不做剔除，只往下递归
            n["children"] = prune_unrenderable(kids, dropped)
        if n.get("kind") == "text" and not (n.get("text") or ""):
            a = n["rect"]
            dropped.append(f"{n['name']} @ ({a[0]:g},{a[1]:g}) {a[2]:g}×{a[3]:g}"
                           f" —— 文字内容为空串")
            continue
        kept.append(n)
    return kept


def collect_empty_images(nodes, out):
    """记下**没有图源**的图节点；**留在树里**（组装时可以用 `--fill` 补上）。

    FGUI 里 loader 是留给代码运行时 `setURL` 的占位（`btnKouPai.xml` 的
    `KW_Value` 就是牌面，由逻辑填），XML 里根本没写图名 —— 既不能克隆源 PSD
    零件，也没有 atlas 文件可读。**必须逐条报出来**：出图的人要一眼看到
    "这四张牌面是空的"，而不是等美术翻半天发现少了一层。
    """
    for n in nodes:
        if n.get("kind") == "image" and not n.get("asset"):
            a = n["rect"]
            out.append(f"{n['name']} @ ({a[0]:g},{a[1]:g}) {a[2]:g}×{a[3]:g}"
                       + (f" [{n['url']}]" if n.get("url") else " [XML 里没写图名]"))
        if n.get("children"):
            collect_empty_images(n["children"], out)


def build_manifest(view_xml: Path, assets_root: Path, reuse=None, state_default=None, state_over=None, scale9_names=None):
    assets = Assets(assets_root)
    view = ComponentDef.load(view_xml)
    reuse = reuse or []
    state_default = state_default or {}
    state_over = state_over or {}
    scale9_names = scale9_names or []

    pkgid = None
    for pid, p in assets.pkgs.items():
        if p["xml"].parent == view_xml.parent:
            pkgid = pid
            break
    if pkgid is None:
        warn(f"找不到 {view_xml.name} 所属的包（按目录匹配 package.xml）")

    ctx = {
        "assets": assets,
        "pkg_id": pkgid,
        "root_pkg_id": pkgid,
        "state": dict(view.default_state()),
        "state_default": state_default,
        "state_over": state_over,
        # 从界面根往下的累计变换（2×3 仿射）：父级设计空间 -> 画布
        "xf": mat_identity(),
        "deviations": [],
        "empty_images": [],
        "dropped_text": [],
        "_used_ctrl": set(),
        "_hit_ctrl": set(),
    }

    nodes = []
    root_parent = {"w": view.w, "h": view.h, "dw": view.w, "dh": view.h}
    if view.display_list is not None:
        expand_display_list(view.display_list, root_parent, ctx, nodes)

    hits = apply_art_spec_tags(nodes, reuse_names=set(reuse), scale9_names=set(scale9_names), root_pkg_id=pkgid)
    nodes = prune_unrenderable(nodes, ctx["dropped_text"])
    collect_empty_images(nodes, ctx["empty_images"])

    # 命令行给了但一次都没命中的，明确告警（防止"以为改了其实没改"）
    for k in state_default:
        if k not in ctx["_hit_ctrl"]:
            warn(f"--state-default {k}=... 没命中任何组件（控制器名写错了？）")
    for node_name in state_over:
        if node_name not in ctx["_used_ctrl"]:
            warn(f"--state {node_name}=... 没找到这个组件节点")

    return {
        "canvas": {"w": view.w, "h": view.h},
        "source": {"view": str(view_xml), "assets_root": str(assets_root), "pkg_id": pkgid},
        "reuse_prefix": REUSE_PREFIX,
        "reuse_hits": [{"node": a, "asset": b} for a, b in hits],
        "state_default": state_default,
        "state_over": state_over,
        "deviations": ctx["deviations"],
        "empty_images": ctx["empty_images"],
        "dropped_text": ctx["dropped_text"],
        "warnings": WARNINGS,
        "nodes": nodes,
    }


def iter_nodes(nodes):
    for n in nodes:
        yield n
        for c in n.get("children") or []:
            yield from iter_nodes([c])


def fmt_rect(r):
    return f"({r[0]:g},{r[1]:g}) {r[2]:g}×{r[3]:g}"


def print_tree(nodes, indent=1):
    for n in nodes:
        pad = "  " * indent
        kind = n["kind"]
        tag = {"group": "组", "text": "文字", "image": "图", "rect": "形状"}.get(kind, kind)
        extra = ""
        if kind == "text":
            extra = (f'  "{n["text"]}" {n["fontSize"]:g}px'
                     f'{"粗" if n.get("bold") else ""}'
                     f' {(n.get("color") or {}).get("hex", "")}')
        elif kind == "image":
            a = n.get("asset") or {}
            px = a.get("px")
            extra = f'  [{a.get("name") or n.get("url") or "无图"}]'
            if px:
                r = n["rect"]
                if abs(px[0] - r[2]) > 0.01 or abs(px[1] - r[3]) > 0.01:
                    extra += f" {px[0]}×{px[1]}→缩放{r[2]:g}×{r[3]:g}"
        elif kind == "rect":
            f = n.get("fill") or {}
            extra = f'  {f.get("hex","")} α{f.get("alpha",1):g}'
        flags = []
        if n.get("reused"):
            flags.append("复用")
        if not n.get("visible", True):
            flags.append("隐藏")
        if n.get("grayed"):
            flags.append("变灰")
        if n.get("state_label"):
            flags.append("态=" + n["state_label"])
        sc = n.get("scale")
        if sc and (abs(sc[0] - 1) > 1e-6 or abs(sc[1] - 1) > 1e-6):
            flags.append(f"缩放{sc[0]:g}×{sc[1]:g}")
        if n.get("rotation"):
            flags.append(f"旋转{n['rotation']:g}°")
        sk = n.get("skew")
        if sk and (abs(sk[0]) > 1e-6 or abs(sk[1]) > 1e-6):
            flags.append(f"斜切{sk[0]:g},{sk[1]:g}")
        if n.get("list_item_count"):
            flags.append(f"{n.get('list_layout')}列表×{n['list_item_count']}"
                         f"（item={n.get('list_item')} {n['list_item_size'][0]:g}×{n['list_item_size'][1]:g}）")
        flag_s = ("  ← " + " ".join(flags)) if flags else ""
        layer = n.get("layer")
        layer_s = f"  层名[{layer}]" if layer and layer != n["name"] else ""
        print(f"{pad}{tag} {n['name']}  {fmt_rect(n['rect'])}{extra}{layer_s}{flag_s}")
        if n.get("children"):
            print_tree(n["children"], indent + 1)


def main():
    ap = argparse.ArgumentParser(description="FGUI 界面 XML -> 布局还原清单 JSON")
    ap.add_argument("view", nargs="?", help="界面 XML（如 XxxMahXuanZiView.xml，给 --spec 时可省）")
    ap.add_argument("--spec", help="输入客观事实 psd-spec.json 路径（自动读取 view、复用与九宫格）")
    ap.add_argument("--assets", default=None,
                    help="FGUI assets 根目录（默认从界面 XML/当前目录向上找 *.fairy + assets/）")
    ap.add_argument("--out", help="manifest JSON 输出路径（不给就只打印不写）")
    ap.add_argument("--reuse", default="",
                    help="复用了现有资源、不需要重导出的图片文件名，逗号分隔")
    ap.add_argument("--scale9", default="",
                    help="九宫格切片资源文件名，逗号分隔")
    ap.add_argument("--state-default", action="append", default=[],
                    metavar="控制器=页", help="统一指定控制器页值，可重复")
    ap.add_argument("--state", action="append", default=[],
                    metavar="节点名=控制器:页", help="按节点名单独指定页值，可重复")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    reuse = [s.strip() for s in a.reuse.split(",") if s.strip()]
    scale9 = [s.strip() for s in a.scale9.split(",") if s.strip()]
    view_path_str = a.view

    if a.spec:
        spec_p = Path(a.spec).resolve()
        if not spec_p.is_file():
            raise SystemExit(f"!! 找不到 spec 文件：{spec_p}")
        try:
            sdata = json.loads(spec_p.read_text(encoding="utf-8-sig"))
            if not view_path_str and sdata.get("view_xml"):
                view_path_str = sdata.get("view_xml")
            for node in sdata.get("nodes", []):
                n_name = node.get("name")
                f_name = node.get("file")
                if node.get("is_reuse"):
                    if n_name: reuse.append(n_name)
                    if f_name: reuse.append(f_name)
                if node.get("is_scale9"):
                    if n_name: scale9.append(n_name)
                    if f_name: scale9.append(f_name)
        except Exception as e:
            raise SystemExit(f"!! 读取 spec 失败：{e}")

    if not view_path_str:
        raise SystemExit("!! 必须提供界面 XML 或 --spec 参数")

    state_default = {}
    for s in a.state_default:
        if "=" not in s:
            raise SystemExit(f"!! --state-default 格式应为 控制器=页，收到 {s!r}")
        k, v = s.split("=", 1)
        state_default[k.strip()] = v.strip()

    state_over = {}
    for s in a.state:
        if "=" not in s or ":" not in s:
            raise SystemExit(f"!! --state 格式应为 节点名=控制器:页，收到 {s!r}")
        node, rest = s.split("=", 1)
        ctrl, page = rest.rsplit(":", 1)
        state_over.setdefault(node.strip(), {})[ctrl.strip()] = page.strip()

    view = Path(view_path_str)
    if not view.is_file():
        # 尝试从 a.assets 或 workspace.json 的 client_dir 寻找
        cand_roots = []
        if a.assets:
            cand_roots.append(Path(a.assets))
        ws_root = find_project_root(Path.cwd())
        if ws_root:
            cand_roots.append(ws_root)
        # 读取 workspace.json
        try:
            dotopen = Path(__file__).resolve().parents[3]
            ws_cfg_path = dotopen / "workspace.json"
            if ws_cfg_path.is_file():
                wscfg = json.loads(ws_cfg_path.read_text(encoding="utf-8-sig"))
                cdir = wscfg.get("client_dir")
                if cdir:
                    cand_roots.append(Path(cdir))
                    cand_roots.append(dotopen.parent / cdir)
        except Exception:
            pass

        found = False
        for r in cand_roots:
            cand = (r / view_path_str).resolve()
            if cand.is_file():
                view = cand
                found = True
                break
            cand2 = (r / "assets" / view_path_str).resolve()
            if cand2.is_file():
                view = cand2
                found = True
                break
        if not found:
            raise SystemExit(f"!! 找不到界面 XML：{view_path_str}")
    else:
        view = view.resolve()

    assets_root = resolve_assets(view, a.assets)
    m = build_manifest(view, assets_root, reuse, state_default, state_over, scale9_names=scale9)

    if not a.quiet:
        print("=" * 70)
        print(f"  界面：{view.name}")
        print(f"  画布：{m['canvas']['w']:g} × {m['canvas']['h']:g}")
        print(f"  资源包：{m['source']['pkg_id']}")
        print("=" * 70)
        print_tree(m["nodes"])
        print("-" * 70)
        if m["reuse_hits"]:
            agg = {}
            for h in m["reuse_hits"]:
                agg.setdefault(h["asset"], []).append(h["node"])
            print("复用标记（层名加前缀「%s」，表示不需要重新导出）：" % REUSE_PREFIX)
            for asset, nodes_ in agg.items():
                print(f"   {asset}  ×{len(nodes_)}  ->  {', '.join(sorted(set(nodes_)))}")
        else:
            print("复用标记：无")
        print(f"共 {sum(1 for _ in iter_nodes(m['nodes']))} 个节点")
        if m.get("empty_images"):
            print(f"\n**没有图源**的图节点 {len(m['empty_images'])} 个"
                  f"（loader 由代码运行时 setURL，XML 里没有图名）：")
            for s in m["empty_images"]:
                print("   -", s)
            print("   → 组装时可用 `_fgui_asm.py --fill 节点名=源PSD里的层名` 补上")
        if m.get("dropped_text"):
            print(f"\n**文字为空串、不出层**的节点 {len(m['dropped_text'])} 个：")
            for s in m["dropped_text"]:
                print("   -", s)
        if m["deviations"]:
            print(f"\nrelation 增量修正 {len(m['deviations'])} 处：")
            for d in m["deviations"]:
                print("   -", d)
        if m["warnings"]:
            print(f"\n!! {len(m['warnings'])} 条告警（见上）")

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        if not a.quiet:
            print(f"\n清单已写出：{Path(a.out).resolve()}")

    return 0 if not m["warnings"] else 2


if __name__ == "__main__":
    sys.exit(main())
