"""
LLM 知识库系统 — 数据摄取脚本
==============================
将各种原始资料（URL/PDF/文件）统一收集到 raw/ 目录中。

用法:
    python scripts/ingest.py url <URL>         # 摄取网页
    python scripts/ingest.py pdf <路径>         # 摄取 PDF
    python scripts/ingest.py file <路径>        # 摄取本地文件
    python scripts/ingest.py list              # 列出已摄取的资料
"""

import sys
import shutil
import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import (
    load_config,
    write_markdown,
    read_markdown,
    slugify,
    date_today,
    timestamp_now,
    log_info,
    log_success,
    log_warning,
    log_error,
    display_path,
    get_path,
    console,
)


# ── URL 摄取 ──────────────────────────────────────────


def _fetch_with_defuddle(url: str) -> tuple[str, str]:
    """
    使用 defuddle CLI 提取网页内容（更干净，省 token）。
    Returns: (title, body_markdown)
    Raises: RuntimeError if defuddle fails
    """
    import subprocess
    import json

    log_info("  尝试 defuddle 提取...")

    # 先获取标题
    try:
        title_result = subprocess.run(
            ["npx", "defuddle", "parse", url, "-p", "title"],
            capture_output=True, text=True, timeout=30,
        )
        title = title_result.stdout.strip() if title_result.returncode == 0 else ""
    except Exception:
        title = ""

    # 获取 Markdown 内容
    result = subprocess.run(
        ["npx", "defuddle", "parse", url, "--md"],
        capture_output=True, text=True, timeout=60,
    )

    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"defuddle 失败: {result.stderr[:200]}")

    body = result.stdout.strip()

    if not title:
        # 从内容第一行提取标题
        first_line = body.split("\n")[0].strip()
        title = first_line.lstrip("# ").strip()[:100] if first_line else ""

    return title, body


def _fetch_with_trafilatura(url: str) -> tuple[str, str]:
    """
    使用 trafilatura 提取网页内容（回退方案）。
    Returns: (title, body_markdown)
    """
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise RuntimeError(f"无法下载: {url}")

    body = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=True,
        include_images=True,
        include_tables=True,
    )

    if not body:
        raise RuntimeError(f"无法提取内容: {url}")

    title = trafilatura.extract(downloaded, output_format="txt")
    if title:
        title = title.split("\n")[0].strip()[:100]
    else:
        title = ""

    return title, body


def ingest_url(url: str, config: dict) -> Path:
    """
    下载网页内容并转为 Markdown，存入 raw/articles/。

    优先使用 defuddle（更干净、省 token），失败时回退到 trafilatura。
    """
    log_info(f"正在抓取网页: {url}")

    title, body = "", ""

    # 策略 1: 优先使用 defuddle
    try:
        title, body = _fetch_with_defuddle(url)
        log_success("  defuddle 提取成功 ✓")
    except Exception as e:
        log_warning(f"  defuddle 失败: {e}")
        # 策略 2: 回退到 trafilatura
        try:
            log_info("  回退到 trafilatura...")
            title, body = _fetch_with_trafilatura(url)
            log_success("  trafilatura 提取成功 ✓")
        except Exception as e2:
            log_error(f"两种方式均失败: {e2}")
            raise RuntimeError(f"无法提取内容: {url}")

    # 标题兜底
    if not title:
        parsed = urlparse(url)
        title = parsed.path.strip("/").split("/")[-1] or parsed.netloc

    # 构建 frontmatter
    meta = {
        "title": title,
        "source": url,
        "type": "article",
        "ingested_at": timestamp_now(),
        "date": date_today(),
        "compiled": False,
        "tags": [],
    }

    # 生成文件名并保存
    filename = f"{date_today()}_{slugify(title)}.md"
    raw_dir = get_path(config, "raw") / "articles"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / filename

    # 避免文件名冲突
    counter = 1
    while output_path.exists():
        output_path = raw_dir / f"{date_today()}_{slugify(title)}_{counter}.md"
        counter += 1

    write_markdown(output_path, meta, body)
    log_success(f"网页已摄取: {display_path(output_path)}")
    log_info(f"标题: {title}")
    log_info(f"内容长度: {len(body)} 字符")

    return output_path


# ── PDF 摄取 ──────────────────────────────────────────


