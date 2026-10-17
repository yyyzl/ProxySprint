import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'probe_controller.dart';
import 'ui_style.dart';

void _toast(BuildContext context, String text) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
}

Future<void> showConnectionDialog(
  BuildContext context,
  ProbeController c,
) async {
  final fields = {
    for (final key in [
      'binary_path',
      'config_path',
      'core_dir',
      'controller',
      'named_pipe',
      'unix_socket',
      'interface',
    ])
      key: TextEditingController(text: c.connection[key]?.toString() ?? ''),
  };
  final standalone = c.source['type'] != 'client';
  var manual = standalone, saving = false;
  String error = '';
  try {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocal) {
          Future<void> browse(String key) async {
            final path = key == 'core_dir'
                ? await getDirectoryPath()
                : (await openFile(
                    acceptedTypeGroups: key == 'config_path'
                        ? const [
                            XTypeGroup(
                              label: '配置文件',
                              extensions: ['yaml', 'yml', 'json'],
                            ),
                          ]
                        : const [],
                  ))?.path;
            if (path != null && dialogContext.mounted) {
              fields[key]!.text = path;
            }
          }

          final labels = {
            'binary_path': 'Mihomo 内核路径',
            if (!standalone) 'config_path': '生效配置路径',
            if (!standalone) 'core_dir': '内核工作目录',
            if (!standalone) 'controller': '控制器地址',
            if (!standalone && Platform.isWindows)
              'named_pipe': 'Windows named pipe',
            if (!standalone && Platform.isMacOS) 'unix_socket': 'Unix socket',
            'interface': '出站物理网卡',
          };
          return DialogShell(
            title: '连接设置',
            actions: [
              TextButton(
                onPressed: saving ? null : () => Navigator.pop(dialogContext),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        setLocal(() => saving = true);
                        final connection = manual
                            ? {
                                for (final entry in fields.entries)
                                  entry.key: entry.value.text.trim(),
                              }
                            : {for (final key in fields.keys) key: ''};
                        final ok = await c.save(
                          newConnection: connection,
                          newSource: manual && standalone
                              ? c.source
                              : {'type': 'client'},
                        );
                        if (!dialogContext.mounted) return;
                        if (ok) {
                          Navigator.pop(dialogContext);
                          await c.refreshCatalog();
                        } else {
                          setLocal(() {
                            saving = false;
                            error = c.error;
                          });
                        }
                      },
                child: Text(saving ? '正在保存…' : '保存连接'),
              ),
            ],
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('自动发现')),
                    ButtonSegment(value: true, label: Text('手动配置')),
                  ],
                  selected: {manual},
                  onSelectionChanged: saving
                      ? null
                      : (value) => setLocal(() {
                          manual = value.first;
                          error = '';
                        }),
                  showSelectedIcon: false,
                ),
                const SizedBox(height: 22),
                if (!manual) ...[
                  const Center(
                    child: Icon(Icons.power_outlined, color: blue, size: 46),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    '查找正在运行的 Clash Verge Rev',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '自动读取生效配置、内核路径和本机控制接口。',
                    style: TextStyle(color: muted),
                  ),
                  const SizedBox(height: 18),
                  OutlinedButton.icon(
                    onPressed: saving
                        ? null
                        : () async {
                            setLocal(() => saving = true);
                            final ok = await c.save(
                              newConnection: {
                                for (final key in fields.keys) key: '',
                              },
                              newSource: {'type': 'client'},
                            );
                            if (ok) await c.refreshCatalog();
                            if (!dialogContext.mounted) return;
                            setLocal(() {
                              saving = false;
                              error = c.error;
                              for (final key in fields.keys) {
                                fields[key]!.text =
                                    c.connection[key]?.toString() ?? '';
                              }
                            });
                          },
                    icon: const Icon(Icons.refresh, size: 18),
                    label: const Text('检测客户端'),
                  ),
                  if (c.catalog != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 18),
                      child: Text(
                        '内核：${c.catalog!['version']?.toString() ?? '未连接'}\n配置：${c.connection['config_path']?.toString() ?? ''}',
                        style: const TextStyle(fontSize: 13, color: muted),
                      ),
                    ),
                ] else ...[
                  Text(
                    standalone
                        ? '使用应用自带内核。也可选择其他 Mihomo，或指定出站物理网卡。'
                        : '留空字段自动发现，不需要填写控制器密码或订阅令牌。',
                    style: const TextStyle(color: muted),
                  ),
                  const SizedBox(height: 18),
                  for (final entry in labels.entries)
                    LabeledField(
                      label: entry.value,
                      child: Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: fields[entry.key],
                              decoration: const InputDecoration(
                                hintText: '自动发现',
                              ),
                            ),
                          ),
                          if ([
                            'binary_path',
                            'config_path',
                            'core_dir',
                          ].contains(entry.key)) ...[
                            const SizedBox(width: 8),
                            OutlinedButton(
                              onPressed: () => browse(entry.key),
                              child: const Text('浏览'),
                            ),
                          ],
                        ],
                      ),
                    ),
                ],
                if (error.isNotEmpty)
                  Text(error, style: const TextStyle(color: red)),
              ],
            ),
          );
        },
      ),
    );
  } finally {
    for (final field in fields.values) {
      field.dispose();
    }
  }
}

