# 发消息必卡：dev daemon 的 --watch 杀掉会话进程

## 问题现象

应用会话里发任何消息（哪怕 `hi`）都「卡住」：turn 显示 interrupted，agentMessage 为空。
时间线上 userMessage 写入后无任何模型请求。

## 排查过程

1. 会话 API 返回 `agent.status: idle`、最后 turn `status: interrupted` → 不是网络/模型问题。
2. 会话 jsonl 停在 user 消息写入 → agent 子进程在发起模型请求前就死了。
3. daemon 日志：POST turns 202 后 17 秒出现 `Restarting 'src/daemon/server.ts --dev'`
   → daemon watcher 因**文件变动**重启，杀掉正在跑的 agent 进程。

## 根因

`dev:daemon` 脚本带 `node --watch`（`package.json` 的 `dev:daemon`）。
在「边改代码边开着会话调试」的工作流里，每次保存 `src/` 下任何文件都会重启 daemon，
把进行中的会话 turn 全部中断。误以为是模型/网桥问题，实际是开发工具链行为。

## 解决方案

- **调试期间**（需要会话保持稳定）：不用 `bun run dev:daemon`，改用
  `node --import tsx src/daemon/server.ts --dev`（去掉 `--watch`）+ `prepare:preinstalled-plugins` 先行。
- **改后端代码后**：无 watch 模式不会自动重启，改完必须手动重启 daemon（先杀旧 node 进程再拉起）。
- 前端（renderer/vite）不受影响，HMR 照常。

## 预防 / 注意事项

- 「发消息卡住」先查三件事：① `agent.status` 是否 idle；② 最后 turn 是否 interrupted；
  ③ daemon 日志有无 `Restarting`。三个都中就是本坑，不是模型问题。
- 叠加多个 daemon watcher（历史教训）+ watch 模式 = 会话随时被杀；单进程无 watch = 稳定。
- interrupted 的 turn 内容不丢，刷新页面可见历史；重发消息即可续上。
