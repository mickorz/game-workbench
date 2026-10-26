# Electron 二进制下载失败（fetch failed）

## 问题现象

在 ohmygame（仓库根）执行 `bun install` 后，`node_modules/electron/dist/` 不存在，
`node node_modules/electron/install.js` 报 `TypeError: fetch failed`（退出码 2），
启动桌面端时找不到 `electron.exe`。

## 排查过程

- `bun install` 本身成功（793 包），但 bun 默认不执行 Electron 的 postinstall 下载脚本
- 手动跑 `node node_modules/electron/install.js` 直连 GitHub release 下载，`fetch failed`（网络到 github.com release 下载不通）

## 根因

Electron 二进制托管在 GitHub Releases，本机直连下载失败；与 bun 是否执行 postinstall 无关（手动触发同样失败）。

## 解决方案

用 npmmirror 镜像环境变量重跑安装脚本：

```bash
ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/" node node_modules/electron/install.js
```

验证：`node_modules/electron/dist/electron.exe --version` 输出 `v43.3.0`。

## 预防/注意事项

- 以后任何依赖里带 Electron（或类似从 GitHub Releases 拉二进制的包，如 electron-builder），
  安装失败时优先加 `ELECTRON_MIRROR`（国内镜像 npmmirror）再重跑对应 install 脚本
- `package:win` 打包时 electron-builder 也可能要下载二进制，同样可用 `ELECTRON_MIRROR` / `ELECTRON_BUILDER_BINARIES_MIRROR`
