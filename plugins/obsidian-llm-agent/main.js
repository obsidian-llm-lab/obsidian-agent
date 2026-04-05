const {
    Plugin,
    Notice,
    PluginSettingTab,
    Setting,
    Modal,
    ItemView,
} = require('obsidian');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const VIEW_TYPE_AGENT_TASKS = 'llm-agent-task-view';

const DEFAULT_SETTINGS = {
    agentDirectory: '',
    pythonCommand: 'python3',
    autoOpenResult: true,
    openIndexAfterCompile: true,
    saveQaReport: true,
    showVerboseLogs: false,
};

function tailText(text, maxLines = 12) {
    return text
        .split(/\r?\n/)
        .map((line) => line.trimEnd())
        .filter(Boolean)
        .slice(-maxLines)
        .join('\n');
}

function extractMatch(text, pattern) {
    const match = text.match(pattern);
    return match ? match[1].trim() : '';
}

class TextPromptModal extends Modal {
    constructor(app, options) {
        super(app);
        this.options = options;
        this.value = options.initialValue || '';
    }

    onOpen() {
        const { contentEl } = this;
        const { title, placeholder, buttonText, description, multiline } = this.options;

        this.modalEl.addClass('llm-agent-modal');
        contentEl.empty();
        contentEl.addClass('llm-agent-modal-content');
        contentEl.createEl('h2', { text: title });
        if (description) {
            contentEl.createEl('p', {
                text: description,
                cls: 'llm-agent-modal-description',
            });
        }

        const formEl = contentEl.createDiv({ cls: 'llm-agent-modal-form' });
        const inputEl = multiline
            ? formEl.createEl('textarea', {
                  attr: {
                      rows: '6',
                      placeholder: placeholder || '',
                  },
                  cls: 'llm-agent-modal-input llm-agent-modal-textarea',
              })
            : formEl.createEl('input', {
                  type: 'text',
                  placeholder: placeholder || '',
                  cls: 'llm-agent-modal-input',
              });

        inputEl.value = this.value;
        inputEl.focus();
        inputEl.select?.();

        const hint = multiline
            ? '按 Cmd/Ctrl + Enter 提交'
            : '按 Enter 提交';
        contentEl.createEl('p', {
            text: hint,
            cls: 'setting-item-description llm-agent-modal-hint',
        });

        const buttonRow = contentEl.createDiv({
            cls: 'llm-agent-modal-actions',
        });

        const submitButton = buttonRow.createEl('button', {
            text: buttonText || '提交',
            cls: 'mod-cta',
        });

        const submit = () => {
            const value = inputEl.value.trim();
            if (!value) {
                new Notice('请输入内容后再继续。');
                return;
            }
            this.close();
            this.options.onSubmit(value);
        };

        submitButton.addEventListener('click', submit);
        inputEl.addEventListener('keydown', (evt) => {
            const isSubmit = multiline
                ? evt.key === 'Enter' && (evt.metaKey || evt.ctrlKey)
                : evt.key === 'Enter';
            if (isSubmit) {
                evt.preventDefault();
                submit();
            }
        });
    }

    onClose() {
        this.modalEl.removeClass('llm-agent-modal');
        this.contentEl.empty();
    }
}

class LLMAgentTaskView extends ItemView {
    constructor(leaf, plugin) {
        super(leaf);
        this.plugin = plugin;
    }

    getViewType() {
        return VIEW_TYPE_AGENT_TASKS;
    }

    getDisplayText() {
        return 'LLM Agent';
    }

    getIcon() {
        return 'bot';
    }

    async onOpen() {
        this.render();
    }

