# -*- coding: utf-8 -*-
"""PhotoCraft 桌面端控制协议客户端（s3/s4 的渲染后端）。

替代原来的 Photopea 浏览器流程：本模块直接跟本机 PhotoCraft 的 control 端口
（默认 127.0.0.1:7878）说 JSON 行协议，做四件事：

    ensure()      没开就按 --control/--control-token-file/--automation-*-root 拉起桌面端
    engine(...)   执行任意引擎命令（file.new / layer.new.group / file.placeEmbedded / type.create ...）
    open_doc()    打开 PSD（app.open，走自动化读根）
    save_doc()    保存/导出（app.save，走自动化写根；扩展名决定格式）

协议（见 PhotoCraft docs/control-protocol.md）：
    每条连接先发 {"id":"auth","method":"auth","params":{"token":"<64 hex>"}}
    之后每行一条 {"id":n,"method":...,"params":{...}}，回一行 {"id":n,"ok":...}

配置优先级：显式参数 > 环境变量 > .opencode/photocraft.json > 内建默认。
环境变量：PHOTOCRAFT_EXE / PHOTOCRAFT_CONTROL_PORT / PHOTOCRAFT_CONTROL_TOKEN_FILE
          PHOTOCRAFT_READ_ROOT / PHOTOCRAFT_WRITE_ROOT

命令行自检：  python .opencode/lib/photocraft.py --check
"""
from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_PORT = 7878
DEFAULT_TOKEN_FILE = r"D:\PhotoCraft-Work\.photocraft-control.token"

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]          # ...\<工作区根>
LIB_DIR = Path(__file__).resolve().parent
CONFIG_PATH = WORKSPACE_ROOT / ".opencode" / "photocraft.json"


class PhotoCraftError(RuntimeError):
    pass


# ---------------------------------------------------------------- 配置
def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _find_exe() -> str:
    exe = os.environ.get("PHOTOCRAFT_EXE") or _load_config().get("exe")
    if exe and Path(exe).exists():
        return str(exe)
    for cmd in ("photocraft.exe", "photocraft"):
        found = _which(cmd)
        if found:
            return found
    # 本机常见布局：D:\AI工具\photocraft-main\photocraft-main\target\release\photocraft.exe
    for base in (Path("D:/"), Path("C:/")):
        if not base.exists():
            continue
        for d in base.glob("AI*/photocraft-main/photocraft-main/target/release/photocraft.exe"):
            return str(d)
    raise PhotoCraftError(
        "找不到 photocraft.exe：设 PHOTOCRAFT_EXE 或写 .opencode/photocraft.json 的 exe")


def _which(name: str):
    from shutil import which
    return which(name)


def config(port=None, token_file=None, read_root=None, write_root=None,
           exe=None) -> dict:
    c = _load_config()
    port = int(port or os.environ.get("PHOTOCRAFT_CONTROL_PORT")
               or c.get("port") or DEFAULT_PORT)
    token_file = (token_file or os.environ.get("PHOTOCRAFT_CONTROL_TOKEN_FILE")
                  or c.get("token_file") or DEFAULT_TOKEN_FILE)
    read_root = (read_root or os.environ.get("PHOTOCRAFT_READ_ROOT")
                 or c.get("read_root") or str(WORKSPACE_ROOT.parent))
    write_root = (write_root or os.environ.get("PHOTOCRAFT_WRITE_ROOT")
                  or c.get("write_root") or str(WORKSPACE_ROOT))
    exe = exe or (os.environ.get("PHOTOCRAFT_EXE") or c.get("exe") or None)
    return {
        "port": port,
        "token_file": str(Path(token_file).expanduser()),
        "read_root": str(Path(read_root).expanduser().resolve()),
        "write_root": str(Path(write_root).expanduser().resolve()),
        "exe": exe,
    }


# ---------------------------------------------------------------- 协议
def _read_line(sock: socket.socket) -> bytes:
    buf = bytearray()
    while True:
        ch = sock.recv(1)
        if not ch:
            raise PhotoCraftError("控制连接被对端关闭")
        if ch == b"\n":
            return bytes(buf)
        buf += ch


