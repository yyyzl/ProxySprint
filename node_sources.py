"""在本机获取 Clash/Mihomo YAML 来源，生成只包含测速所需字段的私有快照。"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit
import uuid

import yaml

MAX_BYTES = 32 * 1024 * 1024
MAX_PROVIDERS = 20
MAX_NODES = 10000
DOWNLOAD_SECONDS = 20
DEFAULT_SOURCE = {'type': 'client', 'location': '', 'snapshot': '', 'fetch_providers': False}


def valid_text(value, limit):
    return isinstance(value, str) and len(value) <= limit and all(32 <= ord(c) != 127 for c in value)


def validate_url(value):
    if not valid_text(value, 8192):
        raise ValueError('订阅地址无效。')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.username is not None or parsed.password is not None or parsed.fragment):
            raise ValueError()
        _ = parsed.port
    except ValueError:
        raise ValueError('订阅地址必须是有效的 HTTP/HTTPS URL，不能包含用户名或密码。') from None
    return value


def normalize_source(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_SOURCE):
        raise ValueError('节点来源格式无效。')
    source = dict(DEFAULT_SOURCE, **value)
    if source['type'] not in ('client', 'file', 'url'):
        raise ValueError('请选择客户端、配置文件或订阅链接。')
    location = source['location']
    if not valid_text(location, 8192):
        raise ValueError('节点来源地址或路径无效。')
    source['location'] = location.strip()
    if not isinstance(source['fetch_providers'], bool):
        raise ValueError('远程节点来源下载选项无效。')
    if not isinstance(source['snapshot'], str) or not re.fullmatch(r'(?:[a-f0-9]{32})?', source['snapshot']):
        raise ValueError('节点快照标识无效，请重新导入。')
    if source['type'] == 'client':
        return dict(DEFAULT_SOURCE)
    if not source['location']:
        raise ValueError('请填写订阅链接或选择配置文件。')
    if source['type'] == 'url':
        validate_url(source['location'])
    return source


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    """限制重定向，不把配置内的认证请求头发送给其他站点。"""
    max_redirections = 3
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        before, after = urlsplit(req.full_url), urlsplit(newurl)
        if before.scheme == 'https' and after.scheme != 'https':
            raise ValueError('订阅地址重定向到不安全的 HTTP 地址。')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and (before.scheme, before.hostname, before.port) != (after.scheme, after.hostname, after.port):
            for key in list(redirected.headers):
                if key.lower() != 'user-agent':
                    del redirected.headers[key]
        return redirected


def header_value(values):
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list) or not values or any(not valid_text(v, 8192) for v in values):
        raise ValueError('远程节点来源的请求头内容无效。')
    value = ', '.join(values)
    try:
        value.encode('latin-1')
    except UnicodeError:
        raise ValueError('远程节点来源包含无法发送的请求头字符。') from None
    return value


def request_headers(raw=None):
    headers = {'User-Agent': 'mihomo/1.19.32 ProxySprint/1.2.0', 'Accept-Encoding': 'identity'}
    if raw is None:
        return headers
    if not isinstance(raw, dict):
        raise ValueError('远程节点来源的请求头格式无效。')
    for key, values in raw.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9-]+', key):
            raise ValueError('远程节点来源的请求头名称无效。')
        if key.lower() in ('host', 'cookie', 'proxy-authorization', 'content-length', 'accept-encoding'):
            raise ValueError('远程节点来源包含不支持的请求头。')
        headers[key] = header_value(values)
    return headers


def read_response(response, deadline):
    if response.headers.get('Content-Encoding', 'identity').lower() not in ('', 'identity'):
        raise ValueError('订阅服务器返回了不支持的压缩内容。')
    try:
        length = int(response.headers.get('Content-Length', '0'))
    except ValueError:
        raise ValueError('订阅服务器返回了无效的内容长度。') from None
    if length > MAX_BYTES:
        raise ValueError('订阅内容超过 32 MiB。')
    data = bytearray()
    while True:
        if time.monotonic() >= deadline:
            raise ValueError('订阅获取超时，请稍后重试或导入本地配置文件。')
        chunk = response.read1(min(65536, MAX_BYTES + 1 - len(data)))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise ValueError('订阅内容超过 32 MiB。')


def trust_bundle():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / 'core/cacert.pem'
    return Path(__file__).resolve().parent / 'third_party/certifi/cacert.pem'


def subscription_tls():
    context = ssl.create_default_context()
    try:
        context.load_verify_locations(cafile=str(trust_bundle()))
    except (OSError, ssl.SSLError):
        raise ValueError('HTTPS 证书根缺失或损坏，请使用完整 ProxySprint 程序包。') from None
    return context


def download(url, deadline, headers=None):
    validate_url(url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError('订阅获取超时，请稍后重试或导入本地配置文件。')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), SafeRedirect(),
                                        urllib.request.HTTPSHandler(context=subscription_tls()))
    request = urllib.request.Request(url, headers=request_headers(headers))
    try:
        with opener.open(request, timeout=min(remaining, 10)) as response:
            return read_response(response, deadline), response.geturl()
    except urllib.error.HTTPError as error:
        error.close()
        raise ValueError(f'订阅服务器返回 HTTP {error.code}，请检查链接是否有效。') from None
    except (OSError, urllib.error.URLError):
        raise ValueError('无法直连获取订阅，请检查网络和链接，或导入已下载的配置文件。') from None


def read_file(path):
    try:
        with Path(path).open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError:
        raise ValueError('无法读取配置文件，请检查路径和权限。') from None
    if len(data) > MAX_BYTES:
        raise ValueError('配置内容超过 32 MiB。')
    return data


def parse_config(data):
    try:
        config = yaml.safe_load(data.decode('utf-8-sig'))
        if not isinstance(config, dict):
            raise ValueError()
        # 禁止循环、别名复用和过深结构，避免转换私有 JSON 快照时无限展开。
        pending, seen, count = [(config, 0)], set(), 0
        while pending:
            value, depth = pending.pop()
            count += 1
            if depth > 32 or count > 200000:
                raise ValueError()
            if isinstance(value, (list, dict)):
                if id(value) in seen:
                    raise ValueError()
                seen.add(id(value))
                items = value.values() if isinstance(value, dict) else value
                pending.extend((item, depth + 1) for item in items)
        json.dumps(config, allow_nan=False)
        return config
    except (UnicodeError, yaml.YAMLError, ValueError, TypeError, RecursionError):
        raise ValueError('内容不是可导入的 Clash/Mihomo YAML 或 JSON 配置；本版本暂不支持 URI/Base64 订阅。') from None


def validate_nodes(nodes):
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise ValueError('节点列表格式无效或超过 10000 个节点。')
    if any(not isinstance(node, dict) or not isinstance(node.get('name'), str)
           or not isinstance(node.get('type'), str) for node in nodes):
        raise ValueError('节点定义缺少有效的名称或类型。')
    return nodes


def reject_remote_assets(value, proxy_type=''):
    if isinstance(value, dict):
        for key, item in value.items():
            if (key in ('certificate', 'private-key', 'ca', 'ca-file', 'client-cert', 'client-key')
                    and isinstance(item, str) and '\n' not in item and not item.startswith('-----BEGIN')
                    and not (key == 'private-key' and proxy_type == 'wireguard')):
                raise ValueError('远程订阅引用了本地证书文件，请改用包含所需资产的本地配置文件。')
            reject_remote_assets(item, value.get('type', proxy_type))
    elif isinstance(value, list):
        for item in value:
            reject_remote_assets(item, proxy_type)


def provider_nodes(settings, base_url, base_dir, deadline):
    kind = settings.get('type')
    if kind == 'inline':
        return validate_nodes(settings.get('payload') or []), 0
    if kind == 'http':
        url = settings.get('url')
        if not isinstance(url, str):
            raise ValueError('远程节点来源缺少有效 URL。')
        payload, _ = download(urljoin(base_url, url), deadline, settings.get('header'))
    elif kind == 'file' and base_dir is not None and isinstance(settings.get('path'), str):
        payload = read_file(base_dir / settings['path'])
    else:
        raise ValueError('存在不支持的节点来源；远程订阅不能读取本机文件。')
    return validate_nodes(parse_config(payload).get('proxies')), len(payload)


def resolve_providers(providers, base_url, base_dir, deadline, total_bytes):
    resolved = {}
    for name, settings in providers.items():
        if not isinstance(name, str) or not isinstance(settings, dict):
            raise ValueError('节点来源定义无效。')
        nodes, size = provider_nodes(settings, base_url, base_dir, deadline)
        total_bytes += size
        if total_bytes > MAX_BYTES:
            raise ValueError('订阅及其节点来源总内容超过 32 MiB。')
        if settings.get('type') == 'http' or base_dir is None:
            reject_remote_assets(nodes)
            reject_remote_assets(settings.get('override') or {})
        resolved[name] = {key: copy.deepcopy(settings[key]) for key in
                          ('filter', 'exclude-filter', 'exclude-type', 'override') if key in settings}
        resolved[name].update(type='inline', payload=nodes)
    return resolved


class SourceStore:
    def __init__(self, data_dir):
        self.folder = Path(data_dir) / 'sources'
        self.folder.mkdir(mode=0o700, exist_ok=True)

    def snapshot_path(self, source):
        if not source['snapshot']:
            raise ValueError('节点来源尚未导入，请先导入并预览节点。')
        return self.folder / (source['snapshot'] + '.json')

    def connection(self, source, connection):
        if source['type'] == 'client':
            return connection
        path = self.snapshot_path(source)
        if not path.is_file():
            raise ValueError('已导入的节点快照缺失，请重新导入。')
        return dict(connection, config_path=str(path),
                    core_dir=str(Path(source['location']).expanduser().resolve().parent
                                 if source['type'] == 'file' else self.folder),
                    controller='', named_pipe='', unix_socket='', _standalone=True)

    def prepare(self, value):
        source = normalize_source(value)
        if source['type'] == 'client':
            raise ValueError('客户端来源请使用连接设置。')
        deadline = time.monotonic() + DOWNLOAD_SECONDS
        remote = source['type'] == 'url'
        if remote:
            data, base_url = download(source['location'], deadline)
            base_dir = None
        else:
            path = Path(source['location']).expanduser().resolve()
            source['location'] = str(path)
            data, base_url, base_dir = read_file(path), '', path.parent
        config = parse_config(data)
        providers = config.get('proxy-providers') or {}
        if not isinstance(providers, dict) or len(providers) > MAX_PROVIDERS:
            raise ValueError('节点来源列表格式无效或超过 20 个来源。')
        remote_names = [name for name, settings in providers.items()
                        if isinstance(settings, dict) and settings.get('type') == 'http']
        if remote_names and not source['fetch_providers']:
            return source, None, remote_names
        result = {key: copy.deepcopy(config[key]) for key in
                  ('proxies', 'proxy-groups', 'global-client-fingerprint', 'tls') if key in config}
        result['proxies'] = validate_nodes(result.get('proxies') or [])
        resolved = resolve_providers(providers, base_url, base_dir, deadline, len(data))
        if resolved:
            result['proxy-providers'] = resolved
        if remote:
            reject_remote_assets(result)
        total_nodes = len(result['proxies']) + sum(len(p['payload']) for p in resolved.values())
        if not 1 <= total_nodes <= MAX_NODES:
            raise ValueError('配置中没有节点，或节点总数超过 10000。')
        source['snapshot'] = uuid.uuid4().hex
        return source, result, []
