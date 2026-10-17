import 'package:flutter/material.dart';

import 'probe_controller.dart';
import 'probe_dialogs.dart';
import 'ui_style.dart';

class ProbePage extends StatefulWidget {
  final ProbeController controller;
  const ProbePage({super.key, required this.controller});
  @override
  State<ProbePage> createState() => _ProbePageState();
}

class _ProbePageState extends State<ProbePage> {
  bool advanced = false;
  final _settingsScroll = ScrollController();
  final _resultsScroll = ScrollController();
  @override
  void dispose() {
    _settingsScroll.dispose();
    _resultsScroll.dispose();
    super.dispose();
  }

  ProbeController get c => widget.controller;
  void toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), duration: const Duration(seconds: 3)),
    );
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: c,
    builder: (context, _) => Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 900;
          if (desktop) {
            return Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1560),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _header(),
                      _connectionBar(),
                      const SizedBox(height: 20),
                      Expanded(
                        child: c.ready
                            ? Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  SizedBox(
                                    width: 350,
                                    child: Column(
                                      children: [
                                        Expanded(
                                          child: Scrollbar(
                                            controller: _settingsScroll,
                                            child: SingleChildScrollView(
                                              key: const Key('settings-scroll'),
                                              controller: _settingsScroll,
                                              padding: const EdgeInsets.only(
                                                bottom: 24,
                                                right: 10,
                                              ),
                                              child: _configuration(
                                                includeActions: false,
                                              ),
                                            ),
                                          ),
                                        ),
                                        const Divider(height: 24),
                                        Padding(
                                          padding: const EdgeInsets.only(
                                            right: 10,
                                            bottom: 18,
                                          ),
                                          child: _samplingAndActions(),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 24),
                                  Expanded(
                                    child: Container(
                                      padding: const EdgeInsets.only(left: 24),
                                      decoration: const BoxDecoration(
                                        border: Border(
                                          left: BorderSide(color: border),
                                        ),
                                      ),
                                      child: Scrollbar(
                                        controller: _resultsScroll,
                                        child: SingleChildScrollView(
                                          key: const Key('results-scroll'),
                                          controller: _resultsScroll,
                                          padding: const EdgeInsets.only(
                                            bottom: 24,
                                            right: 10,
                                          ),
                                          child: Column(
                                            children: [
                                              _results(),
                                              const SizedBox(height: 30),
                                              _footer(),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              )
                            : Center(
                                child: c.error.isEmpty
                                    ? const CircularProgressIndicator()
                                    : _notice(c.error, failure: true),
                              ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }
          return SingleChildScrollView(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1560),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _header(),
                      _connectionBar(),
                      const SizedBox(height: 20),
                      if (c.ready)
                        Column(
                          children: [
                            _configuration(),
                            const SizedBox(height: 28),
                            const Divider(),
                            _results(),
                          ],
                        )
                      else if (c.error.isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(60),
                          child: Center(child: CircularProgressIndicator()),
                        )
                      else
                        _notice(c.error, failure: true),
                      const SizedBox(height: 30),
                      _footer(),
                      const SizedBox(height: 18),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    ),
  );

  Widget _header() => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(vertical: 18),
    child: Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 30,
      runSpacing: 10,
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.explore_outlined, color: blue, size: 34),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('ProxySprint', style: heading(25)),
                const Text(
                  '代理节点测速 · 按网站选出更快、更稳的节点',
                  style: TextStyle(fontSize: 12, color: muted),
                ),
              ],
            ),
          ],
        ),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton(
              onPressed: c.running || c.busy || !c.ready
                  ? null
                  : () async {
                      if (await c.save()) toast('网站与筛选设置已保存');
                    },
              child: const Text('保存设置'),
            ),
            const SizedBox(width: 6),
            OutlinedButton.icon(
              onPressed: c.running || c.busy || !c.ready
                  ? null
                  : () => showConnectionDialog(context, c),
              icon: const Icon(Icons.settings_outlined, size: 18),
              label: const Text('连接设置'),
            ),
          ],
        ),
      ],
    ),
  );

  Widget _connectionBar() {
    final connected = (c.catalog?['version']?.toString() ?? '').isNotEmpty;
    final count = (c.catalog?['nodes'] as List? ?? []).length;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: paper,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        children: [
          const Icon(Icons.power_outlined, color: muted, size: 21),
          const SizedBox(width: 12),
          Expanded(
            child: Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 5,
              children: [
                Text(
                  c.source['type'] == 'url'
                      ? '订阅链接'
                      : c.source['type'] == 'file'
                      ? '配置文件'
                      : c.catalog == null
                      ? '节点来源'
                      : 'Clash Verge Rev',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  c.busy
                      ? '正在读取节点…'
                      : connected
                      ? '已连接 · $count 个可测节点'
                      : '请导入节点，或连接客户端',
                  style: TextStyle(
                    fontSize: 13,
                    color: connected ? green : muted,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          OutlinedButton.icon(
            onPressed: c.busy || c.running || !c.ready
                ? null
                : () => showSourceDialog(context, c),
            icon: const Icon(Icons.add_link, size: 18),
            label: const Text('导入节点'),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: c.busy || c.running || !c.ready ? null : c.refreshSource,
            icon: c.busy
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh, size: 18),
            label: const Text('刷新节点'),
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(String number, String title, Widget trailing) => Row(
    children: [
      Container(
        width: 30,
        height: 30,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: yellowTint,
          borderRadius: BorderRadius.circular(7),
        ),
        child: Text(number, style: heading(16)),
      ),
      const SizedBox(width: 10),
      Expanded(child: Text(title, style: heading(18))),
      trailing,
    ],
  );

  Widget _configuration({bool includeActions = true}) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      IgnorePointer(
        ignoring: c.running || c.busy,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle(
              '01',
              '测试目标',
              TextButton(
                onPressed: () => showSitesDialog(context, c),
                child: const Text('管理网站 ›'),
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 0,
              children: c.sites.map((site) {
                final id = site['id'].toString();
                return SizedBox(
                  width: 160,
                  child: InkWell(
                    onTap: () => c.toggleSite(id),
                    child: Row(
                      children: [
                        Checkbox(
                          value: c.selectedSites.contains(id),
                          visualDensity: VisualDensity.compact,
                          onChanged: (_) => c.toggleSite(id),
                        ),
                        Flexible(child: Text(site['name'].toString())),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
            const SizedBox(height: 20),
            _sectionTitle(
              '02',
              '节点范围',
              TextButton(
                onPressed: () => c.setOption('regions', <String>[]),
                child: const Text('全部地区'),
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: c.regions.map((region) {
                final id = region['id'].toString();
                final selected = (c.options['regions'] as List).contains(id);
                return FilterChip(
                  label: Text(
                    region['name'].toString(),
                    style: const TextStyle(fontSize: 13),
                  ),
                  selected: selected,
                  selectedColor: yellowTint,
                  backgroundColor: paper,
                  side: BorderSide(
                    color: selected ? const Color(0xffebd373) : border,
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  onSelected: (_) => c.toggleRegion(id),
                );
              }).toList(),
            ),
            const SizedBox(height: 18),
            _scopeSelect('策略组', 'group', [
              for (final item in (c.catalog?['groups'] as List? ?? []))
                (item as Map)['name'].toString(),
            ], '全部策略组'),
            const SizedBox(height: 12),
            _scopeSelect(
              '来源',
              'provider',
              List<String>.from(c.catalog?['providers'] as List? ?? []),
              '全部来源',
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () => setState(() => advanced = !advanced),
              style: TextButton.styleFrom(
                foregroundColor: ink,
                padding: const EdgeInsets.symmetric(vertical: 10),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('高级筛选'),
                  Icon(
                    advanced ? Icons.expand_more : Icons.chevron_right,
                    size: 17,
                  ),
                ],
              ),
            ),
            if (advanced) ..._advancedFields(),
          ],
        ),
      ),
      if (includeActions) ...[
        const SizedBox(height: 16),
        const Divider(),
        const SizedBox(height: 12),
        _samplingAndActions(),
      ],
    ],
  );

  Widget _samplingAndActions() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      IgnorePointer(
        ignoring: c.running || c.busy,
        child: Row(
          children: [
            Expanded(child: _sampling('测试轮次', 'rounds', [1, 3, 5, 10], '轮')),
            const SizedBox(width: 10),
            Expanded(
              child: _sampling('并发数', 'workers', [1, 2, 4, 8, 16], '并发'),
            ),
            const SizedBox(width: 10),
            Expanded(child: _sampling('超时时间', 'timeout', [5, 8, 15, 30], '秒')),
          ],
        ),
      ),
      const SizedBox(height: 16),
      // 停止按钮独立响应，不受配置区 IgnorePointer 影响。
      if (!c.running)
        Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: c.busy ? null : c.start,
                icon: const Icon(Icons.play_arrow, size: 20),
                label: const Text('开始测速', style: TextStyle(fontSize: 16)),
              ),
            ),
            const SizedBox(width: 10),
            OutlinedButton.icon(
              onPressed: c.busy ? null : () => showNodesDialog(context, c),
              icon: const Icon(Icons.list, size: 20),
              label: const Text('预览范围'),
            ),
          ],
        )
      else
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: c.stopping ? null : c.stop,
            icon: const Icon(Icons.stop, size: 20),
            label: Text(c.stopping ? '正在停止…' : '停止测速'),
          ),
        ),
      const SizedBox(height: 10),
      Text(
        c.catalog == null ? '导入节点或连接客户端后可预览范围' : '已读取节点清单 · 地区和其他筛选取交集',
        style: const TextStyle(fontSize: 13, color: muted),
      ),
    ],
  );

  Widget _scopeSelect(
    String label,
    String key,
    List<String> values,
    String defaultLabel,
  ) {
    final selected = c.options[key]?.toString() ?? '';
    final items = {'', ...values, if (selected.isNotEmpty) selected};
    return Row(
      children: [
        SizedBox(width: 70, child: Text(label)),
        Expanded(
          child: DropdownButtonFormField<String>(
            initialValue: selected,
            isExpanded: true,
            key: ValueKey('$key-$selected-${items.length}'),
            items: items
                .map(
                  (value) => DropdownMenuItem(
                    value: value,
                    child: Text(
                      value.isEmpty ? defaultLabel : value,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: (value) => c.setOption(key, value ?? ''),
          ),
        ),
      ],
    );
  }

  List<Widget> _advancedFields() => [
    LabeledField(
      label: '名称包含',
      hint: '多个关键词用英文逗号分隔。',
      child: TextFormField(
        initialValue: c.options['include']?.toString(),
        decoration: const InputDecoration(hintText: '留空不限制，例如：东京, 专线'),
        onChanged: (value) => c.setOption('include', value),
      ),
    ),
    LabeledField(
      label: '名称排除',
      child: TextFormField(
        initialValue: c.options['exclude']?.toString(),
        decoration: const InputDecoration(hintText: '留空不排除，例如：备用, 测试'),
        onChanged: (value) => c.setOption('exclude', value),
      ),
    ),
    LabeledField(
      label: '最多节点数',
      hint: '0 表示不限制，单次最多 200 个候选。',
      child: TextFormField(
        initialValue: c.options['limit'].toString(),
        keyboardType: TextInputType.number,
        onChanged: (value) => c.setOption('limit', int.tryParse(value) ?? 0),
      ),
    ),
    Row(
      children: [
        Expanded(
          child: Text(
            (c.options['node_names'] as List).isEmpty
                ? '全部匹配节点'
                : '手动选择 ${(c.options['node_names'] as List).length} 个',
            style: const TextStyle(fontSize: 13, color: muted),
          ),
        ),
        TextButton(
          onPressed: () => showNodesDialog(context, c),
          child: const Text('手动选择'),
        ),
      ],
    ),
  ];

  Widget _sampling(String label, String key, List<int> choices, String unit) {
    final value = (c.options[key] as num).toInt();
    final items = {...choices, value}.toList()..sort();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 13, color: muted)),
        const SizedBox(height: 7),
        DropdownButtonFormField<int>(
          initialValue: value,
          key: ValueKey('$key-$value'),
          isExpanded: true,
          items: items
              .map(
                (n) => DropdownMenuItem(
                  value: n,
                  child: Text('$n $unit', style: const TextStyle(fontSize: 13)),
                ),
              )
              .toList(),
          onChanged: (n) {
            if (n != null) c.setOption(key, n);
          },
        ),
      ],
    );
  }

  Widget _results() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Expanded(child: Text('测速结果', style: heading(24))),
          OutlinedButton.icon(
            onPressed: c.report == null || c.running
                ? null
                : () => showExportDialog(context, c),
            icon: const Icon(Icons.download_outlined, size: 18),
            label: const Text('导出报告'),
          ),
        ],
      ),
      const SizedBox(height: 16),
      Wrap(
        children: c.resultSites.map((site) {
          final id = site['id'].toString();
          final active = c.activeSite == id;
          return Container(
            decoration: BoxDecoration(
              color: active ? blueTint : null,
              border: Border(
                bottom: BorderSide(
                  color: active ? blue : Colors.transparent,
                  width: 2,
                ),
              ),
            ),
            child: TextButton(
              onPressed: () => c.selectResultSite(id),
              style: TextButton.styleFrom(
                foregroundColor: active ? blue : muted,
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 15,
                ),
              ),
              child: Text(site['name'].toString()),
            ),
          );
        }).toList(),
      ),
      const Divider(height: 1),
      const SizedBox(height: 16),
      if (c.error.isNotEmpty) _notice(c.error, failure: true),
      if (c.running) _runningNotice(),
      if (c.cancelled)
        _notice(c.report == null ? '测速已停止，本次未生成完整报告。' : '测速已停止，下方保留上次完整报告。'),
      if (c.recommendation != null) _recommendation(),
      if (c.rows.isEmpty) _emptyState(),
      if (c.rows.isNotEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Wrap(
            alignment: WrapAlignment.spaceBetween,
            spacing: 30,
            children: [
              Text(
                _reportLabel(),
                style: const TextStyle(fontSize: 13, color: muted),
              ),
              const Text('成功率优先', style: TextStyle(fontSize: 13, color: muted)),
            ],
          ),
        ),
      _table(),
      if (c.warnings.isNotEmpty)
        Padding(
          padding: const EdgeInsets.only(top: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final warning in c.warnings)
                Padding(
                  padding: const EdgeInsets.only(bottom: 5),
                  child: Text(
                    warning,
                    style: const TextStyle(fontSize: 13, color: muted),
                  ),
                ),
            ],
          ),
        ),
    ],
  );

  String _reportLabel() {
    final count = c.rows.length;
    final date = DateTime.tryParse(c.report?['created_at']?.toString() ?? '');
    if (c.running || date == null) return '$count 条结果';
    final time = date.toLocal().toString().split('.').first;
    return '$count 条结果 · 完整报告 $time';
  }

  Widget _runningNotice() => Container(
    padding: const EdgeInsets.all(15),
    margin: const EdgeInsets.only(bottom: 16),
    decoration: BoxDecoration(
      color: blueTint,
      borderRadius: BorderRadius.circular(8),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(
              child: Text(
                '正在测速',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            TextButton(
              onPressed: c.stopping ? null : c.stop,
              child: Text(c.stopping ? '正在停止…' : '停止测速'),
            ),
          ],
        ),
        Text(
          c.progressText,
          style: const TextStyle(fontSize: 13, color: muted),
        ),
        const SizedBox(height: 12),
        LinearProgressIndicator(
          value: c.total == 0 ? null : c.completed / c.total,
          minHeight: 5,
          borderRadius: BorderRadius.circular(3),
        ),
        const SizedBox(height: 9),
        Text(
          '已完成 ${c.completed} / ${c.total} 组节点 × 网站',
          style: const TextStyle(fontSize: 13, color: muted),
        ),
      ],
    ),
  );

  Widget _notice(String message, {bool failure = false}) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(15),
    margin: const EdgeInsets.only(bottom: 16),
    decoration: BoxDecoration(
      color: failure ? const Color(0xfffff0f0) : const Color(0xfffaf6eb),
      borderRadius: BorderRadius.circular(8),
    ),
    child: Text(message, style: TextStyle(color: failure ? red : ink)),
  );

  Widget _recommendation() {
    final recommendation = c.recommendation!;
    return Padding(
      padding: const EdgeInsets.only(top: 2, bottom: 12),
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      c.cancelled ? '✓ 上次完整报告的推荐' : '✓ 本次推荐',
                      style: const TextStyle(color: green, fontSize: 13),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      recommendation['name'].toString(),
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 19,
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      '全部轮次成功',
                      style: TextStyle(fontSize: 13, color: muted),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    formatMs(recommendation['median_ms']),
                    style: const TextStyle(
                      fontSize: 28,
                      color: blue,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const Text(
                    '响应延迟（中位数）',
                    style: TextStyle(fontSize: 13, color: muted),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 17),
          const Divider(height: 1),
        ],
      ),
    );
  }

  Widget _emptyState() => Padding(
    padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 12),
    child: Center(
      child: Column(
        children: [
          const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.dns_outlined, size: 48, color: muted),
              SizedBox(width: 28),
              Icon(Icons.arrow_forward, color: muted),
              SizedBox(width: 28),
              Icon(Icons.public, size: 45, color: muted),
            ],
          ),
          const SizedBox(height: 26),
          Text(
            c.running ? '正在等待首组结果' : '选好网站和节点，开始测速',
            style: heading(23),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 12),
          const Text(
            '先导入订阅或配置文件，再选择你常用的网站。\n完成后查看各网站的节点排名与推荐。',
            style: TextStyle(color: muted),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    ),
  );

  Widget _table() => Container(
    decoration: BoxDecoration(
      color: paper,
      border: Border.all(color: border),
      borderRadius: BorderRadius.circular(8),
    ),
    clipBehavior: Clip.antiAlias,
    child: LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            minWidth: constraints.maxWidth > 560 ? constraints.maxWidth : 560,
          ),
          child: DataTable(
            headingRowColor: const WidgetStatePropertyAll(Color(0xfffaf6eb)),
            headingRowHeight: 44,
            dataRowMinHeight: 64,
            dataRowMaxHeight: 70,
            columnSpacing: 18,
            horizontalMargin: 16,
            dividerThickness: .6,
            columns: [
              _sortColumn('节点', 'name'),
              const DataColumn(label: Text('地区')),
              const DataColumn(label: Text('成功率')),
              _sortColumn('响应延迟', 'median_ms'),
              const DataColumn(label: Text('波动')),
            ],
            rows: c.rows
                .map(
                  (row) => DataRow(
                    color: WidgetStatePropertyAll(_rowColor(row)),
                    cells: [
                      DataCell(
                        SizedBox(
                          width: 215,
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                row['name'].toString(),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                              Text(
                                (row['provider']?.toString() ?? '').isEmpty
                                    ? '本地配置'
                                    : row['provider'].toString(),
                                style: const TextStyle(
                                  fontSize: 13,
                                  color: muted,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                        onTap: () => showDetailDialog(context, row, c),
                      ),
                      DataCell(Text(c.regionName(row['region'].toString()))),
                      DataCell(
                        Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${((row['success_rate'] as num) * 100).toStringAsFixed(0)}%',
                              style: TextStyle(
                                color: row['eligible'] == true ? green : red,
                              ),
                            ),
                            Text(
                              '${row['successes']}/${row['total']}',
                              style: const TextStyle(
                                fontSize: 13,
                                color: muted,
                              ),
                            ),
                          ],
                        ),
                      ),
                      DataCell(Text(formatMs(row['median_ms']))),
                      DataCell(Text(formatMs(row['jitter_ms']))),
                    ],
                  ),
                )
                .toList(),
          ),
        ),
      ),
    ),
  );

  DataColumn _sortColumn(String label, String key) => DataColumn(
    label: InkWell(
      onTap: () => c.toggleSort(key),
      child: Row(
        children: [
          Text(label),
          if (c.sortKey == key) ...[
            const SizedBox(width: 7),
            Text(c.ascending ? '↑' : '↓', style: const TextStyle(color: blue)),
          ],
        ],
      ),
    ),
  );

  Color? _rowColor(Json row) {
    if (row['eligible'] != true) return const Color(0xfffff8f4);
    final recommendation = c.recommendation;
    return recommendation != null && recommendation['name'] == row['name']
        ? const Color(0xfff5f8ee)
        : null;
  }

  Widget _footer() => Column(
    children: [
      const Divider(),
      const SizedBox(height: 12),
      const Wrap(
        alignment: WrapAlignment.spaceBetween,
        spacing: 60,
        runSpacing: 7,
        children: [
          Text(
            'ⓘ 地区依据节点名称识别 · 推荐不会切换主节点',
            style: TextStyle(fontSize: 13, color: muted),
          ),
          Text(
            '设计规范：ESTHER不二 · CC BY-NC-SA 4.0',
            style: TextStyle(fontSize: 13, color: muted),
          ),
        ],
      ),
    ],
  );
}