class Client:
    def __init__(self, port=None, token_file=None, timeout=120, **cfg):
        self.cfg = config(port=port, token_file=token_file, **cfg)
        self.port = self.cfg["port"]
        self.timeout = timeout
        self._token = None
        self._next_id = 1

    # -- 基础 ---------------------------------------------------------
    def _token_value(self) -> str:
        if self._token:
            return self._token
        tf = Path(self.cfg["token_file"])
        if not tf.exists():
            raise PhotoCraftError(f"control token 文件不存在：{tf}（先 ensure() 拉起桌面端）")
        tok = tf.read_text(encoding="utf-8", errors="replace").strip()
        if len(tok) < 32:
            raise PhotoCraftError(f"control token 文件内容不像 token：{tf}")
        self._token = tok
        return tok

    def _connect(self, timeout=None):
        return socket.create_connection(("127.0.0.1", self.port),
                                        timeout=timeout or self.timeout)

    def _request_once(self, method, params=None, timeout=None):
        payload = {"id": self._next_id, "method": method, "params": params or {}}
        self._next_id += 1
        s = self._connect(timeout)
        try:
            s.sendall((json.dumps({"id": "auth", "method": "auth",
                                   "params": {"token": self._token_value()}},
                                  ensure_ascii=False) + "\n").encode("utf-8"))
            auth = json.loads(_read_line(s).decode("utf-8", "replace"))
            if not auth.get("ok"):
                raise PhotoCraftError(f"控制端口认证失败：{auth.get('error')}")
            s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            reply = json.loads(_read_line(s).decode("utf-8", "replace"))
        finally:
            try:
                s.close()
            except Exception:
                pass
        if reply.get("id") != payload["id"]:
            raise PhotoCraftError(f"控制回复 id 不符：{reply.get('id')} != {payload['id']}")
        if not reply.get("ok"):
            raise PhotoCraftError(str(reply.get("error") or "未知错误"))
        return reply.get("result")

    def request(self, method, params=None, timeout=None, retries=2):
        last = None
        for i in range(retries + 1):
            try:
                return self._request_once(method, params, timeout)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError,
                    socket.timeout, OSError) as e:
                last = e
                if i < retries:
                    time.sleep(0.8 * (i + 1))
        raise PhotoCraftError(f"控制请求失败 {method}: {last}")

    # -- 常用封装 -----------------------------------------------------
    def engine(self, command, params=None, timeout=None):
        return self.request("engine.execute",
                            {"command": command, "params": params or {}},
                            timeout=timeout)

    def inspect(self):
        return self.engine("document.inspect")

    def open_doc(self, path):
        return self.request("app.open", {"path": str(path)}, timeout=300)

    def save_doc(self, path, **kw):
        params = {"path": str(path)}
        params.update(kw)
        return self.request("app.save", params, timeout=600)

    def save_png(self, path):
        return self.save_doc(path)

    def close_doc(self):
        return self.request("app.close", {})

    def ping(self):
        return self.request("ui.inspect", {})


# ---------------------------------------------------------------- 拉起
def _port_open(port, timeout=0.5) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure(port=None, token_file=None, read_root=None, write_root=None,
           exe=None, wait=60, verbose=True) -> Client:
    """确保桌面端在跑并能认证；没跑就按配置自动拉起。返回可用的 Client。"""
    cfg = config(port=port, token_file=token_file, read_root=read_root,
                 write_root=write_root, exe=exe)
    cli = Client(port=cfg["port"], token_file=cfg["token_file"])
    if _port_open(cfg["port"]):
        if verbose:
            print(f"  PhotoCraft 已在 127.0.0.1:{cfg['port']}", flush=True)
        # 能连上但文件未生成时，认证会报清楚原因
        cli.ping()
        return cli

    exe_path = cfg["exe"] or _find_exe()
    tf = Path(cfg["token_file"])
    tf.parent.mkdir(parents=True, exist_ok=True)
    args = [
        str(exe_path),
        "--control", str(cfg["port"]),
        "--control-token-file", str(tf),
        "--automation-read-root", cfg["read_root"],
        "--automation-write-root", cfg["write_root"],
    ]
    if verbose:
        print(f"  启动 PhotoCraft：{exe_path}", flush=True)
        print(f"    read_root  = {cfg['read_root']}", flush=True)
        print(f"    write_root = {cfg['write_root']}", flush=True)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | \
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(args, close_fds=True, creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t0 = time.time()
    last = None
    while time.time() - t0 < wait:
        if _port_open(cfg["port"]):
            try:
                cli.ping()
                if verbose:
                    print(f"  PhotoCraft 就绪（{time.time()-t0:.1f}s）", flush=True)
                return cli
            except Exception as e:      # 端口开了但还没认证好
                last = e
        time.sleep(0.5)
    raise PhotoCraftError(
        f"PhotoCraft 没能在 {wait}s 内就绪（端口 {cfg['port']}）：{last or '端口未监听'}")


def check() -> int:
    cfg = config()
    print("配置：")
    for k, v in cfg.items():
        print(f"  {k:<11}= {v}")
    exe = cfg["exe"] or "（自动查找）"
    print(f"  exe        = {exe}")
    try:
        cli = ensure()
        info = cli.ping()
        print(f"  ✓ 已连接，窗口 {info.get('window')}")
        print(f"  ✓ 当前文档：{(info.get('session') or {}).get('documents')}")
        return 0
    except Exception as e:
        print(f"  ✗ {e}")
        return 1


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    print(__doc__)
