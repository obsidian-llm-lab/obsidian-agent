"""
LLM 知识库系统 — 问答 Agent
==============================
基于编译好的 Wiki 回答用户问题。

用法:
    python scripts/qa.py                    # 交互式问答模式
    python scripts/qa.py "你的问题"          # 单次问答
    python scripts/qa.py --save "你的问题"   # 问答并保存答案
"""

import sys
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
    list_wiki_articles,
    vault_relative_path,
    display_path,
    log_info,
    log_success,
    log_warning,
    log_error,
    console,
)


# ── Prompt 模板 ───────────────────────────────────────

RETRIEVAL_PROMPT = """你是一个知识库检索助手。以下是知识库的索引信息，请根据用户的问题，选择最相关的文章（最多 {max_articles} 篇）。

知识库索引:
{index_info}

用户问题: {question}

请返回最相关的文章文件名列表，每行一个文件名（相对于 wiki/ 目录的路径），按相关性排序。
只返回文件名，不要添加其他文字。如果没有相关文章，返回 "NONE"。
"""

QA_PROMPT = """你是一个专业的知识库问答助手。请根据以下知识库文章内容，回答用户的问题。

{context}

---

用户问题: {question}

要求:
1. 用中文回答
2. 基于知识库内容回答，如果知识库中没有相关信息，明确说明
3. 使用 Markdown 格式
4. 引用来源时使用 Obsidian 链接语法 [[文章名]]
5. 回答要准确、有条理
"""


# ── 检索 ──────────────────────────────────────────────


def build_index_info(config: dict) -> str:
    """构建用于检索的索引信息。"""
    wiki_dir = get_path(config, "wiki")
    articles = list_wiki_articles(config)

    info_parts = []
    for a in articles:
        rel = a.relative_to(wiki_dir)
        meta, body = read_markdown(a)
        title = meta.get("title", a.stem)
        article_type = meta.get("type", "")
        definition = meta.get("definition", "")

        entry = f"- {rel}: {title}"
        if article_type:
            entry += f" (类型: {article_type})"
        if definition:
            entry += f" — {definition}"

        # 添加前几行内容作为预览
        preview = body[:200].replace("\n", " ").strip()
        if preview:
            entry += f"\n  预览: {preview}..."

        info_parts.append(entry)

    return "\n".join(info_parts)


def retrieve_articles(
    question: str, config: dict, index_info: str
) -> list[tuple[Path, dict, str]]:
    """检索与问题相关的文章。"""
    qa_config = config.get("qa", {})
    max_articles = qa_config.get("max_context_articles", 10)

    # 让 LLM 根据索引选择相关文章
    prompt = RETRIEVAL_PROMPT.format(
        index_info=index_info,
        question=question,
        max_articles=max_articles,
    )
    response = call_llm(prompt, config=config)

    if response.strip() == "NONE":
        return []

    # 解析文件名列表
    wiki_dir = get_path(config, "wiki")
    articles = []
    for line in response.strip().split("\n"):
        line = line.strip().lstrip("- ").strip()
        if not line:
            continue
        path = wiki_dir / line
        if path.exists():
            meta, body = read_markdown(path)
            articles.append((path, meta, body))
        else:
            # 尝试模糊匹配
            for candidate in wiki_dir.rglob("*.md"):
                if line in str(candidate.relative_to(wiki_dir)):
                    meta, body = read_markdown(candidate)
                    articles.append((candidate, meta, body))
                    break

    return articles[:max_articles]


# ── 问答 ──────────────────────────────────────────────


def answer_question(
    question: str, config: dict, save: bool = False
) -> str:
    """回答一个问题。"""
    wiki_dir = get_path(config, "wiki")
    articles = list_wiki_articles(config)

    if not articles:
        return "⚠️ 知识库中还没有任何文章。请先使用 `ingest` 和 `compile` 命令添加并编译资料。"

    log_info("正在检索相关文章...")
    index_info = build_index_info(config)
    relevant = retrieve_articles(question, config, index_info)

    if not relevant:
        log_warning("未找到直接相关的文章，将尝试基于全部索引信息回答")
        context = f"知识库索引概览:\n{index_info}"
    else:
        log_info(f"找到 {len(relevant)} 篇相关文章:")
        context_parts = []
        for path, meta, body in relevant:
            rel = path.relative_to(wiki_dir)
            title = meta.get("title", path.stem)
            log_info(f"  → {title} ({rel})")
            context_parts.append(
                f"### 📄 {title}\n文件: {rel}\n\n{body[:5000]}"
            )
        context = "\n\n---\n\n".join(context_parts)

    # 让 LLM 生成答案
    log_info("正在生成答案...\n")
    prompt = QA_PROMPT.format(context=context, question=question)
    answer = call_llm(
        prompt,
        system_prompt="你是一个精通知识管理的中文问答助手，善于从知识库文章中提取信息并给出结构化的回答。",
        config=config,
    )

    # 可选：保存答案
    if save or config.get("qa", {}).get("save_answers", False):
        report_meta = {
            "title": f"问答: {question[:50]}",
            "type": "qa_report",
            "question": question,
            "created_at": timestamp_now(),
            "date": date_today(),
            "referenced_articles": [
                vault_relative_path(p, config) for p, _, _ in relevant
            ],
        }
        filename = f"{date_today()}_{slugify(question[:40])}.md"
        report_path = get_path(config, "output") / "reports" / filename
        report_body = f"## 问题\n\n{question}\n\n## 答案\n\n{answer}"
        write_markdown(report_path, report_meta, report_body)
        log_success(f"答案已保存: {display_path(report_path)}")

    return answer


# ── 交互模式 ──────────────────────────────────────────


def interactive_mode(config: dict):
    """交互式问答 REPL。"""
    console.print("\n[bold cyan]🧠 LLM 知识库问答系统[/bold cyan]")
    console.print("[dim]输入问题开始提问，输入 'quit' 或 'exit' 退出[/dim]")
    console.print("[dim]输入 'save' + 问题 将答案保存到 output/reports/[/dim]\n")

    while True:
        try:
            question = console.input("[bold green]❓ [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见！[/dim]")
            break

        if not question:
            continue

        if question.lower() in ("quit", "exit", "q"):
            console.print("[dim]再见！[/dim]")
            break

        save = False
        if question.lower().startswith("save "):
            save = True
            question = question[5:].strip()

        try:
            answer = answer_question(question, config, save=save)
            console.print(f"\n{answer}\n")
            console.print("[dim]" + "─" * 60 + "[/dim]\n")
        except Exception as e:
            log_error(f"回答失败: {e}")
            console.print()


# ── CLI 入口 ──────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="LLM 知识库 — 问答 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/qa.py                        # 交互式问答
    python scripts/qa.py "什么是 Transformer？"   # 单次问答
    python scripts/qa.py --save "对比 RNN 和 CNN"  # 问答并保存
        """,
    )

    parser.add_argument("question", nargs="?", help="要回答的问题")
    parser.add_argument("--save", action="store_true", help="将答案保存到 output/reports/")

    args = parser.parse_args()
    config = load_config()

    if args.question:
        answer = answer_question(args.question, config, save=args.save)
        console.print(f"\n{answer}\n")
    else:
        interactive_mode(config)


if __name__ == "__main__":
    main()
