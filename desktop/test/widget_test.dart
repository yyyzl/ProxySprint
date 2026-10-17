import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:proxy_sprint/engine_bridge.dart';
import 'package:proxy_sprint/probe_controller.dart';
import 'package:proxy_sprint/probe_page.dart';
import 'package:proxy_sprint/ui_style.dart';

class FakeEngine implements EngineApi {
  bool failSave = false;
  bool stopped = false;
  bool failImport = false;
  bool failCatalog = false;
  bool requireProviders = false;
  List<String> commands = [];
  final settings = <String, dynamic>{
    'sites': [
      {
        'id': 'chatgpt',
        'name': 'ChatGPT',
        'url': 'https://chatgpt.com/cdn-cgi/trace',
        'statuses': [200],
        'validator': 'chatgpt-trace',
      },
      {
        'id': 'github',
        'name': 'GitHub',
        'url': 'https://github.com/',
        'statuses': [200],
        'validator': 'none',
      },
    ],
    'regions': [
      {'id': 'jp', 'name': '日本'},
      {'id': 'sg', 'name': '新加坡'},
    ],
    'options': {
      'regions': ['jp', 'sg'],
      'group': '',
      'provider': '',
      'include': '',
      'exclude': '',
      'limit': 0,
      'rounds': 3,
      'workers': 4,
      'timeout': 8,
      'node_names': [],
    },
    'connection': {
      'binary_path': '',
      'config_path': '',
      'core_dir': '',
      'controller': '',
      'named_pipe': '',
      'unix_socket': '',
      'interface': '',
    },
    'last_report': null,
    'source': {'type': 'client'},
    'warnings': <String>[],
  };
  @override
  Future<Json> call(String command, [Json payload = const {}]) async {
    commands.add(command);
    switch (command) {
      case 'bootstrap':
        return settings;
      case 'catalog':
        if (failCatalog) throw StateError('未找到 Clash/Mihomo 配置，请指定生效配置。');
        return {
          'connection': settings['connection'],
          'nodes': [],
          'groups': [],
          'providers': [],
          'warnings': [],
          'version': 'test',
        };
      case 'settings':
        if (failSave) throw StateError('保存失败');
        return payload;
      case 'import_source':
        if (failImport) throw StateError('订阅获取失败');
        if (requireProviders) {
          return {
            'requires_provider_download': true,
            'providers': ['source-a'],
          };
        }
        final saved = {...settings, 'source': payload['source']};
        return {
          'settings': saved,
          'catalog': {
            'connection': settings['connection'],
            'nodes': [
              {
                'name': '日本 fixture',
                'region': 'jp',
                'type': 'http',
                'provider': '',
              },
            ],
            'groups': [],
            'providers': [],
            'warnings': [],
            'version': '独立 Mihomo',
          },
        };
      case 'start':
        stopped = false;
        return {'id': 'test', 'running': true};
      case 'stop':
        stopped = true;
        return {'stopping': true};
      case 'job':
        return {
          'running': !stopped,
          'events': [],
          'progress': {'completed': 0, 'total': 2},
          'report': null,
          'error': stopped ? '已取消' : null,
        };
      case 'preview':
        return {'nodes': [], 'count': 0, 'warnings': []};
    }
    throw StateError(command);
  }

  @override
  Future<void> close() async {}
}

