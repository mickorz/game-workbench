# 隐藏工作室后首页新建弹窗崩溃（默认 projectType 落空）

## 问题现象

`test/runtime-recovery.test.tsx` 两条失败（基线同样失败，曾被误判为环境性）：
`TypeError: undefined is not an object (evaluating 'current.value')`，指向
`ProjectTypeSelector`（`src/renderer/project-prompt-creator.tsx:571`）。

## 排查过程

1. 崩溃点：`const current = options.find((option) => option.value === value)!`——
   find 落空后非空断言失效，`current.value` 崩。
2. `home.tsx`：`useState<ProjectType>("web-game")` 硬编码默认 + 
   `projectTypes={GAME_PROJECT_TYPES}`。
3. 隐藏工作室特性把 `GAME_PROJECT_TYPES` 过滤到只剩 `["fairygui"]`（P2
   工作室阶段引入 `HIDDEN_PROJECT_TYPE_IDS`），"web-game" 已不在选项里 → find 落空。

## 根因

默认值硬编码了一个可能被过滤掉的类型；选项列表与默认值是**两个独立来源**，
过滤列表的人不会想到另一处的默认值。

## 解决方案

默认值取可见列表首项：`useState<ProjectType>(GAME_PROJECT_TYPES[0]?.value ?? "web-game")`。
`game-studio-home.tsx` 不传 `projectTypes`（默认 `PROJECT_TYPES` 全集含 fairygui）不受影响。

## 预防/注意事项

- 「基线同样失败」≠ 环境性。**只对比失败名单不看失败原因**是误判根源：
  本例 5 条被误判为环境性的失败里，3 条其实是 fairygui/隐藏工作室的真实回归
  （plugin-catalog 断言少 fairygui、runtime-recovery 崩溃、project-types 断言）。
  正确姿势：基线对比后，对非 symlink/EPERM/超时类的失败**逐条看 AssertionError 内容**。
- 选项列表与选中值解耦的组件，默认值应从列表派生，不应硬编码成员。
- 非空断言 `!` 配动态过滤列表 = 崩溃埋雷；`find(...)!` 的前提是调用方保证 value ∈ options。
