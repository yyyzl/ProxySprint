# 开发、测试与打包

ProxySprint 使用 Flutter 桌面界面与 Python 测速引擎。普通用户请直接[下载安装包](https://github.com/yyyzl/ProxySprint/releases/latest)。

## 环境与源码

- Flutter 3.47.7、Python 3.13 或更新版本。
- Windows 构建需要 Visual Studio 的 C++ 桌面开发工具；macOS 构建需要 Xcode。
- `desktop/`：原生桌面界面；`server.py`、`engine.py`、`node_sources.py`：设置、测速与节点来源。
- `scripts/`：构建与发布；`tests/`：引擎与安装验证；`prototypes/ui/`：早期界面原型及历史截图。

```sh
python -m pip install -r requirements.txt pyinstaller
python scripts/download_test_core.py
cd desktop
flutter pub get
```

下载脚本获取固定版本 Mihomo 并核对 SHA-256。Windows 若未开启开发者模式，可运行 `scripts/prepare_windows_links.ps1` 创建项目内插件联接，不改动系统配置。

开发启动参数见 [desktop/README.md](desktop/README.md)。

## 验证

从项目根目录运行：

```sh
python scripts/run_engine_tests.py
cd desktop
flutter analyze --no-pub
flutter test --no-pub --timeout 60s
```

Python 回归按文件执行，每个后台测试进程最多 60 秒。CI 同样为 Flutter、已打包引擎和安装验证设置 60 秒的进程上限。测试使用隔离的本地 HTTP/HTTPS 服务，不提交真实订阅、节点凭据或用户报告。

## 打包与发布

从项目根目录运行：

```sh
python scripts/build_bundle.py
# Windows 另生成安装器：
python scripts/build_installer.py
```

产物位于 `dist/`：Windows EXE 与便携 ZIP，macOS 按当前 CPU 架构生成 DMG。包内包含 Python 引擎、固定 Mihomo、公共根证书和许可文件。

GitHub Actions 在 Windows、Apple Silicon Mac 和 Intel Mac 上分别构建。推送 `v*` 标签后，三个平台全部通过检查才上传四份程序包和 `SHA256SUMS.txt`。macOS 始终交付 DMG。

Windows 安装验证覆盖安装、开始菜单、覆盖升级、已安装引擎与卸载后数据保留。macOS 验证 DMG 挂载、复制安装、卸载镜像后的签名与架构，并从安装副本运行真实引擎。安装测试须在干净环境运行，检测到已有安装时会停止。

## 本地数据

改名后保留稳定的数据目录，使已有用户直接沿用设置、节点快照和报告：

- Windows：`%LOCALAPPDATA%/NodeScope`
- macOS：`~/Library/Application Support/NodeScope`

开发或测试时用 `--data-dir` 指定隔离目录。Windows 安装器 AppId 和 macOS Bundle ID 同样保持稳定。Windows 默认安装目录沿用 `%LOCALAPPDATA%/Programs/NodeScope`，程序和快捷方式显示 ProxySprint。

订阅仅在主动导入或刷新时下载。启动和测速读取本机快照。实现边界见 [DESIGN.md](DESIGN.md)，依赖再分发要求见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
