"""
LLM 知识库系统 — Wiki 编译脚本
================================
将 raw/ 中的原始资料增量编译为 wiki/ 中的结构化知识文章。

用法:
    python scripts/compile.py              # 增量编译（仅处理未编译的资料）
    python scripts/compile.py --all        # 重新编译所有资料
    python scripts/compile.py --index      # 仅更新索引
    python scripts/compile.py --status     # 查看编译状态
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.utils import (
    load_config,
    call_llm,
    read_markdown,
    write_markdown,
    slugify,
    date_today,
    timestamp_now,
    get_path,
    get_uncompiled_raw_files,
    list_wiki_articles,
    find_article_by_concept,
    vault_relative_path,
    display_path,
    log_info,
    log_success,
    log_warning,
    log_error,
    console,
)


# ── Prompt 模板 ───────────────────────────────────────

SUMMARY_PROMPT = """请为以下原始资料撰写一篇中文摘要文章。

要求：
1. 用清晰的中文撰写，使用 Markdown 格式
2. 包含一个简短的概述段落（2-3 句话）
3. 提取关键要点，用列表形式呈现
4. 保留原文中的重要数据、数字和引用
5. 字数控制在 {max_length} 字以内
6. 不要添加你自己的观点，只概括原始内容

原始资料标题: {title}
来源: {source}

---

{content}
"""

CONCEPT_PROMPT = """请分析以下文章内容，提取其中涉及的核心概念。

要求：
1. 提取最多 {max_concepts} 个核心概念
2. 每个概念给出：名称（中文）、英文名（如有）、简短定义（一句话）
3. 按重要性排序

请以 JSON 数组格式返回，示例:
[
    {{"name": "变压器架构", "name_en": "Transformer", "definition": "一种基于自注意力机制的神经网络架构"}},
    {{"name": "注意力机制", "name_en": "Attention Mechanism", "definition": "让模型在处理序列时动态关注不同位置的机制"}}
]

只返回 JSON 数组，不要添加任何其他文字。

---

{content}
"""

CONCEPT_ARTICLE_PROMPT = """请为以下概念撰写一篇中文知识条目。

概念名称: {name}
英文名称: {name_en}
定义: {definition}

相关上下文（来自摘要）:
{context}

要求:
1. 用清晰的中文撰写，使用 Markdown 格式
2. 包含：定义、核心思想、应用场景
3. 在文中使用 Obsidian 双向链接语法 [[概念名]] 引用相关概念
4. 字数 200-500 字
5. 保持客观准确
"""

CONCEPT_UPDATE_PROMPT = """以下是一篇已有的知识条目，请根据新的上下文信息补充和完善它。

已有内容:
{existing_content}

新的上下文（来自新摘要）:
{new_context}

要求:
1. 保留已有内容中正确的部分
2. 补充新的信息，不要重复
3. 使用 Obsidian 双向链接语法 [[概念名]] 引用相关概念
4. 保持文章的连贯性和结构
5. 返回完整的更新后文章（不要只返回差异）
"""

INDEX_PROMPT = """请根据以下 Wiki 文章列表，生成一个结构化的中文索引页面。

文章列表:
{articles_info}

