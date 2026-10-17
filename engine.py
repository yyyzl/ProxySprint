"""Read-only discovery and isolated Mihomo HTTP timing benchmarks.

No controller mutation, subscription downloads, login cookies or model calls.
Sources: https://wiki.metacubex.one/config/inbound/listeners/
https://wiki.metacubex.one/config/proxy-providers/ and /api/.
"""
from __future__ import annotations
import copy
import hashlib
import re
import os
import sys
import json
import shlex
import shutil
import subprocess
import socket
import tempfile
import time
import uuid
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
import yaml
from windows_support import discover_windows, physical_interface, pipe_api, hidden_process, resolve_pipe


REGIONS = [{'id': k, 'name': v} for k, v in [('jp', '日本'), ('sg', '新加坡'), ('hk', '香港'), ('kr', '韩国'), ('tw', '台湾'), ('us', '美国'), ('other', '其他')]]
DEFAULT_OPTIONS = {'regions': ['jp', 'sg'], 'group': '', 'provider': '', 'include': '', 'exclude': '', 'limit': 0, 'rounds': 3, 'workers': 4, 'timeout': 8, 'node_names': []}
DEFAULT_SITES = [
    {'id': 'chatgpt', 'name': 'ChatGPT', 'url': 'https://chatgpt.com/cdn-cgi/trace', 'statuses': [200], 'validator': 'chatgpt-trace'},
    {'id': 'github', 'name': 'GitHub', 'url': 'https://github.com/', 'statuses': [200], 'validator': 'none'},
    {'id': 'google', 'name': 'Google', 'url': 'https://www.google.com/generate_204', 'statuses': [204], 'validator': 'none'},
    {'id': 'youtube', 'name': 'YouTube', 'url': 'https://www.youtube.com/', 'statuses': [200], 'validator': 'none'},
    {'id': 'wikipedia', 'name': 'Wikipedia', 'url': 'https://www.wikipedia.org/', 'statuses': [200], 'validator': 'none'},
]


