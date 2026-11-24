# 品牌名带空格暴露 commandPaths 引号切词缺陷

## 问题现象

全量品牌改名（XC-UI-Flow → Game Workbench）后，`test/agent-runtime-units.test.ts`
的「工作区在数据目录内」用例从 allow 变 ask：`ls "<workspace>/assets"`（workspace
fixture 路径含空格 `~/Game Workbench/data/...`）被审批策略误判为越界。

## 排查过程

1. 基线对比（git stash 后跑同一批用例）确认该用例改名前通过 → 新引入，非环境问题。
2. 失败的是 kind=command 分支 → 定位 `commandPaths`：
   旧实现先 `replace(/["'`]/g, " ")` 删掉所有引号再按 `[\s;&|()<>]+` 切词，
   带空格的引号路径被拆成 `...Game` 和 `Workbench\...` 两段，后半段相对解析后
   落到工作区外 → 误判 ask。
3. 老品牌名 `XC-UI-Flow` 不含空格，恰好掩盖了这个缺陷——改名即暴露。

## 根因

`src/daemon/agent-runtimes/policy.ts` 的 `commandPaths` 不感知引号：
任何路径带空格的真实用户（如 `E:\My Games\...`）在自己工作区内执行
`ls/cat` 等命令都会被误弹审批，属于真实产品缺陷，不只是测试 fixture 问题。

## 解决方案

- `commandPaths` 改为引号感知的字符扫描：引号外的分隔符才切词，引号字符仍被
  剥掉（保证 `zsh -lc '...'` 包装不隐藏路径）。
- deny 检查用 `reachCandidates`（粘合 token + 其内部空白子词）双保险：
  嵌套引号里藏的受保护路径（`zsh -lc 'cat "$HOME/.claude.json"'`）仍判 deny；
  越界 ask 检查只用粘合 token，避免子词造成新误报。

## 预防 / 注意事项

- 改品牌名/改任何会进入路径 fixture 的常量时，先 grep 测试里的路径字面量，
  评估空格、大小写对路径解析类函数的影响。
- 「换个名字导致测试挂」不一定是测试要跟着改——先判断暴露的是不是真 bug
  （本例：fixture 带空格后暴露的策略解析缺陷，修产品而非改断言）。
- Windows 无管理员权限跑不了 symlink 类测试（同批失败多为该环境问题，
  基线对比可快速甄别）。
