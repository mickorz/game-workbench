# 安装与运行验收清单

## 总览

验收目标：OpenCode 工作区能定位 client 工程，s1→s2 全链路能跑通，产物落点正确。

## 安装检查

- [ ] `opencode --version` 可执行
- [ ] `python --version` 输出 3.10+，`python -c "import PIL"` 不报错
- [ ] 在 `卡五星自动化流程-10-20/` 启动 OpenCode 能加载 `.opencode/command/` 下的 s0~s4 命令
- [ ] `/s0-env` 运行后 `.opencode/workspace.json` 里 client_dir、game_key 均已写入

## 冒烟测试

- [ ] `python .opencode/lib/workspace.py where` 三条路径解析正确
- [ ] `python .opencode/skills/fgui-flow/scripts/scan_fgui.py` 生成 `.opencode/work/facts.json`，`lookup.py --check` 报"事实表可用"
- [ ] `python .opencode/skills/fgui-req/scripts/excel_to_req.py`（inbox 有测试 Excel）生成需求目录，含 参考图_1334x750/
- [ ] `python .opencode/lib/photocraft.py --check` 连接成功（仅 s4 需要）

## 最终清单

- [ ] s1 产物（清单.json/施工单.md）字段完整（每条需求有 名称+描述）
- [ ] s2 改动只在方案列出的文件范围内，client 工程其他文件零改动
- [ ] 备份在 `<需求>/备份/`，快照在 `<需求>/FGUI/`
- [ ] 效果经人确认后才补文档与交付
