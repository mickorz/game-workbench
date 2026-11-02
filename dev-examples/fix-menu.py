# 工具栏菜单与命令 id：agentbridge -> xclink（无连字符变体检漏）
import io

p = "thirdparties/xc-link-plugin/main.js"
s = io.open(p, encoding="utf-8").read()
assert '"agentbridge_restart"' in s
s = s.replace('"agentbridge_restart"', '"xclink_restart"')
s = s.replace("Agent bridge: restart server", "XCLink: restart server")
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# 分发副本同步
shutil.copyfile(p, "plugins/fairygui/editor-plugin/main.js")
print("fixed")
