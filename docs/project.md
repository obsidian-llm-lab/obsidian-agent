# 个人知识库系统 — 基于 LLM + Obsidian

> 灵感来源：[Andrej Karpathy 的推文](https://x.com/karpathy/status/2039805659525644595)
> Karpathy 提出了一种全新的知识管理范式：**让 LLM 全权管理个人知识库**，人类只负责"投喂"原始资料和"查询"知识。

---

## 一、核心理念

传统知识库（如 Obsidian Vault）依赖人工手动编写和整理笔记。Karpathy 的方案颠覆了这一模式：

- **LLM 是知识库的"编辑"**：人类几乎不直接编辑 Wiki，LLM 负责撰写、摘要、分类、链接
- **原始资料 → 编译 → Wiki**：类似于代码编译流程，原始数据被"编译"成结构化的 Markdown 文章
- **知识库是活的**：持续增量更新，而非一次性构建
- **Obsidian 是前端**：用于浏览和可视化，而非手动编辑

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────┐
│                    Obsidian Vault                     │
│  (当前目录: /path/to/your-vault)                      │
│                                                       │
│  ├── raw/              ← 原始资料输入                  │
│  │   ├── articles/     ← 文章/网页剪藏                 │
│  │   ├── papers/       ← 学术论文                      │
│  │   ├── code/         ← 代码片段/仓库说明              │
│  │   ├── images/       ← 图片资料                      │
│  │   └── misc/         ← 其他资料                      │
│  │                                                     │
│  ├── wiki/             ← LLM 编译生成的知识 Wiki        │
│  │   ├── index.md      ← 自动生成的总索引               │
│  │   ├── concepts/     ← 按概念分类的文章               │
│  │   ├── summaries/    ← 原始资料的摘要                 │
│  │   └── relations/    ← 关联分析文档                   │
│  │                                                     │
│  ├── output/           ← LLM 生成的衍生产物             │
│  │   ├── slides/       ← Marp 演示文稿                  │
│  │   ├── charts/       ← 可视化图表                     │
│  │   └── reports/      ← 分析报告                       │
│  │                                                     │
│  ├── scripts/          ← 后端与安装脚本                 │
│  │   ├── ingest.py     ← 数据摄取脚本                   │
│  │   ├── compile.py    ← Wiki 编译脚本                  │
│  │   ├── qa.py         ← 问答 Agent 脚本                │
│  │   ├── install.sh    ← 环境安装脚本                   │
│  │   ├── bootstrap_*.sh← 空白 vault 引导脚本            │
│  │   └── lint.py       ← Wiki 健康检查脚本              │
│  │                                                     │
│  └── .obsidian/        ← Obsidian 配置                  │
└──────────────────────────────────────────────────────┘
```

---

## 三、核心模块与需要做的事情

### 模块 1：数据摄取 (Data Ingest)

**目标**：将各种原始资料统一收集到 `raw/` 目录中。

**需要做的事情**：
- [ ] 创建 `raw/` 目录及其子目录结构
- [ ] 编写 `scripts/ingest.py` 脚本，支持：
  - 从剪贴板/URL 自动下载网页并转为 Markdown（类似 Obsidian Web Clipper 的功能）
  - 解析 PDF 论文并提取文本
  - 接受本地文件（图片、代码等）的拷贝
  - 为每个原始资料生成元数据文件（来源 URL、日期、类型标签等）
- [ ] 配置 Obsidian Web Clipper 浏览器扩展，设置保存路径指向 `raw/articles/`
- [ ] 设计原始资料的命名规范和元数据格式（YAML frontmatter）

### 模块 2：知识编译 (Wiki Compilation)

**目标**：让 LLM 增量式地将 `raw/` 中的资料"编译"成 `wiki/` 中的结构化文章。

**需要做的事情**：
- [ ] 编写 `scripts/compile.py` 脚本，核心功能：
  - 扫描 `raw/` 中新增/修改的资料
  - 调用 LLM API，为每份资料生成：
    - **摘要文章**（存入 `wiki/summaries/`）
    - **概念提取**（识别关键概念，存入或更新 `wiki/concepts/`）
    - **反向链接**（自动在相关文章间建立 `[[双向链接]]`）
  - 增量更新：仅处理新增/变更的资料，避免重复编译
  - 自动生成/更新 `wiki/index.md` 总索引
- [ ] 设计 Wiki 文章模板（统一的 frontmatter 格式、标签体系）
- [ ] 设计概念分类的层级体系（可以让 LLM 自动维护分类树）
- [ ] 选择 LLM 提供商和模型（OpenAI / Anthropic / 本地模型等）
- [ ] 实现 Prompt 工程：
  - 摘要生成 prompt
  - 概念提取 prompt
  - 关联发现 prompt
  - 文章编写 prompt

### 模块 3：问答交互 (Q&A Agent)

**目标**：基于编译好的 Wiki，运行一个能回答复杂问题的 LLM Agent。

**需要做的事情**：
- [ ] 编写 `scripts/qa.py` 脚本，核心功能：
  - 接受用户自然语言问题
  - 自动检索 Wiki 中的相关文章（基于索引 + 关键词匹配 / 简单相似度搜索）
  - 将相关上下文提供给 LLM 生成答案
  - 答案以 Markdown 格式输出，可选保存到 `output/reports/`
- [ ] 实现简单的索引机制（Karpathy 提到在中小规模下，LLM 自动维护的索引和摘要比 RAG 更高效）：
  - 利用 Wiki 自身的结构（index.md、概念分类、反向链接）作为"索引"
  - LLM 先读取索引 → 定位相关文章 → 读取详情 → 回答问题
- [ ] 支持交互式终端问答模式（REPL）
- [ ] 可选：支持生成 Markdown 文件、幻灯片等作为回答产物

### 模块 4：输出生成 (Output Generation)

**目标**：LLM 不仅返回文本答案，还能直接生成可视化产物。

**需要做的事情**：
- [ ] 创建 `output/` 目录结构
- [ ] 支持生成 Marp 格式幻灯片（配合 Obsidian 的 Marp 插件）
- [ ] 支持生成 Matplotlib/Mermaid 图表
- [ ] 生成的产物自动存入 `output/` 对应子目录
- [ ] 产物也可被反馈回 Wiki，成为知识库的一部分

### 模块 5：知识检查 (Wiki Linting & Health Checks)

**目标**：运行 LLM 对 Wiki 进行质量检查和自动修复。

**需要做的事情**：
- [ ] 编写 `scripts/lint.py` 脚本，核心功能：
  - 检查数据一致性（如：概念文章是否都有链接、摘要是否完整等）
  - 发现孤立页面（没有任何链接指向的文章）
  - 识别过期或矛盾的信息
  - 补充缺失信息（结合搜索工具 / 网络查询）
  - 发现新的关联点（跨主题的联系）
  - 生成健康检查报告
- [ ] 设计检查规则集（可配置）
- [ ] 可选：定时运行（如每天/每周一次）

---

## 四、技术选型（待定）

| 组件 | 候选方案 | 说明 |
|------|---------|------|
| LLM API | OpenAI GPT-4o / Claude Sonnet / 本地 Ollama | 需评估成本、速度、质量 |
| 脚本语言 | Python | 最佳 LLM 生态支持 |
| Markdown 解析 | python-markdown / mistune | 用于解析和生成 Wiki 文章 |
| PDF 解析 | PyMuPDF / pdfplumber | 用于论文摄取 |
| 网页抓取 | trafilatura / readability | 用于 URL 文章抓取 |
| 幻灯片 | Marp CLI | 用于生成演示文稿 |
| 图表 | Matplotlib / Mermaid | 用于可视化 |
| 搜索增强 | Tavily / SerpAPI | 用于 lint 阶段补充信息 |
| 前端界面 | Obsidian | 浏览和可视化知识库 |
| 配置管理 | YAML / .env | 存储 API 密钥、模型选择等 |

---

## 五、实施路线图

### Phase 1：基础设施（预计 1-2 天）
1. 创建目录结构
2. 配置 Python 环境和依赖
3. 配置 LLM API 连接
4. 设计 Markdown 文章模板和 frontmatter 规范

### Phase 2：数据摄取（预计 2-3 天）
1. 实现 URL → Markdown 转换
2. 实现 PDF 解析
3. 实现本地文件摄取
4. 元数据自动提取

### Phase 3：知识编译（预计 3-5 天）— 核心模块
1. 实现增量编译逻辑
2. 实现摘要生成
3. 实现概念提取和自动分类
4. 实现双向链接自动生成
5. 实现索引自动生成/更新

### Phase 4：问答交互（预计 2-3 天）
1. 实现基于索引的文档检索
2. 实现问答 Agent
3. 实现交互式终端

### Phase 5：输出与检查（预计 2-3 天）
1. 实现幻灯片/图表生成
2. 实现 Wiki 健康检查
3. 输出反馈回 Wiki

---

## 六、关键设计决策（需要讨论）

1. **LLM 选择**：使用云端 API（如 GPT-4o、Claude）还是本地模型（如 Ollama + Llama）？涉及成本、隐私和速度的权衡。
2. **索引策略**：Karpathy 认为在中小规模下，LLM 自动维护的索引优于 RAG 向量检索。是否采用这一策略，还是同时支持两种模式？
3. **编译粒度**：一篇原始资料生成一篇摘要，还是按概念拆分成多篇？
4. **自动化程度**：是否设置文件监听（watchdog），实现资料投入即自动编译？
5. **多语言支持**：Wiki 使用中文还是英文撰写？是否支持多语言输入？

---

## 七、参考资源

- [Karpathy 原文推文](https://x.com/karpathy/status/2039805659525644595)
- [Obsidian 官网](https://obsidian.md/)
- [Obsidian Web Clipper](https://obsidian.md/clipper)
- [Marp - Markdown 演示文稿](https://marp.app/)
