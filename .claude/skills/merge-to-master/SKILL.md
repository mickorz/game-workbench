---
name: merge-to-master
version: 0.1.0
display_name: Worktree 合并回 master
display_name_en: Merge Worktree Branch Back to Master
description: >
  把当前 git worktree 上的功能分支安全合并回 master 主 worktree：
  先 fetch origin 并把 origin/master 合入当前分支（在本 worktree 解决冲突、
  跑完项目验证门禁），再从 master 主 worktree fast-forward 合回并推送。
  master 永不接收未验证代码、永不承担冲突解决。
  Use when the user says 合并回 master、合回主干、把这个分支合到 master、
  merge back to master、整合当前 worktree 的代码.
---

# Worktree 合并回 master（merge-to-master）

## 能力

把当前 worktree 检出的功能分支，安全合并回 master 主 worktree 并推送远端。
核心顺序决策（已固化，不要临时改）：**先合 master 入分支（此处解决冲突 + 验证），再合分支回 master（应 fast-forward）**。

## 何时使用

- 用户要求把当前 worktree / 当前分支的代码合并回 master / 主干
- 功能开发完成，分支需要回合主干

## 能力边界

- **只做 merge 回合**：不做 rebase、不做 cherry-pick、不改写任何已存在的提交
- **不在 master 上解决冲突**：冲突一律在当前功能分支 worktree 内解决
- **不 force push**：push 被拒（远端又有新提交）时回到同步步骤重走，绝不 `--force`
- 分支删除不属于本流程（需用户明确要求另行处理）

## 关键规则

1. 当前 worktree 工作区必须干净（`git status` 无未提交改动）才开始合并
2. master 主 worktree 路径从 `git worktree list` 动态获取，不写死
3. 回合 master 必须 fast-forward 或无冲突；否则说明 master 又动了，回分支重新同步
4. 集成态必须先在功能分支跑完验证门禁，master 才能接收

## 执行流程

进入 [references/merge-flow.md](references/merge-flow.md) 按步骤执行。

## 完成标准

- chatbox 分支已合入 master 主 worktree 且已推送 origin
- master 上合并为 fast-forward（或无冲突 merge），工作区干净
- 分支上的验证门禁（typecheck / test / build）全部通过后才推送
- 向用户报告：合并的提交范围、master 主 worktree 路径、验证结果、推送状态
