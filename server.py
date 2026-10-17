"""ProxySprint 本地网页入口：仅监听回环地址，不修改主客户端。"""
from __future__ import annotations
import argparse
import copy
import csv
import io
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import datetime
import signal
import webbrowser
from urllib.parse import parse_qs, urlsplit
from node_sources import DEFAULT_SOURCE, SourceStore, normalize_source

VERSION = '1.2.0'
ROOT = Path(__file__).resolve().parent
CONNECTION_KEYS = ('config_path', 'binary_path', 'core_dir', 'controller', 'unix_socket', 'interface', 'named_pipe')

class JobConflict(RuntimeError):
    pass

class App:
    def __init__(self, data_dir, engine_module=None):
        self.engine = engine_module or importlib.import_module('engine')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sources = SourceStore(self.data_dir)
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.settings = {'sites': copy.deepcopy(self.engine.DEFAULT_SITES),
                         'options': copy.deepcopy(self.engine.DEFAULT_OPTIONS),
                         'connection': {k: '' for k in CONNECTION_KEYS}, 'source': dict(DEFAULT_SOURCE)}
        self.last_report = None
        self.job = {'id': None, 'running': False, 'events': [], 'report': None,
                    'error': None, 'progress': {'completed': 0, 'total': 0}}
        self.stop = threading.Event()
        self.worker = None
        self.settings_warnings = []
        saved = self.data_dir / 'settings.json'
        if saved.exists():
            try:
                self.settings = self.normalize_settings(json.loads(saved.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError, RuntimeError):
                self.settings_warnings.append('已保存的设置无法读取，本次使用默认值；原文件尚未覆盖。')
        latest = self.data_dir / 'latest.json'
        if latest.exists():
            try:
                if latest.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError('报告过大')
                report = json.loads(latest.read_text(encoding='utf-8'))
                if not isinstance(report, dict) or not isinstance(report.get('rows'), list):
                    raise ValueError('报告格式无效')
                self.last_report = report
            except (OSError, ValueError):
                self.settings_warnings.append('上次报告无法读取，尚未删除原文件。')

    def normalize_connection(self, connection):
        if not isinstance(connection, dict) or set(connection) - set(CONNECTION_KEYS):
            raise ValueError('连接设置包含未知字段。')
        result = {}
        for key in CONNECTION_KEYS:
            value = connection.get(key, '')
            if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
                raise ValueError('连接设置必须是有效路径或地址。')
            result[key] = value.strip()
        return result

    def normalize_settings(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('设置格式无效。')
        sites = payload.get('sites', self.settings['sites'])
        if not isinstance(sites, list) or not 1 <= len(sites) <= 20:
            raise ValueError('请保存 1～20 个网站配置。')
        sites = [self.engine.validate_site(site) for site in sites]
        if len({site['id'] for site in sites}) != len(sites):
            raise ValueError('网站标识不能重复。')
        options = self.engine.validate_options(payload.get('options', self.settings['options']))
        connection = self.normalize_connection(payload.get('connection', self.settings['connection']))
        source = normalize_source(payload.get('source', self.settings['source']))
        return {'sites': sites, 'options': options, 'connection': connection, 'source': source}

    def write_json(self, path, value):
        temporary = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def save_settings(self, payload):
        with self.lock:
            if self.job['running']:
                raise JobConflict('测速过程中不能修改设置，请先等待或停止。')
            normalized = self.normalize_settings(payload)
            self.write_json(self.data_dir / 'settings.json', normalized)
            self.settings = normalized
            return copy.deepcopy(normalized)

    def source_connection(self, payload):
        connection = self.normalize_connection(payload.get('connection', self.settings['connection']))
        source = normalize_source(payload.get('source', self.settings['source']))
        return self.sources.connection(source, connection)

    def catalog(self, payload):
        return self.engine.catalog(self.source_connection(payload))

    def import_source(self, payload):
        with self.lock:
            if self.job['running']:
                raise JobConflict('测速过程中不能更新节点来源，请先等待或停止。')
            source, config, providers = self.sources.prepare(payload.get('source', self.settings['source']))
            if providers:
                return {'requires_provider_download': True, 'providers': providers}
            self.write_json(self.sources.snapshot_path(source), config)
            connection = self.normalize_connection(payload.get('connection', self.settings['connection']))
            catalog = self.engine.catalog(self.sources.connection(source, connection))
            if not catalog['nodes']:
                raise ValueError('配置没有可测试节点，请检查节点类型及来源筛选。')
            changed = (source['type'], source['location']) != (self.settings['source']['type'], self.settings['source']['location'])
            options = dict(self.settings['options'])
            if changed:
                options.update(group='', provider='', node_names=[])
            saved = self.save_settings({'source': source, 'connection': connection, 'options': options})
            return {'settings': saved, 'catalog': catalog}

    def job_state(self):
        with self.lock:
            return copy.deepcopy(self.job)

    def emit(self, kind, **data):
        with self.lock:
            self.job['events'].append(dict(data, event=kind, seq=len(self.job['events']) + 1))
            if kind == 'start':
                self.job['progress'] = {'completed': 0, 'total': data.get('total', 0)}
            elif kind == 'row':
                self.job['progress'] = {'completed': data.get('completed', 0), 'total': data.get('total', 0)}

    def start_job(self, payload):
        with self.lock:
            if self.job['running']:
                raise JobConflict('已有测速任务在运行，请先等待或停止。')
            options = self.engine.validate_options(payload.get('options', self.settings['options']))
            connection = self.source_connection(payload)
            ids = payload.get('site_ids', [])
            if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or any(not isinstance(i, str) for i in ids):
                raise ValueError('请一次选择 1～10 个网站。')
            known = {site['id']: site for site in self.settings['sites']}
            if len(set(ids)) != len(ids) or any(i not in known for i in ids):
                raise ValueError('选中的网站不存在或重复，请先保存网站设置。')
            sites = [copy.deepcopy(known[i]) for i in ids]
            self.stop = threading.Event()
            job_id = secrets.token_hex(8)
            self.job = {'id': job_id, 'running': True, 'events': [], 'report': None,
                        'error': None, 'progress': {'completed': 0, 'total': 0}}
            self.worker = threading.Thread(target=self.run_job, args=(connection, sites, options, self.stop), daemon=True)
            self.worker.start()
            return {'id': job_id, 'running': True}

    def run_job(self, connection, sites, options, stop):
        try:
            report = self.engine.benchmark(connection, sites, options, self.emit, stop)
            if stop.is_set():
                raise RuntimeError('测速已停止；没有覆盖上次完整报告。')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            reports = self.data_dir / 'reports'
            reports.mkdir(exist_ok=True)
            self.write_json(reports / f'{stamp}-{self.job["id"]}.json', report)
            self.write_json(self.data_dir / 'latest.json', report)
            with self.lock:
                self.last_report = report
                self.job['report'] = report
                self.emit('done', report=report)
        except Exception as error:
            message = str(error) if isinstance(error, (RuntimeError, ValueError)) else '测速运行失败，请检查本地配置、内核和网络。'
            with self.lock:
                self.job['error'] = message
                self.emit('error', text=message)
        finally:
            with self.lock:
                self.job['running'] = False

    def bootstrap(self):
        with self.lock:
            return copy.deepcopy(dict(self.settings, csrf=self.csrf, regions=self.engine.REGIONS,
                                      last_report=self.last_report, version=VERSION, warnings=self.settings_warnings))

    def csv_report(self, selected_report=None):
        with self.lock:
            report = copy.deepcopy(selected_report if selected_report is not None else self.last_report)
        if report is None:
            raise ValueError('尚无完整测速报告。')
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['节点', '地区', '来源', '网站', 'URL', '成功率', '成功次数', '轮数', '首字节中位数(ms)', '波动(ms)', '失败原因'])
        def safe(value):
            text = '' if value is None else str(value)
            if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
                text = "'" + text
            return text
        for row in report.get('rows', []):
            failures = '；'.join(dict.fromkeys(str(x.get('reason', '')) for x in row.get('samples', []) if not x.get('ok') and x.get('reason')))
            writer.writerow([safe(row.get(k)) for k in ('name', 'region', 'provider', 'site_name', 'url', 'success_rate', 'successes', 'total', 'median_ms', 'jitter_ms')] + [safe(failures)])
        return stream.getvalue().encode('utf-8-sig')

class Handler(BaseHTTPRequestHandler):
    server_version = 'NodeProbe/' + VERSION

    def log_message(self, *args):
        pass  # Do not log paths containing a one-time launch capability.

    def send_body(self, status, body, content_type='application/json; charset=utf-8', extra=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        for key, value in {'Content-Type': content_type, 'Content-Length': str(len(body)),
                           'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                           'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY',
                           'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
            self.send_header(key, value)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorized(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            item = cookies.get('nodeprobe_session')
            return bool(item and hmac.compare_digest(item.value, self.server.app.session))
        except (ValueError, TypeError):
            return False

    def host_valid(self):
        return self.headers.get('Host', '') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.host_valid():
            return self.send_body(403, {'error': '无效的本地访问地址。'})
        parsed = urlsplit(self.path)
        launch = parse_qs(parsed.query).get('launch', [''])[0]
        if parsed.path == '/' and launch and hmac.compare_digest(launch.encode('utf-8'), self.server.app.session.encode('ascii')):
            return self.send_body(303, b'', extra={'Location': '/', 'Set-Cookie': 'nodeprobe_session=' + self.server.app.session + '; HttpOnly; SameSite=Strict; Path=/'})
        if not self.authorized():
            return self.send_body(403, {'error': '请通过启动脚本打开工具，当前会话无效。'})
        if parsed.path in ('/api/export.json', '/api/export.csv'):
            with self.server.app.lock:
                report = copy.deepcopy(self.server.app.last_report)
            if report is None:
                return self.send_body(404, {'error': '尚无完整测速报告。'})
            if parsed.path.endswith('.csv'):
                return self.send_body(200, self.server.app.csv_report(), 'text/csv; charset=utf-8', {'Content-Disposition': 'attachment; filename="node-probe-results.csv"'})
            return self.send_body(200, report, extra={'Content-Disposition': 'attachment; filename="node-probe-results.json"'})
        if parsed.path == '/api/job':
            return self.send_body(200, self.server.app.job_state())
        if parsed.path == '/api/bootstrap':
            return self.send_body(200, self.server.app.bootstrap())
        if parsed.path == '/':
            try:
                return self.send_body(200, (ROOT / 'static' / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            except OSError:
                return self.send_body(503, {'error': '页面文件缺失，请重新解压完整工具包。'})
        return self.send_body(404, {'error': '未找到接口。'})

    def do_POST(self):
        expected_origin = f'http://{self.headers.get("Host", "")}'
        if (not self.host_valid() or not self.authorized()
                or not hmac.compare_digest(self.headers.get('X-CSRF-Token', '').encode('utf-8'), self.server.app.csrf.encode('ascii'))
                or self.headers.get('Origin', expected_origin) != expected_origin):
            return self.send_body(403, {'error': '本地会话或请求校验失败，请重新打开工具。'})
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('请求必须使用 JSON 格式。')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 262144:
                raise ValueError('请求内容为空或过大。')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('请求内容必须是对象。')
            path = urlsplit(self.path).path
            if path in ('/api/catalog', '/api/preview'):
                app = self.server.app
                catalog = app.catalog(payload)
                if path == '/api/catalog':
                    return self.send_body(200, catalog)
                options = app.engine.validate_options(payload.get('options', app.settings['options']))
                nodes = app.engine.filter_nodes(catalog, options)
                return self.send_body(200, {'nodes': nodes, 'total': len(nodes), 'catalog': catalog, 'warnings': catalog.get('warnings', [])})
            if path == '/api/start':
                return self.send_body(200, self.server.app.start_job(payload))
            if path == '/api/stop':
                self.server.app.stop.set()
                return self.send_body(200, {'stopping': True})
            if path == '/api/settings':
                return self.send_body(200, self.server.app.save_settings(payload))
            return self.send_body(404, {'error': '未找到接口。'})
        except JobConflict as error:
            return self.send_body(409, {'error': str(error)})
        except RuntimeError as error:
            return self.send_body(400, {'error': str(error)})
        except (ValueError, TypeError) as error:
            return self.send_body(400, {'error': str(error)})
        except OSError:
            return self.send_body(500, {'error': '无法读取或写入本地文件，请检查权限。'})

def default_data_dir():
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'ClashSiteProbe'
    return Path.home() / '.clash-site-probe'

def make_server(port=0, data_dir=None, engine_module=None):
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    httpd.app = App(data_dir or default_data_dir(), engine_module)
    httpd.url = f'http://127.0.0.1:{httpd.server_port}/?launch={httpd.app.session}'
    httpd.daemon_threads = True
    return httpd


def main(argv=None):
    parser = argparse.ArgumentParser(description='ProxySprint · 代理节点测速：本地多站点、分区域 Clash/Mihomo 测速工具')
    parser.add_argument('--port', type=int, default=0, help='本地网页端口，0 表示自动分配')
    parser.add_argument('--data-dir', type=Path, default=default_data_dir(), help='设置和测速报告保存目录')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('端口必须在 0～65535 之间。')
    httpd = None
    try:
        httpd = make_server(args.port, args.data_dir)
        if args.ready_file:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            httpd.app.write_json(args.ready_file, {'url': httpd.url, 'pid': os.getpid(), 'port': httpd.server_port})
        print('ProxySprint · 代理节点测速已启动：' + httpd.url, flush=True)
        print('仅本机访问；不修改当前 Clash 线路。按 Control+C 退出。', flush=True)
        if not args.no_browser:
            webbrowser.open(httpd.url)
        def interrupt(*_):
            httpd.app.stop.set()
            raise KeyboardInterrupt
        signal.signal(signal.SIGINT, interrupt)
        signal.signal(signal.SIGTERM, interrupt)
        httpd.serve_forever(poll_interval=0.2)
        return 0
    except KeyboardInterrupt:
        print('\n已停止本地服务。', flush=True)
        return 0
    except ModuleNotFoundError:
        print('缺少运行依赖，请执行 python3 -m pip install -r requirements.txt，或使用启动.command。', file=sys.stderr)
        return 1
    except OSError:
        print('无法启动本地服务，请检查端口及数据目录权限。', file=sys.stderr)
        return 1
    finally:
        if httpd is not None:
            httpd.app.stop.set()
            if httpd.app.worker is not None:
                httpd.app.worker.join(timeout=40)
            httpd.server_close()
        if args.ready_file:
            args.ready_file.unlink(missing_ok=True)

if __name__ == '__main__':
    raise SystemExit(main())
