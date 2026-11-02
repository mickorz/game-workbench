const COMPONENT_NAME_BODY = "[A-Z][A-Za-z0-9_]{3,}";
const FENCED_CODE_RE = /\n```[\s\S]*?\n```|\n~~~[\s\S]*?\n~~~/g;
const LINKED_NAME_RE = new RegExp("\\[(`?(" + COMPONENT_NAME_BODY + ")`?)\\]\\(([^)]*)\\)", "g");
const NON_COMPONENT_URL_RE = /\.(png|jpe?g|gif|webp|svg|md|pdf|zip|mp4|mp3|wav|json)$/i;
const BARE_TICK_NAME_RE = new RegExp("`(" + COMPONENT_NAME_BODY + ")`(?!\\]\\(fgui)", "g");
function linkify(text) {
  return text.split(FENCED_CODE_RE).map((part, index) => {
    if (index % 2 === 1) return part;
    let out = part.replace(LINKED_NAME_RE, (m, _outer, name, url) => {
      if (url.startsWith("fgui://") || NON_COMPONENT_URL_RE.test(url)) return m;
      return "[`" + name + "`](fgui://component/" + name + ")";
    });
    out = out.replace(BARE_TICK_NAME_RE, (m, name) => {
      if (/[./]/.test(name)) return m;
      return "[`" + name + "`](fgui://component/" + name + ")";
    });
    return out;
  }).join("");
}
const src = [
  "带反引号链接 [`KW_BTN_ACTIVITY`](LobbyBottomView.xml) 和空链接 [`C_LoginBtn`]()",
  "无反引号链接 [AwardBoxView](lobby_award_box) 与文件链接 [规则图](design/x.jpg) 保留",
  "裸反引号 `GameFirstWinView` 与文字",
  "```xml\n<image name=\"KW_BTN_ACTIVITY\"/>\n``` 代码块不动",
  "组件名链接 [LoginBtn](components/LoginBtn.xml) 也要中",
].join("\n");
console.log(linkify(src));
