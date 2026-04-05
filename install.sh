#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ID="obsidian-llm-agent"
PLUGIN_SRC_DIR="$REPO_ROOT/plugins/$PLUGIN_ID"
DEFAULT_VAULT_PATH="$REPO_ROOT/../obsidian"
VAULT_PATH="${1:-$DEFAULT_VAULT_PATH}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少依赖命令: $1" >&2
    exit 1
  fi
}

require_command python3
require_command node
require_command npm

VAULT_PATH="$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$VAULT_PATH")"
VENV_DIR="$REPO_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
PLUGIN_DEST_DIR="$VAULT_PATH/.obsidian/plugins/$PLUGIN_ID"
PLUGIN_DATA_PATH="$PLUGIN_DEST_DIR/data.json"
COMMUNITY_PLUGINS_PATH="$VAULT_PATH/.obsidian/community-plugins.json"

echo "==> Repo root: $REPO_ROOT"
echo "==> Vault path: $VAULT_PATH"

mkdir -p \
  "$VAULT_PATH/.obsidian/plugins" \
  "$VAULT_PATH/raw/articles" \
  "$VAULT_PATH/raw/papers" \
  "$VAULT_PATH/raw/code" \
  "$VAULT_PATH/raw/images" \
  "$VAULT_PATH/raw/misc" \
  "$VAULT_PATH/wiki/concepts" \
  "$VAULT_PATH/wiki/summaries" \
  "$VAULT_PATH/wiki/relations" \
  "$VAULT_PATH/output/reports" \
  "$VAULT_PATH/output/charts" \
  "$VAULT_PATH/output/slides"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> 创建 Python 虚拟环境"
  python3 -m venv "$VENV_DIR"
fi

echo "==> 安装 Python 依赖"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$REPO_ROOT/requirements.txt"

echo "==> 安装 Node 依赖"
(cd "$REPO_ROOT" && npm install)

if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "==> 生成 .env"
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi

echo "==> 更新 config.yaml 中的 vault_dir"
python3 - "$REPO_ROOT/config.yaml" "$VAULT_PATH" <<'PY'
from pathlib import Path
import re
import sys

config_path = Path(sys.argv[1])
vault_path = sys.argv[2]
text = config_path.read_text(encoding="utf-8")
quoted_vault_path = '"' + vault_path.replace("\\", "\\\\").replace('"', '\\"') + '"'
updated, count = re.subn(
    r"(^\s*vault_dir:\s*).*$",
    lambda match: match.group(1) + quoted_vault_path,
    text,
    count=1,
    flags=re.MULTILINE,
)
if count != 1:
    raise SystemExit("无法在 config.yaml 中找到 vault_dir 配置项")
config_path.write_text(updated, encoding="utf-8")
PY

echo "==> 安装 Obsidian 插件"
rm -rf "$PLUGIN_DEST_DIR"
mkdir -p "$PLUGIN_DEST_DIR"
cp "$PLUGIN_SRC_DIR/manifest.json" "$PLUGIN_DEST_DIR/manifest.json"
cp "$PLUGIN_SRC_DIR/main.js" "$PLUGIN_DEST_DIR/main.js"
cp "$PLUGIN_SRC_DIR/styles.css" "$PLUGIN_DEST_DIR/styles.css"

echo "==> 写入插件配置"
python3 - "$PLUGIN_DATA_PATH" "$REPO_ROOT" "$VENV_PYTHON" <<'PY'
from pathlib import Path
import json
import sys

data_path = Path(sys.argv[1])
repo_root = Path(sys.argv[2]).resolve()
python_path = Path(sys.argv[3])
payload = {
    "agentDirectory": str(repo_root),
    "pythonCommand": str(python_path),
    "autoOpenResult": True,
    "openIndexAfterCompile": True,
    "saveQaReport": True,
    "showVerboseLogs": False,
}
data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY

echo "==> 启用社区插件"
python3 - "$COMMUNITY_PLUGINS_PATH" "$PLUGIN_ID" <<'PY'
from pathlib import Path
import json
import sys

plugins_path = Path(sys.argv[1])
plugin_id = sys.argv[2]

if plugins_path.exists():
    try:
        plugins = json.loads(plugins_path.read_text(encoding="utf-8"))
        if not isinstance(plugins, list):
            plugins = []
    except json.JSONDecodeError:
        plugins = []
else:
    plugins = []

if plugin_id not in plugins:
    plugins.append(plugin_id)

plugins_path.write_text(json.dumps(plugins, ensure_ascii=False, indent=2), encoding="utf-8")
PY

cat <<EOF

安装完成。

接下来只需要：
1. 编辑 $REPO_ROOT/.env，填入 GEMINI_API_KEY
2. 在 Obsidian 中打开 $VAULT_PATH
3. 确认已允许社区插件，然后启用 "$PLUGIN_ID"

之后你就可以通过左侧机器人图标打开 LLM Agent 面板。
EOF
