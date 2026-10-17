# 交付验证记录

日期：2026-10-14。环境：Windows、本地 Python 虚拟环境、真实 Mihomo v1.19.32。此前 UI 验证使用 Chrome 无头浏览器；本次未修改 UI，未重跑浏览器测试。未在 Mac 实机测试，不提供公网 ChatGPT 或其他公网网站排名。

## 本次 provider 优先级修复与回归

仅修改 `engine._inventory` 的 provider 来源选择与运行时成员核对：

- `inline` 使用 payload；`file/http` 优先读取现有本地缓存，包括 HTTP provider 的默认 MD5 缓存路径，不下载订阅。
- 缓存缺失时，仅允许获得运行时成员确认的 fallback payload 节点；无法确认时跳过并提示检查控制器、`core_dir` 或在主客户端更新订阅。
- 本地节点经现有过滤、override 和重命名后，若无法与运行时成员核对则跳过并给出操作提示；已确认的空成员列表也不会纳入节点。
- 保留离线缓存清单、纯 inline 行为、缓存名称适配、override 和 provider 筛选，以及 `catalog` 自动发现的 `require_runtime=False` 语义。保留此前 `udp: False` 修复。

先增加 6 项回归，再修改实现：RED 为 `Ran 6 tests in 1.082s`、`FAILED (failures=12)`（包含子测试）；GREEN 为 `Ran 6 tests in 1.419s`、`OK`。真实核心回归先等待 `/providers/proxies` 确认 `JP live cache` 初始化完成，原实现仍错误选择 `SG fallback only`；修复后清单及临时探针配置均使用缓存 JP 节点及端口 2，夹具配置/缓存内容和核心选择不变。

回归还覆盖 file/http 缓存与 fallback 并存、过滤和 override、inline 忽略缓存、名称不匹配与空成员、缺失缓存的 fallback 确认，以及离线清单读取缓存。证据为 scratch 中的 `provider-regression-red.log` 与 `provider-regression-green.log`。

本次未增加功能或重设计，未提交或推送 Git，未读取用户凭据，未修改用户主核心配置或调用其变更接口。与原发布包比较，代码修改仅涉及 `engine.py`、`tests/test_engine.py`，另更新本验证记录。

## 此前 UDP 修复保留

已捕获的启动日志显示：6 个 mixed listener 的 UDP 绑定均出现 Windows 禁止访问端口错误。端口预留只涉及 TCP，测速也仅需要 HTTP/TCP。

- 先在原有隔离配置测试中断言每个 listener 的 `udp` 均显式为 `False`，执行 1 项测试，实际失败。
- 再仅为 `engine._isolated_config` 的 listener 增加 `udp: False`，同一项测试通过。
- 保留内核配置校验、监听器归属检查、端口冲突重试、失败行和取消检查；没有放宽测试。
- 未重设计界面或新增功能；未提交或推送 Git。仓库本地 `core.autocrlf` 已读取确认为 `false`；启动器源文件已确认为 LF。

回归证据位于下述 scratch 目录的 `udp-regression-red.log` 与 `udp-regression-green.log`。

## 执行命令与结果

在项目根目录执行以下 PowerShell 命令。临时测试文件和浏览器证据放在指定 scratch 目录；未安装额外依赖。

```powershell
$env:MIHOMO_TEST_BINARY = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe/mihomo/mihomo-windows-amd64-compatible.exe'
$env:TEMP = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
.venv/Scripts/python.exe -W error::ResourceWarning -m unittest discover -s tests -v

.venv/Scripts/python.exe tests/integration_real.py --mihomo $env:MIHOMO_TEST_BINARY --scratch $env:TEMP
# 本次 provider 修复后完整执行一次；此前 UDP 修复后连续执行三次。

$env:CSP_PLAYWRIGHT_PATH = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/csp-ui-test-deps/node_modules/playwright'
$env:CSP_SERVER_PYTHON = 'C:/Users/10455/ClashSiteProbe/.venv/Scripts/python.exe'
$env:CSP_UI_EVIDENCE = 'C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe/ui-evidence'
node static/tests.js

& 'F:/Git/bin/bash.exe' -n 启动.command
```

