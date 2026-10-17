"""在原生 Mac 上挂载 DMG、复制应用并验证签名与可执行文件。"""
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    if sys.platform != 'darwin':
        raise RuntimeError('DMG 挂载与安装验证需要 macOS。')
    architecture = platform.machine()
    image = ROOT / f'dist/ProxySprint-macOS-{architecture}.dmg'
    if not image.is_file():
        raise RuntimeError('缺少当前架构的 DMG。')
    installed = ROOT / 'work/dmg-install/Applications/ProxySprint.app'
    installed.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['hdiutil', 'verify', str(image)], check=True, timeout=20)
    with tempfile.TemporaryDirectory(prefix='proxysprint-dmg-mount-') as directory:
        mount = Path(directory) / 'mounted'
        mount.mkdir()
        attached = False
        try:
            subprocess.run(['hdiutil', 'attach', '-readonly', '-nobrowse', '-noautoopen',
                            '-mountpoint', str(mount), str(image)], check=True, timeout=20)
            attached = True
            visible = {entry.name for entry in mount.iterdir() if not entry.name.startswith('.')}
            assert visible == {'ProxySprint.app', 'Applications', 'README.md', 'THIRD_PARTY_NOTICES.md'}, visible
            shortcut = mount / 'Applications'
            assert shortcut.is_symlink() and os.readlink(shortcut) == '/Applications'
            subprocess.run(['ditto', str(mount / 'ProxySprint.app'), str(installed)],
                           check=True, timeout=20)
        finally:
            if attached:
                subprocess.run(['hdiutil', 'detach', str(mount)], check=True, timeout=15)
    # 镜像卸载后再验证，确保复制后的应用不依赖挂载路径。
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(installed)],
                   check=True, timeout=15)
    with (installed / 'Contents/Info.plist').open('rb') as stream:
        executable = plistlib.load(stream)['CFBundleExecutable']
    engine = installed / 'Contents/Resources/engine/probe-engine'
    binaries = [installed / 'Contents/MacOS' / executable,
                engine / 'probe-engine', engine / 'core/mihomo']
    for binary in binaries:
        assert binary.is_file() and os.access(binary, os.X_OK), binary
        subprocess.run(['lipo', str(binary), '-verify_arch', architecture],
                       check=True, timeout=10)
    for name in ('LICENSE', 'CA-LICENSE', 'cacert.pem'):
        assert (engine / 'core' / name).is_file(), name
    print(f'DMG 校验、只读挂载、应用复制、卸载后签名和 {architecture} 架构验证通过。')


if __name__ == '__main__':
    run()
