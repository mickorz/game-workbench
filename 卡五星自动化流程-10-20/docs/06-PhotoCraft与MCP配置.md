# 06 · PhotoCraft 与 MCP 配置

s3/s4 的 PSD 操作依赖 **PhotoCraft 桌面端**。本流程有**两条通道**连它：

| 通道 | 谁在用 | 怎么连 | 是否自动拉起桌面端 |
|---|---|---|---|
| **Python 控制客户端** | s3 `_pc_build.py`、s4 `_pc_export.py` 等 | `.opencode/lib/photocraft.py` → `127.0.0.1:7878` | ✅ 没开会自动拉起 |
| **opencode MCP** | 在 opencode 里直接调 `photocraft-live_*` 工具 | `photocraft-cli.exe mcp --bridge ...` → 桌面端 | ❌ 需要桌面端已在运行 |

两条通道最终都走同一个**本机控制端口 + token**，所以端口、token 文件、读写根必须一致。

## 1. 前置条件

需要 PhotoCraft 的两个可执行文件：

```
photocraft.exe       桌面端（提供控制端口和 UI）
photocraft-cli.exe   MCP / headless CLI
```

常见构建产物位置：

```
<PhotoCraft源码>\target\release\photocraft.exe
<PhotoCraft源码>\target\release\photocraft-cli.exe
```

示例（**按你自己的机器替换**）：

```
D:\Tools\PhotoCraft\target\release\photocraft.exe
D:\Tools\PhotoCraft\target\release\photocraft-cli.exe
```

## 2. 选择端口、token 文件、读写根

建议固定一套：

| 项 | 建议值 | 说明 |
|---|---|---|
| 端口 | `7878` | 只监听 `127.0.0.1` |
| token 文件 | `D:\PhotoCraft-Work\.photocraft-control.token` | 桌面端第一次启动会自动生成 256-bit token |
| 读根 | 工作区根的**上一级** | 要覆盖 client 工程 + PSD 素材库 |
| 写根 | **工作区根** | 要覆盖 `.opencode/work/<需求>/` 的输出 |

> 读根/写根是**桌面端进程**的参数，不是 MCP CLI 的参数。MCP bridge 只负责转发；文件权限由桌面端决定。

示例：

```
读根 = D:\YourProject
写根 = D:\YourProject\自动化流程
```

如果 PSD 或工程在别处，把读根放宽到共同上级，或分别配置。

## 3. 启动桌面端

### 方式 A：手动启动（推荐首次排查用）

```powershell
& "D:\Tools\PhotoCraft\target\release\photocraft.exe" `
  --control 7878 `
  --control-token-file "D:\PhotoCraft-Work\.photocraft-control.token" `
  --automation-read-root "D:\YourProject" `
  --automation-write-root "D:\YourProject\自动化流程"
```

- token 文件不存在时，PhotoCraft 会创建并写入新 token；
- 已有文件会复用；
- 不想用命令行暴露 token，就用 token 文件，不要用 `--control-token` 直接传。

### 方式 B：让 Python 客户端自动拉起

先配好 `.opencode/photocraft.json`（见第 4 节），然后：

```powershell
python .opencode/lib/photocraft.py --check
```

桌面端没开时，`photocraft.py` 会按配置启动：

```
photocraft.exe --control <port> --control-token-file <token_file>
  --automation-read-root <read_root> --automation-write-root <write_root>
```

### 方式 C：环境变量

适合临时切换：

```powershell
$env:PHOTOCRAFT_EXE = "D:\...\photocraft.exe"
$env:PHOTOCRAFT_CONTROL_PORT = "7878"
$env:PHOTOCRAFT_CONTROL_TOKEN_FILE = "D:\PhotoCraft-Work\.photocraft-control.token"
$env:PHOTOCRAFT_READ_ROOT = "D:\YourProject"
$env:PHOTOCRAFT_WRITE_ROOT = "D:\YourProject\自动化流程"
```

## 4. 配置 Python 客户端：`.opencode/photocraft.json`

复制示例：

```powershell
Copy-Item .opencode/photocraft.example.json .opencode/photocraft.json
```

内容：

