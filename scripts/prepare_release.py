"""全部平台通过后才准备 Release，避免只发布某一个系统的附件。"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ASSETS = ('ProxySprint-Setup.exe', 'ProxySprint-Windows-x64.zip',
                   'ProxySprint-macOS-arm64.dmg', 'ProxySprint-macOS-x86_64.dmg')


def prepare(folder):
    missing = [name for name in REQUIRED_ASSETS if not (folder / name).is_file()]
    if missing:
        raise RuntimeError('Release 缺少必需的平台附件：' + '、'.join(missing))
    lines = []
    for name in REQUIRED_ASSETS:
        digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        lines.append(digest + '  ' + name)
    (folder / 'SHA256SUMS.txt').write_text(chr(10).join(lines) + chr(10), encoding='utf-8')


if __name__ == '__main__':
    prepare(ROOT / 'work/release')
    (ROOT / 'work/release-notes.md').write_text(chr(10).join([
        '**ProxySprint · 代理节点测速**', '',
        '导入订阅，找出访问常用网站更快、更稳的节点。支持 Windows 和 macOS。', '',
        'ProxySprint 是 NodeScope 的新名称，已有设置和报告继续使用。', '',
        '- Windows：下载安装器，或解压完整便携 ZIP。',
        '- Apple Silicon Mac：下载 ProxySprint-macOS-arm64.dmg。',
        '- Intel Mac：下载 ProxySprint-macOS-x86_64.dmg。',
        '- Mac 安装：打开 DMG，将 ProxySprint 拖到 Applications，再从应用程序中打开。',
        '- 旧版升级：Windows 可直接覆盖安装；Mac 请打开新安装的 ProxySprint。',
        '- 随包提供独立 Mihomo，可直接导入 Clash/Mihomo 订阅链接或配置文件测速。',
        '- SHA256SUMS.txt 提供全部程序包的摘要。', '',
        'macOS 当前为 ad-hoc 签名，尚未做 Apple Developer 公证。', '',
        '随包 Mihomo v1.19.32 未修改，按 GPL-3.0 分发。其对应源代码可免费下载：'
        '[完整源码及构建文件](https://github.com/MetaCubeX/mihomo/archive/refs/tags/v1.19.32.tar.gz)，'
        '[上游构建说明](https://github.com/MetaCubeX/mihomo/tree/v1.19.32)。',
    ]) + chr(10), encoding='utf-8')
