# DeepAnalyze（miniclaude）

CLI AI agent，**TypeScript + ink**，对标 Claude Code 的终端渲染。连接阿里云 dashscope 的 Anthropic 兼容端点（qwen3.7-plus），支持工具调用、流式输出、skill、会话存储、剪贴板图片粘贴。

## 特性

- **流式逐字 + 底部状态栏常驻 + 鼠标滚轮翻原生 scrollback** 三者兼得 —— ink `<Static>` + 动态区 diff，对标 Claude Code（prompt_toolkit 做不到）
- 6 工具：`bash` / `read` / `write` / `edit` / `skill` / `ask`
- 流式思考（默认折叠，`/verbose` 展开）
- ESC 中断流式（AbortController）
- 13 斜杠命令 + Tab 补全
- Ctrl-V 粘贴剪贴板图片（`[Image #N]`）
- skill 系统 + 会话自动保存 / 快照 / 加载
- 跨平台剪贴板（WSL2 / Linux / macOS / Windows）

## 快速开始

```bash
# 1. 安装依赖
npm install

# 2. 设置 dashscope API key
export DASHSCOPE_API_KEY=sk-e5919bf6a13a4f4b98a59420c1ffd80e

# 3. 启动
npm start        # = tsx src/main.tsx
```

输入 `q` 退出，或 Ctrl-C（ink 默认 exitOnCtrlC）。

## 命令

| 命令 | 作用 |
|---|---|
| `/help` | 列出命令 |
| `/context` `/perf` | 开关底部状态栏（context / perf 指标）|
| `/verbose` | 展开 / 折叠思考内容 |
| `/clear` | 清空对话 |
| `/save` `/load` `/sessions` | 会话保存 / 加载 / 列表 |
| `/compact` | 压缩上下文（媒体 + 旧工具结果）|
| `/tools` `/skills` `/model` `/history` | 信息查看 |
| `/q` | 退出 |

**交互**：`Tab` 补全命令；`Ctrl-V` 粘贴剪贴板图片；`ESC` 中断流式。

## 架构

| 维度 | 选择 |
|---|---|
| 运行时 | Node.js + **tsx**（直接跑 .tsx，无 build）|
| UI | **ink 5 + react 18**，`<Static>` 复刻 CC 的 scrollback 魔法 |
| LLM | `@anthropic-ai/sdk` 配 dashscope（`baseURL` + `authToken` + `signal`）|
| 状态 | `createStore` + `useSyncExternalStore`（CC 风格）|
| 图片 | **sharp**（替代 PIL）|

核心模块（`src/`）：
- `llm.ts` — 流式（自己累积 content_blocks）+ 5 事件 + timing + AbortSignal
- `agent.ts` — `handleSubmit` + `runTurn`（多轮工具循环）
- `tools.ts` / `executor.ts` — 6 工具 + 分批并发 + sharp 压缩
- `commands.ts` / `skills.ts` / `session.ts` / `compaction.ts` — 命令 / skill / 会话 / 压缩
- `clipboard.ts` — 5 平台剪贴板图片
- `components/` — App（`<Static>` + 动态区）/ Input / MessageList / StatusBar

详见 `CLAUDE.md`。

## 验证脚本

```bash
npm run probe        # 验证 dashscope SDK 兼容（流式 + usage/timing）
npm run typecheck    # tsc 类型检查
```

`src/scripts/render-test.tsx` — `ink-testing-library` 确定性渲染验证（流式逐字 + 状态栏常驻 + 命令补全，不依赖 tty）。

## 状态栏说明

底部状态栏（`/context` `/perf` 开启）：
- **ctx**：`ctx N/131,072 (X%) ███░░░` —— 上下文占用进度条
- **perf**：`perf in N · out N · TTFT · TPOT · decode tok/s` —— 性能指标

流式期间状态栏**常驻不消失**（在动态区，每帧 diff），这是换 ink 的核心收益。
