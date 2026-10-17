import 'dart:io';

import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

import 'engine_bridge.dart';
import 'probe_controller.dart';
import 'probe_page.dart';
import 'ui_style.dart';

String? _argument(List<String> args, String key) {
  final position = args.indexOf(key);
  return position >= 0 && position + 1 < args.length
      ? args[position + 1]
      : null;
}

Future<void> main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();
  // 数据目录作为稳定标识保留，改名后继续读取已有设置和报告。
  final dataDirectory =
      _argument(args, '--data-dir') ??
      (Platform.isWindows && Platform.environment['LOCALAPPDATA'] != null
          ? '${Platform.environment['LOCALAPPDATA']!}/NodeScope'
          : '${Platform.environment['HOME']!}/Library/Application Support/NodeScope');
  ProbeController? controller;
  String? startupError;
  try {
    final bridge = await EngineBridge.launch(
      dataDirectory,
      developmentPython: _argument(args, '--engine-python'),
      developmentScript: _argument(args, '--engine-script'),
    );
    controller = ProbeController(bridge);
  } catch (failure) {
    startupError = ProbeController.message(failure);
  }
  await windowManager.setPreventClose(true);
  runApp(ProxySprintApp(controller: controller, startupError: startupError));
  await windowManager.waitUntilReadyToShow(
    const WindowOptions(
      size: Size(1240, 800),
      minimumSize: Size(800, 600),
      center: true,
      title: 'ProxySprint · 代理节点测速',
      backgroundColor: cream,
      titleBarStyle: TitleBarStyle.normal,
    ),
    () async {
      await windowManager.show();
      await windowManager.focus();
    },
  );
  if (controller != null) await controller.initialize();
}

class ProxySprintApp extends StatefulWidget {
  final ProbeController? controller;
  final String? startupError;
  const ProxySprintApp({super.key, this.controller, this.startupError});
  @override
  State<ProxySprintApp> createState() => _ProxySprintAppState();
}

class _ProxySprintAppState extends State<ProxySprintApp> with WindowListener {
  bool _closing = false;
  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);
  }

  @override
  void dispose() {
    windowManager.removeListener(this);
    super.dispose();
  }

  @override
  void onWindowClose() async {
    if (_closing) return;
    _closing = true;
    await windowManager.hide();
    widget.controller?.dispose();
    try {
      await widget.controller?.engine.close();
    } finally {
      await windowManager.destroy();
    }
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'ProxySprint · 代理节点测速',
    debugShowCheckedModeBanner: false,
    theme: probeTheme(),
    home: widget.controller != null
        ? ProbePage(controller: widget.controller!)
        : Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(36),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline, color: red, size: 40),
                    const SizedBox(height: 18),
                    Text(
                      widget.startupError ?? '本地测速引擎无法启动。',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: onWindowClose,
                      child: const Text('关闭应用'),
                    ),
                  ],
                ),
              ),
            ),
          ),
  );
}
