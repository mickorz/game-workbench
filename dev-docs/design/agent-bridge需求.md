还有一个核心微信的问题 dev-examples/fairygui-test-project/plugins/agent-bridge 这个插件没有被git跟踪，平时有大量修改时，万一丢失，非常危险

首先需要改名agent-bridge，改名称xc-link-plugin，里面也要检索agent-bridge相关的都替换成xc-link-plugin

然后要把这个插件放到当前目录，第三方库里面，目标工程通过link的方式安装这个插件，每次修改都可以直接同步