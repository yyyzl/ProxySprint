# ProxySprint 引擎与来源设计

## 架构与职责

Flutter 通过私有进程管道调用 desktop_host.py，server.App 负责设置、节点来源和测速任务。
node_sources.SourceStore 获取用户明确导入的 URL / 文件，将可移植节点保存为用户私有 JSON
快照；engine.py 负责只读节点清单、筛选、独立 Mihomo 进程、真实 HTTP 请求与统计。

来源设置包含 type、location、snapshot 和 fetch_providers。默认客户端模式承接旧设置。
snapshot 是随机标识，不能包含路径；清单、报告和进度不包含订阅 URL 或节点密码。
下载 / 解析失败不替换当前来源。更换来源会清空旧组、provider 与手选节点。

## 获取与隔离

用户主动导入或刷新才执行订阅 HTTP 请求，启动应用和测速使用快照。
下载直连进行，发送 Mihomo User-Agent；单次导入最多 20 秒、总共 32 MiB 和 20 个 provider。
重定向限制为 3 次，拒绝 HTTPS 降级与非 HTTP 协议，跨站移除配置提供的认证请求头。
HTTPS 保留主机名与证书校验，并加载随包的 certifi 2026.7.22 Mozilla 公共根证书。
根证书来自固定上游提交，不依赖用户安装 Python，也不导出开发机系统证书。
HTTP provider 的获取由界面列出名称后确认；本地 file provider 只在本地配置模式读取。

快照只保留 proxies、proxy-providers（转为 inline）、proxy-groups、global-client-fingerprint
及 tls。忽略原配置的规则、控制器、TUN、DNS 和脚本。远程内容不能引用本机文件 / 证书。
已有 provider 过滤和 override 继续由 engine.py 解释；不支持的表达式按现有规则警告并跳过。

独立模式使用随包固定官方 Mihomo；开发模式从 work/test-core 获取已校验内核。
客户端模式保留原有生效配置、缓存和控制器核对。测速使用临时 loopback listener，
不切换或修改主客户端。macOS 自动绑定物理接口，测试可明确选择 lo0。

## 发布

Windows、macOS arm64、macOS x86_64 在各自原生 runner 上构建和验证。
v* 标签推送或 GitHub Release 发布后启动构建，全部通过后 prepare_release.py 检查
四个必需程序附件并生成 SHA-256 清单，
再统一上传到 GitHub Release。避免把“Actions 构建成功”误当作“Release 已包含附件”。
Mihomo 使用固定官方摘要，随包保留 GPL-3.0 与对应源码 / 构建文件链接。
macOS 使用系统 hdiutil 创建 HFS+ / UDZO 压缩只读 DMG，在隔离暂存目录中仅放入
ProxySprint.app、指向 /Applications 的快捷方式和说明文档。两种架构分别交付 DMG。
原生 runner 挂载镜像并复制应用到测试安装目录，卸载后核对签名、架构与权限，
再执行真实包内引擎集成，避免只验证构建目录而遗漏安装后的问题。

## 验证与限制

来源回归覆盖失败恢复、缓存、下载确认、重定向、凭据隐藏与大小限制。
打包集成覆盖自带内核的 URL / 文件真实测速及已有客户端路径。
Flutter 窗口测试覆盖宽 / 窄布局、导入交互和左右滚动隔离。

暂只支持 YAML / JSON，订阅需可直连；尚无代码签名 / Apple 公证。
地区按节点名推断，网站可达和 TTFB 不等于账号服务可用或模型生成速度。

## 变更历史

2026-10-15：根据用户对 Mac 安装方式的要求，将 macOS 发行格式改为 DMG。
影响范围为打包、安装验证、Release 附件与说明；测速功能和 Windows 发行方式保持现有行为。
以 v1.1.1 发布打包修正版，保留 v1.1.0 的历史版本记录。

2026-10-18：品牌改为 ProxySprint · 代理节点测速。README 优先展示用途、下载与使用，
开发和打包说明移至 CONTRIBUTING.md。统一窗口标题、报告、程序包、原型文本与仓库链接。
为避免升级后丢失设置，保留 NodeScope 数据目录、Windows AppId 和 macOS Bundle ID。
Windows 安装器替换旧程序及快捷方式；历史版本验证记录保持原名，避免改写已有证据。
界面将 TTFB 标为“响应延迟”，在详情和 README 解释计算口径，统计逻辑不变。
