"""下载固定官方 Mihomo 并校验摘要，供真实测试和独立测速发行包使用。"""
import gzip
import hashlib
import os
from pathlib import Path
import platform
import urllib.request
import zipfile

VERSION='v1.19.32'
ASSETS={
    'windows':('mihomo-windows-amd64-compatible-v1.19.32.zip',
       '974a4d7ad69aed27aa2e8f91d61113573c14dadb14562c63e58effabf59816f0'),
    'darwin-arm64':('mihomo-darwin-arm64-v1.19.32.gz',
       '3312a6780652c622890fd4357c6a853bbf865464fd047ac7b7f52dab8de18652'),
    'darwin-amd64':('mihomo-darwin-amd64-compatible-v1.19.32.gz',
       '18b382df77bded2ad0fb3db27db5636cb15b20729d5ba995a357eeb9b46bf507'),
}
def download_core():
    root=Path(__file__).resolve().parents[1]
    folder=root/'work/test-core'
    folder.mkdir(parents=True,exist_ok=True)
    key='windows' if os.name=='nt' else (
        'darwin-arm64' if platform.machine()=='arm64' else 'darwin-amd64')
    asset,digest=ASSETS[key]
    archive=folder/asset
    if not archive.exists():
        request=urllib.request.Request(
            'https://github.com/MetaCubeX/mihomo/releases/download/'+VERSION+'/'+asset,
            headers={'User-Agent':'ProxySprint-build'})
        with urllib.request.urlopen(request,timeout=60) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:
        raise RuntimeError('内核摘要不匹配，请重新获取固定官方资产')
    binary=folder/('mihomo.exe' if os.name=='nt' else 'mihomo')
    if asset.endswith('.zip'):
        with zipfile.ZipFile(archive) as bundle:
            names=[name for name in bundle.namelist() if name.endswith('.exe')]
            if len(names)!=1:
                raise RuntimeError('官方内核包内容异常')
            binary.write_bytes(bundle.read(names[0]))
    else:
        binary.write_bytes(gzip.decompress(archive.read_bytes()))
    if os.name!='nt': binary.chmod(0o755)
    return binary
if __name__=='__main__':
    binary=download_core()
    github_env=os.environ.get('GITHUB_ENV')
    if github_env:
        with open(github_env,'a',encoding='utf-8') as stream:
            stream.write('MIHOMO_TEST_BINARY='+str(binary)+chr(10))
    print('已校验官方 Mihomo '+VERSION+'（独立测速及真实测试共用）')
