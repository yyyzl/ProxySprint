# ProxySprint · 代理节点测速

导入订阅，找出访问常用网站更快、更稳的节点。

## 安装与打开

- Windows 安装版：运行 ProxySprint-Setup.exe，按向导安装。
- Windows 便携版：完整解压 ZIP，打开 ProxySprint.exe，保留旁边的文件和目录。
- macOS：将 ProxySprint 拖入 Applications，再从“应用程序”打开；安装后可推出 DMG。

无需安装 Python、Flutter 或额外的代理客户端。Windows 安装包尚无代码签名，macOS 应用尚未经过 Apple 公证。

## 三步使用

1. 点击「导入节点」，粘贴 Clash/Mihomo 订阅链接，或选择 YAML / JSON 配置文件。
2. 选择常用网站和节点范围；不限地区时点击「全部地区」。
3. 点击「开始测速」，比较各网站的推荐与排名。需要留存时导出报告。

优先选择成功率 100% 的节点，再比较响应延迟和波动，数值越小越好。响应延迟是从发出请求到收到网站首个字节的时间，不代表下载带宽、模型生成速度或服务解锁结果。

订阅目前直连获取；导入失败时可改用本地文件。暂不支持 Base64 订阅或单条分享链接。请使用自己的订阅，应用不提供节点。

## 从 NodeScope 升级

ProxySprint 是 NodeScope 的新名称，已有设置和报告继续使用。Windows 可直接覆盖安装；Mac 安装新应用后打开 ProxySprint，确认正常后可自行移除旧 NodeScope.app。

设置与报告保存在本机的 NodeScope 数据目录中，订阅链接和节点密码不会写入报告。

使用说明：https://github.com/yyyzl/ProxySprint

反馈问题：https://github.com/yyyzl/ProxySprint/issues

许可与依赖见随包 THIRD_PARTY_NOTICES.md。
