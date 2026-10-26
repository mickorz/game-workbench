#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备份当前代码与资源，打成模板 zip。

备份范围（默认全部）：
  - 源码：src/、plugins/、scripts/、player/、integrations/、config/、build/、test/、patches/
  - 配置与入口：*.ts/*.json/*.html/*.md、bunfig.toml、bun.lock、electron-builder.yml、.gitignore、.gitattributes、.env.example
  - 交付包：卡五星自动化流程-10-20/（排除 .opencode/work 等运行产物）
  - 仓库文档：docs/、CLAUDE.md 等

排除（不进备份）：
  node_modules/、dist/、.runtime/、.data/、release/、coverage/、.vite/、.git/、
  thirdparties/（子模块，恢复时 git submodule update --init）、
  dev-docs/、dev-examples/（开发过程目录）、*.log、.env*

用法（仓库根执行）：
  python backup_template.py                        # 备份全项目 -> backups/xc-ui-flow-template-YYYYMMDD-HHMMSS.zip
  python backup_template.py --name my-snapshot     # 指定模板名
  python backup_template.py --out D:/Backups       # 指定输出目录
  python backup_template.py --no-delivery          # 不含卡五星交付包（体积大幅减小）
  python backup_template.py --list backups/xxx.zip # 查看 zip 内容清单

退出码：0 成功；1 失败。
"""
from __future__ import annotations

import argparse
import datetime
import sys
import zipfile
from pathlib import Path

# 仓库根 = 脚本所在目录
ROOT = Path(__file__).resolve().parent

# 目录级排除（相对仓库根，支持出现在任意层级的名字）
EXCLUDE_DIR_NAMES = {
    "node_modules", "dist", ".runtime", ".data", "release", "coverage",
    ".vite", ".git", "thirdparties", "dev-docs", "dev-examples",
    ".playwright-cli", ".claude", ".opencode", ".objs", "__pycache__",
    ".vscode", ".idea",
}
# 目录级排除（相对仓库根的精确路径；.opencode/work 等运行产物）
EXCLUDE_REL_DIRS = {
    "卡五星自动化流程-10-20/.opencode/work",
    "卡五星自动化流程-10-20/.opencode/node_modules",
    "卡五星自动化流程-10-20/.opencode/inbox",
    "卡五星自动化流程-10-20/work",  # 扫描器产物（facts.json 等），可重扫
}
# 文件名通配排除
EXCLUDE_FILE_SUFFIXES = (".log", ".zip", ".bak", ".pyc")
EXCLUDE_FILE_NAMES = {".env", ".DS_Store"}
EXCLUDE_FILE_PREFIXES = (".env.",)  # 但保留 .env.example
KEEP_DESPITE_PREFIX = {".env.example"}

# 备份目录（脚本产物自身也不进备份）
BACKUP_DIR_NAME = "backups"

# 交付包目录名
DELIVERY_DIR = "卡五星自动化流程-10-20"


def setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def excluded_rel_dirs() -> set[str]:
    """windows / posix 分隔符都收进来，匹配时统一用 posix 风格比较。"""
    out = set()
    for d in EXCLUDE_REL_DIRS:
        out.add(d.replace("\\", "/"))
    return out


def should_skip(path: Path, rel: str, no_delivery: bool) -> bool:
    rel_posix = rel.replace("\\", "/")

    # 文件级规则
    if path.is_file():
        name = path.name
        if name in EXCLUDE_FILE_NAMES:
            return True
        if name.startswith(EXCLUDE_FILE_PREFIXES) and name not in KEEP_DESPITE_PREFIX:
            return True
        if name.endswith(EXCLUDE_FILE_SUFFIXES):
            return True

    # 目录级规则（精确相对路径）
    for d in excluded_rel_dirs():
        if rel_posix == d or rel_posix.startswith(d + "/"):
            return True
    return False


def iter_backup_files(no_delivery: bool) -> list[tuple[Path, str]]:
    """收集要进 zip 的文件，返回 (绝对路径, zip 内相对路径) 列表。"""
    files: list[tuple[Path, str]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        # 任一父目录命中排除名 → 跳过（rglob 会递归进 node_modules，先在目录名层面挡掉）
        if any(part in EXCLUDE_DIR_NAMES for part in Path(rel).parts[:-1]):
            continue
        # 顶层交付包整体开关（rglob 返回的是文件，要按第一级目录判断）
        if no_delivery and Path(rel).parts and Path(rel).parts[0] == DELIVERY_DIR:
            continue
        # 备份目录自身
        if Path(rel).parts and Path(rel).parts[0] == BACKUP_DIR_NAME:
            continue
        # zip 在 Windows 上有时以正在写入的姿态被 rglob 到，跳过所有 .zip
        if path.suffix == ".zip":
            continue
        if should_skip(path, rel, no_delivery):
            continue
        files.append((path, rel))
    return files


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}GB"


def make_template(out_dir: Path, name: str | None, no_delivery: bool) -> int:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tpl_name = name or f"xc-ui-flow-template-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{tpl_name}.zip"

    files = iter_backup_files(no_delivery)
    if not files:
        print("!! 没有可备份的文件，检查脚本是否放在仓库根")
        return 1

    total = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for abs_path, rel in files:
            zf.write(abs_path, rel)
            total += abs_path.stat().st_size

    print(f"[成功] 模板已生成：{zip_path}")
    print(f"  文件数：{len(files)}")
    print(f"  原始大小：{human_size(total)} -> zip 大小：{human_size(zip_path.stat().st_size)}")
    if no_delivery:
        print("  （--no-delivery：未包含卡五星交付包）")
    print(f"  恢复方式：解压到目标目录后执行 bun install（子模块另需 git submodule update --init）")
    return 0


def list_zip(zip_path: Path) -> int:
    if not zip_path.is_file():
        print(f"!! 文件不存在：{zip_path}")
        return 1
    with zipfile.ZipFile(zip_path) as zf:
        infos = sorted(zf.infolist(), key=lambda i: i.filename)
        total_c = sum(i.compress_size for i in infos)
        total_u = sum(i.file_size for i in infos)
        print(f"== {zip_path.name}  共 {len(infos)} 项  {human_size(total_u)} -> {human_size(total_c)} ==")
        # 只展示顶层与二级目录摘要 + 若干文件示例
        dirs: dict[str, int] = {}
        for i in infos:
            parts = i.filename.split("/")
            key = parts[0] if len(parts) == 1 else "/".join(parts[:2]) + "/"
            dirs[key] = dirs.get(key, 0) + 1
        for key in sorted(dirs):
            print(f"  {dirs[key]:>6}  {key}")
    return 0


def main(argv=None) -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description="备份当前代码与资源为模板 zip")
    ap.add_argument("--name", help="模板名（默认 xc-ui-flow-template-时间戳）")
    ap.add_argument("--out", help="输出目录（默认 <仓库根>/backups/）")
    ap.add_argument("--no-delivery", action="store_true", help="不包含卡五星交付包")
    ap.add_argument("--list", dest="list_zip_path", help="查看指定 zip 的内容清单")
    args = ap.parse_args(argv)

    if args.list_zip_path:
        return list_zip(Path(args.list_zip_path).resolve())

    out_dir = Path(args.out).resolve() if args.out else ROOT / BACKUP_DIR_NAME
    return make_template(out_dir, args.name, args.no_delivery)


if __name__ == "__main__":
    sys.exit(main())
