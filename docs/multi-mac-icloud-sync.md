# 使用 Apple iCloud 在多台 Mac 之间同步知识库

这篇文档说明如何在 **同一个 Apple ID** 下，使用 **iCloud Drive** 在多台 Mac 之间同步多个 Obsidian 知识库，并结合本仓库的脚本完成初始化、接入和本地软链接管理。

适合的场景：

- 一台 MacBook Air / Pro 作为移动工作机
- 一台 Mac mini 作为固定工作机
- 两台机器都登录同一个 Apple 账号
- 希望多个知识库在两台机器之间自动同步

## 推荐原则

建议把 **知识库本身** 放在 iCloud Drive 中，把 **obsidian-agent 后端仓库** 放在每台机器自己的本地目录。

推荐结构：

```text
本地机器 A / B
├── ~/docs/obsidian-agent                 # 本地后端仓库，各台机器各自一份
└── ~/Library/Mobile Documents/com~apple~CloudDocs/
    ├── obsidian                          # 知识库 1
    ├── Knowledge Base A                  # 知识库 2
    └── Knowledge Base B                  # 知识库 3
```

这样做的好处：

- 知识库内容通过 iCloud 自动同步
- 后端环境、`.venv`、Node 依赖不放在 iCloud，避免同步冲突
- 每台 Mac 都可以独立升级后端和插件

## 一、在第一台 Mac 上创建知识库

假设第一台机器是你的主力开发机。

### 1. 准备本地后端

先在本地克隆并安装 `obsidian-agent`：

```bash
git clone https://github.com/obsidian-llm-lab/obsidian-agent.git
cd obsidian-agent
./scripts/install.sh
```

如果你已经有这个仓库，可以跳过这一步。

### 2. 在 iCloud Drive 下创建新知识库

例如创建一个新的知识库：

```bash
./scripts/bootstrap_vault.sh "/Users/your-name/Library/Mobile Documents/com~apple~CloudDocs/My Knowledge Base"
```

这个脚本会：

- 创建最小 `.obsidian/` 结构
- 安装 `obsidian-llm-agent` 插件
- 写入插件默认配置
- 把插件加入 `community-plugins.json`

### 3. 在 Obsidian 中打开这个 vault

然后在 Obsidian 里：

1. 打开这个 iCloud 路径下的新 vault
2. 启用社区插件
3. 启用 `obsidian-llm-agent`
4. 打开左侧 `LLM Agent` 面板
5. 点击“初始化知识库”
6. 选择模板，例如：
   - `通用知识库`
   - `金融研究库`

至此，第一台 Mac 上的知识库就准备好了。

## 二、在第二台 Mac 上接入同一个知识库

第二台机器不需要重新创建知识库，只需要接入同一个 iCloud 目录。

### 1. 确认使用同一个 Apple ID

第二台 Mac 必须登录同一个 Apple 账号，并且开启 iCloud Drive。

### 2. 等待 iCloud 同步知识库目录

在第二台机器上，你应该能看到同样的目录：

```text
~/Library/Mobile Documents/com~apple~CloudDocs/
```

其中会包含你在第一台机器上创建的：

- `obsidian`
- `Knowledge Base A`
- `Knowledge Base B`
- 其他知识库目录

### 3. 在第二台 Mac 本地准备后端仓库

同样在第二台机器本地准备一份 `obsidian-agent`：

```bash
git clone https://github.com/obsidian-llm-lab/obsidian-agent.git
cd obsidian-agent
./scripts/install.sh
```

这里的重点是：

- 后端仓库是每台机器各自本地的一份
- 但知识库目录是同一份 iCloud 数据

### 4. 打开 iCloud 中已有的 vault

在第二台机器的 Obsidian 中，直接打开 iCloud 里的现有知识库路径即可。

如果插件配置没有自动对上本机的 `obsidian-agent` 路径，可以在插件设置里检查：

- `Agent Directory`
- `Python Command`

通常改成第二台机器本地的仓库路径即可。

## 三、如何统一管理多个 iCloud 知识库