- 本次 Python：35/35 通过，无跳过；记录为 `Ran 35 tests in 16.185s`、`OK`，含新增真实核心 provider 回归及既有纯 inline、自动发现、UDP、取消和端口竞争检查。后台执行使用 `subprocess.run(timeout=60)` 限制最大时长，并启用 `-W error::ResourceWarning`。
- 本次整服务 `tests/integration_real.py`：退出码 0，真实核心版本 v1.19.32，结果见下表。
- 此前浏览器：11/11 通过，包括连接/预览/保存/开始/停止、网站管理、结果和失败行展示、桌面/手机布局，以及真实本地服务的会话、持久化与错误显示。UI 源文件与此前发布包逐字节一致，本次未重跑。
- 此前启动器：`bash -n` 退出码 0，仅证明 Bash 语法通过；本次源文件与此前发布包一致，并重新核对 ZIP 内 LF 与 Unix 0755。

## 真实内核集成

所有计时来自真实 curl → 独立 Mihomo → 本地转发代理 → 本地 HTTP 服务。每次均包含缓存 provider 节点；日本/新加坡默认预览为 3 个节点。

| 次数 | 退出码 | 节点 | 网站 | HTTP 请求 | 结果行 | 取消耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| 此前 UDP 1 | 0 | 6 | 2 | 36 | 12 | 28 ms |
| 此前 UDP 2 | 0 | 6 | 2 | 36 | 12 | 11 ms |
| 此前 UDP 3 | 0 | 6 | 2 | 36 | 12 | 16 ms |
| 本次 provider 修复 | 0 | 6 | 2 | 36 | 12 | 21 ms |

上述各次均断言通过：

- `fixture-ok` 推荐“日本 A”，`fixture-204` 推荐“新加坡 B”，两站分别排名。
- 两个网站各保留一行“香港失败”，成功率均为 0。
- 主内核选择前后不变，缓存 provider 被加载，JSON/CSV 导出通过。
- 停止慢请求后任务结束，并保留上一份完整报告。

原始证据目录：`C:/Users/10455/AppData/Local/hermes/cache/scratch/clashsiteprobe`。本次为 `provider-unit-tests.log`、`provider-integration.log`、`provider-integration-result.json` 和上述 RED/GREEN 日志。此前的 `unit-tests.log`、`ui-tests.log`、三次集成日志/JSON 及 `ui-evidence/` 保留。这些本地证据不作为用户测速报告捆入发布包。

## 发布包检查

`ClashSiteProbe-mac.zip` 根目录为 `ClashSiteProbe/`，文件白名单如下：

```text
engine.py
server.py
README.md
VALIDATION.md
requirements.txt
preview.png
启动.command
static/index.html
static/tests.js
tests/integration_real.py
tests/test_discovery_fix.py
tests/test_engine.py
tests/test_server.py
```

本次按原白名单重建发布包，共 13 个文件，根目录为 `ClashSiteProbe/`。包内不含 `.git`、`.venv`、`__pycache__`、缓存、本地设置、测速报告、真实节点配置、凭据或 ZIP 自身。重新检查 `ZipFile.testzip()`、与原白名单相同的 manifest、逐文件内容比对、Python 源码语法、启动器 LF 换行及 Unix `external_attr` 的 `0755` 执行权限。现有 `preview.png` 为界面截图。检查记录保存于 scratch 的 `provider-zip-verification.json`。

## 验证边界

- Mac 双击启动、原生自动发现、物理网卡绑定和实际 Clash Verge Rev 共存行为仍需 Mac 实机验证；模拟 Mac 发现测试和 Windows 上的 Bash 语法检查不等于原生验收。
- 本地夹具证明当前代码通过真实 Mihomo 的网络路径和任务流程，不证明机场节点、公网网站或 ChatGPT 账号业务可用。
- 本次 provider 回归及整服务验证、此前 UDP 的三次集成通过覆盖了已复现问题；不能保证所有操作系统环境永远没有端口竞争。
# NodeScope 1.1.0 验证补充（2026-10-14）