    render() {
        const { contentEl } = this;
        const task = this.plugin.taskState;

        contentEl.empty();
        contentEl.addClass('llm-agent-view');

        const heroEl = contentEl.createDiv({ cls: 'llm-agent-hero' });
        const heroTopEl = heroEl.createDiv({ cls: 'llm-agent-hero-top' });
        heroTopEl.createEl('h2', { text: 'LLM Agent' });
        heroTopEl.createEl('span', {
            text: this.plugin.getTaskStatusLabel(task),
            cls: `llm-agent-status-badge is-${task.status}`,
        });

        heroEl.createEl('p', {
            text: task.message || '在 Obsidian 里直接触发摄取、编译和问答。',
            cls: 'llm-agent-hero-description',
        });

        const actionRow = contentEl.createDiv({ cls: 'llm-agent-actions' });
        const actions = [
            ['摄取 URL', () => this.plugin.openIngestModal()],
            ['增量编译', () => this.plugin.runCompile()],
            ['查看编译状态', () => this.plugin.runStatus()],
            ['知识库问答', () => this.plugin.openQaModal()],
        ];

        actions.forEach(([label, action]) => {
            const button = actionRow.createEl('button', {
                text: label,
                cls: 'llm-agent-action-button',
            });
            button.disabled = task.status === 'running';
            button.addEventListener('click', action);
        });

        const statusBox = contentEl.createDiv({ cls: 'llm-agent-card llm-agent-status' });
        statusBox.createEl('h3', { text: '任务状态' });
        const metaList = statusBox.createDiv({ cls: 'llm-agent-meta-list' });

        if (task.type) {
            metaList.createEl('p', {
                text: `任务类型: ${task.type}`,
            });
        }

        if (task.startedAt) {
            metaList.createEl('p', {
                text: `开始时间: ${new Date(task.startedAt).toLocaleString()}`,
            });
        }

        if (task.endedAt) {
            metaList.createEl('p', {
                text: `结束时间: ${new Date(task.endedAt).toLocaleString()}`,
            });
        }

        if (task.summary) {
            const summaryBox = contentEl.createDiv({ cls: 'llm-agent-card' });
            summaryBox.createEl('h3', { text: '结果摘要' });
            summaryBox.createEl('pre', {
                text: task.summary,
                cls: 'llm-agent-summary',
            });
            if (task.resultPath) {
                const resultLinkRow = summaryBox.createDiv({ cls: 'llm-agent-result-row' });
                resultLinkRow.createEl('span', {
                    text: '结果文件',
                    cls: 'llm-agent-result-label',
                });
                const resultButton = resultLinkRow.createEl('button', {
                    text: path.basename(task.resultPath),
                    cls: 'llm-agent-result-button',
                });
                resultButton.addEventListener('click', () => this.plugin.openVaultFile(task.resultPath));
            }
        }

        const openRow = contentEl.createDiv({ cls: 'llm-agent-card llm-agent-open-actions' });
        openRow.createEl('h3', { text: '快速打开' });

        const openIndexButton = openRow.createEl('button', {
            text: '打开索引',
            cls: 'llm-agent-secondary-button',
        });
        openIndexButton.addEventListener('click', () => this.plugin.openVaultFile('wiki/index.md'));

        const openLatestReportButton = openRow.createEl('button', {
            text: '打开最新报告',
            cls: 'llm-agent-secondary-button',
        });
        openLatestReportButton.addEventListener('click', async () => {
            const latest = this.plugin.findLatestVaultFile('output/reports/');
            if (!latest) {
                new Notice('还没有可打开的问答报告。');
                return;
            }
            await this.plugin.openVaultFile(latest.path);
        });

        if (task.output) {
            const detailsEl = contentEl.createEl('details', {
                cls: 'llm-agent-card llm-agent-log-details',
            });
            detailsEl.createEl('summary', { text: '查看最近输出' });
            detailsEl.createEl('pre', {
                text: task.output,
                cls: 'llm-agent-output',
            });
        }
    }
}

