<p align="center">
  <img src="desktop/macos/Runner/Assets.xcassets/AppIcon.appiconset/app_icon_128.png" width="80" alt="ProxySprint 图标">
</p>

# ProxySprint · 代理节点测速

**导入订阅，找出访问常用网站更快、更稳的节点。**

ProxySprint 按网站测试你的代理节点，比较访问成功率、响应延迟和波动，给出各网站的节点排名与推荐。支持 **Windows / macOS**，安装后即可使用。

[**下载安装**](https://github.com/yyyzl/ProxySprint/releases/latest) · [三步上手](#三步上手) · [常见问题](#常见问题) · [English](README.en.md)

![ProxySprint 测速结果界面：左侧选择网站与节点，右侧查看推荐和排名](preview.png)

*界面截图使用演示节点与示例数据，仅展示操作和结果布局。*

## 它能帮你做什么

- **按网站选节点**：分别测试 ChatGPT、GitHub、Google、YouTube、Wikipedia，也可添加自己的网址。
- **直接导入订阅**：粘贴 Clash/Mihomo 订阅链接，或选择 YAML / JSON 配置文件，无需另装代理客户端。
- **看速度，也看稳定性**：多轮请求比较成功率、响应延迟和波动；每轮都成功的节点才进入推荐。
- **缩小范围、保存结果**：按地区、策略组、来源或名称筛选，手动挑选节点，导出 CSV / JSON。

## 下载

| 你的设备 | 下载 | 安装方式 |
| --- | --- | --- |
| Windows 10/11 · x64 | [安装包 EXE](https://github.com/yyyzl/ProxySprint/releases/latest/download/ProxySprint-Setup.exe) | 双击，按向导安装 |
| Mac · Apple Silicon（M 系列） | [Apple Silicon DMG](https://github.com/yyyzl/ProxySprint/releases/latest/download/ProxySprint-macOS-arm64.dmg) | 打开后拖入 Applications |
| Mac · Intel | [Intel DMG](https://github.com/yyyzl/ProxySprint/releases/latest/download/ProxySprint-macOS-x86_64.dmg) | 打开后拖入 Applications |

Windows 另有[便携 ZIP](https://github.com/yyyzl/ProxySprint/releases/latest/download/ProxySprint-Windows-x64.zip)，完整解压后打开 `ProxySprint.exe`。无需安装 Python、Flutter 或 Node.js。

当前 Windows 安装包尚无代码签名；macOS 应用尚未经过 Apple 公证，系统可能显示安全提示。文件校验值见 Release 中的 `SHA256SUMS.txt`。

## 三步上手

1. **导入节点**：点击「导入节点」，粘贴自己的订阅链接，或选择配置文件。
2. **选择范围**：勾选常用网站，选择地区或节点。不限制地区时点击「全部地区」。
3. **开始测速**：查看各网站的推荐和排名；需要留存时点击「导出报告」。

已有 Clash Verge Rev 用户也可在「连接设置」中读取客户端节点。测速不会切换客户端正在使用的节点。

## 结果怎么看

| 指标 | 含义 | 怎么选 |
| --- | --- | --- |
| 成功率 | 多轮请求中，成功访问的比例 | 优先看 100% |
| 响应延迟 | 从发出请求到收到网站首个字节的时间，取多轮中位数 | 越小，响应越快 |
| 波动 | 多轮响应延迟的差异 | 越小，表现越稳定 |

这里测的是网站响应表现，不是下载带宽。ChatGPT 测试也不代表模型生成速度、账号可用性或服务解锁结果。结果反映本次网络状况，地区根据节点名称识别。

## 常见问题

**支持哪些订阅？** Clash/Mihomo 格式的 YAML / JSON。暂不支持 Base64 订阅或单条节点分享链接。应用不提供节点或订阅。

**订阅导入失败怎么办？** 当前通过直连获取订阅。可先下载配置文件，再从本地导入；订阅引用其他远程节点来源时，需要在界面中确认获取。

**订阅和报告放在哪里？** 保存在本机；订阅链接、节点密码不会写入测速报告。Windows 和 macOS 的数据目录见[开发说明](CONTRIBUTING.md#本地数据)。

**以前的 NodeScope 怎么升级？** ProxySprint 是 NodeScope 的新名称。Windows 直接覆盖安装；Mac 将新应用拖入 Applications，以后打开 ProxySprint。已有设置与报告继续使用，Mac 上旧的 NodeScope.app 可在确认新版本可用后自行移除。

## 开发与许可

[开发、测试与打包](CONTRIBUTING.md) · [架构与设计](DESIGN.md) · [验证记录](VALIDATION.md) · [反馈问题](https://github.com/yyyzl/ProxySprint/issues)

界面改编自 [ESTHER不二的 esther-design-system](https://github.com/esthersjw/esther-design-system)，遵循 **CC BY-NC-SA 4.0**（署名、非商业、相同方式共享）。随包 Mihomo 及其他依赖的许可证和源码链接见[第三方说明](THIRD_PARTY_NOTICES.md)。
