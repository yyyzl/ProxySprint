"""节点来源导入、凭据边界、缓存与 Release 附件完整性回归。"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import ssl
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import desktop_host
import engine
import node_sources
from server import App
from scripts.prepare_release import REQUIRED_ASSETS, prepare
from tls_fixture import certificate

NODE = {'name': '日本 fixture', 'type': 'http', 'server': '127.0.0.1', 'port': 1234,
        'password': 'PRIVATE_NODE_PASSWORD'}


@contextmanager
def subscription_server(routes, tls=None):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append((self.path, self.headers.get('Authorization')))
            status, content, headers = routes.get(self.path, (404, b'', {}))
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(content)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    if tls:
        server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        yield f'{"https" if tls else "http"}://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def encoded(value):
    return json.dumps(value).encode('utf-8')


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.core = patch.object(engine, 'bundled_core', return_value=sys.executable)
        self.interface = patch.object(engine, 'physical_interface', return_value='')
        self.core.start()
        self.interface.start()
        self.app = App(self.folder / 'data')

    def tearDown(self):
        self.core.stop()
        self.interface.stop()
        self.directory.cleanup()

    def test_url_import_is_standalone_and_bootstrap_reuses_private_snapshot(self):
        config = {'proxies': [NODE], 'tun': {'enable': True}, 'external-controller': '0.0.0.0:9090',
                  'secret': 'PRIVATE_CONTROLLER_SECRET', 'rules': ['MATCH,DIRECT']}
        with subscription_server({'/sub?token=PRIVATE_TOKEN': (200, encoded(config), {})}) as (url, calls), \
                patch.object(engine, 'discover_windows', side_effect=AssertionError('不应查找客户端')):
            result = self.app.import_source({'source': {'type': 'url', 'location': url + '/sub?token=PRIVATE_TOKEN'}})
            self.assertEqual(len(result['catalog']['nodes']), 1)
            self.assertEqual(result['catalog']['version'], '独立 Mihomo')
            public = json.dumps(result['catalog'])
            self.assertNotIn('PRIVATE_', public)
            snapshot = node_sources.parse_config(self.app.sources.snapshot_path(self.app.settings['source']).read_bytes())
            self.assertEqual(set(snapshot), {'proxies'})
            restored = App(self.app.data_dir)
            self.assertEqual(len(desktop_host.dispatch(restored, 'catalog', {})['nodes']), 1)
            self.assertEqual(len(calls), 1)

    def test_https_checks_certificate_and_accepts_only_trusted_local_fixture(self):
        cert, key = certificate(self.folder)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(str(cert), str(key))
        with subscription_server({'/sub': (200, encoded({'proxies': [NODE]}), {})}, tls) as (url, calls):
            with self.assertRaises(ValueError):
                self.app.import_source({'source': {'type': 'url', 'location': url + '/sub'}})
            self.assertEqual(calls, [])
            with patch.object(node_sources, 'trust_bundle', return_value=cert):
                result = self.app.import_source({'source': {'type': 'url', 'location': url + '/sub'}})
            self.assertEqual(len(result['catalog']['nodes']), 1)
            self.assertEqual(len(calls), 1)

    def test_portable_public_ca_bundle_is_loaded(self):
        self.assertGreater(len(node_sources.subscription_tls().get_ca_certs()), 100)

    def test_remote_providers_require_explicit_download_and_keep_overrides(self):
        config = {'proxy-providers': {'source-a': {'type': 'http', 'url': '/nodes',
                                                 'override': {'additional-prefix': '[A] '}}},
                  'proxy-groups': [{'name': 'all', 'type': 'select', 'use': ['source-a']}]}
        routes = {'/sub': (200, encoded(config), {}), '/nodes': (200, encoded({'proxies': [NODE]}), {})}
        with subscription_server(routes) as (url, calls):
            draft = {'type': 'url', 'location': url + '/sub'}
            result = self.app.import_source({'source': draft})
            self.assertTrue(result['requires_provider_download'])
            self.assertEqual(result['providers'], ['source-a'])
            self.assertEqual(self.app.settings['source']['type'], 'client')
            self.assertEqual([path for path, _ in calls], ['/sub'])
            result = self.app.import_source({'source': dict(draft, fetch_providers=True)})
            self.assertEqual(result['catalog']['nodes'][0]['name'], '[A] 日本 fixture')
            self.assertEqual(result['catalog']['groups'][0]['all'], ['[A] 日本 fixture'])

    def test_file_provider_is_resolved_without_running_client(self):
        cache = self.folder / 'nodes.json'
        cache.write_bytes(encoded({'proxies': [NODE]}))
        config = self.folder / 'config.json'
        config.write_bytes(encoded({'proxy-providers': {'local': {'type': 'file', 'path': cache.name}}}))
        result = self.app.import_source({'source': {'type': 'file', 'location': str(config)}})
        self.assertEqual(result['catalog']['nodes'][0]['provider'], 'local')
        core_dir = Path(self.app.sources.connection(self.app.settings['source'], {})['core_dir'])
        self.assertTrue(core_dir.samefile(self.folder))

    def test_invalid_import_preserves_previous_source_settings_and_report(self):
        config = self.folder / 'config.json'
        config.write_bytes(encoded({'proxies': [NODE]}))
        self.app.import_source({'source': {'type': 'file', 'location': str(config)}})
        previous = self.app.settings.copy()
        self.app.last_report = {'rows': [{'name': '上次结果'}]}
        with subscription_server({'/bad?token=PRIVATE_TOKEN': (403, b'', {})}) as (url, _):
            with self.assertRaisesRegex(ValueError, 'HTTP 403') as failure:
                self.app.import_source({'source': {'type': 'url', 'location': url + '/bad?token=PRIVATE_TOKEN'}})
            self.assertNotIn('PRIVATE_TOKEN', str(failure.exception))
        self.assertEqual(self.app.settings, previous)
        self.assertEqual(self.app.last_report['rows'][0]['name'], '上次结果')

    def test_source_changes_clear_selection_from_previous_source(self):
        self.app.settings['options'].update(group='old', provider='old', node_names=['old'])
        config = self.folder / 'config.json'
        config.write_bytes(encoded({'proxies': [NODE]}))
        self.app.import_source({'source': {'type': 'file', 'location': str(config)}})
        self.assertEqual(self.app.settings['options']['node_names'], [])
        self.assertEqual(self.app.settings['options']['provider'], '')

    def test_unsupported_format_and_yaml_errors_do_not_echo_credentials(self):
        for data in (b'ss://PRIVATE_TOKEN', b'<html>login</html>', b'password: [PRIVATE_PASSWORD',
                     b'proxies: &a [*a]'):
            with self.subTest(data=data[:8]), self.assertRaises(ValueError) as failure:
                node_sources.parse_config(data)
            self.assertNotIn('PRIVATE_', str(failure.exception))

    def test_remote_configuration_cannot_read_local_certificate_or_file_provider(self):
        configs = [{'proxies': [dict(NODE, certificate='../../secret.pem')]},
                   {'proxy-providers': {'local': {'type': 'file', 'path': '/private/config'}}}]
        for config in configs:
            with subscription_server({'/sub': (200, encoded(config), {})}) as (url, _):
                with self.assertRaisesRegex(ValueError, '本地证书|本机文件'):
                    self.app.import_source({'source': {'type': 'url', 'location': url + '/sub'}})

    def test_cross_origin_redirect_drops_authentication_header(self):
        with subscription_server({'/nodes': (200, encoded({'proxies': [NODE]}), {})}) as (target, target_calls):
            routes = {'/redirect': (302, b'', {'Location': target + '/nodes'})}
            with subscription_server(routes) as (url, calls):
                node_sources.download(url + '/redirect', node_sources.time.monotonic() + 3,
                                      {'Authorization': ['Bearer PRIVATE_HEADER']})
            self.assertEqual(calls[0][1], 'Bearer PRIVATE_HEADER')
            self.assertIsNone(target_calls[0][1])

    def test_size_limit_and_invalid_redirect_scheme(self):
        routes = {'/large': (200, b'x' * 33, {}), '/redirect': (302, b'', {'Location': 'file:///private'})}
        with subscription_server(routes) as (url, _):
            with patch.object(node_sources, 'MAX_BYTES', 32), self.assertRaisesRegex(ValueError, '32 MiB'):
                node_sources.download(url + '/large', node_sources.time.monotonic() + 3)
            with self.assertRaises(ValueError):
                node_sources.download(url + '/redirect', node_sources.time.monotonic() + 3)

    def test_snapshot_identifiers_cannot_escape_private_directory(self):
        with self.assertRaises(ValueError):
            node_sources.normalize_source({'type': 'file', 'location': 'fixture', 'snapshot': '../secret'})

    def test_source_updates_are_rejected_during_benchmark(self):
        self.app.job['running'] = True
        with self.assertRaisesRegex(RuntimeError, '测速过程中'):
            self.app.import_source({'source': {'type': 'file', 'location': 'fixture'}})


class ReleaseTests(unittest.TestCase):
    def test_release_requires_both_mac_architectures_and_writes_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in REQUIRED_ASSETS[:2]:
                (folder / name).write_bytes(b'fixture')
            with self.assertRaisesRegex(RuntimeError, 'macOS-arm64.*macOS-x86_64'):
                prepare(folder)
            for name in ('ProxySprint-macOS-arm64.zip', 'ProxySprint-macOS-x86_64.zip'):
                (folder / name).write_bytes(b'legacy zip')
            with self.assertRaisesRegex(RuntimeError, r'macOS-arm64\.dmg.*macOS-x86_64\.dmg'):
                prepare(folder)
            for name in REQUIRED_ASSETS[2:]:
                (folder / name).write_bytes(b'fixture')
            prepare(folder)
            self.assertEqual(len((folder / 'SHA256SUMS.txt').read_text().splitlines()), 4)


if __name__ == '__main__':
    unittest.main()
