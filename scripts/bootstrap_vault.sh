#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_ID="obsidian-llm-agent"
PLUGIN_SRC_DIR="$REPO_ROOT/plugins/$PLUGIN_ID"
DEFAULT_VAULT_PATH="$REPO_ROOT/../new-obsidian-vault"
if [[ $# -gt 0 ]]; then
  VAULT_PATH="$*"
else
  VAULT_PATH="$DEFAULT_VAULT_PATH"
fi

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少依赖命令: $1" >&2
    exit 1
  fi
}

require_command python3

VAULT_PATH="$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$VAULT_PATH")"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"
PLUGIN_DEST_DIR="$VAULT_PATH/.obsidian/plugins/$PLUGIN_ID"
PLUGIN_DATA_PATH="$PLUGIN_DEST_DIR/data.json"
COMMUNITY_PLUGINS_PATH="$VAULT_PATH/.obsidian/community-plugins.json"
APP_JSON_PATH="$VAULT_PATH/.obsidian/app.json"

if [[ ! -d "$PLUGIN_SRC_DIR" ]]; then
  echo "插件源码目录不存在: $PLUGIN_SRC_DIR" >&2
  exit 1
fi

if [[ -x "$VENV_PYTHON" ]]; then
  PYTHON_COMMAND="$VENV_PYTHON"
else
  PYTHON_COMMAND="python3"
fi

echo "==> Repo root: $REPO_ROOT"
echo "==> Vault path: $VAULT_PATH"

mkdir -p "$VAULT_PATH/.obsidian/plugins"

echo "==> 写入最小 Obsidian 配置"
if [[ ! -f "$APP_JSON_PATH" ]]; then
  cat > "$APP_JSON_PATH" <<'EOF'
{
  "promptDelete": false
}
EOF
fi

echo "==> 安装 Obsidian 插件"
rm -rf "$PLUGIN_DEST_DIR"
mkdir -p "$PLUGIN_DEST_DIR"
cp "$PLUGIN_SRC_DIR/manifest.json" "$PLUGIN_DEST_DIR/manifest.json"
cp "$PLUGIN_SRC_DIR/main.js" "$PLUGIN_DEST_DIR/main.js"
cp "$PLUGIN_SRC_DIR/styles.css" "$PLUGIN_DEST_DIR/styles.css"

echo "==> 写入插件默认配置"
python3 - "$PLUGIN_DATA_PATH" "$REPO_ROOT" "$PYTHON_COMMAND" <<'PY'
from pathlib import Path
import json
import sys

data_path = Path(sys.argv[1])
repo_root = Path(sys.argv[2]).resolve()
python_command = sys.argv[3]
payload = {
    "agentDirectory": str(repo_root),
    "pythonCommand": python_command,
    "autoOpenResult": True,
    "openIndexAfterCompile": True,
    "saveQaReport": True,
    "showVerboseLogs": False,
    "apiKey": "",
    "modelPro": "gemini-2.5-pro",
    "modelFlash": "gemini-2.5-flash",
    "modelLite": "gemini-2.5-flash-lite",
    "roleSummary": "flash",
    "roleConceptExtract": "flash",
    "roleConceptArticle": "pro",
    "roleConceptUpdate": "flash",
    "roleIndex": "lite",
    "roleQaRetrieve": "lite",
    "roleQaAnswer": "pro",
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

空白 vault 引导完成。

你现在可以：
1. 在 Obsidian 中打开 $VAULT_PATH
2. 进入 Settings -> Community plugins，确认已允许社区插件
3. 启用 "$PLUGIN_ID"
4. 打开左侧 LLM Agent 面板
5. 点击“初始化知识库”，选择“通用知识库”或“金融研究库”

说明：
- 这个脚本只负责给全新 vault 安装插件和最小配置
- 如果你还没有准备好后端依赖，请先在仓库根目录运行 ./scripts/install.sh
- 如果 .venv 不存在，插件会先使用系统 python3
EOF
