"""打包 Flutter 窗口与原 Python 引擎，发布目录无需安装 Python。"""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from download_test_core import download_core

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--flutter',default='flutter')
args=parser.parse_args()
target='windows' if os.name=='nt' else 'macos'
flutter_binary=shutil.which(args.flutter) or args.flutter
subprocess.run([flutter_binary,'build',target,'--release','--no-pub'],
    cwd=ROOT/'desktop',check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--onedir',
    '--console','--name','probe-engine','--hidden-import','engine',
    '--hidden-import','windows_support','--hidden-import','node_sources','--distpath',str(ROOT/'work/frozen'),
    '--workpath',str(ROOT/'work/pyinstaller'),'desktop_host.py'],
    cwd=ROOT,check=True)
if os.name=='nt':
    output=ROOT/'dist/ProxySprint-Windows-x64'
    # 增量编译可能留有旧品牌 EXE，只交付当前应用的入口。
    shutil.copytree(ROOT/'desktop/build/windows/x64/runner/Release',
        output,dirs_exist_ok=True,
        ignore=lambda directory,names: [name for name in names
            if name.endswith('.exe') and name!='ProxySprint.exe'])
    assert (output/'ProxySprint.exe').is_file(),'未找到 ProxySprint.exe'
    vswhere=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    installation=subprocess.check_output([str(vswhere),'-latest','-products','*',
        '-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
        '-property','installationPath'],text=True).strip()
    crt=list((Path(installation)/'VC/Redist/MSVC').glob('*/x64/Microsoft.VC143.CRT'))
    if not crt:
        raise RuntimeError('未找到可再分发的 Visual C++ Runtime')
    for library in sorted(crt)[-1].glob('*.dll'):
        shutil.copy2(library,output/library.name)
    engine=output/'engine/probe-engine'
else:
    output=ROOT/('dist/ProxySprint-macOS-'+platform.machine())
    output.mkdir(parents=True,exist_ok=True)
    built=ROOT/'desktop/build/macos/Build/Products/Release/ProxySprint.app'
    assert built.is_dir(),'未找到 ProxySprint.app'
    app=output/'ProxySprint.app'
    shutil.copytree(built,app,symlinks=True,dirs_exist_ok=True)
    engine=app/'Contents/Resources/engine/probe-engine'
shutil.copytree(ROOT/'work/frozen/probe-engine',engine,dirs_exist_ok=True)
core=engine/'core'
core.mkdir(exist_ok=True)
shutil.copy2(download_core(),core/('mihomo.exe' if os.name=='nt' else 'mihomo'))
shutil.copy2(ROOT/'third_party/mihomo/LICENSE',core/'LICENSE')
ca_bundle=ROOT/'third_party/certifi/cacert.pem'
if hashlib.sha256(ca_bundle.read_bytes()).hexdigest()!='9cc2a774b5198dcff14d9be1e66091f538975d867ce029a96bce15a55dfd730f':
    raise RuntimeError('固定公共根证书的 SHA-256 校验失败')
shutil.copy2(ca_bundle,core/'cacert.pem')
shutil.copy2(ROOT/'third_party/certifi/LICENSE',core/'CA-LICENSE')
shutil.copy2(ROOT/'packaging/README.md',output/'README.md')
shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.md',output/'THIRD_PARTY_NOTICES.md')
if os.name=='nt':
    archive=output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for entry in sorted(output.rglob('*')):
            if entry.is_file():
                bundle.write(entry,output.name+'/'+entry.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
else:
    subprocess.run(['codesign','--force','--sign','-','--timestamp=none',str(core/'mihomo')],check=True)
    subprocess.run(['codesign','--force','--deep','--sign','-',
        '--entitlements',str(ROOT/'desktop/macos/Runner/Release.entitlements'),
        '--timestamp=none',str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    archive=output.with_suffix('.dmg')
    with tempfile.TemporaryDirectory(prefix='proxysprint-dmg-') as directory:
        staging=Path(directory)
        subprocess.run(['ditto',str(app),str(staging/'ProxySprint.app')],check=True)
        (staging/'Applications').symlink_to('/Applications',target_is_directory=True)
        for name in ('README.md','THIRD_PARTY_NOTICES.md'):
            shutil.copy2(output/name,staging/name)
        subprocess.run(['hdiutil','create','-volname','ProxySprint',
            '-srcfolder',str(staging),'-fs','HFS+','-format','UDZO','-ov',
            str(archive)],check=True)
print('已生成 '+str(archive))
