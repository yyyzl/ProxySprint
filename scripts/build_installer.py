"""用项目内的便携 Inno Setup 编译 Windows 单文件安装包。"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
INNO_VERSION = '6.7.3'
INNO_SHA256 = '9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732'
INNO_URL = (f'https://github.com/jrsoftware/issrc/releases/download/'
            f'is-{INNO_VERSION.replace(".", "_")}/innosetup-{INNO_VERSION}.exe')


def compiler():
    tools = ROOT / '.tools' / f'inno-{INNO_VERSION}'
    tools.mkdir(parents=True, exist_ok=True)
    download = tools / 'compiler-setup.exe'
    if not download.exists():
        with urllib.request.urlopen(INNO_URL, timeout=60) as source:
            download.write_bytes(source.read())
    if hashlib.sha256(download.read_bytes()).hexdigest() != INNO_SHA256:
        raise RuntimeError('Inno Setup 官方文件的 SHA-256 校验失败')
    install = tools / 'portable'
    executable = install / 'ISCC.exe'
    if not executable.exists():
        # 官方便携模式不创建卸载注册项、文件关联或系统 PATH。
        subprocess.run([str(download), '/PORTABLE=1', '/CURRENTUSER',
                        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                        '/NOICONS', '/TASKS=', f'/DIR={install}'],
                       check=True, timeout=60)
    if not executable.is_file():
        raise RuntimeError('没有找到 Inno Setup 编译器')
    return executable


def main():
    if os.name != 'nt':
        raise RuntimeError('Windows 安装器必须在 Windows 上编译')
    payload = ROOT / 'dist' / 'ProxySprint-Windows-x64'
    if not (payload / 'ProxySprint.exe').is_file():
        raise RuntimeError('请先运行 scripts/build_bundle.py 生成 Windows 程序目录')
    version = re.search(r'^version:\s*(\d+\.\d+\.\d+)\+(\d+)',
                        (ROOT / 'desktop/pubspec.yaml').read_text('utf-8'), re.M)
    if not version:
        raise RuntimeError('Flutter 版本必须使用 x.y.z+build 格式')
    subprocess.run([str(compiler()), f'/DAppVersion={version[1]}',
                    f'/DAppBuild={version[2]}', f'/DPayloadDir={payload}',
                    f'/DOutputDir={ROOT / "dist"}',
                    str(ROOT / 'packaging/windows/ProxySprint.iss')], check=True)
    print(f'已生成 {ROOT / "dist/ProxySprint-Setup.exe"}')


if __name__ == '__main__':
    main()