Future<void> showSourceDialog(BuildContext context, ProbeController c) async {
  var type = c.source['type'] == 'file' ? 'file' : 'url';
  final url = TextEditingController(
    text: c.source['type'] == 'url'
        ? c.source['location']?.toString() ?? ''
        : '',
  );
  final file = TextEditingController(
    text: c.source['type'] == 'file'
        ? c.source['location']?.toString() ?? ''
        : '',
  );
  var saving = false, allowProviders = false, showUrl = false;
  String error = '';
  List<String> providers = [];
  try {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocal) => DialogShell(
          title: '导入节点',
          actions: [
            TextButton(
              onPressed: saving ? null : () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: saving
                  ? null
                  : () async {
                      setLocal(() {
                        saving = true;
                        error = '';
                      });
                      final result = await c.importSource({
                        'type': type,
                        'location': (type == 'url' ? url : file).text.trim(),
                        'fetch_providers': allowProviders,
                      });
                      if (!dialogContext.mounted) return;
                      if (result != null &&
                          result['requires_provider_download'] != true) {
                        Navigator.pop(dialogContext);
                        await showNodesDialog(context, c);
                      } else {
                        setLocal(() {
                          saving = false;
                          if (result?['requires_provider_download'] == true) {
                            providers = List<String>.from(
                              result!['providers'] as List,
                            );
                            error = '配置引用了其他远程节点来源，请确认是否下载后再次导入。';
                          } else {
                            error = c.error;
                          }
                        });
                      }
                    },
              child: Text(saving ? '正在导入…' : '导入并预览'),
            ),
          ],
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                    value: 'url',
                    icon: Icon(Icons.link),
                    label: Text('订阅链接'),
                  ),
                  ButtonSegment(
                    value: 'file',
                    icon: Icon(Icons.description_outlined),
                    label: Text('配置文件'),
                  ),
                ],
                selected: {type},
                showSelectedIcon: false,
                onSelectionChanged: saving
                    ? null
                    : (value) => setLocal(() {
                        type = value.first;
                        providers = [];
                        allowProviders = false;
                        error = '';
                      }),
              ),
              const SizedBox(height: 20),
              const Text(
                '支持 Clash/Mihomo YAML 或 JSON 配置。使用应用自带内核，无需先打开代理客户端。',
                style: TextStyle(color: muted),
              ),
              const SizedBox(height: 20),
              if (type == 'url')
                LabeledField(
                  label: '订阅 URL',
                  hint: '订阅只在本机获取和解析，链接不会写入测速报告。',
                  child: TextField(
                    controller: url,
                    enabled: !saving,
                    obscureText: !showUrl,
                    autocorrect: false,
                    enableSuggestions: false,
                    onChanged: (_) => setLocal(() {
                      providers = [];
                      allowProviders = false;
                      error = '';
                    }),
                    decoration: InputDecoration(
                      hintText: 'https://…',
                      suffixIcon: IconButton(
                        tooltip: showUrl ? '隐藏链接' : '显示链接',
                        onPressed: saving
                            ? null
                            : () => setLocal(() => showUrl = !showUrl),
                        icon: Icon(
                          showUrl
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                        ),
                      ),
                    ),
                  ),
                )
              else
                LabeledField(
                  label: '配置文件',
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: file,
                          enabled: !saving,
                          onChanged: (_) => setLocal(() {
                            providers = [];
                            allowProviders = false;
                            error = '';
                          }),
                          decoration: const InputDecoration(
                            hintText: '选择 YAML / JSON 文件',
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: saving
                            ? null
                            : () async {
                                final selected = await openFile(
                                  acceptedTypeGroups: const [
                                    XTypeGroup(
                                      label: 'Clash 配置',
                                      extensions: ['yaml', 'yml', 'json'],
                                    ),
                                  ],
                                );
                                if (selected != null && dialogContext.mounted) {
                                  setLocal(() {
                                    file.text = selected.path;
                                    providers = [];
                                    allowProviders = false;
                                    error = '';
                                  });
                                }
                              },
                        child: const Text('浏览'),
                      ),
                    ],
                  ),
                ),
              if (providers.isNotEmpty) ...[
                Text(
                  '远程节点来源：${providers.join('、')}',
                  style: const TextStyle(color: muted),
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: allowProviders,
                  onChanged: saving
                      ? null
                      : (value) =>
                            setLocal(() => allowProviders = value ?? false),
                  title: const Text('允许获取这些远程节点来源'),
                ),
              ],
              if (error.isNotEmpty)
                Text(error, style: const TextStyle(color: red)),
            ],
          ),
        ),
      ),
    );
  } finally {
    url.dispose();
    file.dispose();
  }
}

