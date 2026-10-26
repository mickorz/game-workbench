---
name: backup-template
version: 0.1.0
display_name: 项目模板备份
display_name_en: Project Template Backup
description: >
  把当前仓库的代码与资源打包成「模板」zip（源码 / 配置 / docs / 交付包，
  排除 node_modules、dist、.runtime、.env、子模块、开发过程目录）。
  Use when the user says 备份代码、打个模板、备份成 zip、存档当前状态、
  backup the project / snapshot the template. Wraps the repo-root script
  backup_template.py with the right scope decisions and post-run checks.
---

# 项目模板备份（backup-template）

把 `xc-ui-flow` 当前状态打成一个可解压即用的模板 zip。执行层是仓库根的
`backup_template.py`，本技能负责**怎么调、怎么验、什么时候用哪个开关**。

## 一句话

```bash
python backup_template.py                # 全项目 -> backups/xc-ui-flow-template-<时间戳>.zip
```

输出目录默认 `<仓库根>/backups/`（已 gitignore，不进 git）。

## 先判断：要不要带交付包

| 场景 | 命令 | 体积参考 |
|---|---|---|
| 只是给代码/界面存档、要小包 | `python backup_template.py --no-delivery` | 1087 文件，18.7MB → 10.8MB |
| 要连「卡五星自动化流程-10-20」交付内容一起存档 | `python backup_template.py` | 1112 文件，21.2MB → 13.1MB |

拿不准就问一句，或者默认**不带交付包**（`--no-delivery`）：交付包本身有版本化的独立目录，重复备份成本高。

## 常用变体

```bash
python backup_template.py --name v1-baseline        # 命名模板，便于对照
python backup_template.py --out D:/Backups          # 输出到仓库外（推荐长期存档）
python backup_template.py --list backups/xxx.zip    # 查看 zip 内容清单（按目录聚合计数）
```

## 备份范围（脚本内置，改范围改脚本常量）

**收**：`src/`、`plugins/`、`scripts/`、`player/`、`integrations/`、`config/`、
`build/`、`test/`、`patches/`、`docs/`、根级配置文件（`*.ts`/`*.json`/`*.html`/
`*.md`、`bun.lock`、`electron-builder.yml`、`.gitignore`…）、可以带上交付包目录。

**不收**：`node_modules`、`dist`、`.runtime`、`.data`、`release`、`coverage`、
`.vite`、`thirdparties`（子模块）、`dev-docs`、`dev-examples`、`backups` 自身、
`.env*`（保留 `.env.example`）、`*.log`、`*.zip`、交付包内的 `work/` 扫描产物。

改范围改脚本顶部三组常量：`EXCLUDE_DIR_NAMES`、`EXCLUDE_REL_DIRS`、
`EXCLUDE_FILE_*`。

## 跑完必须核对（脚本会打印，别跳过）

1. **文件数**是否落在预期量级（约 1100，明显偏少 = 排除写太狠；偏多 = 漏排 node_modules）
2. **原始大小 → zip 大小**压缩比正常（约 2:1）
3. 用 `--list` 抽查：目标目录在、`node_modules`/`dist` 不在
4. 切换 `--no-delivery` 后要复验：交付包目录项应为 **0**

> 已知坑：早期版本 `--no-delivery` 只挡了目录名，没挡其下文件（`rglob` 返回的是文件）。
> 判断必须落在**文件收集层**、按路径第一级目录比较。改动这块逻辑后立刻用
> `--no-delivery` + `--list` 双跑验证，别只看打印的"文件数变了"。

## 恢复方式（写进交付说明时照抄）

```bash
unzip xc-ui-flow-template-<时间戳>.zip -d <目标目录>
cd <目标目录>
bun install
git submodule update --init        # thirdparties/ohmygame 不在包里
cp .env.example .env               # 按需填
```

Electron 二进制若拉取失败，见 `dev-docs/experience/electron-postinstall-fetch-failed.md`。

## 边界

- 这是**离线快照**，不是版本控制替代品：日常改动走 git，模板包用于交接/里程碑存档。
- 不备份 secrets。`.env`、密钥、token 在排除名单里，是有意为之，不要"顺手加上"。
- 不改脚本行为来"迁就"某种目录；范围是显式常量，改就改常量。
