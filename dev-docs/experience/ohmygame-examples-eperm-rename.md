# ohmygame 示例工程构建后 rename 报 EPERM（Windows 文件锁）

## 问题现象

仓库根跑 `bun run dev`（ohmygame），daemon 日志报：

```
Examples are unavailable: EPERM: operation not permitted, rename
'E:\...\ .runtime\examples-build-l5qAQ7\output' -> 'E:\...\.runtime\examples'
```

daemon 本身照常起（Server listening），但示例库为空（`/plugins` 正常、examples 缺失）。

## 排查过程

- `bun run dev` 的结构：`build:player && concurrently(dev:daemon, dev:renderer)`
- `dev:daemon` 里 `prepare:examples` 与 `dev:renderer`（vite dev server）**同时启动**；
  日志里能看到 vite 在 prepare-examples 构建期间对 `.runtime/examples-build-*/` 下文件
  反复触发 "page reload / changed tsconfig file detected"——vite 的 watcher 正盯着这些文件
- 杀掉整个栈，清掉 `.runtime/examples*`，**单独**跑 `bun run dev:daemon`（无 vite watcher）：
  rename 成功，`Prepared 4 examples`，`.runtime/examples/` 落齐 circuit-craftsman / ember-route /
  tidal-workshop / wetland-birdwatching + catalog.json

## 根因

Windows 上目标目录里有文件被其他进程打开时，目录 rename 报 EPERM。
vite dev server 的文件 watcher 在 prepare-examples 构建期间持有
`.runtime/examples-build-*/` 下文件的句柄，导致 daemon 完成构建后的原子 rename 失败。

## 解决方案

首次运行（或 examples 需要重建时）按这个顺序：

```bash
bun run dev:daemon        # 先单独跑 daemon（内含 prepare:examples），等 Server listening
bun run dev:renderer      # 再另开终端起 vite dev server（127.0.0.1:43120）
```

已就位后日常跑 `bun run dev` 仍可能复发（prepare 每次重建再 rename，vite 同时在 watch），
同理：先 daemon 后 renderer，或干脆两个终端分开跑。

## 预防/注意事项

- 看到 "Examples are unavailable: EPERM" 不用慌：daemon 是好的，只是示例库没就位
- 清理重置：`rm -rf .runtime/examples .runtime/examples-build-*` 后按上面顺序重来
- 这类"构建产物目录被 dev server watch"的锁冲突是 Windows 常见模式，其他项目遇到
  目录 rename/move 失败先查有没有 vite/webpack watcher 或编辑器占着文件