def validate_options(options):
    if not isinstance(options, dict):
        raise ValueError('测试选项必须是对象')
    result = copy.deepcopy(DEFAULT_OPTIONS)
    result.update({k: v for k, v in options.items() if k in result})
    if not isinstance(result['regions'], list) or any(not isinstance(r, str) or r not in {v['id'] for v in REGIONS} for r in result['regions']):
        raise ValueError('地区选项无效')
    for key, lower, upper in [('limit', 0, 200), ('rounds', 1, 10), ('workers', 1, 16), ('timeout', 1, 120)]:
        v = result[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lower <= v <= upper or (key != 'timeout' and int(v) != v):
            raise ValueError(f'{key} 必须在 {lower}..{upper}')
        result[key] = float(v) if key == 'timeout' else int(v)
    for key in ['group', 'provider', 'include', 'exclude']:
        if not isinstance(result[key], str) or len(result[key]) > 2000:
            raise ValueError(f'{key} 必须是短文本')
    if not isinstance(result['node_names'], list) or len(result['node_names']) > 200 or any(not isinstance(n, str) for n in result['node_names']):
        raise ValueError('node_names 必须是最多 200 个节点名称的列表')
    return result


def _region(name):
    text = name.casefold()
    for key, terms in [
        ('jp', ['日本', '东京', '東京', '大阪', '🇯🇵', r'(?<![a-z])(?:jp|japan|tokyo|osaka)(?![a-z])']),
        ('sg', ['新加坡', '狮城', '獅城', '🇸🇬', r'(?<![a-z])(?:sg|singapore)(?![a-z])']),
        ('hk', ['香港', '🇭🇰', r'(?<![a-z])(?:hk|hong[ -]?kong)(?![a-z])']),
        ('kr', ['韩国', '韓國', '首尔', '首爾', '🇰🇷', r'(?<![a-z])(?:kr|korea|seoul)(?![a-z])']),
        ('tw', ['台湾', '台灣', '台北', '臺灣', '臺北', '🇹🇼', r'(?<![a-z])(?:tw|taiwan|taipei)(?![a-z])']),
        ('us', ['美国', '美國', '洛杉矶', '纽约', '🇺🇸', r'(?<![a-z])(?:us|usa|united states|los angeles|new york)(?![a-z])']),
    ]:
        if any(re.search(term, text) for term in terms):
            return key
    return 'other'


def _pseudo(name, proxy_type=''):
    return name.upper() in ('DIRECT', 'REJECT', 'REJECT-DROP', 'PASS', 'COMPATIBLE') or proxy_type.casefold() in ('direct', 'reject', 'reject-drop', 'dns', 'pass', 'compatible') or bool(re.search(r'剩余流量|剩餘流量|套餐到期|流量重置|到期时间|到期時間|有效期|订阅信息|訂閱信息|(?i:traffic remaining|remaining traffic|expire(?:s|d)?[ :])', name))


def filter_nodes(catalog_dict, options):
    opts = validate_options(options)
    groups = {g['name']: g.get('all', []) for g in catalog_dict.get('groups', [])}
    allowed = None
    if opts['group']:
        if opts['group'] not in groups:
            raise ValueError('选择的策略组不存在，请刷新节点')
        allowed, seen = set(), set()
        def expand(name):
            if name in seen:
                return
            seen.add(name)
            if name in groups:
                for child in groups[name]:
                    expand(child)
            else:
                allowed.add(name)
        expand(opts['group'])
    includes = [s.strip().casefold() for s in opts['include'].split(',') if s.strip()]
    excludes = [s.strip().casefold() for s in opts['exclude'].split(',') if s.strip()]
    result, seen = [], set()
    for node in catalog_dict.get('nodes', []):
        name = node['name']
        if name in seen or _pseudo(name, str(node.get('type', ''))):
            continue
        if allowed is not None and name not in allowed:
            continue
        if opts['regions'] and node.get('region', _region(name)) not in opts['regions']:
            continue
        if opts['provider'] and node.get('provider') != opts['provider']:
            continue
        if opts['node_names'] and name not in opts['node_names']:
            continue
        if includes and not any(s in name.casefold() for s in includes):
            continue
        if any(s in name.casefold() for s in excludes):
            continue
        seen.add(name)
        result.append(node)
    if opts['limit']:
        result = result[:opts['limit']]
    if len(result) > 200:
        raise ValueError('候选节点超过 200，请缩小筛选范围或设置 limit')
    return result


def _load(path):
    try:
        path = Path(path)
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError('配置或缓存超过 32 MiB')
        data = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError('配置必须是 YAML/JSON 对象')
        return data
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError('无法读取配置或缓存，请检查路径和权限') from exc


def _controller(value):
    if not value:
        return ''
    value = str(value)
    if '://' not in value:
        value = 'http://' + value
    parsed = urlsplit(value)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username is not None or parsed.password is not None or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('控制器只允许本机回环 HTTP 地址，禁止远程控制器')
    try:
        _ = parsed.port
    except ValueError:
        raise ValueError('控制器端口无效') from None
    return value.rstrip('/')


def bundled_core():
    """优先使用随包的固定内核；开发时使用已校验的项目内内核。"""
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    name = 'mihomo.exe' if os.name == 'nt' else 'mihomo'
    return next((str(p) for p in (root / 'core' / name, root / 'work/test-core' / name) if p.is_file()), '')


def discover(overrides, require_runtime=True):
    # Browser forms send all keys; blank values explicitly mean auto-discover.
    overrides = {k: v for k, v in (overrides or {}).items() if v not in ('', None)}
    standalone = bool(overrides.get('_standalone'))
    hints = {}
    if not standalone and sys.platform == 'win32' and (not overrides.get('config_path') or (require_runtime and not overrides.get('binary_path'))):
        hints = discover_windows()
    if not standalone and sys.platform == 'darwin':
        try:
            listing = subprocess.run(['/bin/ps', '-axo', 'command='], capture_output=True, text=True, timeout=3).stdout
            for line in listing.splitlines():
                if 'clash-site-probe-' in line:
                    continue
                if not re.search(r'(?:verge-)?mihomo(?:\s|$)', line):
                    continue
                executable = re.match(r'''\s*["']?(.+?(?:verge-)?mihomo)(?=["']?\s|$)''', line)
                tokens = shlex.split(line)
                candidate = executable.group(1) if executable else (tokens[0] if tokens else '')
                if candidate and Path(candidate).is_file():
                    hints['binary_path'] = candidate
                    for match in re.finditer(r'''(?:^|\s)-([df])\s+(.+?)(?=\s+-[A-Za-z]|$)''', line):
                        value = match.group(2).strip().strip('"').strip("'")
                        hints['core_dir' if match.group(1) == 'd' else 'config_path'] = value
                    if 'core_dir' in hints and 'config_path' not in hints:
                        hints['config_path'] = str(Path(hints['core_dir']) / 'config.yaml')
                    break
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    home = Path.home()
    config_candidates = [home / 'Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/clash-verge.yaml', home / 'Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/config.yaml', home / '.config/mihomo/config.yaml', home / '.config/clash/config.yaml']
    config = overrides.get('config_path') or hints.get('config_path') or next((str(p) for p in config_candidates if p.is_file()), '')
    if not config or not Path(config).expanduser().is_file():
        raise RuntimeError('未找到 Clash/Mihomo 配置，请指定运行中核心实际使用的 config_path')
    config = str(Path(config).expanduser().resolve())
    cfg = _load(config)
    binary_candidates = ['/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo', '/Applications/Clash Verge.app/Contents/MacOS/mihomo', str(home / 'Applications/Clash Verge.app/Contents/MacOS/verge-mihomo')]
    binary = (overrides.get('binary_path') or bundled_core()) if standalone else (overrides.get('binary_path') or hints.get('binary_path') or next((p for p in binary_candidates if Path(p).is_file()), '') or shutil.which('mihomo'))
    if not binary or not Path(binary).expanduser().is_file():
        if require_runtime:
            raise RuntimeError('未找到独立 Mihomo，请安装完整 ProxySprint 包或指定内核路径。' if standalone else '未找到 Mihomo 可执行文件，请指定 binary_path')
        binary = ''
    interface = overrides.get('interface', '')
    if sys.platform == 'win32' and not interface and (standalone or not overrides.get('config_path')):
        interface = physical_interface()
    if sys.platform == 'darwin' and not interface:
        try:
            state = subprocess.run(['/usr/sbin/scutil'], input='show State:/Network/Global/IPv4\n', capture_output=True, text=True, timeout=3).stdout
            match = re.search(r'PrimaryInterface\s*:\s*(\S+)', state)
            interface = match.group(1) if match else ''
        except (OSError, subprocess.TimeoutExpired):
            pass
    if interface and (len(interface) > 64 or any(ord(c) < 32 for c in interface) or (sys.platform != 'win32' and not re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', interface))):
        raise ValueError('物理网络接口名称无效')
    if require_runtime and sys.platform == 'darwin' and (not interface or str(interface).startswith(('utun', 'tun'))):
        raise RuntimeError('无法确定物理网络接口；请指定 en0/en1 等接口，避免经过主核心 TUN')
    unix_socket = overrides.get('unix_socket', '')
    if not standalone and sys.platform == 'darwin' and not unix_socket and 'controller' not in overrides:
        candidates = ['/tmp/verge/verge-mihomo.sock', f'/var/run/clash-verge-service/users/{os.getuid()}/verge-mihomo.sock']
        unix_socket = next((p for p in candidates if Path(p).exists()), '')
    controller = overrides.get('controller', cfg.get('external-controller', ''))
    if 'controller' not in overrides and controller:
        controller = re.sub(r'^(?:http://)?0\.0\.0\.0:', '127.0.0.1:', str(controller))
        controller = re.sub(r'^(?:http://)?\[::\]:', '[::1]:', str(controller))
    return {'config_path': config, 'binary_path': str(Path(binary).expanduser().resolve()) if binary else '',
            'core_dir': str(Path(overrides.get('core_dir') or hints.get('core_dir') or Path(config).parent).expanduser().resolve()),
            'controller': _controller(controller),
            'unix_socket': str(unix_socket), 'interface': interface,
            'named_pipe': resolve_pipe(str(overrides.get('named_pipe') or cfg.get('external-controller-pipe') or '')) if sys.platform == 'win32' else '',
            '_standalone': standalone}


def _api(connection, cfg, endpoint):
    secret = str(cfg.get('secret') or '')
    if connection.get('named_pipe'):
        return pipe_api(connection['named_pipe'], endpoint, secret)
    if connection.get('unix_socket'):
        args = [shutil.which('curl') or 'curl', '-q', '--silent', '--fail', '--noproxy', '*', '--max-time', '4', '--unix-socket', connection['unix_socket']]
        # Header on stdin avoids exposing controller credentials in process arguments.
        if secret:
            args += ['--config', '-']
        args += ['http://localhost' + endpoint]
        escaped = secret.replace('\\', '\\\\').replace('"', '\\"')
        result = subprocess.run(args, input=f'header = "Authorization: Bearer {escaped}"\n' if secret else None, capture_output=True, text=True, timeout=6)
        if result.returncode:
            raise RuntimeError('无法访问本机 Unix socket 控制器')
        return json.loads(result.stdout)
    controller = _controller(connection.get('controller', ''))
    if not controller:
        raise RuntimeError('未配置本机控制器；仅能读取本地配置')
    request = urllib.request.Request(controller + endpoint, headers={'Authorization': 'Bearer ' + secret} if secret else {})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError('控制器重定向已拒绝，防止泄漏认证信息')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=4) as response:
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise RuntimeError('控制器响应过大')
        return json.loads(body)


def _inventory(connection):
    cfg = _load(connection['config_path'])
    warnings, runtime, memberships, version = [], {}, {}, ''
    memberships_available = False
    if connection.get('_standalone'):
        if connection.get('binary_path'):
            version = '独立 Mihomo'
        else:
            warnings.append('独立内核缺失，请使用完整安装包或在连接设置中选择内核。')
    else:
        try:
            version = str(_api(connection, cfg, '/version').get('version', ''))
            runtime = _api(connection, cfg, '/proxies').get('proxies', {})
            if cfg.get('proxy-providers'):
                memberships = _api(connection, cfg, '/providers/proxies').get('providers', {})
                memberships_available = True
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            warnings.append('本机控制器不可用；策略组与 provider 名称按本地缓存解析，请检查控制器/Unix socket')
    proxies, providers = {}, {}
    def add(proxy, provider=''):
        if not isinstance(proxy, dict) or not isinstance(proxy.get('name'), str) or not proxy.get('type'):
            return
        name = proxy['name']
        if _pseudo(name, str(proxy['type'])):
            return
        if name in proxies:
            warnings.append(f'节点重名，保留首个定义：{name}')
            return
        proxies[name] = (copy.deepcopy(proxy), provider)
    for proxy in cfg.get('proxies', []) or []:
        add(proxy)
    for provider, settings in (cfg.get('proxy-providers') or {}).items():
        payload = settings.get('payload') if settings.get('type') == 'inline' else None
        if settings.get('type') != 'inline':
            path = settings.get('path')
            if not path and settings.get('type') == 'http' and settings.get('url'):
                # Mihomo constant/path.go GetPathByHash("proxies", URL).
                path = str(Path('proxies') / hashlib.md5(str(settings['url']).encode(), usedforsecurity=False).hexdigest())
            resolved = Path(connection['core_dir']) / path if path else None
            if resolved is None or not resolved.is_file():
                payload = settings.get('payload')
                if payload is None:
                    warnings.append(f'provider {provider} 缓存缺失；请先在主客户端更新订阅，或指定正确 core_dir（本工具不下载订阅）')
                    providers[provider] = []
                    continue
                if not memberships_available:
                    warnings.append(f'provider {provider} 缓存缺失且 fallback payload 未获运行时成员确认，已跳过；请检查控制器/Unix socket、core_dir，或在主客户端更新订阅')
                    providers[provider] = []
                    continue
            else:
                try:
                    payload = _load(resolved).get('proxies', [])
                except (ValueError, RuntimeError):
                    warnings.append(f'provider {provider} 缓存读取失败，请在主客户端刷新')
                    providers[provider] = []
                    continue
        providers[provider] = []
        override = settings.get('override') or {}
        runtime_names = {p.get('name') for p in memberships.get(provider, {}).get('proxies', []) if isinstance(p, dict)}
        for original in payload or []:
            if not isinstance(original, dict) or not isinstance(original.get('name'), str):
                continue
            proxy = copy.deepcopy(original)
            try:
                if settings.get('filter') and not any(re.search(p, original['name']) for p in settings['filter'].split('`')):
                    continue
                if settings.get('exclude-filter') and any(re.search(p, original['name']) for p in settings['exclude-filter'].split('`')):
                    continue
                if original.get('type', '').casefold() in str(settings.get('exclude-type', '')).casefold().split('|'):
                    continue
            except re.error:
                warnings.append(f'provider {provider} 筛选正则无法解析，未纳入不确定节点')
                continue
            if override.get('override-expr'):
                warnings.append(f'provider {provider} 使用不支持的 override-expr；无法安全复制运行时配置，跳过该节点')
                continue
            name = str(override.get('additional-prefix', '')) + proxy['name'] + str(override.get('additional-suffix', ''))
            proxy.update({k: v for k, v in override.items() if k not in ('additional-prefix', 'additional-suffix', 'proxy-name')})
            # regex rename is supported only with exact runtime membership confirmation.
            for rule in override.get('proxy-name', []) or []:
                try:
                    replacement = re.sub(r'\$\{?(\d+)\}?', lambda m: r'\g<' + m.group(1) + '>', rule['target'])
                    name = re.sub(rule['pattern'], replacement, name)
                except (KeyError, TypeError, re.error):
                    warnings.append(f'provider {provider} 节点重命名规则无法解析')
            if memberships_available and name not in runtime_names:
                if original['name'] in runtime_names:
                    name = original['name']
                else:
                    warnings.append(f'provider {provider} 节点 {name} 无法匹配运行时成员，已跳过；请在主客户端刷新 provider，并检查 core_dir/override')
                    continue
            proxy['name'] = name
            add(proxy, provider)
            providers[provider].append(name)
    groups = []
    for group in cfg.get('proxy-groups', []) or []:
        active = runtime.get(group['name'], {})
        members = list(group.get('proxies', []) or [])
        for provider in group.get('use', []) or []:
            members.extend(providers.get(provider, []))
        groups.append({'name': group['name'], 'now': active.get('now', ''), 'all': active.get('all', list(dict.fromkeys(members)))})
    for name, value in runtime.items():
        if 'all' in value and not any(g['name'] == name for g in groups):
            groups.append({'name': name, 'now': value.get('now', ''), 'all': value['all']})
    if not connection.get('interface'):
        warnings.append('未绑定物理接口，隔离出站依赖操作系统路由；主客户端 TUN 可能影响结果')
    public = {'connection': {k: connection.get(k, '') for k in ('config_path', 'binary_path', 'core_dir', 'controller', 'unix_socket', 'interface', 'named_pipe')},
              'nodes': [{'name': n, 'region': _region(n), 'provider': p, 'type': v['type']} for n, (v, p) in proxies.items()],
              'groups': groups, 'providers': list(providers), 'warnings': warnings, 'version': version}
    return public, proxies, cfg


def _isolated_config(connection, selected, proxies, original, ports):
    closure, visiting = {}, set()
    def include(name):
        if name in ('DIRECT', 'REJECT'):
            return
        if name in visiting:
            raise ValueError('dialer-proxy 存在循环依赖')
        if name in closure:
            return
        if name not in proxies:
            raise ValueError(f'dialer-proxy {name} 不属于可移植节点；不保留动态策略组')
        visiting.add(name)
        proxy = copy.deepcopy(proxies[name][0])
        dependency = proxy.get('dialer-proxy')
        if dependency:
            include(dependency)
        def assets(value):
            if isinstance(value, dict):
                result = {}
                for key, item in value.items():
                    if key in ('certificate', 'private-key', 'ca', 'ca-file', 'client-cert', 'client-key', 'path') and isinstance(item, str) and '\n' not in item and not item.startswith('-----BEGIN'):
                        # Websocket/plugin paths are not local assets.
                        if key == 'path' or (key == 'private-key' and proxy.get('type') == 'wireguard'):
                            result[key] = item
                            continue
                        path = Path(connection['core_dir']) / item
                        if not path.is_file():
                            raise ValueError(f'节点 {name} 的证书/资产路径不可读取；请使用可移植绝对路径')
                        result[key] = str(path.resolve())
                    else:
                        result[key] = assets(item)
                return result
            if isinstance(value, list):
                return [assets(v) for v in value]
            return value
        proxy = assets(proxy)
        proxy.pop('routing-mark', None)
        proxy.pop('interface-name', None)
        if connection.get('interface'):
            proxy['interface-name'] = connection['interface']
        closure[name] = proxy
        visiting.remove(name)
    for node in selected:
        include(node['name'])
    config = {'mode': 'rule', 'log-level': 'info', 'allow-lan': False, 'bind-address': '127.0.0.1', 'ipv6': False,
              'tun': {'enable': False}, 'dns': {'enable': False}, 'profile': {'store-selected': False, 'store-fake-ip': False},
              'proxies': list(closure.values()), 'rules': ['MATCH,REJECT'],
              'listeners': [{'name': 'probe-' + str(i), 'type': 'mixed', 'listen': '127.0.0.1', 'port': ports[node['name']], 'proxy': node['name'], 'udp': False} for i, node in enumerate(selected)]}
    if connection.get('interface'):
        config['interface-name'] = connection['interface']
    if original.get('global-client-fingerprint'):
        config['global-client-fingerprint'] = original['global-client-fingerprint']
    if original.get('tls'):
        config['tls'] = copy.deepcopy(original['tls'])
    return config


def _terminate(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    for stream in (process.stdout, process.stderr):
        if stream is not None and not stream.closed:
            stream.close()


def _sample(port, site, timeout, stop, folder):
    failed = {'ok': False, 'status': 0, 'ttfb_ms': None, 'total_ms': None, 'reason': '已取消'}
    if stop.is_set():
        return failed
    curl = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/curl.exe') if sys.platform == 'win32' else shutil.which('curl')
    if not curl:
        raise RuntimeError('未找到 curl，请安装系统 curl')
    body = Path(folder) / ('body-' + uuid.uuid4().hex)
    args = [curl, '-q', '--silent', '--show-error', '--proxy', f'http://127.0.0.1:{port}', '--noproxy', '',
            '--proto', '=http,https', '--proto-redir', '=http,https', '--location', '--max-redirs', '5',
            '--connect-timeout', str(timeout), '--max-time', str(timeout), '--max-filesize', str(2 * 1024 * 1024),
            '--output', str(body), '--write-out',
            '{"http_code":"%{http_code}","time_starttransfer":%{time_starttransfer},"time_total":%{time_total}}',
            '--url', site['url']]
    env = os.environ.copy()
    for key in list(env):
        if key.casefold() in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
            env.pop(key)
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, **hidden_process())
    try:
        deadline = time.monotonic() + timeout + 2
        while True:
            if stop.is_set() or time.monotonic() > deadline or (body.exists() and body.stat().st_size > 2 * 1024 * 1024):
                _terminate(process)
                return {**failed, 'reason': '已取消' if stop.is_set() else '响应超时或超过 2 MiB'}
            try:
                output, _ = process.communicate(timeout=0.05)
                break
            except subprocess.TimeoutExpired:
                continue
        try:
            timing = json.loads(output)
        except (ValueError, UnicodeError):
            return {**failed, 'reason': f'curl 失败（退出码 {process.returncode}）'}
        status = int(timing.get('http_code', 0))
        ok = process.returncode == 0 and status in site['statuses']
        reason = '' if ok else (f'curl 失败（退出码 {process.returncode}）' if process.returncode else f'HTTP {status} 不在成功状态码列表')
        if ok and site['validator'] == 'chatgpt-trace':
            content = body.read_bytes()[:65536].decode('utf-8', errors='replace')
            ok = bool(re.search(r'(?m)^h=chatgpt\.com\r?$', content))
            if not ok:
                reason = 'ChatGPT trace 校验失败；可能是拦截页，不能证明 ChatGPT 可达'
        return {'ok': ok, 'status': status, 'ttfb_ms': float(timing.get('time_starttransfer', 0)) * 1000,
                'total_ms': float(timing.get('time_total', 0)) * 1000, 'reason': reason}
    finally:
        _terminate(process)
        body.unlink(missing_ok=True)


def _reserve_ports(names):
    sockets, ports = [], {}
    try:
        for name in names:
            sock = socket.socket()
            sock.bind(('127.0.0.1', 0))
            sockets.append(sock)
            ports[name] = sock.getsockname()[1]
        return ports
    finally:
        for sock in sockets:
            sock.close()


def _launch_core(connection, selected, proxies, original, folder, stop, emit):
    config_path = Path(folder) / 'config.json'
    for attempt in range(3):
        if stop.is_set():
            raise RuntimeError('测试已取消')
        ports = _reserve_ports([n['name'] for n in selected])
        config = _isolated_config(connection, selected, proxies, original, ports)
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        config_path.chmod(0o600)
        args = [connection['binary_path'], '-d', str(folder), '-f', str(config_path)]
        with open(Path(folder) / 'validation.log', 'wb') as log:
            check = subprocess.Popen([args[0], '-t', *args[1:]], stdout=log, stderr=log, **hidden_process())
            try:
                deadline = time.monotonic() + 15
                while check.poll() is None:
                    if stop.wait(0.05) or time.monotonic() > deadline:
                        raise RuntimeError('配置校验已取消或超时；请检查 Mihomo 版本及节点资产')
                if check.returncode:
                    # Never return core logs; they can echo proxy credentials.
                    raise RuntimeError('独立 Mihomo 配置校验失败；请检查节点类型、证书与核心版本（需支持 listeners.proxy）')
            finally:
                _terminate(check)
        log = open(Path(folder) / 'core.log', 'wb')
        try:
            core = subprocess.Popen(args, stdout=log, stderr=log, **hidden_process())
        except OSError:
            log.close()
            raise RuntimeError('无法启动 Mihomo；请检查 binary_path 和执行权限') from None
        deadline = time.monotonic() + 10
        ready = False
        while core.poll() is None and time.monotonic() < deadline and not stop.is_set():
            ready = True
            for port in ports.values():
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                        pass
                except OSError:
                    ready = False
                    break
            # A connectable port could belong to a process that won a bind race.
            # Require Mihomo's own startup acknowledgement for every listener.
            startup = (Path(folder) / 'core.log').read_bytes()[:1024 * 1024].decode('utf-8', errors='replace')
            owned = all(re.search(r'listening at: 127\.0\.0\.1:' + str(port) + r'(?:[^0-9]|$)', startup) for port in ports.values())
            if ready and owned:
                return core, log, ports
            if re.search(r'level=(?:error|fatal)', startup):
                break
            stop.wait(0.05)
        _terminate(core)
        log.close()
        if stop.is_set():
            raise RuntimeError('测试已取消')
        emit('progress', text=f'独立核心监听启动失败，重新分配端口（{attempt + 1}/3）')
    raise RuntimeError('独立 Mihomo 无法监听全部回环端口；请检查核心版本、端口占用与防火墙')


def _row(node, site, samples, rounds):
    values = [s['ttfb_ms'] for s in samples if s['ok'] and s['ttfb_ms'] is not None]
    successes = sum(s['ok'] for s in samples)
    return {'name': node['name'], 'region': node['region'], 'provider': node.get('provider', ''),
            'site_id': site['id'], 'site_name': site['name'], 'url': site['url'],
            'success_rate': successes / rounds, 'successes': successes, 'total': rounds,
            'median_ms': statistics.median(values) if values else None,
            'jitter_ms': statistics.pstdev(values) if values else None, 'samples': samples,
            'eligible': successes == rounds and len(samples) == rounds}


def benchmark(connection, sites, options, emit, stop):
    if stop.is_set():
        raise RuntimeError('测试已取消')
    opts = validate_options(options)
    if not isinstance(sites, list) or not 1 <= len(sites) <= 20:
        raise ValueError('请选择 1..20 个网站')
    sites = [validate_site(s) for s in sites]
    if len({s['id'] for s in sites}) != len(sites):
        raise ValueError('网站 id 不能重复')
    connection = discover(connection)
    public, proxies, original = _inventory(connection)
    selected = filter_nodes(public, opts)
    if not selected:
        details = '；'.join(public['warnings'])
        raise ValueError('没有符合条件的可测试节点；请检查地区/策略组/provider 筛选与缓存。' + details)
    if stop.is_set():
        raise RuntimeError('测试已取消')
    total = len(selected) * len(sites)
    emit('start', total=total)
    rows = []
    with tempfile.TemporaryDirectory(prefix='clash-site-probe-') as tmp:
        folder = Path(tmp)
        folder.chmod(0o700)
        emit('progress', text='校验并启动独立 Mihomo；不会修改主核心或切换策略组')
        core, log, ports = _launch_core(connection, selected, proxies, original, folder, stop, emit)
        watcher_done = threading.Event()
        def watch():
            while not watcher_done.wait(0.05):
                if stop.is_set():
                    _terminate(core)
                    return
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            def run(node, site):
                samples = []
                for _ in range(opts['rounds']):
                    if stop.is_set():
                        break
                    samples.append(_sample(ports[node['name']], site, opts['timeout'], stop, folder))
                return _row(node, site, samples, opts['rounds'])
            with ThreadPoolExecutor(max_workers=opts['workers']) as executor:
                futures = [executor.submit(run, node, site) for node in selected for site in sites]
                for future in as_completed(futures):
                    row = future.result()
                    rows.append(row)
                    emit('row', row=row, completed=len(rows), total=total)
        finally:
            watcher_done.set()
            watcher.join(timeout=3)
            _terminate(core)
            log.close()
    rows.sort(key=lambda r: (r['site_id'], -r['success_rate'], float('inf') if r['median_ms'] is None else r['median_ms'] + (r['jitter_ms'] or 0), r['name']))
    recommendations = []
    for site in sites:
        eligible = [r for r in rows if r['site_id'] == site['id'] and r['eligible']]
        if eligible and not stop.is_set():
            best = eligible[0]
            recommendations.append({k: best[k] for k in ('site_id', 'site_name', 'name', 'median_ms', 'success_rate')})
    warnings = list(public['warnings'])
    if stop.is_set():
        warnings.append('测试已取消；保留已完成样本，不生成推荐')
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'rows': rows, 'recommendations': recommendations,
            'warnings': warnings, 'note': '测量真实 HTTP 请求的首字节时间（TTFB）与成功率；不是模型生成速度，也不证明账号或模型可用。抖动为成功样本 TTFB 的总体标准差。', 'options': opts}


def catalog(connection):
    return _inventory(discover(connection, require_runtime=False))[0]


def validate_site(site):
    if not isinstance(site, dict):
        raise ValueError('网站必须是对象')
    url = str(site.get('url', ''))
    if any(ord(c) < 32 or ord(c) == 127 for c in url):
        raise ValueError('网站地址包含控制字符')
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        _ = parsed.port
    except ValueError:
        raise ValueError('网站只允许无凭据的 HTTP/HTTPS 地址') from None
    identifier = site.get('id') or 'site-' + hashlib.sha256(url.encode()).hexdigest()[:12]
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier):
        raise ValueError('网站 id 格式无效')
    raw = site.get('statuses', [200])
    if not isinstance(raw, list) or not raw:
        raise ValueError('成功状态码必须是非空列表')
    codes = []
    for value in raw:
        if isinstance(value, bool) or not re.fullmatch(r'\d{3}', str(value)) or not 100 <= int(value) <= 599:
            raise ValueError('HTTP 状态码必须在 100..599')
        codes.append(int(value))
    validator = site.get('validator', 'none')
    if validator not in ('none', 'chatgpt-trace'):
        raise ValueError('网站校验器无效')
    return {'id': identifier, 'name': str(site.get('name') or parsed.hostname)[:120], 'url': url,
            'statuses': list(dict.fromkeys(codes)), 'validator': validator}
