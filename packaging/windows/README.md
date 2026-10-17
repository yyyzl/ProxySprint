# ProxySprint Windows 安装器

将已验证的 Flutter 程序目录封装为一个可双击安装的 EXE，提供中文向导、
开始菜单、可选桌面快捷方式、覆盖安装和 Windows 卸载入口。

## 使用方法

在项目根目录的 Windows 环境中执行：

    python scripts/build_bundle.py
    python scripts/build_installer.py
    python tests/windows_installer.py

最后一条命令需要 MIHOMO_TEST_BINARY 指向测试内核；CI 自动准备。
输出为 dist/ProxySprint-Setup.exe。版本读取 desktop/pubspec.yaml。
安装器只负责部署现有应用，不改动 Flutter 控件或测速流程。

## 依赖与文件

- ProxySprint.iss：Inno Setup 安装脚本，输入为完整 dist/ProxySprint-Windows-x64。
- ChineseSimplified.isl：取自 jrsoftware/issrc 的 is-6_7_3 标签，保留译者信息。
- 构建器：scripts/build_installer.py 下载固定 Inno Setup 6.7.3 并验证官方摘要，
  放在项目 .tools 中，采用官方便携模式。
- 测试：tests/windows_installer.py 验证文件、入口、更新、真实引擎及卸载。

默认安装到当前用户 LocalAppData/Programs/NodeScope，无需管理员权限。
用户设置和报告仍存于 LocalAppData/NodeScope，卸载保留。
设计权衡见 [DESIGN.md](DESIGN.md)，运行依赖许可见根目录 THIRD_PARTY_NOTICES.md。

对外名称为 ProxySprint；安装身份与内部目录沿用 NodeScope，使已有用户覆盖升级。