```json
{
  "exe": "D:/Tools/PhotoCraft/target/release/photocraft.exe",
  "port": 7878,
  "token_file": "D:/PhotoCraft-Work/.photocraft-control.token",
  "read_root": "D:/YourProject",
  "write_root": "D:/YourProject/自动化流程"
}
```

字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `exe` | 否 | `photocraft.exe` 路径；不填则查 PATH 和 `D:/AI*/photocraft-main/...` |
| `port` | 否 | 默认 `7878` |
| `token_file` | 否 | 默认 `D:\PhotoCraft-Work\.photocraft-control.token` |
| `read_root` | 否 | 默认**工作区根的上一级** |
| `write_root` | 否 | 默认**工作区根** |

**配置优先级**：

```
显式参数 > 环境变量 > .opencode/photocraft.json > 内建默认
```

对应环境变量：

```
PHOTOCRAFT_EXE
PHOTOCRAFT_CONTROL_PORT
PHOTOCRAFT_CONTROL_TOKEN_FILE
PHOTOCRAFT_READ_ROOT
PHOTOCRAFT_WRITE_ROOT
```

> 上面这组是 **Python 客户端**（`photocraft.py`）的变量。桌面端进程自己的读写根环境变量名是 `PHOTOCRAFT_AUTOMATION_READ_ROOT` / `PHOTOCRAFT_AUTOMATION_WRITE_ROOT`；MCP bridge 不读读写根，读写根只在桌面端配置。

> `photocraft.py` 的 `exe` 只用于**拉起桌面端**；MCP 用的是 `photocraft-cli.exe`，两者不要混。

### 自检

```powershell
python .opencode/lib/photocraft.py --check
```

正常输出类似：

```
配置：
  port       = 7878
  token_file = D:\PhotoCraft-Work\.photocraft-control.token
  read_root  = D:\YourProject
  write_root = D:\YourProject\自动化流程
  exe        = （自动查找）
  PhotoCraft 已在 127.0.0.1:7878
  ✓ 已连接，窗口 {...}
  ✓ 当前文档：[]
```

如果桌面端已用**别的读写根**启动，`ensure()` 会直接复用、不会重启。路径越界时请关掉桌面端，用第 3 节的命令重新启动。

## 5. 配置 opencode MCP

### 5.1 配置文件放哪

两种都行：

| 位置 | 作用范围 | 适合 |
|---|---|---|
| `<工作区根>/opencode.json` | 只对这个项目 | **推荐随包交付**，换机器只改路径 |
| `~/.config/opencode/opencode.json` | 当前用户所有项目 | 本机长期使用 |

如果项目级和用户级都有，opencode 会合并；同键以项目级为准。**改完必须重启 opencode**。

### 5.2 配置片段

