"""在已打包的引擎进程中验证真实 Mihomo 请求、导出、取消和 EOF 清理。"""
import base64
import json
import os
from pathlib import Path
import queue
import ssl
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from integration_real import TargetHandler, ForwardHandler, launch_http
from tls_fixture import certificate


def bundle_engine():
    if os.environ.get('PROXYSPRINT_ENGINE_BINARY'):
        return Path(os.environ['PROXYSPRINT_ENGINE_BINARY'])
    if os.name=='nt':
        return ROOT/'dist/ProxySprint-Windows-x64/engine/probe-engine/probe-engine.exe'
    binaries=list((ROOT/'dist').glob(
        'ProxySprint-macOS-*/ProxySprint.app/Contents/Resources/engine/probe-engine/probe-engine'))
    assert len(binaries)==1
    return binaries[0]


def run():
    binary=Path(os.environ['MIHOMO_TEST_BINARY'])
    fixtures=[]
    process=None
    with tempfile.TemporaryDirectory(prefix='proxysprint-packaged-') as directory:
        folder=Path(directory)
        try:
            if os.environ.get('PROXYSPRINT_TEST_CERT') and os.environ.get('PROXYSPRINT_TEST_KEY'):
                cert, key = (Path(os.environ[name]) for name in ('PROXYSPRINT_TEST_CERT', 'PROXYSPRINT_TEST_KEY'))
            else:
                cert, key = certificate(folder)
            class ObservedTarget(TargetHandler):
                def do_GET(self):
                    if self.path == '/subscription?token=PRIVATE_SUBSCRIPTION_TOKEN':
                        content = json.dumps({'proxies': nodes}).encode('utf-8')
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    if self.path=='/slow': self.server.slow_started.set()
                    super().do_GET()
            target=launch_http(ObservedTarget)
            target.slow_started=threading.Event()
            fixtures.append(target)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(str(cert), str(key))
            secure_subscription = launch_http(ObservedTarget)
            secure_subscription.socket = tls.wrap_socket(secure_subscription.socket, server_side=True)
            fixtures.append(secure_subscription)
            nodes=[]
            specs=[('日本 local',{'/ok':.015,'/second':.30},False),
                   ('新加坡 local',{'/ok':.30,'/second':.015},False),
                   ('香港 failure',{},True)]
            for name,delays,fail in specs:
                proxy=launch_http(ForwardHandler)
                proxy.target_port=target.server_port
                proxy.delays=delays
                proxy.fail=fail
                fixtures.append(proxy)
                nodes.append({'name':name,'type':'http','server':'127.0.0.1',
                              'port':proxy.server_port})
            config=folder/'main.json'
            config.write_text(json.dumps({'proxies':nodes}),encoding='utf-8')
            process=subprocess.Popen([str(bundle_engine()),'--data-dir',str(folder/'data')],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                text=True,encoding='utf-8',env=dict(os.environ, SSL_CERT_FILE=str(cert)))
            output=queue.Queue()
            reader=threading.Thread(target=lambda: [
                output.put(json.loads(line)) for line in process.stdout],daemon=True)
            reader.start()
            sequence=0
            def call(command,payload=None):
                nonlocal sequence
                sequence+=1
                process.stdin.write(json.dumps({'id':sequence,'command':command,
                    'payload':payload or {}})+'\n')
                process.stdin.flush()
                answer=output.get(timeout=20)
                assert answer['id']==sequence
                assert 'error' not in answer,answer.get('error')
                return answer['result']
            bootstrap=call('bootstrap')
            assert bootstrap['options']['regions']==['jp','sg']
            connection={'binary_path':str(binary),'config_path':str(config),
                'core_dir':str(folder),'controller':'','unix_socket':'',
                'named_pipe':'','interface':'lo0' if sys.platform=='darwin' else ''}
            sites=[{'id':'ok','name':'本地200','url':f'http://127.0.0.1:{target.server_port}/ok',
                    'statuses':[200],'validator':'none'},
                   {'id':'second','name':'本地204','url':f'http://127.0.0.1:{target.server_port}/second',
                    'statuses':[204],'validator':'none'}]
            options=dict(bootstrap['options'],regions=[],rounds=2,workers=3,timeout=2)
            call('settings',{'sites':sites,'options':options,'connection':connection})
            assert len(call('catalog')['nodes'])==3
            assert call('preview')['count']==3
            call('start',{'site_ids':['ok','second']})
            deadline=time.monotonic()+30
            while True:
                job=call('job')
                if not job['running']: break
                assert time.monotonic()<deadline
                time.sleep(.1)
            report=job['report']
            assert report and len(report['rows'])==6
            assert len([r for r in report['rows'] if not r['eligible']])==2
            names={r['site_id']:r['name'] for r in report['recommendations']}
            assert names=={'ok':'日本 local','second':'新加坡 local'},names
            csv=base64.b64decode(call('export',{'format':'csv'})['content'])
            assert '香港 failure' in csv.decode('utf-8-sig')
            previous=base64.b64decode(call('export',{'format':'json'})['content'])
            standalone_connection = {'interface': 'lo0' if sys.platform == 'darwin' else ''}
            for source in ({'type': 'url', 'location': f'https://127.0.0.1:{secure_subscription.server_port}/subscription?token=PRIVATE_SUBSCRIPTION_TOKEN'},
                           {'type': 'file', 'location': str(config)}):
                imported = call('import_source', {'source': source, 'connection': standalone_connection})
                catalog = imported['catalog']
                assert len(catalog['nodes']) == 3
                assert '/core/' in catalog['connection']['binary_path'].replace('\\', '/')
                assert (Path(catalog['connection']['binary_path']).parent / 'cacert.pem').is_file()
                assert 'PRIVATE_SUBSCRIPTION_TOKEN' not in json.dumps(catalog)
                call('settings', {'options': dict(options, rounds=1), 'connection': standalone_connection})
                call('start', {'site_ids': ['ok']})
                deadline = time.monotonic() + 15
                while call('job')['running']:
                    assert time.monotonic() < deadline
                    time.sleep(.1)
                standalone_report = call('job')['report']
                assert standalone_report and len(standalone_report['rows']) == 3
                assert len([row for row in standalone_report['rows'] if row['eligible']]) == 2
                assert 'PRIVATE_SUBSCRIPTION_TOKEN' not in json.dumps(standalone_report)
                previous = base64.b64decode(call('export', {'format': 'json'})['content'])
            slow=[{'id':'slow','name':'慢请求','url':f'http://127.0.0.1:{target.server_port}/slow',
                   'statuses':[200],'validator':'none'}]
            call('settings',{'sites':slow,'options':dict(options,timeout=8),
                             'connection':connection})
            call('start',{'site_ids':['slow']})
            call('stop')
            deadline=time.monotonic()+10
            while call('job')['running']:
                assert time.monotonic()<deadline
                time.sleep(.05)
            assert base64.b64decode(call('export',{'format':'json'})['content'])==previous
            target.slow_started.clear()
            call('start',{'site_ids':['slow']})
            assert target.slow_started.wait(timeout=10),'慢请求尚未进入实际网络路径'
            process.stdin.close()
            process.wait(timeout=12)
            assert process.returncode==0
            assert not list((folder/'data/temp').glob('clash-site-probe-*'))
            print(json.dumps({'frozen_engine':True,'rows':6,'requests':12,
                'distinct_recommendations':True,'failed_rows':2,
                'export':True,'cancel_preserves_report':True,'eof_cleanup':True,
                'standalone_url_and_file':True,'bundled_core':True,'https_subscription':True}))
        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            if process:
                if not process.stdin.closed: process.stdin.close()
                process.stdout.close()
                reader.join(timeout=2)
            for fixture in fixtures:
                fixture.shutdown()
                fixture.server_close()


if __name__=='__main__':
    run()
