"""
LLM 知识库系统 — 共用工具函数
==============================
提供配置加载、LLM 调用、Markdown 读写等基础能力。
"""

import os
os.environ["GOOGLE_API_USE_REST"] = "1"
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "False"
import re
import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console

# ── 全局常量 ──────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
ENV_PATH = ROOT_DIR / ".env"

console = Console()

# ── 配置加载 ──────────────────────────────────────────


def load_config() -> dict:
    """加载 config.yaml 配置文件。"""
    if not CONFIG_PATH.exists():
        console.print(f"[red]错误: 配置文件不存在 {CONFIG_PATH}[/red]")
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_path(config: dict, key: str) -> Path:
    """根据配置获取绝对路径，支持外部 vault。"""
    vault_base = Path(config["paths"].get("vault_dir", "."))
    if not vault_base.is_absolute():
        vault_base = ROOT_DIR / vault_base
    return vault_base / config["paths"][key]


# ── 环境变量 ──────────────────────────────────────────


def load_env():
    """加载 .env 文件中的环境变量。"""
    load_dotenv(ENV_PATH)


def get_api_key() -> str:
    """获取 Gemini API Key。"""
    load_env()
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "your-gemini-api-key-here":
        console.print("[red]错误: 请在 .env 文件中设置有效的 GEMINI_API_KEY[/red]")
        console.print("[dim]获取地址: https://aistudio.google.com/apikey[/dim]")
        raise ValueError("GEMINI_API_KEY 未配置")
    return key


# ── LLM 调用 ──────────────────────────────────────────

OBSIDIAN_MARKDOWN_GUIDE = """你是一个专业的知识库编辑助手，擅长用中文撰写结构化的知识文章。
你的输出将直接存入 Obsidian vault，请严格使用 Obsidian Flavored Markdown 语法：

## Obsidian 语法规范
- 内部链接使用 wikilinks: [[笔记名]], [[笔记名|显示文本]], [[笔记名#标题]]
- 嵌入内容: ![[笔记名]], ![[image.png|600]]
- 标注块 (Callout): > [!note], > [!tip], > [!warning], > [!important], > [!example]
- 高亮: ==关键文本==
- 标签: #标签名, #层级/标签
- 隐藏注释: %%隐藏内容%%
- Properties 使用 YAML frontmatter (---) 格式
- 任务列表: - [ ] 待办, - [x] 已完成

## 写作规范
- 使用 [[双向链接]] 连接相关概念，而非普通 Markdown 链接
- 重要信息使用 > [!note] 或 > [!important] callout 标注
- 关键术语首次出现时使用 ==高亮== 标记
- 每篇文章使用恰当的 frontmatter 元数据
"""


def _resolve_model(config: dict, role: Optional[str] = None) -> str:
    """
    根据场景角色(role)解析出具体的模型名称。

    模型分级策略:
      pro   — 复杂推理（概念文章撰写、问答回答）      gemini-2.5-pro
      flash — 日常任务（摘要生成、概念提取）            gemini-2.5-flash
      lite  — 简单任务（索引生成、检索选择）            gemini-2.5-flash-lite
    """
    llm_config = config.get("llm", {})
    models = llm_config.get("models", {})
    roles = llm_config.get("roles", {})

    if role and role in roles:
        tier = roles[role]  # e.g. "pro", "flash", "lite"
        model = models.get(tier, "gemini-2.5-flash")
    else:
        # 默认使用 flash（性价比最优）
        model = models.get("flash", "gemini-2.5-flash")

    return model


def call_llm(
    prompt: str,
    system_prompt: str = OBSIDIAN_MARKDOWN_GUIDE,
    config: Optional[dict] = None,
    role: Optional[str] = None,
) -> str:
    """
    调用 Google Gemini API。

    Args:
        prompt: 用户提示词
        system_prompt: 系统提示词
        config: 配置字典，如果为 None 则自动加载
        role: 场景角色，用于选择对应模型等级
              可选值: summary, concept_extract, concept_article,
                     concept_update, index, qa_retrieve, qa_answer

    Returns:
        LLM 生成的文本
    """
    from google import generativeai as genai

    if config is None:
        config = load_config()

    llm_config = config.get("llm", {})
    api_key = get_api_key()
    model_name = _resolve_model(config, role)

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=llm_config.get("temperature", 0.3),
            max_output_tokens=llm_config.get("max_tokens", 8192),
        ),
    )

    return response.text.strip()