当 iCloud 根目录下的知识库越来越多时，建议在每台机器上建立一个本地“软链接聚合目录”。

例如：

```bash
mkdir -p ~/icloud-vaults
./scripts/link_icloud_roots.sh ~/icloud-vaults
```

这个脚本会扫描：

```text
~/Library/Mobile Documents/com~apple~CloudDocs
```

并自动：

- 跳过 `Desktop`
- 跳过 `Documents`
- 跳过隐藏项
- 把其他一级目录都软链接到 `~/icloud-vaults`

例如执行后，你会得到：

```text
~/icloud-vaults/
├── obsidian -> ~/Library/Mobile Documents/com~apple~CloudDocs/obsidian
├── Knowledge Base A -> ~/Library/Mobile Documents/com~apple~CloudDocs/Knowledge Base A
└── Knowledge Base B -> ~/Library/Mobile Documents/com~apple~CloudDocs/Knowledge Base B
```

这样做的好处：

- 你可以用一个固定目录统一管理多个知识库入口
- 多台 Mac 上都可以保持同样的目录习惯
- 对 Obsidian、Alfred、Raycast、脚本和自动化都更友好

常用命令：

```bash
# 先预演
./scripts/link_icloud_roots.sh --dry-run ~/icloud-vaults

# 真正创建
./scripts/link_icloud_roots.sh ~/icloud-vaults

# 如果目标目录已存在冲突，允许覆盖
./scripts/link_icloud_roots.sh --force ~/icloud-vaults
```

## 四、推荐工作流

推荐你这样使用两台 Mac：

### 主力机

- 创建新知识库
- 初始化目录和模板
- 配置插件和模型参数
- 做主要的资料摄取和编译

### 辅助机

- 打开同一个 iCloud 知识库
- 浏览 `wiki/`
- 做轻量修改、问答和临时补充
- 必要时也可执行编译

## 五、注意事项

### 1. 不建议把整个 `obsidian-agent` 仓库放到 iCloud 里

尤其是这些目录不适合同步：

- `.venv/`
- `node_modules/`
- 本地缓存文件

推荐始终把后端仓库保留在各台机器的本地目录。

### 2. 知识库内容适合放到 iCloud

适合同步的通常是：

- `raw/`
- `wiki/`
- `output/`
- `.obsidian/`

### 3. 两台机器不要同时做大规模编译

虽然内容能同步，但如果两台机器同时对同一个知识库做大量编译，仍然可能出现同步时序上的覆盖或冲突。

更稳妥的建议是：

- 一台机器负责主要编译
- 另一台机器负责浏览、问答和轻量补充

### 4. API Key 不建议依赖 iCloud 同步

插件会把配置写到本地后端的：

- `.env`
- `config.yaml`

这些文件位于每台机器自己的本地仓库中，所以你需要在每台机器上分别确认 API Key 和模型配置。

## 六、最小可执行方案

如果你只想快速跑通，最短路径是：

### 第一台 Mac

```bash
cd ~/docs/obsidian-agent
./scripts/bootstrap_vault.sh "~/Library/Mobile Documents/com~apple~CloudDocs/Knowledge Base A"
```

然后在 Obsidian 里打开 `Knowledge Base A`，启用插件，点击“初始化知识库”。

### 第二台 Mac

```bash
mkdir -p ~/icloud-vaults
cd ~/docs/obsidian-agent
./scripts/link_icloud_roots.sh ~/icloud-vaults
```

然后直接在 Obsidian 中打开：

```text
~/icloud-vaults/Knowledge Base A
```

## 七、总结

最推荐的组合是：

- **知识库放 iCloud**
- **后端仓库放本地**
- **每台机器各自安装一份 `obsidian-agent`**
- **用 `bootstrap_vault.sh` 初始化空白 vault**
- **用 `link_icloud_roots.sh` 统一管理多个知识库入口**

这样既保留了 iCloud 在多台 Mac 之间自动同步的便利，也避免了把 Python/Node 运行环境同步进云盘带来的不稳定因素。
