# 🧠 LLM 个人知识库系统 (Agent 后台)

基于 [Andrej Karpathy 的理念](https://x.com/karpathy/status/2039805659525644595)，使用 LLM 自动构建和维护 Obsidian 知识库。

本项目是一个独立的 **大模型后台控制台 (`obsidian-agent`)**，它独立于你的文档库运行。它负责将你搜集的网页、论文等原始素材提取，然后通过 Google Gemini API 驱动智能体，自动帮你把材料"编译"成精美、带有 `[[双向连接]]` 的结构化概念维基，并注入到你平行的 `obsidian` 纯净内容库中！

> **核心思想**：LLM 是知识库的全自动"编辑长"，而你只负责投喂来源，并在 Obsidian 中纵享阅读与问答。

---

## 🚀 核心特性

- **代码与数据分离架构**：脚本与配置存放在 `obsidian-agent` 侧，你的知识笔记保存在外部挂载的 `obsidian` 侧。极致优雅，大模型产生的缓存不会弄脏你的笔记板！
- **双引擎高质量数据摄取**：优先使用 `defuddle` 提取最干净的网页 Markdown（移除广告、导航），按需回退至 `trafilatura`，对 Token 极度友好。
- **多模型分级架构**：针对任务难度自动切换 Gemini 模型，完美贴合成本控制：
  - **Gemini 2.5 Pro**：处理复杂推理任务，如撰写深度概念文章、回答高难度提问。
  - **Gemini 2.5 Flash**：处理日常任务，如生成摘要、局部更新。
  - **Gemini 2.5 Flash-Lite**：处理简单且频繁的任务，如索引生成、检索匹配（极度节省成本）。
- **原生兼容 Obsidian 语法**：深度集成 [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) 的 markdown 规范。生成的知识库自动使用 `[[双向链接]]`、`> [!note]` 提示框，以及正确的 YAML properties 和 `==高亮==` 标注。

---

## 目录结构设计

经过代码解耦后的双核架构：

```text
你的工作区 (例如 ~/docs) 
├── obsidian/             # 👉 纯内容的 Obsidian Vault 你的专属外脑
│   ├── raw/              # 原始资料（由 Agent 自动写入或人工投喂）
│   ├── wiki/             # Agent 持续编译扩充的核心概念维基
│   └── output/           # Agent 进行问答互动沉淀的输出报告
│
└── obsidian-agent/       # 👉 控制端与大脑 (当前所在本项目)
    ├── scripts/          
    │   ├── utils.py      # 共用工具（Gemini 调用、模型降级、目录解耦）
    │   ├── ingest.py     # 外部网络数据提取
    │   ├── compile.py    # Wiki 编译中枢
    │   └── qa.py         # 问答伴侣
    ├── config.yaml       # 用户配置偏好
    ├── .env              # API 密钥（安全隔离）
    └── requirements.txt  # Python 依赖
```

---

## 快速开始

### 1. 环境依赖 (需要在 `obsidian-agent` 中执行)

确保系统中已安装 Node.js 和 Python 3：

```bash
# 切换到 Agent 设置组
cd obsidian-agent/

# Python 依赖
pip3 install -r requirements.txt

# Node.js 依赖 (用于更高质量网页内容提取)
npm install -g defuddle
```

### 2. 配置 API Key 与挂载参数

编辑 `obisian-agent/.env` 文件，填入你的 Google Gemini API Key [获取地址](https://aistudio.google.com/apikey)：

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

并在 `config.yaml` 确认 `vault_dir` 正确指向了你的知识库目录：
```yaml
paths:
  vault_dir: "../obsidian"  # 挂载参数指向你的笔记区！
```

### 3. 操作指令示例

*注意：以下所有指令均在 `obsidian-agent/` 目录路径下执行*

**摄取资料（投喂素材）：**
```bash
# 摄取网络长文
python3 scripts/ingest.py url https://lilianweng.github.io/posts/2023-06-23-agent/

# 摄取 PDF 论文
python3 scripts/ingest.py pdf ~/papers/attention.pdf

# 摄取任意本地文件
python3 scripts/ingest.py file ~/code/script.py

# 查看已存入文档库的源文件列表
python3 scripts/ingest.py list
```

**触发全自动编译思考（构建维基）：**
```bash
# 执行增量编译（大模型只会花费极少的 token 去补全新资料并更新全网链接）
python3 scripts/compile.py

# 查看编译库的进展大盘！
python3 scripts/compile.py --status
```

**对话与查阅（调取心智）：**
```bash
# 运行问答机器人（Agent）
python3 scripts/qa.py

# 以快捷流直接丢问题进去获取解答，并帮你把整篇整理导出成 Markdown 到 output/
python3 scripts/qa.py --save "大语言模型如何应对思维链局限问题？"
```

---

## 在 Obsidian 中使用（最佳化体验建议）

因为我们完全剥离出了 `obsidian/` 目录，你可以直接在 Obsidian 极其清爽地打开 `../obsidian` 文件夹作为你的顶级 Vault 源。

为了实现零代码、全鼠标流体验，我们强烈建议你：
1. **安装 Obsidian 第三方插件 `Shell Commands`**。
2. 配置好命令： `python3 /你的绝对路径/obsidian-agent/scripts/compile.py`，并将它设置一个别名叫做 `“触发 Agent 中枢”`。
3. 把上述命令放到侧边栏，从而你可以一边舒舒服服看文章，一边按下侧边栏图标让 Agent 后台帮你萃取最新导入的论文材料。