本版增加 Clash/Mihomo YAML / JSON 的 URL 和文件导入、自带固定官方 Mihomo、远程
provider 获取确认与私有快照。宽窗口的设置和结果独立滚动，测试参数与操作固定于左侧底部。

- Python 53 项回归通过，覆盖来源导入、失败恢复、缓存、跨站认证头剥离和凭据隐藏，
  新增本地 HTTPS 夹具验证不可信证书被拒绝、可信证书可导入及公共根证书加载。
- Flutter analyze 通过；15 项控制器 / 窗口测试通过，覆盖 1280、960、880 像素窗口、
  右侧长报告滚动、左侧筛选独立滚动、固定开始按钮和窄窗口停止操作。
  首次启动没有客户端时显示导入提示，明确填写的连接设置失败时保留错误。
- Windows 完整程序包与安装器构建成功。打包引擎实际使用内核旁的 core/mihomo.exe
  执行 HTTPS URL / 文件测速，验证成功行、失败行、推荐、导出、取消及 EOF 清理。
- 本机存在用户已安装的 NodeScope，安装器烟雾测试按保护规则停止，未覆盖已有安装。
  安装 / 升级 / 卸载检查安排在 GitHub Actions 的干净 Windows runner 上执行。
- GitHub 默认矩阵包含 Windows、macOS arm64、macOS x86_64；v* 标签发布前检查四个
  必需程序附件。补充测试确认缺少任一 macOS 架构时拒绝生成发布清单。
- 跨平台来源测试使用 samefile 校验真实目录，支持 macOS /var 别名和 Windows 短路径。
- Intel runner 的整组回归接近 60 秒，因此使用 scripts/run_engine_tests.py 按文件执行
  全部测试，每个后台进程仍严格限制 60 秒；没有延长上限或删除测试。

订阅 / 节点 / HTTP 网站均为本地隔离测试夹具，不代表公网性能成绩；未获取用户真实订阅。
下文为早期 Python / HTML 版本的历史验证记录。

## NodeScope 1.1.1 DMG 打包验证（2026-10-15）

macOS 发行改为两种架构的压缩只读 DMG，版本为 1.1.1+4。
本地 14 项来源 / 发布回归及打包脚本语法检查通过；发布回归确认旧 Mac ZIP
不能满足 DMG 附件要求。Windows 本机不能执行 hdiutil，原生安装验证由对应 Mac runner 执行。

CI 的 tests/macos_dmg.py 校验映像、只读挂载、Applications 快捷方式、复制安装与推出镜像，
再核对复制后应用的签名、界面 / 引擎 / Mihomo 架构、执行权限、根证书和许可文件。
tests/packaged_engine.py 随后从复制后的应用运行，验证镜像卸载后的 HTTPS 导入、
实际测速、推荐、失败行、导出、取消及 EOF 清理。两个后台验证步骤分别限制为 60 秒。
测试安装目录位于项目 work/dmg-install，不写入 runner 的系统 Applications 目录。


## ProxySprint 1.2.0 品牌与文案验证（2026-10-18）

- 本地 Python 共 53 项回归通过，包含真实 Mihomo 内核测试；每个测试进程上限 60 秒。
- Flutter 15 项测试与静态分析通过，包含 960 / 1280 宽窗口的左右独立滚动检查。
- Windows 实际生成 ProxySprint-Setup.exe 和 ProxySprint-Windows-x64.zip。
- 已打包引擎通过 URL / 文件导入、HTTPS 订阅、真实本地请求、各网站独立推荐、导出、取消和退出清理验证。
- 使用隔离的演示数据实际打开 Windows 新应用，检查中文标题、品牌、副标题和结果布局。README 截图来自该窗口，已标注示例数据。
- 稳定保留 NodeScope 数据目录、Windows AppId 与 macOS Bundle ID；历史验证记录保留原产品名称。
- 本地已有用户安装，安装器升级与卸载检查在干净 CI 中执行；新增固定 SHA-256 的 v1.1.1 真实旧版覆盖升级检查。
- macOS 的两种 DMG 仍由原生 CI 验证挂载、复制、签名、架构与安装后的引擎，本机 Windows 不模拟这些结果。
