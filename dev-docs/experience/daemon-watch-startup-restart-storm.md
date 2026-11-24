# dev daemon 启动期重启风暴（静默自愈）

## 问题现象

`bun run dev` 启动后，daemon 日志连续出现 `Restarting 'src/daemon/server.ts --dev'`
（一次 5~12 次不等），期间无任何报错输出、无 `Server listening`，43110 端口时有时无
（curl 偶发 000）。转几圈后自动稳定：某次重启成功监听，此后不再重启。

- 发生环境：master 分支，Windows，`dev:daemon` 已带 `--watch-path=./src` 限制。
- 取证：风暴期间 `git status src/` 干净、`find src -newer <marker>` 无文件变动
  → 排除 src 文件变更触发，也排除 node_modules 读取触发（watch-path 已限制）。
- 间隔特征：成功监听后约 44~46 秒又出现下一轮重启，几次后彻底停止。

## 排查过程

1. 先怀疑 master 缺少 feat 分支的 `2f5dac3`（watch 限制到 src）→ cherry-pick 后风暴仍在，
   说明该修复只挡「node_modules 读取触发」的会话中断，与本启动风暴无关。
2. 查 `dev-docs/experience/dev-daemon-watch-kills-sessions.md` → 那是「编辑 src 触发」的坑，
   症状不同（本风暴无人编辑代码、src 无变动）。
3. 标记文件法确认 src 无变动 → 触发源不在 watch 的监听范围语义内。

## 根因（暂定，未完全定位）

触发源未定位。可能性排序：
- daemon 启动早期某子系统（pi-agent 环境 / examples 准备）在启动后数十秒内退出子进程，
  使 node --watch 认为进程退出而重启；多次重试中有竞争（端口未及时释放），表现为连发。
- Windows 下 node --watch 对目录元数据变化的误报。

## 解决方案（当前采用）

- 风暴是**启动期瞬态、会自愈**：观察 90 秒，监听稳定、计数不再增长即可认为可用。
- 需要绝对稳定的调试会话时，仍按 `dev-daemon-watch-kills-sessions.md` 的方案：
  去掉 `--watch` 直跑 `node --import tsx src/daemon/server.ts --dev`。

## 预防 / 注意事项

- 启动后若看到连发 `Restarting`，先看是否最终出现 `Server listening` 且计数停止：
  出现即自愈完成，不必反复杀进程重拉。
- 判断"能否使用"的标志：监听 PID 不变 + Restarting 计数 90 秒不涨。
- 若风暴变成无限循环（计数持续增长、永不监听），升级为阻塞性问题，需按根因方向排查。
