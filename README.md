# 🧠 Obsidian Agent

基于 [Andrej Karpathy 的理念](https://x.com/karpathy/status/2039805659525644595)，用 LLM 自动维护你的 Obsidian 知识库。

这个仓库现在同时包含两部分：

- `obsidian-agent` 后端：负责 `ingest / compile / qa`
- `obsidian-llm-agent` Obsidian 插件：在 Obsidian 内直接触发这些能力

目标是让其他人 clone 仓库后，通过一条安装命令把后台、插件和基础目录一起配置好。

## 项目结构

```text
obsidian-agent/
├── install.sh                     # 一键安装后台 + 插件 + vault 目录
├── config.yaml                    # 后端配置
├── .env.example                   # API Key 模板
├── package.json                   # 本地 Node 依赖（defuddle）
├── requirements.txt               # Python 依赖
├── plugins/
│   └── obsidian-llm-agent/        # Obsidian 插件源码
│       ├── manifest.json
│       ├── main.js
│       └── styles.css
└── scripts/
    ├── ingest.py
    ├── compile.py
    ├── qa.py
    └── utils.py
```

## 一键安装

### 1. 克隆仓库

```bash
git clone https://github.com/obsidian-llm-lab/obsidian-agent.git
cd obsidian-agent
```

### 2. 运行安装脚本

默认会把 vault 安装到仓库旁边的 `../obsidian`：

```bash
./install.sh
```

如果你想指定自己的 Obsidian vault 路径：

```bash
./install.sh /absolute/path/to/your-obsidian-vault
```

安装脚本会自动完成这些事情：

- 创建 `.venv`
- 安装 Python 依赖
- 安装本地 Node 依赖 `defuddle`
- 创建 Obsidian vault 所需目录
- 把插件复制到 `vault/.obsidian/plugins/obsidian-llm-agent/`
- 写入插件默认配置
- 将插件加入 `community-plugins.json`
- 如果 `.env` 不存在，则从 `.env.example` 生成
- 将 `config.yaml` 中的 `paths.vault_dir` 改成你的目标 vault 路径

## 安装后只需做两件事

### 1. 配置 Gemini API Key

编辑仓库根目录的 `.env`：

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

### 2. 在 Obsidian 中启用插件

打开你的 vault，然后：

1. 进入 `Settings -> Community plugins`
2. 确认允许社区插件
3. 启用 `LLM Agent Console`

启用后，左侧会出现一个机器人图标，点击即可打开 `LLM Agent` 面板。

## 在 Obsidian 里能做什么

插件面板当前支持：

- `摄取 URL`
- `增量编译`
- `查看编译状态`
- `知识库问答`

所有任务都直接在 Obsidian 内触发，不需要手动打开终端。

## 默认生成的 vault 目录

```text
your-vault/
├── raw/
│   ├── articles/
│   ├── papers/
│   ├── code/
│   ├── images/
│   └── misc/
├── wiki/
│   ├── concepts/
│   ├── summaries/
│   └── relations/
└── output/
    ├── reports/
    ├── charts/
    └── slides/
```

## 后端命令

虽然推荐直接在 Obsidian 插件里使用，你仍然可以手动运行后端命令：

```bash
# 摄取网页
.venv/bin/python scripts/ingest.py url https://example.com/article

# 增量编译
.venv/bin/python scripts/compile.py

# 查看状态
.venv/bin/python scripts/compile.py --status

# 问答并保存报告
.venv/bin/python scripts/qa.py --save "什么是 RLHF？"
```

## 插件开发与同步

仓库中的插件源码位于 `plugins/obsidian-llm-agent/`。

如果你修改了插件源码，重新运行一次安装脚本即可把最新插件同步到目标 vault：

```bash
./install.sh /absolute/path/to/your-obsidian-vault
```

## 当前技术栈

- Python 后端
- Google Gemini API
- Obsidian Desktop 插件
- Node 本地依赖：`defuddle`

## 注意事项

- 这是桌面版 Obsidian 插件，移动端不可用
- 首次启用社区插件时，仍需要你在 Obsidian 里确认安全提示
- `.env` 不会提交到仓库，请自行保管 API Key
