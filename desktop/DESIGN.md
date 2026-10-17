# ProxySprint 桌面模块设计

## 设计目标

在 Windows / macOS 原生 Flutter 窗口中复用现有测速引擎，保持已确认的 HTML
界面、网站范围选择和真实结果。Windows 默认交付 EXE 安装器，同时保留便携 ZIP；
macOS 交付原生应用 DMG，通过 Applications 快捷方式支持拖放安装。暂不增加托盘和自动换节点。

## 架构

Flutter ProbePage → ProbeController → EngineBridge → desktop_host.py → server.App → node_sources.py / engine.py。
通信为私有进程 stdin/stdout 的 JSON 行，请求携带递增 ID。引擎单独打包，前端无需
Python 开发环境。核心读取和测速仍由原实现完成，避免重写统计与 provider 逻辑。

## 关键决策

- 界面使用真实 Flutter 控件，承接 prototypes/ui 的布局、配色及状态。
- 宽窗口固定顶部入口，左侧设置和右侧结果使用各自的 ScrollController，充满剩余窗口高度。
  左侧内容过长时独立滚动；窄窗口上下排列并整体滚动。排序通过表头触发。
  测试参数与开始 / 停止操作固定于左侧底部，不随筛选项滚动。
- 模态窗口可滚动，以容纳完整路径、网站列表、节点清单和逐轮明细。
- 控制器只调用后端命令；成功结果、推荐和取消语义以引擎返回为准。
- 保存成功才替换网站和连接设置；保存失败保留草稿和上次配置。
- 关闭窗口先停止轮询，再关闭引擎 stdin、等待取消和清理，最后销毁窗口。
- Windows 后端使用 Job Object 管理本应用的子进程，不纳入用户主客户端。
- Windows 使用 Inno Setup 封装已有程序目录，当前用户安装、开始菜单和可选桌面入口。
  安装目录与数据目录分离，卸载只移除已安装程序，不删除用户设置和报告。
  构建工具采用项目内便携模式，不引入全局依赖；固定官方版本和 SHA-256。
- macOS 采用 App Store 之外的发行方式，允许读取用户选择的外部 Clash 配置及启动内核。
- 节点来源明确区分客户端、订阅 URL 和配置文件。导入完成才原子保存来源设置；
  导入失败或远程 provider 尚未确认时保留旧来源、节点和报告。
- 来源变更清空旧策略组、provider 和手选节点，保留网站及其他筛选选项。
- URL / 文件模式使用随包固定 Mihomo，跳过客户端进程和控制器发现。
  刷新入口主动重新导入，初始化和测速读取已保存快照，避免测试中途更换节点。

## 依赖

Flutter 3.47.7；window_manager、file_selector；Python、PyYAML、PyInstaller。
运行包包含固定官方 Mihomo v1.19.32、Python 与 Windows 可再分发运行库，使用系统 curl。
客户端模式继续复用用户现有内核。固定版本摘要和 GPL-3.0 许可证随发行保留。

## 已知限制

macOS 构建需 GitHub macOS runner 或带 Xcode 的 Mac。当前只做 ad-hoc 签名，
尚无 Apple Developer 公证。地区按节点名识别，trace 验证不是模型生成速度。
订阅只支持 Clash/Mihomo YAML / JSON，并通过直连下载，暂不支持 URI / Base64。
Windows 安装器尚无代码签名证书。
正常退出与取消验证不代表断电时一定能移除私有目录中的临时文件。

## 验证

Flutter analyze、controller/widget 测试、已有 Python 回归、
打包后真实 Mihomo 本地 HTTP 集成，以及 Windows 实际窗口运行验证。
Windows 安装包另验证完整资源、开始菜单、覆盖安装、已安装引擎和卸载数据保护。
macOS 另验证 DMG 完整性、只读挂载、复制安装、卸载后的签名与 CPU 架构，
再从测试安装目录运行包内真实测速引擎；每个后台验证进程上限为 60 秒。
新增导入失败恢复、provider 下载确认、URL / 文件无需客户端的真实内核测试，
以及长报告滚动时左侧位置保持不变的窗口测试。
GitHub Actions 分别编译 Windows 与 macOS，分支检查通过后才提交和合并 PR。

## 变更历史

2026-10-14：从已确认 HTML 原型实施原生桌面窗口和进程桥接，保留现有引擎。

2026-10-14：根据用户对安装体验的要求增加 Windows 单文件安装器。
仅调整发行方式和版本，沿用已验收的 Flutter 界面与测速引擎。

2026-10-14：增加独立订阅 / 文件测速、自带固定内核和私有节点快照，降低客户端依赖。
根据用户反馈，宽窗口改为设置与结果独立滚动。增加 Apple Silicon / Intel 两种 macOS
构建，并在 v* 标签构建全部通过后自动发布完整平台附件，修复只上传 Actions 产物的问题。

2026-10-15：按用户要求改为 macOS DMG 发行，分别提供 Apple Silicon 和 Intel 包。
使用系统 hdiutil，无新增全局依赖；保留现有应用 ad-hoc 签名及 Apple 公证限制。

2026-10-18：显示品牌统一为 ProxySprint，增加用途副标题；响应延迟采用中文解释。数据目录与 macOS Bundle ID 保留，Windows 与 macOS 产品文件名同步更新。

Windows 原生入口按 UTF-8 编译，避免含中文标题在不同系统代码页下编译失败。