参考 `docs/examples/opencode.mcp.example.json`：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "photocraft-live": {
      "type": "local",
      "enabled": true,
      "command": [
        "D:\\Tools\\PhotoCraft\\target\\release\\photocraft-cli.exe",
        "mcp",
        "--bridge",
        "127.0.0.1:7878",
        "--control-token-file",
        "D:\\PhotoCraft-Work\\.photocraft-control.token"
      ]
    }
  },
  "experimental": {
    "mcp_timeout": 60000
  }
}
```

要点：

- Windows JSON 路径里的反斜杠要写成 `\\`；也可以用 `/`。
- `command` 必须是数组；第一项是可执行文件**完整路径**（不在 PATH 时）。
- `--bridge 127.0.0.1:7878` 必须与桌面端 `--control` 端口一致。
- `--control-token-file` 必须与桌面端使用的 token 文件**同一个**。
- `mcp_timeout` 单位毫秒；长任务建议 `60000`。
- 服务名 `photocraft-live` 决定工具前缀：`photocraft-live_command_run`、`photocraft-live_doc_inspect`、`photocraft-live_ui_screenshot` 等。

### 5.3 启动顺序

```
1. 启动 PhotoCraft 桌面端（带 --control / token / 读写根）
2. 确认端口可连（photocraft.py --check）
3. 启动 / 重启 opencode
4. 在 opencode 里确认 photocraft-live_* 工具出现
```

**MCP bridge 不会替你启动桌面端**。桌面端没开时，MCP 工具会连接失败。

### 5.4 验证 MCP

在 opencode 里让模型执行：

```text
用 photocraft-live 的 command_list 看一下当前可用命令
```

或直接调用 `photocraft-live_command_list`。能返回命令列表，说明 bridge 认证和转发都正常。

## 6. 安全注意事项

- token 是**持有即可控制**的 bearer 凭证：能调 UI、执行命令、控制应用。不要提交、不要发群、不要写日志。
- token 文件放用户私有目录，Windows 下设置仅当前用户可读的 ACL。
- 控制协议**不加密**，只允许 loopback；不要做端口转发、代理或隧道到其他机器。
- 不要把 token 直接写在命令行参数里（进程列表可见）；用 `--control-token-file`。
- 换人使用 / 交付时，**不要带上 token 文件**；对方第一次启动会自动生成新的。
- 模型供应商的 `apiKey` 与 PhotoCraft token 是两套东西，都不要进交付包。

## 7. 排查表

| 现象 | 原因 | 处理 |
|---|---|---|
| `找不到 photocraft.exe` | 没配 `exe`，也不在 PATH / 默认搜索路径 | 配 `photocraft.json` 的 `exe` 或设 `PHOTOCRAFT_EXE` |
| `control token 文件不存在` | 桌面端没启动过，或 token 路径不一致 | 启动桌面端；或让 `photocraft.py --check` 自动拉起 |
| `控制端口认证失败` | 桌面端和客户端用的 token 文件不是同一个 | 统一 `--control-token-file`；重启桌面端 |
| `PhotoCraft 已在 127.0.0.1:7878` 但后续报错 | 端口被别的实例占用 | 关掉多余 PhotoCraft 实例；或换端口并同步配置 |
| MCP 工具不出现 | 配置没加载 / JSON 语法错 / 没重启 | 检查 `opencode.json`；重启 opencode |
| MCP 报连接失败 | 桌面端没开，或 bridge 端口不对 | 先启动桌面端；核对 `--bridge` 与 `--control` |
| `automation read ... failed` | 读根没覆盖输入文件 | 放宽 `--automation-read-root`，重启桌面端 |
| `automation write ... failed` | 写根没覆盖输出目录 | 放宽 `--automation-write-root`，重启桌面端 |
| `the request was not sent` | bridge 连不上或请求未发出 | 检查桌面端/端口；可安全重试 |
| 长命令超时 | 超过 MCP/控制超时 | 用 `wait:false` + `jobs_list` 轮询；或提高 `mcp_timeout` |
| `a document must keep at least one layer` | PhotoCraft 不允许删到 0 层 | 保留最底层垫层，不要删它 |
| 中文路径 / 空格报错 | 命令拼接没加引号 | PowerShell 里用 `& "完整路径"`，JSON 里用 `/` 或 `\\` |
| 换了机器后全挂 | exe/端口/token/读写根还是旧路径 | 按第 3~5 节重配；token 重新生成 |

## 8. 交付时不要带的东西

- `.opencode/photocraft.json`（含本机绝对路径；让对方从示例复制后改）
- token 文件（`.photocraft-control.token`）
- `opencode.json` 里的真实 API Key
- `node_modules/`、`__pycache__/`、`dist/`

需要带的模板：

```
.opencode/photocraft.example.json
docs/examples/opencode.mcp.example.json
.opencode/workspace.example.json
```

## 9. 最小可用检查清单

- [ ] `photocraft.exe` / `photocraft-cli.exe` 路径确认；
- [ ] 端口 `7878` 未被无关程序占用；
- [ ] token 文件路径固定且只有当前用户可读；
- [ ] 桌面端读写根覆盖 client 工程、素材库、需求输出；
- [ ] `python .opencode/lib/photocraft.py --check` 通过；
- [ ] `opencode.json` 的 MCP `command` 路径正确、JSON 合法；
- [ ] 重启 opencode 后能看到 `photocraft-live_*` 工具；
- [ ] `command_list` 能返回结果；
- [ ] 交付包里没有 token / API Key / 本机 `photocraft.json`。