class LLMAgentSettingTab extends PluginSettingTab {
    constructor(app, plugin) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display() {
        const { containerEl } = this;
        containerEl.empty();
        containerEl.createEl('h2', { text: 'LLM Agent 设置' });

        new Setting(containerEl)
            .setName('Agent 目录')
            .setDesc('obsidian-agent 项目的绝对路径。')
            .addText((text) =>
                text
                    .setPlaceholder('/Users/you/docs/obsidian-agent')
                    .setValue(this.plugin.settings.agentDirectory)
                    .onChange(async (value) => {
                        this.plugin.settings.agentDirectory = value.trim();
                        await this.plugin.saveSettings();
                    }),
            );

        new Setting(containerEl)
            .setName('Python 命令')
            .setDesc('用于执行后端脚本的命令前缀，例如 python3 或 uv run python。')
            .addText((text) =>
                text
                    .setPlaceholder('python3')
                    .setValue(this.plugin.settings.pythonCommand)
                    .onChange(async (value) => {
                        this.plugin.settings.pythonCommand = value.trim() || 'python3';
                        await this.plugin.saveSettings();
                    }),
            );

        new Setting(containerEl)
            .setName('执行后自动打开结果')
            .setDesc('任务成功后自动打开本次结果文件。')
            .addToggle((toggle) =>
                toggle.setValue(this.plugin.settings.autoOpenResult).onChange(async (value) => {
                    this.plugin.settings.autoOpenResult = value;
                    await this.plugin.saveSettings();
                }),
            );

        new Setting(containerEl)
            .setName('编译后打开索引')
            .setDesc('增量编译成功后自动打开 wiki/index.md。')
            .addToggle((toggle) =>
                toggle.setValue(this.plugin.settings.openIndexAfterCompile).onChange(async (value) => {
                    this.plugin.settings.openIndexAfterCompile = value;
                    await this.plugin.saveSettings();
                }),
            );

        new Setting(containerEl)
            .setName('QA 默认保存报告')
            .setDesc('知识库问答默认追加 --save，将回答写入 output/reports。')
            .addToggle((toggle) =>
                toggle.setValue(this.plugin.settings.saveQaReport).onChange(async (value) => {
                    this.plugin.settings.saveQaReport = value;
                    await this.plugin.saveSettings();
                }),
            );

        new Setting(containerEl)
            .setName('输出详细日志到控制台')
            .setDesc('启用后会把完整 stdout/stderr 打到开发者控制台。')
            .addToggle((toggle) =>
                toggle.setValue(this.plugin.settings.showVerboseLogs).onChange(async (value) => {
                    this.plugin.settings.showVerboseLogs = value;
                    await this.plugin.saveSettings();
                }),
            );
    }
}