# ── Frontmatter 处理 ──────────────────────────────────


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    解析 Markdown 文件的 YAML frontmatter。

    Returns:
        (frontmatter_dict, body_content)
    """
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return meta, body
            except yaml.YAMLError:
                pass
    return {}, content.strip()


def build_frontmatter(meta: dict) -> str:
    """将字典序列化为 YAML frontmatter 字符串。"""
    yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{yaml_str}\n---"


def read_markdown(path: Path) -> tuple[dict, str]:
    """读取 Markdown 文件并解析 frontmatter。"""
    if not path.exists():
        return {}, ""
    content = path.read_text(encoding="utf-8")
    return parse_frontmatter(content)


def write_markdown(path: Path, meta: dict, body: str):
    """将 frontmatter + body 写入 Markdown 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = build_frontmatter(meta)
    content = f"{frontmatter}\n\n{body}\n"
    path.write_text(content, encoding="utf-8")
    console.print(f"[green]✓ 已写入:[/green] {path.relative_to(ROOT_DIR)}")


# ── 文件工具 ──────────────────────────────────────────


def slugify(text: str) -> str:
    """
    将文本转为安全的文件名。
    保留中文字符，替换特殊字符为下划线。
    """
    # 移除 Markdown 链接语法
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # 保留中文、字母、数字，其他替换为下划线
    text = re.sub(r"[^\w\u4e00-\u9fff-]", "_", text)
    # 合并多个下划线
    text = re.sub(r"_+", "_", text)
    return text.strip("_")[:80]


def file_hash(path: Path) -> str:
    """计算文件的 MD5 哈希值（用于检测变更）。"""
    return hashlib.md5(path.read_bytes()).hexdigest()


def timestamp_now() -> str:
    """返回当前时间戳字符串（ISO 格式）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def date_today() -> str:
    """返回今天日期字符串。"""
    return datetime.now().strftime("%Y-%m-%d")


# ── Wiki 工具 ─────────────────────────────────────────


def list_wiki_articles(config: dict) -> list[Path]:
    """列出 wiki/ 下所有 Markdown 文件。"""
    wiki_dir = get_path(config, "wiki")
    return sorted(wiki_dir.rglob("*.md"))


def list_raw_files(config: dict) -> list[Path]:
    """列出 raw/ 下所有文件。"""
    raw_dir = get_path(config, "raw")
    return sorted(f for f in raw_dir.rglob("*") if f.is_file())


def get_uncompiled_raw_files(config: dict) -> list[Path]:
    """获取尚未编译的原始资料文件（仅 .md 文件）。"""
    raw_dir = get_path(config, "raw")
    uncompiled = []
    for f in raw_dir.rglob("*.md"):
        meta, _ = read_markdown(f)
        if not meta.get("compiled", False):
            uncompiled.append(f)
    return sorted(uncompiled)


def find_article_by_concept(config: dict, concept: str) -> Optional[Path]:
    """在 wiki/concepts/ 中查找与概念匹配的文章。"""
    concepts_dir = get_path(config, "wiki") / "concepts"
    slug = slugify(concept)
    # 精确匹配
    exact = concepts_dir / f"{slug}.md"
    if exact.exists():
        return exact
    # 模糊匹配
    for f in concepts_dir.glob("*.md"):
        if slug.lower() in f.stem.lower():
            return f
    return None


# ── 日志 ──────────────────────────────────────────────


def log_info(msg: str):
    console.print(f"[blue]ℹ[/blue]  {msg}")


def log_success(msg: str):
    console.print(f"[green]✓[/green]  {msg}")


def log_warning(msg: str):
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def log_error(msg: str):
    console.print(f"[red]✗[/red]  {msg}")
