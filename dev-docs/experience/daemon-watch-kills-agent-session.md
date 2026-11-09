# daemon watch 模式误杀 agent 会话（发消息无回复）

## 问题现象

用户在需求检查工作区发消息（如「hi」或一句话需求），agent 永远「思考中」不回复；API 查 turn 状态为 `completed` 但零 assistant 回复，或 `interrupted`。此前两个验证对话也两次「卡思考中」——曾被误判为模型网关挂起。

## 排查过程

1. `GET /projects/:id/conversations/:id`：turn `completed` 但 items 只有 userMessage；另一 turn `interrupted`。
2. daemon.log 无 error/timeout，只有正常 `POST /turns → 202`。
3. 对比 pid：POST turns 由 pid 49992 处理，几分钟后请求由 pid 52768 处理——**daemon 中途重启了**。
4. 日志时间线还原：

   ```
   10:21:47.556  POST /turns（用户消息）→ 202 Accepted（pid 49992）
   10:21:47.601  Change detected in node_modules\openai\lib\ChatCompletionStream.mjs
                 Restarting 'src/daemon/server.ts --dev'
   10:21:52.114  新 daemon 起来（pid 52768）——旧进程连同 agent 会话被杀
   ```

## 根因

`dev:daemon` 用 `node --import tsx --watch src/daemon/server.ts --dev`。**node --watch 不带范围限制时，watch 所有被加载过的模块，包括 node_modules**。agent 会话启动时动态加载 openai SDK 等依赖，文件读取触发 watch 误报变化 → daemon 重启 → 正在跑的 agent 会话被杀 → turn 无回复（状态机把孤儿 turn 标成 completed 空回复或 interrupted）。

即「发消息必挂」：只要 agent 碰到会动态 import node_modules 模块的路径，watch 就重启。

## 解决方案

`package.json` 的 `dev:daemon` 加 `--watch-path=./src`（node ≥ 22 支持）：

```json
"dev:daemon": "bun run prepare:preinstalled-plugins && bun run prepare:examples && node --import tsx --watch --watch-path=./src src/daemon/server.ts --dev"
```

commit `2f5dac3`（分支 `feat/requirement-check-grasp`）。

## 预防/注意事项

- node --watch 默认范围 = 入口 + 所有加载过的模块（含 node_modules）；**必须配 `--watch-path` 限定**。
- node --watch 重启链的形态：父进程带 `--watch` 参数，重启出的子进程命令行**无 watch 参数**——排查时别被无 watch 的命令行骗到，要查 ParentProcessId。
- 「agent 卡思考中 + updatedAt 停滞 + 日志无错」三征同时出现时，先对比处理请求的 pid 是否变了（重启铁证），再怀疑模型网关。
- 改 `package.json` 本身也会触发旧 watcher 的最后一次重启；若重启后起不来（EADDRINUSE 僵尸），杀干净 43110 监听进程及其 watcher 父进程再起新脚本。