要求:
1. 按主题/领域分类组织
2. 每个分类下列出相关文章，使用 Obsidian 链接语法
3. 包含文章的简短描述
4. 在顶部显示统计信息（文章总数、概念数、最后更新时间）
5. 使用 Markdown 格式，层次清晰
"""


# ── 编译核心 ──────────────────────────────────────────


def compile_single(raw_path: Path, config: dict):
    """编译单个原始资料文件。"""
    meta, body = read_markdown(raw_path)
    title = meta.get("title", raw_path.stem)
    source = meta.get("source", str(raw_path))
    compile_config = config.get("compile", {})
    max_length = compile_config.get("summary_max_length", 800)
    max_concepts = compile_config.get("max_concepts", 10)

    log_info(f"正在编译: {title}")

    # ── 步骤 1: 生成摘要 ──
    log_info("  → 生成摘要...")
    summary_prompt = SUMMARY_PROMPT.format(
        title=title,
        source=source,
        content=body[:15000],  # 截断过长内容
        max_length=max_length,
    )
    summary_body = call_llm(summary_prompt, config=config)

    # 保存摘要
    summary_meta = {
        "title": f"{title} — 摘要",
        "source": source,
        "raw_file": vault_relative_path(raw_path, config),
        "type": "summary",
        "created_at": timestamp_now(),
        "date": date_today(),
        "tags": meta.get("tags", []),
    }

    summary_filename = f"{slugify(title)}.md"
    summary_path = get_path(config, "wiki") / "summaries" / summary_filename
    write_markdown(summary_path, summary_meta, summary_body)

    # ── 步骤 2: 提取概念 ──
    log_info("  → 提取概念...")
    concept_prompt = CONCEPT_PROMPT.format(
        content=summary_body,
        max_concepts=max_concepts,
    )
    concept_response = call_llm(concept_prompt, config=config)

    # 解析 JSON 响应
    concepts = _parse_concepts(concept_response)
    concept_names = []

    if concepts:
        for concept in concepts:
            name = concept.get("name", "")
            name_en = concept.get("name_en", "")
            definition = concept.get("definition", "")

            if not name:
                continue

            concept_names.append(name)

            # 检查概念文章是否已存在
            existing_path = find_article_by_concept(config, name)

            if existing_path:
                # 更新已有概念文章
                log_info(f"  → 更新概念: {name}")
                existing_meta, existing_body = read_markdown(existing_path)
                update_prompt = CONCEPT_UPDATE_PROMPT.format(
                    existing_content=existing_body,
                    new_context=summary_body[:3000],
                )
                updated_body = call_llm(update_prompt, config=config)

                # 更新 related_summaries
                related = existing_meta.get("related_summaries", [])
                rel_path = vault_relative_path(summary_path, config)
                if rel_path not in related:
                    related.append(rel_path)
                existing_meta["related_summaries"] = related
                existing_meta["updated_at"] = timestamp_now()

                write_markdown(existing_path, existing_meta, updated_body)
            else:
                # 创建新概念文章
                log_info(f"  → 新建概念: {name}")
                article_prompt = CONCEPT_ARTICLE_PROMPT.format(
                    name=name,
                    name_en=name_en,
                    definition=definition,
                    context=summary_body[:3000],
                )
                article_body = call_llm(article_prompt, config=config)

                concept_meta = {
                    "title": name,
                    "title_en": name_en,
                    "type": "concept",
                    "definition": definition,
                    "created_at": timestamp_now(),
                    "date": date_today(),
                    "related_summaries": [vault_relative_path(summary_path, config)],
                    "tags": [],
                }

                concept_filename = f"{slugify(name)}.md"
                concept_path = get_path(config, "wiki") / "concepts" / concept_filename
                write_markdown(concept_path, concept_meta, article_body)

    # ── 步骤 3: 添加反向链接 ──
    if compile_config.get("auto_backlinks", True) and concept_names:
        log_info("  → 添加反向链接...")
        _add_backlinks_to_summary(summary_path, concept_names)

    # ── 步骤 4: 标记为已编译 ──
    meta["compiled"] = True
    meta["compiled_at"] = timestamp_now()
    meta["concepts"] = concept_names
    write_markdown(raw_path, meta, body)

    log_success(f"编译完成: {title}")
    log_info(f"  摘要: {display_path(summary_path)}")
    log_info(f"  概念: {len(concept_names)} 个 — {', '.join(concept_names[:5])}")


def _parse_concepts(response: str) -> list[dict]:
    """解析 LLM 返回的概念 JSON。"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试从 Markdown 代码块中提取
    import re
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找到 JSON 数组
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    log_warning("无法解析概念列表，跳过概念提取")
    return []


def _add_backlinks_to_summary(summary_path: Path, concept_names: list[str]):
    """在摘要文章底部添加相关概念的反向链接。"""
    meta, body = read_markdown(summary_path)

    # 在正文中将概念名替换为双向链接
    for name in concept_names:
        # 避免重复链接
        if f"[[{name}]]" not in body:
            # 只在正文中第一次出现时添加链接
            body = body.replace(name, f"[[{name}]]", 1)

    # 在底部添加相关概念区块
    backlinks_section = "\n\n---\n\n## 相关概念\n\n"
    backlinks_section += " · ".join(f"[[{name}]]" for name in concept_names)

    body = body.rstrip() + backlinks_section

    write_markdown(summary_path, meta, body)


# ── 索引生成 ──────────────────────────────────────────


