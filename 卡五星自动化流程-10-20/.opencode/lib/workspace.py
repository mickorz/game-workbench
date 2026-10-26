# -*- coding: utf-8 -*-
"""工作区公共模块（阶段0 改造版）

职责：把"工程外的 Out 目录 / PSD 素材库"变成各技能共用的**文件接口**，并负责**定位真实 client 工程**。

模型（见 fgui文档/计划/08-流程细分与s0环境配置.md）：
- **工作区根** = 含 `.opencode` 的目录；`out_root` / `素材库根` 等相对路径都以它为基准。
- `.xflow` 与 `.opencode` 同级；真实 FGUI 工程在 `client_code_root/<game_id>/`。
- `client_dir` 定位：读 `.opencode/xc_spce_info.json` → `client_code_root`；
  第一层目录名 = `game_id`；第二层确认其 `assets/` 下有**以 `game_key` 为前缀**的包。
- 需求产物落 `.opencode/work/<game_key>/<需求>/`（统一工作层，随 `.opencode` 整包可拷）。

子命令：where / env / setup / snapshot / manifest-* / find-asset / place / check
(zero-hardcode: 不写死工程名/盘符)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULTS = {
    "out_root": r".opencode\work",
    "素材库根": r".opencode\PSD素材库",
    "工程快照范围": "packages",
}

ENUM_种类 = {"图片", "九宫格图", "非等比拉伸", "位图字体", "组件", "复用现成"}
ENUM_来源 = {"复用现成", "工程已有", "素材库命中", "AI生图", "占位"}
ENUM_状态 = {"待制作", "占位中", "已产出", "已替换"}
ENUM_需求类型 = {"UI界面", "图标", "场景"}

ENV_OUT = "FGUI_ART_OUT_ROOT"
ENV_LIB = "FGUI_ART_ASSET_LIB"

CONFIG_ORDER = ["out_root", "素材库根", "工程快照范围", "client_dir", "game_key", "game_id"]


# --------------------------------------------------------------- 定位与配置

def find_workspace_root(start=None) -> Path:
    """含 `.opencode` 的那层 = 工作区根。"""
    starts = []
    if start:
        starts.append(Path(start).resolve())
    starts.append(Path.cwd().resolve())
    starts.append(Path(__file__).resolve())
    seen: set[Path] = set()
    for s in starts:
        for d in [s, *s.parents]:
            try:
                if d in seen:
                    continue
                seen.add(d)
                if (d / ".opencode").is_dir():
                    return d
            except Exception:
                continue
    raise SystemExit("!! 找不到工作区根（含 .opencode 的目录）；可用 --root 指定")


def find_fairy_root(start=None):
    """兜底：含 *fairy + assets/ 的目录（旧口径）。找不到返回 None。"""
    starts = []
    if start:
        starts.append(Path(start).resolve())
    starts.append(Path.cwd().resolve())
    starts.append(Path(__file__).resolve())
    for s in starts:
        for d in [s, *s.parents]:
            try:
                if d.is_dir() and any(d.glob("*.fairy")) and (d / "assets").is_dir():
                    return d
            except Exception:
                continue
    return None


def config_path(ws: Path) -> Path:
    return ws / ".opencode" / "workspace.json"


def xc_info_path(ws: Path) -> Path:
    return ws / ".opencode" / "xc_spce_info.json"


def read_json(p: Path) -> dict:
    # utf-8-sig：容忍 PowerShell 等写出的 BOM
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def load_config(ws: Path) -> dict:
    cfg = dict(DEFAULTS)
    p = config_path(ws)
    if p.is_file():
        try:
            cfg.update(read_json(p))
        except Exception as e:
            raise SystemExit(f"!! 配置解析失败 {p}: {e}")
    return cfg


def save_config(ws: Path, cfg: dict) -> Path:
    p = config_path(ws)
    data = {k: cfg[k] for k in CONFIG_ORDER if k in cfg}
    for k, v in cfg.items():
        data.setdefault(k, v)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def load_xc_info(ws: Path) -> dict:
    p = xc_info_path(ws)
    if not p.is_file():
        return {}
    try:
        return read_json(p)
    except Exception:
        return {}


def resolve_path(base: Path, val) -> Path:
    if not val:
        return None
    p = Path(os.path.expandvars(os.path.expanduser(str(val))))
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def rel_or_abs(base: Path, p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(Path(base).resolve())).replace("/", "\\")
    except ValueError:
        return str(p)


def get_out_root(ws: Path, cfg: dict, override=None) -> Path:
    val = override or os.environ.get(ENV_OUT) or cfg.get("out_root") or DEFAULTS["out_root"]
    return resolve_path(ws, val)


def get_lib_root(ws: Path, cfg: dict, override=None) -> Path:
    val = override or os.environ.get(ENV_LIB) or cfg.get("素材库根") or DEFAULTS["素材库根"]
    return resolve_path(ws, val)


# --------------------------------------------------------- client 工程定位

def _assets_has_game_key(client_dir: Path, game_key: str) -> bool:
    assets = client_dir / "assets"
    if not assets.is_dir() or not game_key:
        return False
    for child in assets.iterdir():
        try:
            if child.is_dir() and child.name.startswith(game_key):
                return True
        except Exception:
            continue
    return False


def _list_dirs(p: Path) -> str:
    try:
        dirs = sorted([d.name for d in p.iterdir() if d.is_dir()])
    except Exception:
        dirs = []
    return ", ".join(dirs) if dirs else "（空）"


def resolve_client_dir(ws: Path, xc: dict, override=None) -> Path:
    if override:
        p = resolve_path(ws, override)
        if not p.is_dir():
            raise SystemExit(f"!! --client 指定的目录不存在：{p}")
        return p

    ccr = str(((xc.get("project_info") or {}).get("client_code_root")) or "").strip()
    gid = str(((xc.get("game_info") or {}).get("game_id")) or "").strip()
    gkey = str(((xc.get("game_info") or {}).get("game_key")) or "").strip()
    if not ccr:
        raise SystemExit("!! xc_spce_info.json 缺 project_info.client_code_root；"
                         "可用 workspace.py env --client <路径> 显式指定")

    client_root = resolve_path(ws, ccr)
    if not client_root or not client_root.is_dir():
        raise SystemExit(f"!! client_code_root 解析出的目录不存在：{client_root}\n"
                         f"   （基准 = 工作区根 {ws}）")

    # 第一层：目录名 = game_id
    cand = client_root / gid if gid else None
    if cand and cand.is_dir():
        # 第二层：assets/ 下有以 game_key 为前缀的包
        if _assets_has_game_key(cand, gkey):
            return cand
        print(f"  ⚠ 命中 {cand}（目录名=game_id），但其 assets/ 里没有以 '{gkey}' 为前缀的包；"
              f"若确认无误可继续（--client 显式指定）")
        return cand

    raise SystemExit(
        f"!! 在 {client_root} 下找不到【目录名 = game_id({gid or '?'})】的工程\n"
        f"   现有目录：{_list_dirs(client_root)}\n"
        f"   可用 workspace.py env --client <路径> 显式指定"
    )


def get_project_root(ws: Path, cfg: dict, a=None) -> Path:
    """真实 FGUI 工程目录：优先配置 client_dir，其次兜底向上找 *.fairy+assets/。"""
    override = getattr(a, "client_dir", None) if a else None
    val = override or cfg.get("client_dir")
    if val:
        p = resolve_path(ws, val)
        if p and p.is_dir():
            return p
        raise SystemExit(f"!! 配置里的 client_dir 不存在：{p}（跑 workspace.py env 重新定位）")
    fb = find_fairy_root(getattr(a, "root", None) if a else None)
    if fb:
        return fb
    raise SystemExit("!! 未定位到工程：workspace.json 无 client_dir，且向上找不到 *.fairy+assets/；"
                     "先跑 workspace.py env")


def get_game_key(ws: Path, cfg: dict) -> str:
    if cfg.get("game_key"):
        return str(cfg["game_key"])
    gk = str(((load_xc_info(ws).get("game_info") or {}).get("game_key")) or "").strip()
    return gk or "xxx"


def ctx(a) -> tuple[Path, dict]:
    ws = find_workspace_root(getattr(a, "root", None))
    return ws, load_config(ws)


def req_dir(ws: Path, cfg: dict, req: str, a=None) -> Path:
    out = get_out_root(ws, cfg, getattr(a, "out_root", None) if a else None)
    return out / get_game_key(ws, cfg) / req


def manifest_path(ws: Path, cfg: dict, req: str, a=None) -> Path:
    return req_dir(ws, cfg, req, a) / "清单.json"


def load_manifest(p: Path) -> dict:
    if not Path(p).is_file():
        raise SystemExit(f"!! 清单不存在：{p}（先 manifest-init）")
    return read_json(p)


def save_manifest(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def facts_hash(root: Path, ws: Path = None, cfg: dict = None) -> str:
    cands = []
    if ws is not None:
        try:
            cands.append(get_out_root(ws, cfg or {}) / "facts.json")
        except Exception:
            pass
    cands.append(root / "fgui文档" / "facts.json")   # 旧位置兜底
    for f in cands:
        if f.is_file():
            return hashlib.md5(f.read_bytes()).hexdigest()[:12]
    return ""


def _safe_facts_hash(ws: Path, cfg: dict, a) -> str:
    try:
        root = get_project_root(ws, cfg, a)
    except SystemExit:
        return ""
    return facts_hash(root, ws, cfg)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------- 子命令

def cmd_where(a):
    ws, cfg = ctx(a)
    out = get_out_root(ws, cfg, a.out_root)
    lib = get_lib_root(ws, cfg, a.素材库根)
    rows = [
        ("工作区根", ws),
        ("配置文件", config_path(ws)),
        ("out_root", out),
        ("素材库根", lib),
    ]
    for k, p in rows:
        mark = "✓存在" if p.exists() else "✗不存在"
        print(f"{k:9}: {p}   [{mark}]")
    cdir = cfg.get("client_dir")
    if cdir:
        p = resolve_path(ws, cdir)
        print(f"{'client_dir':9}: {p}   [{'✓存在' if p.is_dir() else '✗不存在'}]")
    else:
        print(f"{'client_dir':9}: (未设置；跑 workspace.py env)")
    print(f"{'game_key':9}: {get_game_key(ws, cfg)}")
    mf = manifest_path(ws, cfg, a.需求, a) if getattr(a, "需求", None) else None
    if mf:
        print(f"{'清单':9}: {mf}   [{'✓' if mf.exists() else '✗'}]")


def cmd_env(a):
    """定位 client 工程；默认写 workspace.json；--check 只查。"""
    ws, cfg = ctx(a)
    xc = load_xc_info(ws)
    gid = str(((xc.get("game_info") or {}).get("game_id")) or "").strip()
    gkey = str(((xc.get("game_info") or {}).get("game_key")) or "").strip()
    try:
        cdir = resolve_client_dir(ws, xc, getattr(a, "client", None))
    except SystemExit as e:
        if a.check:
            print(str(e))
            raise SystemExit(1)
        raise

    if a.check:
        print(f"✓ 工作区根  : {ws}")
        print(f"✓ client_dir: {cdir}")
        print(f"✓ game_key  : {gkey or '（缺）'}")
        print(f"✓ game_id   : {gid or '（缺）'}")
        print("  （--check 未写任何文件）")
        return

    cfg["client_dir"] = rel_or_abs(ws, cdir)
    if gkey:
        cfg["game_key"] = gkey
    if gid:
        cfg["game_id"] = gid
    p = save_config(ws, cfg)
    print(f"✓ 已写入 {p}")
    print(f"  client_dir = {cfg['client_dir']}")
    print(f"  game_key   = {cfg.get('game_key', '')}")
    print(f"  game_id    = {cfg.get('game_id', '')}")


def cmd_setup(a):
    ws = find_workspace_root(getattr(a, "root", None))
    cfg = load_config(ws)
    if a.out_root:
        cfg["out_root"] = a.out_root
    if a.素材库根:
        cfg["素材库根"] = a.素材库根
    if a.工程快照范围:
        cfg["工程快照范围"] = a.工程快照范围
    p = save_config(ws, cfg)
    print(f"✓ 已写入 {p}")
    for k in CONFIG_ORDER:
        if k in cfg:
            print(f"  {k} = {cfg.get(k)}")


def infer_packages(rd: Path) -> list[str]:
    mf = rd / "清单.json"
    if not mf.is_file():
        raise SystemExit("!! 未给 --packages，且无清单.json 可推断本轮包；请显式 --packages a,b")
    data = read_json(mf)
    pkgs = []
    for r in data.get("资源", []):
        slot = str(r.get("槽位名", "")).replace("\\", "/")
        m = re.match(r"assets/([^/]+)/", slot)
        if m and m.group(1) not in pkgs:
            pkgs.append(m.group(1))
    if not pkgs:
        raise SystemExit("!! 清单里没有可推断的包（槽位名应以 assets/<包>/ 开头）；请显式 --packages")
    return pkgs


def cmd_snapshot(a):
    ws, cfg = ctx(a)
    root = get_project_root(ws, cfg, a)
    out = get_out_root(ws, cfg, a.out_root)
    req = a.需求
    rd = out / get_game_key(ws, cfg) / req
    dest = rd / "FGUI"
    rng = a.range or cfg.get("工程快照范围", "packages")
    pkgs = [x.strip() for x in a.packages.split(",") if x.strip()] if a.packages else None

    if rng == "packages" and not pkgs:
        pkgs = infer_packages(rd)
        print(f"· 本轮包（推断）: {', '.join(pkgs)}")

    dest.mkdir(parents=True, exist_ok=True)
    copied = []

    if rng == "all":
        shutil.copytree(root / "assets", dest / "assets", dirs_exist_ok=True)
        copied.append("assets/")
    else:
        for pkg in pkgs:
            src = root / "assets" / pkg
            if not src.is_dir():
                print(f"  ! 包不存在，跳过：{src}")
                continue
            shutil.copytree(src, dest / "assets" / pkg, dirs_exist_ok=True)
            copied.append(f"assets/{pkg}/")

    for name in ("settings",):
        s = root / name
        if s.is_dir():
            shutil.copytree(s, dest / name, dirs_exist_ok=True)
            copied.append(f"{name}/")
    for f in root.glob("*.fairy"):
        shutil.copy2(f, dest / f.name)
        copied.append(f.name)

    print(f"✓ 工程快照 → {dest}")
    for c in copied:
        print(f"  + {c}")


def parse_规格_kv(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise SystemExit(f"!! 规格项要写成 键=值：{spec}")
    return spec.split("=", 1)


def build_规格(a) -> dict:
    spec = {}
    if a.尺寸:
        spec["尺寸"] = a.尺寸
    if a.透明底 is not None:
        spec["透明底"] = a.透明底
    if a.九宫格:
        spec["九宫格"] = a.九宫格
    if a.字形高:
        spec["字形高"] = a.字形高
    if a.字符表:
        spec["字符表"] = a.字符表
    return spec


def validate_enum(field: str, val: str, allowed: set):
    if val and val not in allowed:
        raise SystemExit(f"!! {field} 非法：{val!r}；可选 {sorted(allowed)}")


def cmd_manifest_init(a):
    ws, cfg = ctx(a)
    p = manifest_path(ws, cfg, a.需求, a)
    if p.exists() and not a.force:
        raise SystemExit(f"!! 已存在：{p}（要覆盖加 --force）")
    data = {"需求名": a.需求, "facts_hash": _safe_facts_hash(ws, cfg, a), "创建": now_str(),
            "需求": [], "资源": []}
    save_manifest(p, data)
    print(f"✓ 建清单 {p}")


def cmd_manifest_add(a):
    ws, cfg = ctx(a)
    p = manifest_path(ws, cfg, a.需求, a)
    data = load_manifest(p)
    validate_enum("种类", a.种类, ENUM_种类)
    validate_enum("来源", a.来源, ENUM_来源)
    validate_enum("状态", a.状态, ENUM_状态)
    if not a.槽位名:
        raise SystemExit("!! 缺 --槽位名")
    ids = [str(r.get("id", "")) for r in data["资源"]]
    n = 1
    while f"R{n}" in ids:
        n += 1
    rid = a.id or f"R{n}"
    entry = {
        "id": rid,
        "槽位名": a.槽位名.replace("\\", "/"),
        "种类": a.种类 or "图片",
        "规格": build_规格(a),
        "用途": a.用途 or "",
        "来源": a.来源 or "占位",
        "状态": a.状态 or "待制作",
        "素材库命中": None,
        "重组手法": None,
        "psd": None,
        "切图": None,
        "占位": a.占位 or "",
        "备注": a.备注 or "",
        "美术反馈": {"位置": "", "内容": "", "实际尺寸": ""},
    }
    data["资源"].append(entry)
    save_manifest(p, data)
    print(f"✓ 加 {rid}  {entry['槽位名']}  ({entry['种类']}/{entry['来源']}/{entry['状态']})")


def coerce(v: str):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", ""):
        return None
    return v


def cmd_manifest_set(a):
    ws, cfg = ctx(a)
    p = manifest_path(ws, cfg, a.需求, a)
    data = load_manifest(p)
    targets = data["资源"]
    if a.id:
        targets = [r for r in targets if str(r.get("id")) == str(a.id)]
        if not targets:
            raise SystemExit(f"!! 找不到 id={a.id}")
    for kv in a.set or []:
        k, v = parse_规格_kv(kv)
        v = coerce(v)
        if k.split(".")[0] in ("种类", "来源", "状态"):
            validate_enum(k, v, {"种类": ENUM_种类, "来源": ENUM_来源, "状态": ENUM_状态}[k])
        for r in targets:
            if k.startswith("规格."):
                r.setdefault("规格", {})[k.split(".", 1)[1]] = v
            else:
                r[k] = v
    save_manifest(p, data)
    print(f"✓ 改 {len(targets)} 条")


def spec_summary(spec: dict) -> str:
    if not spec:
        return ""
    return " ".join(f"{k}={v}" for k, v in spec.items())


def cmd_requirement_add(a):
    ws, cfg = ctx(a)
    p = manifest_path(ws, cfg, a.需求, a)
    data = load_manifest(p)
    if not a.名称:
        raise SystemExit("!! 缺 --名称")
    if not a.描述:
        raise SystemExit("!! 缺 --描述")
    if a.类型:
        validate_enum("类型", a.类型, ENUM_需求类型)
    item = {
        "名称": a.名称,
        "描述": a.描述,
        "类型": a.类型 or "",
        "参考图": a.参考图 or "",
        "参考图_1334x750": a.参考图_1334x750 or "",
    }
    data["需求"].append(item)
    save_manifest(p, data)
    print(f"✓ 加需求 {a.名称}（共 {len(data['需求'])} 条）")


def cmd_requirement_set(a):
    ws, cfg = ctx(a)
    p = manifest_path(ws, cfg, a.需求, a)
    data = load_manifest(p)
    targets = data["需求"]
    if a.名称:
        targets = [r for r in targets if r.get("名称") == a.名称]
        if not targets:
            raise SystemExit(f"!! 找不到需求 名称={a.名称}")
    for kv in a.set or []:
        k, v = parse_规格_kv(kv)
        v = coerce(v)
        if k == "类型":
            validate_enum("类型", v, ENUM_需求类型)
        for r in targets:
            r[k] = v
    save_manifest(p, data)
    print(f"✓ 改 {len(targets)} 条需求")


def cmd_manifest_md(a):
    ws, cfg = ctx(a)
    p = manifest_path(ws, cfg, a.需求, a)
    data = load_manifest(p)
    out = p.with_name("清单.md")
    lines = [f"# 清单 · {data.get('需求名','')}", ""]
    lines.append(f"> 生成自 `清单.json`（{now_str()}）｜ 需求：{data.get('需求名','')}"
                 f" ｜ 需求条目 {len(data.get('需求', []))} 条 ｜ 资源 {len(data['资源'])} 条")
    lines.append("")
    reqs = data.get("需求", [])
    if reqs:
        lines.append(f"## 需求（{len(reqs)}）")
        lines.append("")
        lines.append("| 名称 | 描述 | 类型 | 参考图 | 参考图_1334x750 |")
        lines.append("|---|---|---|---|---|")
        for r in reqs:
            lines.append("| {} | {} | {} | {} | {} |".format(
                r.get("名称", ""), r.get("描述", ""), r.get("类型", ""),
                r.get("参考图", ""), r.get("参考图_1334x750", "")))
        lines.append("")
    lines.append("## 资源")
    lines.append("")
    order = ["待制作", "占位中", "已产出", "已替换"]
    by = {}
    for r in data["资源"]:
        by.setdefault(r.get("状态", "待制作"), []).append(r)
    for st in order + [k for k in by if k not in order]:
        rows = by.get(st)
        if not rows:
            continue
        lines.append(f"## {st}（{len(rows)}）")
        lines.append("")
        lines.append("| id | 槽位名 | 种类 | 规格 | 用途 | 来源 | 素材库命中 | 重组手法 | 切图 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                r.get("id", ""), r.get("槽位名", ""), r.get("种类", ""), spec_summary(r.get("规格", {})),
                r.get("用途", ""), r.get("来源", ""), r.get("素材库命中") or "", r.get("重组手法") or "",
                r.get("切图") or ""))
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 生成 {out}")


# ------------------------------------------------------------------ 素材库

def parse_size(s: str):
    m = re.match(r"\s*(\d+)\s*[x×]\s*(\d+)\s*$", str(s or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def score_asset(target: dict, cand: dict) -> tuple[int, list[str]]:
    reasons = []
    if target.get("种类") != cand.get("种类"):
        return -1, ["种类不同，不候选"]
    score = 0
    # 结构相似
    tstruct = set(target.get("结构", [])) if isinstance(target.get("结构"), list) else set(
        re.split(r"[,，/、\s]+", str(target.get("结构", ""))))
    cstruct = set(cand.get("结构", []))
    if tstruct:
        hits = tstruct & cstruct
        score += 2 * len(hits)
        if hits:
            reasons.append(f"结构命中 {len(hits)}: {'/'.join(sorted(hits))}")
    # 尺寸
    tsize = parse_size(target.get("规格", {}).get("尺寸", ""))
    csize = parse_size(cand.get("尺寸", ""))
    ways = cand.get("可复用方式", [])
    if not ways and cand.get("制作单元"):
        for u in cand.get("制作单元", []):
            ways.extend(u.get("可复用方式", []))
    ways = list(set(ways))

    if tsize and csize:
        if tsize == csize:
            score += 3
            reasons.append("尺寸精确匹配")
        elif "改尺寸" in ways:
            score += 1
            reasons.append("尺寸不同但可改尺寸")
    # 外观
    if "换色" in ways or "套样式" in ways:
        score += 1
        if reason := cand.get("外观"):
            reasons.append(f"可换色（素材外观: {'/'.join(reason)}）")
    return score, reasons


def cmd_find_asset(a):
    ws, cfg = ctx(a)
    lib = get_lib_root(ws, cfg, a.素材库根)
    print(f"· 素材库：{lib}")
    if not lib.is_dir():
        print("  素材库未配置或不存在 → 全部走占位（见 .opencode/workspace.json）")
        return
    idx = lib / "index.json"
    if not idx.is_file():
        print("  没有 index.json → 全部走占位（可跑 .opencode/skills/psd-style/scripts/build_index.py --write 生成骨架）")
        return
    assets = read_json(idx).get("素材", [])
    if not assets:
        print("  素材库为空 → 全部走占位")
        return

    mf = manifest_path(ws, cfg, a.需求, a)
    data = load_manifest(mf)
    targets = data["资源"]
    if a.id:
        targets = [r for r in targets if str(r.get("id")) == str(a.id)]
    # 只有"要产出"的才查（复用现成/工程已有 不需要）
    targets = [r for r in targets if r.get("来源") in ("AI生图", "占位", "") or r.get("状态") in ("待制作", "占位中")]
    if not targets:
        print("· 没有待制作的条目")
        return

    for r in targets:
        print(f"\n[{r.get('id')}] {r.get('槽位名')}  ({r.get('种类')} {r.get('规格',{}).get('尺寸','')})")
        ranked = []
        for cand in assets:
            s, why = score_asset(r, cand)
            if s >= 0:
                ranked.append((s, cand, why))
        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            print("  → 无候选（种类不符或素材库无同类）→ 占位")
            continue
        for s, cand, why in ranked[:a.top]:
            print(f"  [{s:>2}分] {cand.get('id','')} {cand.get('文件','')}  画布={cand.get('尺寸','')}")
            if why:
                print(f"         {'; '.join(why)}")
            units = cand.get("制作单元", [])
            if units:
                print(f"         包含制作单元 ({len(units)} 个):")
                for u in units[:5]:
                    preview_str = f" [预览: {u.get('预览图')}]" if u.get('预览图') else ""
                    bg = u.get("底图组")
                    bg_str = f" -> 底图: {bg.get('名')}(lyid={bg.get('lyid')})" if bg else ""
                    txt_str = f" 文本:{u.get('文字内容')}" if u.get('文字内容') else ""
                    print(f"           - {u.get('名')} (lyid={u.get('lyid')}){bg_str}{txt_str}{preview_str}")
                if len(units) > 5:
                    print(f"           ... 更多 {len(units)-5} 个单元略")
        print("  （命中需人工核对预览图并确认；确认后 manifest-set 回填 来源=素材库命中/素材库命中/重组手法）")


# -------------------------------------------------------------------- 回写

def _try_size(p: Path):
    try:
        from PIL import Image
        with Image.open(p) as im:
            return im.size
    except Exception:
        return None


def cmd_place(a):
    ws, cfg = ctx(a)
    root = get_project_root(ws, cfg, a)
    out = get_out_root(ws, cfg, a.out_root)
    rd = out / get_game_key(ws, cfg) / a.需求
    data = load_manifest(rd / "清单.json")
    targets = data["资源"]
    if a.id:
        targets = [r for r in targets if str(r.get("id")) == str(a.id)]
    placed = 0
    for r in targets:
        cut = r.get("切图")
        if not cut:
            continue
        src = Path(cut)
        if not src.is_absolute():
            src = rd / cut
        if not src.is_file():
            print(f"  ! 切图不存在，跳过 {r.get('id')}: {src}")
            continue
        slot = str(r.get("槽位名", "")).replace("\\", "/")
        if not slot.startswith("assets/"):
            print(f"  ! 槽位名不以 assets/ 开头，跳过 {r.get('id')}: {slot}")
            continue
        dsts = [rd / "FGUI" / slot, root / slot]
        ssize = _try_size(src)
        for dst in dsts:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if ssize and dst.is_file():
                dsize = _try_size(dst)
                if dsize and dsize != ssize:
                    print(f"  ⚠ 尺寸不一致（{r.get('id')}）{dst.name}: 切图{ssize} vs 目标{dsize}")
            shutil.copy2(src, dst)
        r["状态"] = "已替换"
        placed += 1
        print(f"  ✓ {r.get('id')} → 快照 + 工程根  ({slot})")
    save_manifest(rd / "清单.json", data)
    print(f"✓ place 完成：{placed} 条（状态=已替换）")


# ------------------------------------------------------------------- 入口

def build_parser():
    p = argparse.ArgumentParser(description="工作区/工程定位 + Out 目录 + 清单 + 素材库 工具")
    p.add_argument("--root", help="工作区根（含 .opencode 的目录；默认自动向上找）")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--out-root", dest="out_root", help="临时覆盖 out_root")
        sp.add_argument("--素材库根", dest="素材库根", help="临时覆盖素材库根")

    w = sub.add_parser("where", help="打印解析后的路径")
    add_common(w)
    w.add_argument("--需求", dest="需求", default=None)
    w.set_defaults(func=cmd_where)

    e = sub.add_parser("env", help="定位 client 工程并写入 workspace.json")
    e.add_argument("--client", default=None, help="显式指定 client 工程目录（跳过自动定位）")
    e.add_argument("--check", action="store_true", help="只查状态，不写文件")
    e.set_defaults(func=cmd_env)

    s = sub.add_parser("setup", help="写/改 workspace.json（路径项）")
    s.add_argument("--out-root", dest="out_root")
    s.add_argument("--素材库根", dest="素材库根")
    s.add_argument("--工程快照范围", dest="工程快照范围", choices=["packages", "all"])
    s.set_defaults(func=cmd_setup)

    sn = sub.add_parser("snapshot", help="建工程快照")
    add_common(sn)
    sn.add_argument("需求")
    sn.add_argument("--range", choices=["packages", "all"], default=None)
    sn.add_argument("--packages", default=None)
    sn.set_defaults(func=cmd_snapshot)

    mi = sub.add_parser("manifest-init", help="建清单骨架")
    add_common(mi)
    mi.add_argument("需求")
    mi.add_argument("--force", action="store_true")
    mi.set_defaults(func=cmd_manifest_init)

    ma = sub.add_parser("manifest-add", help="加一条资源")
    add_common(ma)
    ma.add_argument("需求")
    ma.add_argument("--槽位名", required=True)
    ma.add_argument("--种类", default="图片")
    ma.add_argument("--尺寸", default=None)
    ma.add_argument("--透明底", default=None, type=lambda x: None if x is None else x.lower() == "true")
    ma.add_argument("--九宫格", default=None)
    ma.add_argument("--字形高", default=None)
    ma.add_argument("--字符表", default=None)
    ma.add_argument("--用途", default=None)
    ma.add_argument("--来源", default="占位")
    ma.add_argument("--状态", default="待制作")
    ma.add_argument("--占位", default=None)
    ma.add_argument("--id", default=None)
    ma.add_argument("--备注", default=None)
    ma.set_defaults(func=cmd_manifest_add)

    ms = sub.add_parser("manifest-set", help="改条目")
    add_common(ms)
    ms.add_argument("需求")
    ms.add_argument("--id", default=None)
    ms.add_argument("--set", action="append", default=[])
    ms.set_defaults(func=cmd_manifest_set)

    mm = sub.add_parser("manifest-md", help="生成 清单.md")
    add_common(mm)
    mm.add_argument("需求")
    mm.set_defaults(func=cmd_manifest_md)

    ra = sub.add_parser("需求-add", help="加一条需求条目")
    add_common(ra)
    ra.add_argument("需求", help="清单所在的需求（目录名）")
    ra.add_argument("--名称", required=True)
    ra.add_argument("--描述", required=True)
    ra.add_argument("--类型", default=None, help="UI界面 / 图标 / 场景")
    ra.add_argument("--参考图", default=None)
    ra.add_argument("--参考图-1334x750", dest="参考图_1334x750", default=None)
    ra.set_defaults(func=cmd_requirement_add)

    rs = sub.add_parser("需求-set", help="改需求条目")
    add_common(rs)
    rs.add_argument("需求", help="清单所在的需求（目录名）")
    rs.add_argument("--名称", default=None, help="要改的条目名（不写=全部）")
    rs.add_argument("--set", action="append", default=[])
    rs.set_defaults(func=cmd_requirement_set)

    fa = sub.add_parser("find-asset", help="查素材库")
    add_common(fa)
    fa.add_argument("需求")
    fa.add_argument("--id", default=None)
    fa.add_argument("--top", type=int, default=3)
    fa.set_defaults(func=cmd_find_asset)

    pl = sub.add_parser("place", help="切图回写 快照+工程根")
    add_common(pl)
    pl.add_argument("需求")
    pl.add_argument("--id", default=None)
    pl.set_defaults(func=cmd_place)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
