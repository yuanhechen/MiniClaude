# CLAUDE.md

This file provides guidance when working with code in this repository.

## Project Overview

DeepAnalyze（miniclaude）：CLI AI agent，**TypeScript + ink**（对标 Claude Code 的终端渲染）。连接 dashscope 的 Anthropic 兼容端点（qwen3.7-plus），支持工具调用、流式输出、skill、会话存储、剪贴板图片粘贴。中文 UI / 中文 prompt。

**为什么 ink**：为同时实现「流式逐字 + 底部状态栏常驻 + 鼠标滚轮翻原生 scrollback 历史」三者兼得 —— 这正是 Claude Code 用 ink 渲染模型做到的，prompt_toolkit 无法实现（全屏无 scrollback，inline+patch_stdout 流式延迟）。靠 ink 的 `<Static>`（已完成消息进原生 scrollback）+ 动态区每帧 diff（当前流式 + 状态栏 + 输入）。

## Running

```bash
export DASHSCOPE_API_KEY=sk-...   # dashscope key（必须，从环境变量读，不硬编码）
npm install
npm start                         # = tsx src/main.tsx
```

`q` 退出，或 Ctrl-C（ink 默认 exitOnCtrlC）。其它：`npm run probe`（验证 dashscope SDK 兼容）、`npm run typecheck`（tsc --noEmit）。

硬依赖：`ink` / `react` / `@anthropic-ai/sdk` / `sharp`（图片压缩，替代 PIL）/ `ink-text-input` / `ink-spinner` / `gray-matter`（skill frontmatter）。运行时 `tsx`（直接跑 .tsx，无 build）。见 `package.json`。

## Architecture（src/）

### 核心模块
- **config.ts** — 配置常量（`API_BASE_URL`=`https://dashscope.aliyuncs.com/apps/anthropic`、`MODEL`、`MAX_TOKENS`/`CONTEXT_WINDOW`=131072、`IMAGE_*` 阈值）+ `getApiKey()`（读 env）+ 符号/主色 `#D97757`。
- **types.ts** — Anthropic messages 类型（`MessageParam`/`ContentBlock`/`ToolCall`）+ `StreamEvent`（5 事件）+ `CommittedItem`（进 `<Static>` 的视图模型）。
- **store.ts** — `createStore`（CC 风格，~30 行）+ `useSyncExternalStore`。**核心契约**：`committed` 只增（喂 `<Static>` 进原生 scrollback）；`streamingText`/`phase` 等动态区字段每帧整体替换（ink 行级 diff）。
- **llm.ts** — `callLLMStream` async generator。`@anthropic-ai/sdk` 配 dashscope（`baseURL` + `authToken`→`Authorization: Bearer` + `signal`）。**自己累积 `content_blocks`**（dashscope 与 SDK `currentMessage` 累积不兼容）；yield 5 事件（thinking/text/tool_call/done/interrupted）+ timing（ttft/decode_time/total）。
- **tools.ts** — 6 工具（bash/read/write/edit/skill/ask）+ `compressImage`（sharp，候选策略 PNG/JPEG 取小→JPEG 渐进降质）+ `TOOLS_SCHEMAS`。`ask` 异步化（store `askResolver` + Promise）。
- **executor.ts** — `partitionToolCalls`（连续 safe 合并发批，unsafe 串行）+ `executeBatch`（`Promise.all` 保序）+ `buildToolResultBlock`（Anthropic tool_result 格式）。
- **agent.ts** — `handleSubmit`（命令 / 图片 / 对话分发）+ `runTurn`（多轮工具循环，`MAX_TOOL_ROUNDS`=100，ESC 中断保留 partial）。
- **commands.ts** — 13 斜杠命令（help/clear/compact/tools/skills/model/history/perf/verbose/context/status/save/load/sessions/q）+ `parseCommand`/`handleCommand` + welcome 横幅/logo。
- **skills.ts** — `loadSkills`（扫 `<dir>/<sub>/SKILL.md`，frontmatter 解析）+ `getSkillPrompt`（`$ARGUMENTS` 替换）+ `getSkillListing`（注入 system）。
- **session.ts** — `~/.miniclaude/sessions/`；`autosaveSession`（覆盖 `current_session.json`）+ `saveSession`/`loadSession`/`listSessions`（快照，上限 50）+ `compressContent`（持久化去 base64）。
- **compaction.ts** — `compactMediaMessages`/`compactOldToolResults`（**修正了 Python 版两处 bug**：`image_url`→`image`、`role==tool`→`role==user`+tool_result blocks）。
- **clipboard.ts** — `getClipboardImage`（WSL2 powershell.exe / xclip / wl-paste / macOS osascript / Windows powershell，返回 PNG Buffer）。

### UI 组件（components/）
- **App.tsx** — `<Static items={committed}>`（已完成进 scrollback）+ 动态区（Spinner/流式文本/状态栏/Input）+ `useInput` 全局 ESC 中断。
- **Input.tsx** — `ink-text-input` + `useInput`：Tab 命令补全（`/` 前缀）+ Ctrl-V 粘贴剪贴板图片（`[Image #N]`）+ ask 模式 resolve `askResolver`。
- **MessageList.tsx** — `CommittedItem` 渲染（user `❯` / assistant text / tool `⏺`+`⎿` / system）。
- **StatusBar.tsx** — 底部常驻 context/perf 状态栏（读 store `usage`/`timing`）。

## Key 设计

- **流式 → 状态链路**：SDK `content_block_delta` → `appendText(delta)`（动态区 `streamingText` 累加，ink diff 逐字）→ `done`/`tool_call` 时快照 `commit({kind:'assistant',content})` 进 `<Static>`（scrollback）+ `resetStream()`。
- **dashscope SDK**：`new Anthropic({ baseURL, authToken })`，SDK 自动追加 `/v1/messages`；`client.messages.stream({...}, { signal })` + `for await`；ESC → `AbortController.abort()` → `APIUserAbortError`。
- **`<Static>` 只增**：已 commit 的项永不修改（流式文本 done 时才 commit 定型内容）。
- **ESM**：`"type":"module"`，import 带 `.js` 后缀；`tsx` 直接跑 `.tsx`。

## Tests / 验证脚本
- `src/scripts/probe.ts` — 验证 dashscope SDK 真实兼容（`DASHSCOPE_API_KEY=xxx npm run probe`，看 text 事件流 + done usage/timing）。
- `src/scripts/render-test.tsx` — `ink-testing-library` 确定性渲染验证（流式逐字 + 状态栏常驻 + 命令补全/toggle，不依赖 tty）。
- `read_tool_test/` — 保留的历史 Python 测试目录。
