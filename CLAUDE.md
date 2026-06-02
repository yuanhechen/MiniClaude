# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A minimal CLI-based AI agent ("miniclaude") that connects to an OpenAI-compatible LLM API with tool use and streaming output. Written in Chinese with Chinese-language prompts and UI. The entire agent lives in a single file: `agent_step4.py`.

## Running

```bash
python agent_step4.py
```

No build step, no dependencies beyond Python stdlib + `requests`. Type `q` to quit.

## Architecture

The codebase follows a linear pipeline in one file with clearly labeled sections:

1. **Config** (top) — `API_URL`, `API_KEY`, `MODEL` constants targeting an OpenAI-compatible endpoint
2. **Tool implementations** — `run_bash`, `read_file` (handles images via base64), `write_file`, `list_dir`, `calculate`
3. **Tool registry** (`TOOLS_REGISTRY`) — maps tool names to `(function, JSON schema)` pairs; `TOOLS_SCHEMAS` extracts the schemas for the API call
4. **Streaming LLM caller** (`call_llm_stream`) — SSE-based streaming that accumulates tool call fragments across chunks and yields `("text", ...)`, `("tool_call", ...)`, or `("done", ...)` events
5. **Tool executor** (`execute_tool`) — parses JSON args and dispatches to registry functions
6. **Turn handler** (`process_user_turn`) — loops: stream LLM response → if tool call, execute it and loop back; if text, return to user
7. **Main loop** — `input()` REPL with system prompt, maintains `messages` list for multi-turn conversation

Key design detail: `read_file` on image files returns a base64 dict, which `process_user_turn` handles by injecting a follow-up `user` message with an `image_url` content block so the model can "see" the image.