def update_index(config: dict):
    """更新 wiki/index.md 总索引。"""
    log_info("正在更新索引...")

    wiki_dir = get_path(config, "wiki")
    articles = list_wiki_articles(config)

    if not articles:
        log_warning("Wiki 中没有任何文章，跳过索引生成")
        return

    # 收集文章信息
    articles_info_parts = []
    for a in articles:
        if a.name == "index.md":
            continue
        meta, body = read_markdown(a)
        rel = a.relative_to(wiki_dir)
        info = f"- 文件: {rel}"
        info += f"\n  标题: {meta.get('title', a.stem)}"
        info += f"\n  类型: {meta.get('type', '未知')}"
        if meta.get("definition"):
            info += f"\n  定义: {meta['definition']}"
        if meta.get("tags"):
            info += f"\n  标签: {', '.join(meta['tags'])}"
        articles_info_parts.append(info)

    articles_info = "\n".join(articles_info_parts)

    # 让 LLM 生成索引
    prompt = INDEX_PROMPT.format(articles_info=articles_info)
    index_body = call_llm(prompt, config=config)

    index_meta = {
        "title": "知识库索引",
        "type": "index",
        "updated_at": timestamp_now(),
        "article_count": len(articles) - 1,  # 排除 index.md 自身
    }

    index_path = wiki_dir / "index.md"
    write_markdown(index_path, index_meta, index_body)
    log_success(f"索引已更新: {len(articles) - 1} 篇文章")


# ── 编译状态 ──────────────────────────────────────────


def show_status(config: dict):
    """显示编译状态统计。"""
    raw_dir = get_path(config, "raw")
    wiki_dir = get_path(config, "wiki")

    # 统计原始资料
    raw_files = [f for f in raw_dir.rglob("*.md") if f.is_file()]
    compiled = [f for f in raw_files if read_markdown(f)[0].get("compiled")]
    uncompiled = [f for f in raw_files if not read_markdown(f)[0].get("compiled")]

    # 统计 Wiki 文章
    wiki_articles = list_wiki_articles(config)
    summaries = [a for a in wiki_articles if "summaries" in str(a)]
    concepts = [a for a in wiki_articles if "concepts" in str(a)]

    console.print("\n[bold]📊 编译状态[/bold]\n")
    console.print(f"  原始资料:   {len(raw_files)} 个")
    console.print(f"    已编译:   [green]{len(compiled)}[/green]")
    console.print(f"    未编译:   [yellow]{len(uncompiled)}[/yellow]")
    console.print(f"  Wiki 文章:  {len(wiki_articles)} 篇")
    console.print(f"    摘要:     {len(summaries)}")
    console.print(f"    概念:     {len(concepts)}")

    if uncompiled:
        console.print(f"\n[yellow]待编译:[/yellow]")
        for f in uncompiled:
            meta, _ = read_markdown(f)
            console.print(f"  ○ {meta.get('title', f.stem)}")

    console.print()


# ── CLI 入口 ──────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="LLM 知识库 — Wiki 编译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/compile.py               # 增量编译
    python scripts/compile.py --all         # 重新编译所有
    python scripts/compile.py --index       # 仅更新索引
    python scripts/compile.py --status      # 查看状态
        """,
    )

    parser.add_argument("--all", action="store_true", help="重新编译所有资料")
    parser.add_argument("--index", action="store_true", help="仅更新索引")
    parser.add_argument("--status", action="store_true", help="查看编译状态")

    args = parser.parse_args()
    config = load_config()

    if args.status:
        show_status(config)
        return

    if args.index:
        update_index(config)
        return

    # 获取待编译文件
    if args.all:
        raw_dir = get_path(config, "raw")
        files = sorted(raw_dir.rglob("*.md"))
        # 重置编译状态
        for f in files:
            meta, body = read_markdown(f)
            meta["compiled"] = False
            write_markdown(f, meta, body)
        log_info(f"已重置 {len(files)} 个文件的编译状态")
    else:
        files = get_uncompiled_raw_files(config)

    if not files:
        log_info("没有需要编译的资料 ✓")
        log_info("提示: 使用 'python scripts/ingest.py url <URL>' 添加资料")
        return

    log_info(f"发现 {len(files)} 个待编译资料\n")

    # 逐个编译
    success = 0
    failed = 0
    for f in files:
        try:
            compile_single(f, config)
            success += 1
            console.print()
        except Exception as e:
            log_error(f"编译失败: {f.name} — {e}")
            failed += 1

    # 更新索引
    if success > 0 and config.get("compile", {}).get("update_index", True):
        update_index(config)

    console.print(f"\n[bold]编译完成[/bold]: [green]{success} 成功[/green]", end="")
    if failed:
        console.print(f", [red]{failed} 失败[/red]")
    else:
        console.print()


if __name__ == "__main__":
    main()