module.exports = class LLMAgentPlugin extends Plugin {
    async onload() {
        await this.loadSettings();
        this.taskState = this.createIdleTaskState();

        this.registerView(
            VIEW_TYPE_AGENT_TASKS,
            (leaf) => new LLMAgentTaskView(leaf, this),
        );

        this.addSettingTab(new LLMAgentSettingTab(this.app, this));

        this.addRibbonIcon('bot', '打开 LLM Agent 面板', () => this.activateTaskView(true));

        this.addCommand({
            id: 'open-agent-view',
            name: 'KB: 打开 LLM Agent 面板',
            callback: () => this.activateTaskView(true),
        });

        this.addCommand({
            id: 'agent-ingest-url',
            name: 'KB: 摄取网页 URL',
            callback: () => this.openIngestModal(),
        });

        this.addCommand({
            id: 'agent-compile',
            name: 'KB: 增量编译知识库',
            callback: () => this.runCompile(),
        });

        this.addCommand({
            id: 'agent-status',
            name: 'KB: 查看编译状态',
            callback: () => this.runStatus(),
        });

        this.addCommand({
            id: 'agent-qa',
            name: 'KB: 知识库问答',
            callback: () => this.openQaModal(),
        });
    }

    onunload() {
        this.app.workspace
            .getLeavesOfType(VIEW_TYPE_AGENT_TASKS)
            .forEach((leaf) => leaf.detach());
    }

    createIdleTaskState() {
        return {
            status: 'idle',
            type: '',
            startedAt: '',
            endedAt: '',
            message: '等待执行',
            output: '',
            summary: '',
            resultPath: '',
        };
    }

    async loadSettings() {
        const loaded = await this.loadData();
        this.settings = Object.assign({}, DEFAULT_SETTINGS, loaded);
        if (!this.settings.agentDirectory) {
            this.settings.agentDirectory = this.getDefaultAgentDirectory();
        }
        await this.saveSettings();
    }

    async saveSettings() {
        await this.saveData(this.settings);
    }

    getDefaultAgentDirectory() {
        const vaultPath = this.app.vault.adapter.basePath;
        return path.resolve(vaultPath, '../obsidian-agent');
    }

    getTaskStatusLabel(task) {
        const labels = {
            idle: '空闲',
            running: '运行中',
            success: '执行成功',
            failed: '执行失败',
        };
        return labels[task.status] || task.status;
    }

    updateTaskState(patch) {
        this.taskState = Object.assign({}, this.taskState, patch);
        this.refreshTaskViews();
    }

    refreshTaskViews() {
        this.app.workspace.getLeavesOfType(VIEW_TYPE_AGENT_TASKS).forEach((leaf) => {
            if (leaf.view && typeof leaf.view.render === 'function') {
                leaf.view.render();
            }
        });
    }

    async activateTaskView(focus) {
        let leaf = this.app.workspace.getLeavesOfType(VIEW_TYPE_AGENT_TASKS)[0];
        if (!leaf) {
            leaf = this.app.workspace.getRightLeaf(false);
            await leaf.setViewState({
                type: VIEW_TYPE_AGENT_TASKS,
                active: !!focus,
            });
        }
        if (focus) {
            this.app.workspace.revealLeaf(leaf);
        }
    }

    openIngestModal() {
        new TextPromptModal(this.app, {
            title: '摄取网页 URL',
            description: '输入要写入 raw/articles 的网页链接。',
            placeholder: 'https://example.com/article',
            buttonText: '开始摄取',
            multiline: false,
            onSubmit: (url) => this.runIngest(url),
        }).open();
    }

    openQaModal() {
        new TextPromptModal(this.app, {
            title: '知识库问答',
            description: '输入你的问题，回答会基于当前 wiki 生成。',
            placeholder: '例如：RLHF 的主要阶段包括什么？',
            buttonText: '开始问答',
            multiline: true,
            onSubmit: (question) => this.runQa(question),
        }).open();
    }

    validateRunnerSettings() {
        if (this.taskState.status === 'running') {
            new Notice('已有任务在运行，请等待当前任务完成。');
            return false;
        }

        const agentDirectory = this.settings.agentDirectory;
        if (!agentDirectory || !fs.existsSync(agentDirectory)) {
            new Notice('LLM Agent 插件设置中的 Agent 目录不存在，请先检查设置。');
            return false;
        }

        const scriptsDir = path.join(agentDirectory, 'scripts');
        if (!fs.existsSync(scriptsDir)) {
            new Notice('Agent 目录中没有找到 scripts/，请确认路径正确。');
            return false;
        }

        return true;
    }

    summarizeOutput(stdout, stderr) {
        const parts = [];
        const stdoutTail = tailText(stdout);
        const stderrTail = tailText(stderr);
        if (stdoutTail) {
            parts.push(stdoutTail);
        }
        if (stderrTail) {
            parts.push(`[stderr]\n${stderrTail}`);
        }
        return parts.join('\n\n');
    }

    buildTaskSummary(type, stdout, stderr, resultPath, code) {
        const lines = [];

        if (code !== 0) {
            const stderrSummary = tailText(stderr || stdout, 6);
            if (stderrSummary) {
                lines.push(stderrSummary);
            }
            return lines.join('\n');
        }

        if (type === 'ingest') {
            const title = extractMatch(stdout, /标题:\s*(.+)/);
            const contentLength = extractMatch(stdout, /内容长度:\s*(\d+\s*字符)/);
            if (title) {
                lines.push(`标题: ${title}`);
            }
            if (contentLength) {
                lines.push(`内容长度: ${contentLength}`);
            }
        }

        if (type === 'compile') {
            const pendingCount = extractMatch(stdout, /发现\s+(\d+)\s+个待编译资料/);
            const compileSummary = extractMatch(stdout, /编译完成:\s*([^\n]+)/);
            if (pendingCount) {
                lines.push(`处理资料: ${pendingCount} 个`);
            }
            if (compileSummary) {
                lines.push(`结果: ${compileSummary}`);
            }
        }

        if (type === 'status') {
            const rawCount = extractMatch(stdout, /原始资料:\s+(\d+\s*个)/);
            const compiledCount = extractMatch(stdout, /已编译:\s+(\d+)/);
            const uncompiledCount = extractMatch(stdout, /未编译:\s+(\d+)/);
            const wikiCount = extractMatch(stdout, /Wiki 文章:\s+(\d+\s*篇)/);
            const summaryCount = extractMatch(stdout, /摘要:\s+(\d+)/);
            const conceptCount = extractMatch(stdout, /概念:\s+(\d+)/);
            if (rawCount) {
                lines.push(`原始资料: ${rawCount}`);
            }
            if (compiledCount || uncompiledCount) {
                lines.push(`编译进度: ${compiledCount || '0'} 已编译 / ${uncompiledCount || '0'} 未编译`);
            }
            if (wikiCount) {
                lines.push(`Wiki 文章: ${wikiCount}`);
            }
            if (summaryCount || conceptCount) {
                lines.push(`摘要/概念: ${summaryCount || '0'} / ${conceptCount || '0'}`);
            }
        }

        if (type === 'qa') {
            const relatedCount = extractMatch(stdout, /找到\s+(\d+)\s+篇相关文章/);
            if (relatedCount) {
                lines.push(`引用文章: ${relatedCount} 篇`);
            } else {
                lines.push('回答已生成');
            }
        }

        if (!lines.length) {
            const fallback = tailText(stdout, 5);
            if (fallback) {
                lines.push(fallback);
            }
        }

        return lines.join('\n');
    }

    buildCommandArgs(scriptArgs) {
        const prefix = (this.settings.pythonCommand || 'python3')
            .trim()
            .split(/\s+/)
            .filter(Boolean);
        const command = prefix[0] || 'python3';
        const args = [...prefix.slice(1), ...scriptArgs];
        return { command, args };
    }

    async runIngest(url) {
        if (!/^https?:\/\//.test(url)) {
            new Notice('请输入合法的 http 或 https URL。');
            return;
        }

        await this.runTask({
            type: 'ingest',
            args: ['scripts/ingest.py', 'url', url],
            startNotice: `正在摄取 ${url}`,
            successNotice: '摄取成功，内容已写入 raw/articles。',
            failureNotice: '摄取失败，请查看 LLM Agent 面板输出。',
            resultResolver: () => this.findLatestVaultFile('raw/articles/'),
        });
    }

    async runCompile() {
        await this.runTask({
            type: 'compile',
            args: ['scripts/compile.py'],
            startNotice: '正在执行增量编译，请稍候。',
            successNotice: '增量编译完成。',
            failureNotice: '编译失败，请查看 LLM Agent 面板输出。',
            resultResolver: () =>
                this.settings.openIndexAfterCompile
                    ? this.app.vault.getAbstractFileByPath('wiki/index.md')
                    : null,
        });
    }

    async runStatus() {
        await this.runTask({
            type: 'status',
            args: ['scripts/compile.py', '--status'],
            startNotice: '正在读取编译状态。',
            successNotice: '编译状态已更新。',
            failureNotice: '读取编译状态失败，请查看 LLM Agent 面板输出。',
            resultResolver: () => null,
        });
    }

    async runQa(question) {
        const args = ['scripts/qa.py'];
        if (this.settings.saveQaReport) {
            args.push('--save');
        }
        args.push(question);

        await this.runTask({
            type: 'qa',
            args,
            startNotice: '正在生成回答，请稍候。',
            successNotice: this.settings.saveQaReport
                ? '问答完成，报告已写入 output/reports。'
                : '问答完成。',
            failureNotice: '问答失败，请查看 LLM Agent 面板输出。',
            resultResolver: () =>
                this.settings.saveQaReport
                    ? this.findLatestVaultFile('output/reports/')
                    : null,
        });
    }

    async runTask(options) {
        if (!this.validateRunnerSettings()) {
            return;
        }

        await this.activateTaskView(false);
        new Notice(options.startNotice, 4000);

        const startedAt = new Date().toISOString();
        this.updateTaskState({
            status: 'running',
            type: options.type,
            startedAt,
            endedAt: '',
            message: '任务执行中...',
            output: '',
            summary: '',
            resultPath: '',
        });

        const stdoutParts = [];
        const stderrParts = [];

        await new Promise((resolve) => {
            const { command, args } = this.buildCommandArgs(options.args);
            const child = spawn(command, args, {
                cwd: this.settings.agentDirectory,
                shell: false,
            });

            child.stdout.on('data', (chunk) => {
                stdoutParts.push(chunk.toString());
                this.updateTaskState({
                    output: this.summarizeOutput(stdoutParts.join(''), stderrParts.join('')),
                });
            });

            child.stderr.on('data', (chunk) => {
                stderrParts.push(chunk.toString());
                this.updateTaskState({
                    output: this.summarizeOutput(stdoutParts.join(''), stderrParts.join('')),
                });
            });

            child.on('error', (error) => {
                stderrParts.push(String(error));
            });

            child.on('close', async (code) => {
                const stdout = stdoutParts.join('');
                const stderr = stderrParts.join('');
                const endedAt = new Date().toISOString();

                if (this.settings.showVerboseLogs) {
                    console.log(`[LLM Agent:${options.type}] stdout\n${stdout}`);
                    if (stderr) {
                        console.error(`[LLM Agent:${options.type}] stderr\n${stderr}`);
                    }
                }

                if (code === 0) {
                    const resultFile = await options.resultResolver();
                    const resultPath = resultFile ? resultFile.path : '';

                    this.updateTaskState({
                        status: 'success',
                        endedAt,
                        message: '任务执行完成',
                        output: this.summarizeOutput(stdout, stderr),
                        summary: this.buildTaskSummary(
                            options.type,
                            stdout,
                            stderr,
                            resultPath,
                            code,
                        ),
                        resultPath,
                    });

                    new Notice(options.successNotice, 5000);

                    if (this.settings.autoOpenResult && resultPath) {
                        await this.openVaultFile(resultPath);
                    }
                } else {
                    this.updateTaskState({
                        status: 'failed',
                        endedAt,
                        message: `退出码: ${code}`,
                        output: this.summarizeOutput(stdout, stderr) || '没有捕获到输出。',
                        summary: this.buildTaskSummary(
                            options.type,
                            stdout,
                            stderr,
                            '',
                            code,
                        ),
                        resultPath: '',
                    });
                    new Notice(options.failureNotice, 6000);
                }

                resolve();
            });
        });
    }

    findLatestVaultFile(prefix) {
        const files = this.app.vault
            .getFiles()
            .filter((file) => file.path.startsWith(prefix))
            .sort((a, b) => b.stat.mtime - a.stat.mtime);
        return files[0] || null;
    }

    async openVaultFile(filePath) {
        const target = this.app.vault.getAbstractFileByPath(filePath);
        if (!target) {
            new Notice(`未找到文件: ${filePath}`);
            return;
        }
        await this.app.workspace.getLeaf(true).openFile(target);
    }
};