Future<void> showSitesDialog(
  BuildContext context,
  ProbeController c,
) => showDialog<void>(
  context: context,
  builder: (dialogContext) => AnimatedBuilder(
    animation: c,
    builder: (dialogContext, _) => DialogShell(
      title: '网站管理',
      width: 820,
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext),
          child: const Text('关闭'),
        ),
      ],
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('选择轻量页面作为测试地址。', style: TextStyle(color: muted)),
              ),
              FilledButton(
                onPressed: () => showSiteEditor(dialogContext, c),
                child: const Text('＋ 添加网站'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          for (final site in c.sites) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          site['name'].toString(),
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          site['url'].toString(),
                          style: const TextStyle(fontSize: 13, color: muted),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '预期状态码：${(site['statuses'] as List).join(', ')}',
                          style: const TextStyle(fontSize: 13, color: muted),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Wrap(
                    spacing: 2,
                    children: [
                      TextButton(
                        onPressed: site['validator'] == 'chatgpt-trace'
                            ? null
                            : () =>
                                  showSiteEditor(dialogContext, c, site: site),
                        child: const Text('编辑'),
                      ),
                      TextButton(
                        onPressed: site['validator'] == 'chatgpt-trace'
                            ? null
                            : () async {
                                final confirmed = await showDialog<bool>(
                                  context: dialogContext,
                                  builder: (confirmation) => AlertDialog(
                                    title: const Text('移除网站？'),
                                    content: const Text('已有测速报告会保留。'),
                                    actions: [
                                      TextButton(
                                        onPressed: () =>
                                            Navigator.pop(confirmation, false),
                                        child: const Text('保留'),
                                      ),
                                      TextButton(
                                        onPressed: () =>
                                            Navigator.pop(confirmation, true),
                                        child: const Text('确认移除'),
                                      ),
                                    ],
                                  ),
                                );
                                if (confirmed == true) {
                                  await c.save(
                                    newSites: c.sites
                                        .where((s) => s['id'] != site['id'])
                                        .toList(),
                                  );
                                }
                              },
                        style: TextButton.styleFrom(foregroundColor: red),
                        child: const Text('移除'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
          ],
        ],
      ),
    ),
  ),
);

