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

## 变体二：残留多套 watcher 链，旧链（无 watch-path）继续杀会话（2026-11-09 P3 后补）

- 现象：daemon 已修 `--watch-path=./src`，但 agent 会话仍被莫名中断；日志出现 `Change detected in node_modules\undici\...` 触发 Restarting——明明不在 watch 范围。
- 根因：历史上多次起链/杀链不彻底，机器上**同时存活多套 watcher**（旧脚本的无 watch-path 链 + 新链 + 重复链）。旧链盯全模块，node_modules 变化时它触发重启：杀掉当前占 43110 的子进程（连同活跃 agent 会话），再 spawn 新子进程抢占端口。看起来像「watch-path 没生效」，实际是残留旧链作恶。
- 排查：`Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match 'daemon/server' }`，按命令行有无 `watch-path` 分 OLDWATCH/NEW/CHILD——OLDWATCH 存在即坐实。
- 修法：按 pid 全部 `taskkill //F //PID`（CHILD 会随链退或单独杀），确认 43110 释放后重跑一条 `bun run dev:daemon`；验证进程数 = 2（watcher + child）。
- 预防：每次杀 daemon 时杀整链（`taskkill //F //T //PID <watcher>`），不要只杀子进程；起链前先查端口是否残留。

## 变体：开发期改 daemon 代码 → watch 重启 EADDRINUSE 卡死（2026-11-09 P3 补）

即使加了 `--watch-path=./src`，**跑着 agent 会话时改 daemon 侧 src 文件**仍会踩新坑：

- 现象：日志尾部 `Restarting` → `EADDRINUSE` → `Failed running 'src/daemon/server.ts --dev'. Waiting for file changes before restarting...`，watcher 卡死不再自愈；但 health 仍 200（旧子进程还在服务，跑的是**旧代码**）。
- 根因：旧子进程因活跃 SSE/agent 会话连接未退干净占着 43110，新子进程 spawn 即 EADDRINUSE 死亡，watcher 陷入等待。
- 修法：杀整链 `taskkill //F //T //PID <watcher父pid>`（netstat 拿 43110 监听 pid → 查其 ParentProcessId 即 watcher），重跑 `bun run dev:daemon`。
- 预防：改 daemon 侧代码前先停掉进行中的 agent 会话，或接受重启杀会话后手动重链。