void main() {
  setUpAll(() async {
    if (Platform.environment['PROXYSPRINT_UI_CAPTURE'] == null ||
        !Platform.isWindows) {
      return;
    }
    for (final entry in {
      'Microsoft YaHei': 'C:/Windows/Fonts/msyh.ttc',
      'SimSun': 'C:/Windows/Fonts/simsun.ttc',
      'Ahem': 'C:/Windows/Fonts/msyh.ttc',
      'Roboto': 'C:/Windows/Fonts/msyh.ttc',
      'Segoe UI': 'C:/Windows/Fonts/msyh.ttc',
      'MaterialIcons': '../.tools/flutter/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf',
    }.entries) {
      final font = FontLoader(entry.key)
        ..addFont(
          Future.value(
            ByteData.sublistView(File(entry.value).readAsBytesSync()),
          ),
        );
      await font.load();
    }
  });
  test('首次启动没有客户端时提示导入，手动配置失败仍显示错误', () async {
    for (final manual in [false, true]) {
      final engine = FakeEngine()..failCatalog = true;
      if (manual) {
        (engine.settings['connection'] as Map)['config_path'] =
            '/missing/fixture.yaml';
      }
      final controller = ProbeController(engine);
      await controller.initialize();
      expect(controller.ready, true);
      if (manual) {
        expect(controller.error, contains('未找到'));
      } else {
        expect(controller.error, isEmpty);
        expect(controller.warnings.single, contains('导入订阅'));
      }
      controller.dispose();
    }
  });
  test('导入成功更新节点来源，保留上次报告', () async {
    final controller = ProbeController(FakeEngine());
    await controller.initialize();
    final previous = <String, dynamic>{'rows': [], 'recommendations': []};
    controller.report = previous;
    final result = await controller.importSource({
      'type': 'url',
      'location': 'https://example.invalid/sub',
    });
    expect(result, isNotNull);
    expect(controller.source['type'], 'url');
    expect((controller.catalog!['nodes'] as List).length, 1);
    expect(identical(controller.report, previous), true);
    controller.dispose();
  });
  test('失败或待确认的导入保留当前来源和节点', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    final previous = controller.catalog;
    engine.failImport = true;
    expect(
      await controller.importSource({
        'type': 'url',
        'location': 'https://example.invalid/sub',
      }),
      isNull,
    );
    expect(controller.source['type'], 'client');
    expect(identical(controller.catalog, previous), true);
    engine.failImport = false;
    engine.requireProviders = true;
    final result = await controller.importSource({
      'type': 'url',
      'location': 'https://example.invalid/sub',
    });
    expect(result!['requires_provider_download'], true);
    expect(controller.source['type'], 'client');
    expect(identical(controller.catalog, previous), true);
    controller.dispose();
  });
  testWidgets('导入窗口提供链接与文件入口，链接默认隐藏', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 860));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final controller = ProbeController(FakeEngine());
    await controller.initialize();
    await tester.pumpWidget(
      MaterialApp(
        theme: probeTheme(),
        home: ProbePage(controller: controller),
      ),
    );
    await tester.tap(find.text('导入节点'));
    await tester.pumpAndSettle();
    expect(find.text('订阅链接'), findsOneWidget);
    expect(find.text('配置文件'), findsOneWidget);
    expect(tester.widget<TextField>(find.byType(TextField)).obscureText, true);
    await tester.tap(find.text('配置文件'));
    await tester.pumpAndSettle();
    expect(find.text('浏览'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
  });
  testWidgets('窄窗口左侧停止按钮可以取消任务', (tester) async {
    await tester.binding.setSurfaceSize(const Size(880, 640));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    await controller.start();
    await tester.pumpWidget(
      MaterialApp(
        theme: probeTheme(),
        home: ProbePage(controller: controller),
      ),
    );
    final stop = find.widgetWithText(FilledButton, '停止测速');
    await tester.ensureVisible(stop);
    await tester.tap(stop);
    expect(engine.stopped, true);
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
  });
  for (final size in [const Size(1280, 860), const Size(960, 600)]) {
    testWidgets('右侧长结果滚动时左侧设置保持在 $size 原位', (tester) async {
      await tester.binding.setSurfaceSize(size);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final controller = ProbeController(FakeEngine());
      await controller.initialize();
      controller.report = {
        'recommendations': [
          {'name': '日本 测试节点 0', 'site_id': 'chatgpt', 'median_ms': 10},
        ],
        'rows': List.generate(
          30,
          (i) => {
            'name': '日本 测试节点 $i',
            'region': 'jp',
            'provider': '本地测试',
            'site_id': 'chatgpt',
            'site_name': 'ChatGPT',
            'eligible': true,
            'median_ms': 10 + i,
            'jitter_ms': 1,
            'success_rate': 1.0,
            'successes': 3,
            'total': 3,
            'samples': [],
          },
        ),
      };
      final capture = GlobalKey();
      await tester.pumpWidget(
        RepaintBoundary(
          key: capture,
          child: MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: probeTheme(),
            home: ProbePage(controller: controller),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final folder = Platform.environment['PROXYSPRINT_UI_CAPTURE'];
      Future<void> saveCapture(String name) async {
        if (folder == null) return;
        final boundary =
            capture.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
        await tester.runAsync(() async {
          final image = await boundary.toImage();
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          await File('$folder/$name-${size.width.toInt()}.png')
              .writeAsBytes(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }

      await saveCapture('overview');
      final before = tester.getTopLeft(find.text('测试目标'));
      await tester.drag(
        find.byKey(const Key('results-scroll')),
        const Offset(0, -1000),
      );
      await tester.pumpAndSettle();
      expect(tester.getTopLeft(find.text('测试目标')), before);
      expect(find.text('测试目标').hitTestable(), findsOneWidget);
      expect(find.text('开始测速').hitTestable(), findsOneWidget);
      expect(tester.takeException(), isNull);
      await saveCapture('layout');
      final actionPosition = tester.getTopLeft(find.text('开始测速'));
      await tester.drag(
        find.byKey(const Key('settings-scroll')),
        const Offset(0, -600),
      );
      await tester.pumpAndSettle();
      expect(find.text('高级筛选').hitTestable(), findsOneWidget);
      expect(tester.getTopLeft(find.text('开始测速')), actionPosition);
      await tester.pumpWidget(const SizedBox());
      controller.dispose();
    });
  }
  test('启动后优先展示上次报告的网站', () async {
    final engine = FakeEngine();
    engine.settings['last_report'] = {
      'rows': [
        {
          'site_id': 'github',
          'name': '保存节点',
          'eligible': true,
          'median_ms': 10,
        },
      ],
      'recommendations': [],
    };
    final controller = ProbeController(engine);
    await controller.initialize();
    expect(controller.activeSite, 'github');
    expect(controller.rows.length, 1);
    controller.dispose();
  });
  test('快速连续点击不会启动重复任务', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    await Future.wait([controller.start(), controller.start()]);
    expect(engine.commands.where((command) => command == 'start').length, 1);
    controller.dispose();
  });
  test('设置保存失败保留当前网站配置', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    engine.failSave = true;
    final ok = await controller.save(newSites: []);
    expect(ok, false);
    expect(controller.sites.length, 2);
    expect(controller.error, '保存失败');
    controller.dispose();
  });
  test('取消保留上次完整报告', () async {
    final controller = ProbeController(FakeEngine());
    await controller.initialize();
    final previous = <String, dynamic>{
      'rows': [],
      'recommendations': [],
      'created_at': '2026-10-14T02:00:00Z',
    };
    controller.report = previous;
    await controller.start();
    await controller.stop();
    await controller.poll();
    expect(controller.running, false);
    expect(controller.cancelled, true);
    expect(identical(controller.report, previous), true);
    controller.dispose();
  });
  test('空网站选择不能启动测速', () async {
    final engine = FakeEngine();
    final controller = ProbeController(engine);
    await controller.initialize();
    controller.selectedSites.clear();
    await controller.start();
    expect(engine.commands.contains('start'), false);
    expect(controller.error, contains('至少选择'));
    controller.dispose();
  });
  test('排序不会改变引擎推荐且失败节点仍在末尾', () {
    final controller = ProbeController(FakeEngine());
    controller.report = {
      'rows': [
        {'name': '稳', 'site_id': 'chatgpt', 'eligible': true, 'median_ms': 90},
        {'name': '波动', 'site_id': 'chatgpt', 'eligible': true, 'median_ms': 80},
        {
          'name': '失败',
          'site_id': 'chatgpt',
          'eligible': false,
          'median_ms': 10,
        },
      ],
      'recommendations': [
        {'site_id': 'chatgpt', 'name': '稳'},
      ],
    };
    expect(controller.recommendation!['name'], '稳');
    controller.toggleSort('median_ms');
    expect(controller.rows.last['name'], '失败');
    expect(controller.recommendation!['name'], '稳');
    controller.dispose();
  });
  for (final size in [const Size(1280, 860), const Size(880, 640)]) {
    testWidgets('主界面在 $size 自然排版且没有虚构结果', (tester) async {
      await tester.binding.setSurfaceSize(size);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final controller = ProbeController(FakeEngine());
      await controller.initialize();
      await tester.pumpWidget(
        MaterialApp(
          theme: probeTheme(),
          home: ProbePage(controller: controller),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('ProxySprint'), findsOneWidget);
      expect(find.text('开始测速'), findsOneWidget);
      expect(find.text('首字节从快到慢'), findsNothing);
      expect(find.textContaining('下方还有结果'), findsNothing);
      expect(find.text('本次推荐'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('高级筛选'));
      await tester.pumpAndSettle();
      expect(find.text('名称包含'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      controller.dispose();
    });
  }
}