Future<void> showSiteEditor(
  BuildContext context,
  ProbeController c, {
  Json? site,
}) async {
  final name = TextEditingController(text: site?['name']?.toString() ?? '');
  final url = TextEditingController(text: site?['url']?.toString() ?? '');
  final statuses = TextEditingController(
    text: (site?['statuses'] as List? ?? [200]).join(', '),
  );
  String error = '';
  var saving = false;
  try {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocal) => DialogShell(
          title: site == null ? '添加网站' : '编辑网站',
          actions: [
            TextButton(
              onPressed: saving ? null : () => Navigator.pop(dialogContext),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: saving
                  ? null
                  : () async {
                      final text = name.text.trim();
                      if (text.isEmpty) {
                        setLocal(() => error = '请填写网站名称。');
                        return;
                      }
                      if (c.sites.any(
                        (s) =>
                            s['id'] != site?['id'] &&
                            s['name'].toString().toLowerCase() ==
                                text.toLowerCase(),
                      )) {
                        setLocal(() => error = '已存在同名网站，请使用不同名称。');
                        return;
                      }
                      final codes = statuses.text
                          .split(',')
                          .map((s) => int.tryParse(s.trim()))
                          .toList();
                      if (codes.any((n) => n == null || n < 100 || n > 599)) {
                        setLocal(() => error = '状态码必须为 100–599，用英文逗号分隔。');
                        return;
                      }
                      final item = <String, dynamic>{
                        'id':
                            site?['id'] ??
                            'custom-${DateTime.now().microsecondsSinceEpoch}',
                        'name': text,
                        'url': url.text.trim(),
                        'statuses': codes,
                        'validator': site?['validator'] ?? 'none',
                      };
                      final next = site == null
                          ? [...c.sites, item]
                          : c.sites
                                .map((s) => s['id'] == site['id'] ? item : s)
                                .toList();
                      setLocal(() => saving = true);
                      final ok = await c.save(newSites: next);
                      if (!dialogContext.mounted) return;
                      if (ok) {
                        Navigator.pop(dialogContext);
                      } else {
                        setLocal(() {
                          saving = false;
                          error = c.error;
                        });
                      }
                    },
              child: Text(saving ? '正在保存…' : '保存网站'),
            ),
          ],
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '使用不需要登录、且不含私人凭据的 HTTP / HTTPS 地址。',
                style: TextStyle(color: muted),
              ),
              const SizedBox(height: 20),
              LabeledField(
                label: '网站名称',
                child: TextField(
                  controller: name,
                  autofocus: true,
                  decoration: const InputDecoration(hintText: '例如：Notion'),
                ),
              ),
              LabeledField(
                label: '测试地址',
                child: TextField(
                  controller: url,
                  decoration: const InputDecoration(
                    hintText: 'https://www.notion.so/',
                  ),
                ),
              ),
              LabeledField(
                label: '预期状态码',
                hint: '多个状态码用英文逗号分隔。',
                child: TextField(controller: statuses),
              ),
              if (error.isNotEmpty)
                Text(error, style: const TextStyle(color: red)),
            ],
          ),
        ),
      ),
    );
  } finally {
    name.dispose();
    url.dispose();
    statuses.dispose();
  }
}

Future<void> showNodesDialog(BuildContext context, ProbeController c) async {
  final draft = {...c.options, 'node_names': <String>[]};
  final data = await c.preview(draftOptions: draft);
  if (!context.mounted || data == null) return;
  final nodes = (data['nodes'] as List)
      .map((n) => Json.from(n as Map))
      .toList();
  final selected = Set<String>.from(c.options['node_names'] as List);
  final search = TextEditingController();
  var query = '';
  try {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setLocal) {
          final visible = nodes
              .where(
                (n) => n['name'].toString().toLowerCase().contains(
                  query.toLowerCase(),
                ),
              )
              .toList();
          return DialogShell(
            title: '选择测速节点',
            width: 760,
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: () {
                  c.setOption('node_names', selected.toList());
                  Navigator.pop(dialogContext);
                },
                child: const Text('应用范围'),
              ),
            ],
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '只显示符合当前筛选的节点。未勾选时，测试全部匹配节点。',
                  style: TextStyle(color: muted),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: search,
                  decoration: const InputDecoration(hintText: '搜索节点名称'),
                  onChanged: (text) => setLocal(() => query = text),
                ),
                const SizedBox(height: 12),
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  spacing: 18,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      '匹配 ${nodes.length} 个 · 已勾选 ${selected.length} 个',
                      style: const TextStyle(fontSize: 13, color: muted),
                    ),
                    TextButton(
                      onPressed: () => setLocal(
                        () => selected.addAll(
                          visible.map((n) => n['name'].toString()),
                        ),
                      ),
                      child: const Text('全选当前列表'),
                    ),
                    TextButton(
                      onPressed: () => setLocal(selected.clear),
                      child: const Text('清空勾选'),
                    ),
                  ],
                ),
                const Divider(),
                if (visible.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 30),
                    child: Text('没有找到匹配节点，请调整搜索词或筛选范围。'),
                  ),
                for (final node in visible)
                  CheckboxListTile(
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    title: Text(node['name'].toString()),
                    subtitle: Text(
                      '${c.regionName(node['region'].toString())} · ${node['provider']?.toString() ?? '本地配置'}',
                    ),
                    value: selected.contains(node['name']),
                    onChanged: (_) => setLocal(() {
                      final name = node['name'].toString();
                      selected.contains(name)
                          ? selected.remove(name)
                          : selected.add(name);
                    }),
                  ),
              ],
            ),
          );
        },
      ),
    );
  } finally {
    search.dispose();
  }
}

