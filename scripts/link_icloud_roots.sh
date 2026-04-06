#!/usr/bin/env bash

set -euo pipefail

DEFAULT_SOURCE_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
SOURCE_ROOT="$DEFAULT_SOURCE_ROOT"
TARGET_ROOT=""
DRY_RUN=0
FORCE=0

usage() {
  cat <<'EOF'
用法:
  ./scripts/link_icloud_roots.sh [选项] <目标目录>

说明:
  把 iCloud Drive 根目录下除 Desktop / Documents 之外的一级目录，
  批量创建软链接到指定目标目录下，方便多个 Obsidian 知识库在多台 Mac 之间同步迁移。

选项:
  --source <path>   指定源目录，默认使用 macOS iCloud Drive 根目录
  --dry-run         仅打印将执行的操作，不真正创建软链接
  --force           目标位置已存在时，先删除再重新创建软链接
  -h, --help        显示帮助

示例:
  ./scripts/link_icloud_roots.sh ~/icloud-links
  ./scripts/link_icloud_roots.sh --dry-run ~/icloud-links
  ./scripts/link_icloud_roots.sh --source /tmp/mock-icloud ~/icloud-links
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少依赖命令: $1" >&2
    exit 1
  fi
}

require_command python3

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      if [[ $# -lt 2 ]]; then
        echo "--source 需要传入路径" >&2
        exit 1
      fi
      SOURCE_ROOT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "未知选项: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [[ -n "$TARGET_ROOT" ]]; then
        echo "只允许传入一个目标目录: $1" >&2
        usage >&2
        exit 1
      fi
      TARGET_ROOT="$1"
      shift
      ;;
  esac
done

if [[ -z "$TARGET_ROOT" ]]; then
  echo "缺少目标目录参数" >&2
  usage >&2
  exit 1
fi

canonicalize_path() {
  python3 -c 'import os, sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$1"
}

SOURCE_ROOT="$(canonicalize_path "$SOURCE_ROOT")"
TARGET_ROOT="$(canonicalize_path "$TARGET_ROOT")"

if [[ ! -d "$SOURCE_ROOT" ]]; then
  echo "源目录不存在: $SOURCE_ROOT" >&2
  exit 1
fi

if [[ "$TARGET_ROOT" == "$SOURCE_ROOT" ]] || [[ "$TARGET_ROOT" == "$SOURCE_ROOT/"* ]]; then
  echo "目标目录不能位于源目录内部，否则会产生递归链接: $TARGET_ROOT" >&2
  exit 1
fi

if [[ $DRY_RUN -eq 0 ]]; then
  mkdir -p "$TARGET_ROOT"
fi

echo "==> Source root: $SOURCE_ROOT"
echo "==> Target root: $TARGET_ROOT"
echo "==> Mode: $([[ $DRY_RUN -eq 1 ]] && echo 'dry-run' || echo 'apply')"

created=0
skipped=0
updated=0

for entry in "$SOURCE_ROOT"/*; do
  if [[ ! -e "$entry" && ! -L "$entry" ]]; then
    continue
  fi

  name="$(basename "$entry")"

  case "$name" in
    Desktop|Documents)
      echo "skip  $name (系统目录)"
      skipped=$((skipped + 1))
      continue
      ;;
    .*)
      echo "skip  $name (隐藏项)"
      skipped=$((skipped + 1))
      continue
      ;;
  esac

  if [[ ! -d "$entry" && ! -L "$entry" ]]; then
    echo "skip  $name (不是目录)"
    skipped=$((skipped + 1))
    continue
  fi

  link_path="$TARGET_ROOT/$name"

  if [[ -L "$link_path" ]]; then
    current_target="$(readlink "$link_path")"
    if [[ "$current_target" == "$entry" ]]; then
      echo "keep  $name (已存在且指向正确)"
      skipped=$((skipped + 1))
      continue
    fi
    if [[ $FORCE -eq 1 ]]; then
      echo "update $name -> $entry"
      if [[ $DRY_RUN -eq 0 ]]; then
        rm -f "$link_path"
        ln -s "$entry" "$link_path"
      fi
      updated=$((updated + 1))
      continue
    fi
    echo "skip  $name (已存在其他软链接，使用 --force 可覆盖)"
    skipped=$((skipped + 1))
    continue
  fi

  if [[ -e "$link_path" ]]; then
    if [[ $FORCE -eq 1 ]]; then
      echo "update $name -> $entry"
      if [[ $DRY_RUN -eq 0 ]]; then
        rm -rf "$link_path"
        ln -s "$entry" "$link_path"
      fi
      updated=$((updated + 1))
      continue
    fi
    echo "skip  $name (目标已存在，使用 --force 可覆盖)"
    skipped=$((skipped + 1))
    continue
  fi

  echo "link  $name -> $entry"
  if [[ $DRY_RUN -eq 0 ]]; then
    ln -s "$entry" "$link_path"
  fi
  created=$((created + 1))
done

echo
echo "完成:"
echo "  新建: $created"
echo "  更新: $updated"
echo "  跳过: $skipped"
