# 合并回 master 执行流程

前置：当前 worktree 检出的是功能分支（如 chatbox），master 检出在另一个主 worktree。
执行中任何一步失败或验证不通过：**停在分支上修复，master 保持不动**。

## 步骤 1：预检

1. `git status`——工作区必须干净；有未提交改动时停下，让用户先提交或明确指示处理，不要自行 stash 提交
2. `git worktree list`——找到 master 检出的主 worktree 路径（形如 `E:/...`），后续 `<master>` 均指此路径；找不到 master 检出（本仓库只有主 worktree 自己）时报告用户再继续
3. 确认当前分支名（下称 `<branch>`，如 chatbox）：`git branch --show-current`

## 步骤 2：同步主干到当前分支

```bash
git fetch origin
git merge origin/master
```

- 用 `origin/master` 而不是本地 master：不碰主 worktree 的检出，且远端才是最新事实
- **不要用 `git pull`**：等价但隐式，失败时信息差

结果分派：
- **Already up to date** → 直接进步骤 4
- **干净合并** → 进步骤 3
- **冲突** → 进步骤 2.1

### 步骤 2.1：解决冲突（只在当前分支）

1. `git status --short` 列出冲突文件
2. 逐文件解决：先读双方版本理解语义（一边是 master 新改动、一边是分支改动），按两边意图合并；**禁止**为了消冲突瞎选一边
3. 冲突集中在本批功能相关文件（如 renderer/daemon）时，以分支侧为主、吸收 master 侧对同一处的新改动
4. `git add` 全部解决文件后 `git commit`（保留默认 merge message）
5. 进入步骤 3

## 步骤 3：分支上验证集成态（门禁）

在当前 worktree 按项目门禁跑（xc-ui-flow 仓库的清单）：

```bash
bun run typecheck
bun run test        # 有环境类失败基线时对比 diff，只确认零新增失败
bun run build:renderer
```

任何一项不通过：在分支上修好再重跑；修不动时报告用户，**不进步骤 4**。

其他项目：以该项目的检查命令为准（无门禁可跑时至少完成一次构建或冒烟检查）。

## 步骤 4：回合 master

在 master 主 worktree 执行（不在当前 worktree 切分支——master 被另一 worktree 占用，本 worktree 根本无法检出）：

```bash
git -C <master> merge <branch>
```

- **Fast-forward**（预期结果）→ 进步骤 5
- **无冲突 merge**（master 期间又动了但无冲突）→ 可接受，进步骤 5
- **冲突或非 ff 且有冲突** → 说明同步后 master 又前进了：`git -C <master> merge --abort`，回步骤 2 重新同步重来

## 步骤 5：master 上验证并推送

1. master 快速验证：至少 `git -C <master> ...` 跑该项目 typecheck（完整门禁已在分支跑过，此处防意外）
2. 本仓库带 submodule（`thirdparties/thinkrail`）：`git -C <master> submodule update --init`，让主 worktree 的子模块检出对齐合并进来的 gitlink 指针
3. 推送：`git -C <master> push origin master`
4. push 被拒（远端又有新提交）：`git -C <master> fetch origin` 后回步骤 2 重新同步；**禁止 force push**

## 步骤 6：收尾报告

向用户报告：
- 合并的提交范围（`git log origin/master..<branch> --oneline` 的结果，推送后可从 merge 前记录）
- master 主 worktree 路径、合并类型（fast-forward / clean merge）
- 步骤 3 门禁结果
- 推送状态
- 分支保留现状（未删除；用户要删时 `git branch -d <branch>` 且确认当前 worktree 后续去向）

## 反模式（禁止）

- 在 master 检出上解决冲突（中间态暴露在主干工作区，master 历史留冲突噪音）
- `git pull` 隐式合并、rebase 改写分支历史、cherry-pick 挑拣代替合并
- 验证没跑完就回合 master / force push
- 硬编码主 worktree 路径（换机器即失效，一律 `git worktree list` 动态取）