Future<void> showDetailDialog(
  BuildContext context,
  Json row,
  ProbeController c,
) => showDialog<void>(
  context: context,
  builder: (dialogContext) => DialogShell(
    title: '请求详情',
    width: 820,
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(dialogContext),
        child: const Text('关闭'),
      ),
    ],
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          row['name'].toString(),
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 19),
        ),
        const SizedBox(height: 6),
        Text(
          '${row['site_name']} · ${row['url']}',
          style: const TextStyle(color: muted, fontSize: 13),
        ),
        const SizedBox(height: 20),
        Wrap(
          spacing: 35,
          runSpacing: 12,
          children: [
            Text('成功次数 ${row['successes']}/${row['total']}'),
            Text('响应延迟 ${formatMs(row['median_ms'])}'),
            Text('波动 ${formatMs(row['jitter_ms'])}'),
          ],
        ),
        const SizedBox(height: 18),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            columns: const [
              DataColumn(label: Text('轮次')),
              DataColumn(label: Text('结果')),
              DataColumn(label: Text('状态码')),
              DataColumn(label: Text('响应延迟')),
              DataColumn(label: Text('总耗时')),
              DataColumn(label: Text('说明')),
            ],
            rows: (row['samples'] as List).indexed.map((item) {
              final sample = item.$2 as Map;
              return DataRow(
                cells: [
                  DataCell(Text((item.$1 + 1).toString())),
                  DataCell(
                    Text(
                      sample['ok'] == true ? '成功' : '失败',
                      style: TextStyle(
                        color: sample['ok'] == true ? green : red,
                      ),
                    ),
                  ),
                  DataCell(
                    Text(
                      sample['status'] == 0 ? '—' : sample['status'].toString(),
                    ),
                  ),
                  DataCell(Text(formatMs(sample['ttfb_ms']))),
                  DataCell(Text(formatMs(sample['total_ms']))),
                  DataCell(
                    Text(
                      sample['reason']?.toString().isNotEmpty == true
                          ? sample['reason'].toString()
                          : '通过校验',
                    ),
                  ),
                ],
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          '响应延迟：从发出请求到收到网站首个字节的时间。数值越小，响应越快。',
          style: TextStyle(color: muted, fontSize: 13),
        ),
      ],
    ),
  ),
);

Future<void> showExportDialog(BuildContext context, ProbeController c) async {
  var format = 'csv', exporting = false;
  var includeFailures = true;
  String error = '';
  await showDialog<void>(
    context: context,
    builder: (dialogContext) => StatefulBuilder(
      builder: (dialogContext, setLocal) => DialogShell(
        title: '导出报告',
        actions: [
          TextButton(
            onPressed: exporting ? null : () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: exporting
                ? null
                : () async {
                    setLocal(() => exporting = true);
                    try {
                      final destination = await getSaveLocation(
                        suggestedName: 'ProxySprint-报告.$format',
                        acceptedTypeGroups: [
                          XTypeGroup(
                            label: format.toUpperCase(),
                            extensions: [format],
                          ),
                        ],
                      );
                      if (destination == null) {
                        if (dialogContext.mounted) {
                          setLocal(() => exporting = false);
                        }
                        return;
                      }
                      final data = await c.engine.call('export', {
                        'format': format,
                        'include_failures': includeFailures,
                      });
                      await File(destination.path).writeAsBytes(
                        base64Decode(data['content'].toString()),
                        flush: true,
                      );
                      if (dialogContext.mounted) Navigator.pop(dialogContext);
                      if (context.mounted) {
                        _toast(context, '已导出 ${format.toUpperCase()} 报告');
                      }
                    } catch (failure) {
                      if (dialogContext.mounted) {
                        setLocal(() {
                          exporting = false;
                          error = ProbeController.message(failure);
                        });
                      }
                    }
                  },
            child: Text(exporting ? '正在导出…' : '导出报告'),
          ),
        ],
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('导出上次完整测速报告。', style: TextStyle(color: muted)),
            const SizedBox(height: 20),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'csv', label: Text('CSV 表格')),
                ButtonSegment(value: 'json', label: Text('JSON 完整报告')),
              ],
              selected: {format},
              onSelectionChanged: exporting
                  ? null
                  : (value) => setLocal(() => format = value.first),
            ),
            const SizedBox(height: 20),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              title: const Text('包含未通过全部轮次的节点'),
              value: includeFailures,
              onChanged: exporting
                  ? null
                  : (value) => setLocal(() => includeFailures = value ?? true),
            ),
            const Text(
              '报告包含节点名称与测试地址，不包含节点密码。',
              style: TextStyle(fontSize: 13, color: muted),
            ),
            if (error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 14),
                child: Text(error, style: const TextStyle(color: red)),
              ),
          ],
        ),
      ),
    ),
  );
}
