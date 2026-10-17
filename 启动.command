#!/bin/bash
# macOS launcher: local venv only; never edits Clash or system Python.
set -euo pipefail
cd "$(dirname "$0")"
failed() {
  printf '\n启动失败。请查看上面的错误；说明见 README.md。\n'
  read -r -p '按回车关闭窗口… ' _ || true
}
trap failed ERR
if ! command -v python3 >/dev/null 2>&1; then
  printf '需要 Python 3.10 或更新版本。请先安装 Python，再重新打开本文件。\n'
  failed
  exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 10), "需要 Python 3.10 或更新版本"'
if [ ! -x .venv/bin/python ]; then
  printf '首次启动：正在创建此目录专用的 Python 环境…\n'
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import yaml' >/dev/null 2>&1; then
  printf '首次启动：正在安装 YAML 配置读取依赖 PyYAML，需要联网…\n'
  .venv/bin/python -m pip install -r requirements.txt
fi
printf '\nProxySprint · 代理节点测速已启动。浏览器将自动打开；保留这个终端窗口。\n按 Control+C 退出，不会修改当前 Clash 线路。\n\n'
exec .venv/bin/python server.py