def ingest_pdf(pdf_path: str, config: dict) -> Path:
    """
    解析 PDF 文件并提取文本，存入 raw/papers/。
    """
    import pymupdf  # PyMuPDF

    source = Path(pdf_path).resolve()
    if not source.exists():
        log_error(f"PDF 文件不存在: {source}")
        raise FileNotFoundError(f"文件不存在: {source}")

    log_info(f"正在解析 PDF: {source.name}")

    # 提取文本
    doc = pymupdf.open(str(source))
    text_parts = []
    for page_num, page in enumerate(doc, 1):
        text = page.get_text()
        if text.strip():
            text_parts.append(f"## 第 {page_num} 页\n\n{text.strip()}")

    doc.close()

    if not text_parts:
        log_error(f"无法从 PDF 中提取文本: {source.name}")
        raise RuntimeError(f"无法提取文本: {source.name}")

    body = "\n\n".join(text_parts)
    title = source.stem  # 用文件名作为标题

    # 构建 frontmatter
    meta = {
        "title": title,
        "source": str(source),
        "type": "paper",
        "ingested_at": timestamp_now(),
        "date": date_today(),
        "compiled": False,
        "tags": [],
    }

    # 保存
    filename = f"{date_today()}_{slugify(title)}.md"
    raw_dir = get_path(config, "raw") / "papers"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / filename

    counter = 1
    while output_path.exists():
        output_path = raw_dir / f"{date_today()}_{slugify(title)}_{counter}.md"
        counter += 1

    write_markdown(output_path, meta, body)

    # 同时复制原始 PDF 到 raw/papers/
    pdf_copy = raw_dir / source.name
    if not pdf_copy.exists():
        shutil.copy2(source, pdf_copy)
        log_info(f"原始 PDF 已复制到: {display_path(pdf_copy)}")

    log_success(f"PDF 已摄取: {display_path(output_path)}")
    log_info(f"页数: {len(text_parts)}")
    log_info(f"内容长度: {len(body)} 字符")

    return output_path


# ── 本地文件摄取 ──────────────────────────────────────


def ingest_file(file_path: str, config: dict) -> Path:
    """
    复制本地文件到 raw/ 对应子目录。
    - 图片 → raw/images/
    - 代码 → raw/code/
    - Markdown → raw/articles/
    - 其他 → raw/misc/
    """
    source = Path(file_path).resolve()
    if not source.exists():
        log_error(f"文件不存在: {source}")
        raise FileNotFoundError(f"文件不存在: {source}")

    # 根据文件类型选择目标目录
    suffix = source.suffix.lower()
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}
    code_exts = {".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp", ".h", ".java", ".rb", ".sh"}

    if suffix in image_exts:
        sub_dir = "images"
    elif suffix in code_exts:
        sub_dir = "code"
    elif suffix == ".md":
        sub_dir = "articles"
    else:
        sub_dir = "misc"

    raw_dir = get_path(config, "raw") / sub_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / source.name

    # 避免覆盖
    counter = 1
    while dest.exists():
        dest = raw_dir / f"{source.stem}_{counter}{source.suffix}"
        counter += 1

    shutil.copy2(source, dest)

    # 如果是 Markdown 文件，确保有 frontmatter
    if suffix == ".md":
        meta, body = read_markdown(dest)
        if not meta.get("ingested_at"):
            meta.update({
                "title": meta.get("title", source.stem),
                "source": str(source),
                "type": "article",
                "ingested_at": timestamp_now(),
                "date": date_today(),
                "compiled": False,
            })
            write_markdown(dest, meta, body)

    log_success(f"文件已摄取: {display_path(dest)} (类型: {sub_dir})")
    return dest


# ── 列出已摄取资料 ────────────────────────────────────


def list_ingested(config: dict):
    """列出 raw/ 下所有已摄取的资料。"""
    raw_dir = get_path(config, "raw")
    files = sorted(f for f in raw_dir.rglob("*") if f.is_file())

    if not files:
        log_warning("raw/ 目录中没有任何资料")
        return

    console.print(f"\n[bold]已摄取的资料 ({len(files)} 个):[/bold]\n")

    # 按子目录分组
    groups: dict[str, list[Path]] = {}
    for f in files:
        rel = f.relative_to(raw_dir)
        group = rel.parts[0] if len(rel.parts) > 1 else "root"
        groups.setdefault(group, []).append(f)

    for group, group_files in sorted(groups.items()):
        console.print(f"  [cyan]📁 {group}/[/cyan]")
        for f in group_files:
            # 尝试读取 frontmatter
            if f.suffix == ".md":
                meta, _ = read_markdown(f)
                title = meta.get("title", f.stem)
                compiled = "✓" if meta.get("compiled") else "○"
                console.print(f"    {compiled} {title}")
                if meta.get("source"):
                    console.print(f"      [dim]来源: {meta['source']}[/dim]")
            else:
                console.print(f"    ○ {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        console.print()


# ── CLI 入口 ──────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="LLM 知识库 — 数据摄取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/ingest.py url https://example.com/article
    python scripts/ingest.py pdf ~/papers/attention.pdf
    python scripts/ingest.py file ~/code/script.py
    python scripts/ingest.py list
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="摄取命令")

    # url 子命令
    url_parser = subparsers.add_parser("url", help="摄取网页 URL")
    url_parser.add_argument("target", help="要摄取的 URL")

    # pdf 子命令
    pdf_parser = subparsers.add_parser("pdf", help="摄取 PDF 文件")
    pdf_parser.add_argument("target", help="PDF 文件路径")

    # file 子命令
    file_parser = subparsers.add_parser("file", help="摄取本地文件")
    file_parser.add_argument("target", help="文件路径")

    # list 子命令
    subparsers.add_parser("list", help="列出已摄取的资料")

    args = parser.parse_args()
    config = load_config()

    if args.command == "url":
        ingest_url(args.target, config)
    elif args.command == "pdf":
        ingest_pdf(args.target, config)
    elif args.command == "file":
        ingest_file(args.target, config)
    elif args.command == "list":
        list_ingested(config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
