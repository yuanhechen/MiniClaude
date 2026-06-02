"""
Agent Step4：在 Step3 基础上加流式输出
模型回复边生成边打印，不再等全部生成完才显示
"""

import json
import subprocess
import os
import sys
import base64
import requests
import readline  # 修复退格键显示 ^H 的问题
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 1. 配置
# ============================================================
API_URL = "http://10.143.3.203:8010/v1/chat/completions"
API_KEY = "sk-1011"
MODEL = "qwen3.5"
MAX_CONCURRENT_TOOLS = 10  # 单批次最大并发工具数，与 Claude Code 一致
MAX_TOOL_RESULT_CHARS = 8000  # 单条工具结果最大字符数，超出截断并提示

# ============================================================
# 2. 本地工具实现（和 step3 完全一样）
# ============================================================

def run_bash(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.stderr:
            output += "\n[stderr] " + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output[:2000] if output else "(无输出)"
    except subprocess.TimeoutExpired:
        return "错误：命令执行超时（30秒）"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

def read_pdf(path: str, max_pages: int = 20, dpi: int = 72):
    """将 PDF 每一页渲染为 JPEG 图片（base64），供多模态模型查看"""
    try:
        import fitz  # pymupdf
    except ImportError:
        return {"type": "error", "message": "读取 PDF 需要安装 pymupdf：pip install pymupdf"}
    try:
        doc = fitz.open(path)
    except FileNotFoundError:
        return {"type": "error", "message": f"文件不存在 {path}"}
    except Exception as e:
        return {"type": "error", "message": f"无法打开 PDF：{e}"}

    total_pages = len(doc)
    read_pages = min(total_pages, max_pages)
    pages = []
    for page_num in range(read_pages):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB)
        b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
        pages.append({"page": page_num + 1, "base64": b64, "width": pix.width, "height": pix.height})
    doc.close()

    warning = f"（仅读取前 {max_pages} 页，共 {total_pages} 页）" if total_pages > max_pages else ""
    return {"type": "pdf", "path": path, "page_count": total_pages, "pages": pages, "warning": warning}

def read_file(path: str):
    ext = os.path.splitext(path)[1].lower()

    # PDF 文件：逐页渲染为图片
    if ext == ".pdf":
        return read_pdf(path)

    # 图片文件：二进制读取，返回结构化结果
    if ext in IMAGE_EXTENSIONS:
        try:
            with open(path, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("utf-8")
            media_type = f"image/{'jpeg' if ext in {'.jpg', '.jpeg'} else ext[1:]}"
            return {
                "type": "image",
                "path": path,
                "media_type": media_type,
                "base64": b64,
                "size": len(data),
            }
        except FileNotFoundError:
            return {"type": "error", "message": f"文件不存在 {path}"}
        except Exception as e:
            return {"type": "error", "message": f"错误：{e}"}

    # 文本文件：原有逻辑
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"type": "text", "content": content}
    except FileNotFoundError:
        return {"type": "error", "message": f"文件不存在 {path}"}
    except Exception as e:
        return {"type": "error", "message": f"错误：{e}"}

def write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功写入 {path}（{len(content)} 字符）"
    except Exception as e:
        return f"错误：{e}"

def list_dir(path: str = ".") -> str:
    try:
        entries = os.listdir(path)
        result = []
        for e in sorted(entries):
            full = os.path.join(path, e)
            prefix = "📁 " if os.path.isdir(full) else "📄 "
            result.append(prefix + e)
        return "\n".join(result) if result else "(空目录)"
    except Exception as e:
        return f"错误：{e}"

import math

# calculate 工具可用的安全命名空间
_MATH_SANDBOX = {
    # 内置函数
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow,
    # 数学函数
    "sqrt": math.sqrt, "cbrt": getattr(math, "cbrt", lambda x: x ** (1 / 3)),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "log2": math.log2, "log10": math.log10, "ln": math.log,
    "exp": math.exp,
    "ceil": math.ceil, "floor": math.floor,
    "factorial": math.factorial, "gcd": math.gcd,
    "degrees": math.degrees, "radians": math.radians,
    "hypot": math.hypot, "dist": getattr(math, "dist", None),
    "comb": getattr(math, "comb", None), "perm": getattr(math, "perm", None),
    # 常量
    "pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf,
}

def calculate(expression: str) -> str:
    """执行数学表达式，支持三角函数、对数、阶乘等"""
    sandbox = {k: v for k, v in _MATH_SANDBOX.items() if v is not None}
    try:
        result = eval(expression, {"__builtins__": {}}, sandbox)
        return str(result)
    except ZeroDivisionError:
        return "错误：除数不能为 0"
    except Exception as exc:
        return f"计算错误：{exc}"

# ============================================================
# 3. 工具注册表
# ============================================================
# concurrency_safe: 纯读取/无副作用的工具标记为 True，可并发执行
#                   有副作用的工具标记为 False，必须串行执行
TOOLS_REGISTRY = {
    "run_bash": {
        "function": run_bash,
        "concurrency_safe": False,  # shell 命令可能有副作用
        "schema": {
            "type": "function",
            "function": {
                "name": "run_bash",
                "description": "在本地执行 shell 命令并返回输出",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要执行的 shell 命令"},
                    },
                    "required": ["command"],
                },
            },
        },
    },
    "read_file": {
        "function": read_file,
        "concurrency_safe": True,  # 纯读取，无副作用
        "schema": {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取指定路径的文件内容（支持文本、图片、PDF）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                    },
                    "required": ["path"],
                },
            },
        },
    },
    "write_file": {
        "function": write_file,
        "concurrency_safe": False,  # 写入有副作用
        "schema": {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "将内容写入指定路径的文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "要写入的内容"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
    },
    "list_dir": {
        "function": list_dir,
        "concurrency_safe": True,  # 纯读取
        "schema": {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出指定目录下的文件和文件夹",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "目录路径，默认为当前目录"},
                    },
                    "required": [],
                },
            },
        },
    },
    "calculate": {
        "function": calculate,
        "concurrency_safe": True,
        "schema": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "执行数学表达式计算，支持四则运算、三角函数、对数、指数、阶乘、排列组合等",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，如 'sqrt(2)**2'、'sin(pi/4)'、'log(100,10)'、'factorial(10)'、'(3*pi+2*e)/sqrt(5)'",
                        },
                    },
                    "required": ["expression"],
                },
            },
        },
    },
}

TOOLS_SCHEMAS = [t["schema"] for t in TOOLS_REGISTRY.values()]

# ============================================================
# 4. 流式调用 LLM（核心改动）
# ============================================================
def call_llm_stream(messages: list):
    """
    流式调用 LLM，yield 每个事件。
    返回一个生成器，产出两种事件：
      ("text", "内容片段")     — 模型生成的文本，直接打印
      ("tool_call", {完整信息}) — 模型要调工具，需要执行
    """
    resp = requests.post(
        API_URL,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL, "messages": messages, "tools": TOOLS_SCHEMAS, "max_tokens": 8192, "stream": True, "stream_options": {"include_usage": True}},
        stream=True,
    )
    resp.raise_for_status()

    # 用于拼接流式 tool_call 的中间状态
    tool_calls_accum = {}  # index -> {id, name, arguments}
    content_accum = ""
    usage = None  # 记录 token 用量

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue

        data = line[6:]  # 去掉 "data: " 前缀
        if data == "[DONE]":
            break

        chunk = json.loads(data)

        # usage 可能在单独的 chunk 里（choices 为空）
        if chunk.get("usage"):
            usage = chunk["usage"]

        if not chunk.get("choices"):
            continue

        choice = chunk["choices"][0]
        delta = choice.get("delta", {})

        # 处理文本内容
        if "content" in delta and delta["content"]:
            content_accum += delta["content"]
            yield ("text", delta["content"])

        # 处理 tool_calls（流式时分散在多个 chunk 中）
        if "tool_calls" in delta:
            for tc in delta["tool_calls"]:
                idx = tc.get("index", 0)
                if idx not in tool_calls_accum:
                    tool_calls_accum[idx] = {"id": "", "name": "", "arguments": ""}

                # 第一个 chunk 带来 id 和 function.name
                if tc.get("id"):
                    tool_calls_accum[idx]["id"] = tc["id"]
                if tc.get("function", {}).get("name"):
                    tool_calls_accum[idx]["name"] = tc["function"]["name"]
                # 后续 chunk 只带来 function.arguments 的片段
                if tc.get("function", {}).get("arguments"):
                    tool_calls_accum[idx]["arguments"] += tc["function"]["arguments"]

        # 流结束时，如果积累了 tool_calls，yield 出去
        finish_reason = choice.get("finish_reason")
        if finish_reason == "tool_calls" and tool_calls_accum:
            # 继续读取剩余 chunk 以获取 usage
            for late_line in resp.iter_lines(decode_unicode=True):
                if not late_line or not late_line.startswith("data: "):
                    continue
                late_data = late_line[6:]
                if late_data == "[DONE]":
                    break
                late_chunk = json.loads(late_data)
                if late_chunk.get("usage"):
                    usage = late_chunk["usage"]
            # 组装成和非流式一样的格式
            tool_calls = []
            for idx in sorted(tool_calls_accum.keys()):
                tc = tool_calls_accum[idx]
                tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                })
            assistant_msg = {
                "role": "assistant",
                "content": content_accum or None,
                "tool_calls": tool_calls,
            }
            yield ("tool_call", {"assistant_msg": assistant_msg, "tool_calls": tool_calls, "usage": usage})
            return

        # 正常结束（文本回答）— usage 在 stop 之后的单独 chunk 里，不急着 return
        if finish_reason == "stop":
            assistant_msg = {"role": "assistant", "content": content_accum}
            # 继续读取剩余 chunk 以获取 usage
            for late_line in resp.iter_lines(decode_unicode=True):
                if not late_line or not late_line.startswith("data: "):
                    continue
                late_data = late_line[6:]
                if late_data == "[DONE]":
                    break
                late_chunk = json.loads(late_data)
                if late_chunk.get("usage"):
                    usage = late_chunk["usage"]
            yield ("done", {"assistant_msg": assistant_msg, "usage": usage})
            return

        # token 用完被截断，也当作正常结束处理
        if finish_reason == "length":
            assistant_msg = {"role": "assistant", "content": content_accum}
            yield ("done", {"assistant_msg": assistant_msg, "usage": usage})
            return

# ============================================================
# 5. 工具调度：分批 + 并发/串行执行
# ============================================================
def execute_tool(name: str, arguments: str):
    args = json.loads(arguments)
    func = TOOLS_REGISTRY[name]["function"]
    result = func(**args)
    return result


def partition_tool_calls(tool_calls: list) -> list:
    """
    将 tool calls 分成批次：连续的 concurrency_safe 工具合并为一个并发批次，
    非 safe 的工具各自独占一个串行批次。
    参考 Claude Code 的 partitionToolCalls 设计。

    示例:
      [Read A, Read B, Bash(ls), Read C]
      → [Batch(safe=[Read A, Read B]), Batch(unsafe=[Bash]), Batch(safe=[Read C])]
    """
    batches = []  # [{"safe": bool, "calls": [tc, ...]}, ...]
    for tc in tool_calls:
        name = tc["function"]["name"]
        safe = TOOLS_REGISTRY.get(name, {}).get("concurrency_safe", False)
        last = batches[-1] if batches else None
        # 连续 safe 工具合并到同一批次
        if last and last["safe"] and safe:
            last["calls"].append(tc)
        else:
            batches.append({"safe": safe, "calls": [tc]})
    return batches


def execute_batch(batch: list) -> list:
    """
    执行一个批次的 tool calls：
    - safe 批次：ThreadPoolExecutor 并发执行
    - unsafe 批次：串行执行
    返回 [(tc, result), ...] 按原始顺序排列
    """
    calls = batch["calls"]
    if batch["safe"] and len(calls) > 1:
        results = [None] * len(calls)
        with ThreadPoolExecutor(max_workers=min(len(calls), MAX_CONCURRENT_TOOLS)) as pool:
            futures = {}
            for i, tc in enumerate(calls):
                futures[pool.submit(execute_tool, tc["function"]["name"], tc["function"]["arguments"])] = i
            for fut in as_completed(futures):
                results[futures[fut]] = (calls[futures[fut]], fut.result())
        return results
    else:
        return [(tc, execute_tool(tc["function"]["name"], tc["function"]["arguments"])) for tc in calls]


def _append_tool_result(tc, result, messages, media_blocks):
    """处理单个工具的返回值，追加 tool_result 消息，收集媒体块"""
    name = tc["function"]["name"]
    args = tc["function"]["arguments"]
    short_args = args[:100] + "..." if len(args) > 100 else args

    if isinstance(result, dict) and result.get("type") == "image":
        info = f"已加载图片: {result['path']} ({result['size']} bytes)，已编码为 base64"
        print(f"      → {info}")
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": info})
        data_url = f"data:{result['media_type']};base64,{result['base64']}"
        media_blocks.append({"type": "image_url", "image_url": {"url": data_url}})

    elif isinstance(result, dict) and result.get("type") == "pdf":
        warning = result.get("warning", "")
        info = f"已加载 PDF: {result['path']}，共 {result['page_count']} 页，已渲染为图片{warning}"
        print(f"      → {info}")
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": info})
        for page in result["pages"]:
            data_url = f"data:image/jpeg;base64,{page['base64']}"
            media_blocks.append({"type": "image_url", "image_url": {"url": data_url}})

    elif isinstance(result, dict) and result.get("type") == "error":
        print(f"      → {result['message']}")
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result["message"]})

    elif isinstance(result, dict) and result.get("type") == "text":
        content = result["content"]
        if len(content) > MAX_TOOL_RESULT_CHARS:
            preview = content[:MAX_TOOL_RESULT_CHARS]
            truncated_msg = (f"\n\n[文件内容过大，已截断。完整内容共 {len(content)} 字符，"
                             f"可使用 run_bash('head -n 200 文件路径') 或指定行范围查看]")
            content = preview + truncated_msg
            print(f"      → (文本结果，{len(result['content'])} 字符，已截断至 {MAX_TOOL_RESULT_CHARS})")
        else:
            display = content[:200] + "..." if len(content) > 200 else content
            print(f"      → {display}")
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": content})

    else:
        raw = str(result)
        if len(raw) > MAX_TOOL_RESULT_CHARS:
            raw = raw[:MAX_TOOL_RESULT_CHARS] + "\n\n[输出已截断]"
            print(f"      → (输出已截断至 {MAX_TOOL_RESULT_CHARS} 字符)")
        else:
            display = raw[:200] + "..." if len(raw) > 200 else raw
            print(f"      → {display}")
        messages.append({"role": "tool", "tool_call_id": tc["id"], "content": raw})


# ============================================================
# 6. 处理一次用户输入（流式版）
# ============================================================
def process_user_turn(messages: list):
    round_num = 0
    while True:
        round_num += 1

        # --- 流式接收 ---
        tool_call_info = None
        assistant_msg = None
        last_usage = None
        content_accum = ""

        for event_type, data in call_llm_stream(messages):
            if event_type == "text":
                # 文本片段，直接打印（不换行，实时显示）
                print(data, end="", flush=True)

            elif event_type == "tool_call":
                tool_call_info = data
                assistant_msg = data["assistant_msg"]
                last_usage = data.get("usage")

            elif event_type == "done":
                assistant_msg = data["assistant_msg"]
                last_usage = data.get("usage")

        # 打印本轮 token 用量
        if last_usage:
            print(f"  [tokens] 输入: {last_usage.get('prompt_tokens', '?')} | 输出: {last_usage.get('completion_tokens', '?')}")
        else:
            print("  [tokens] 未获取到 usage")

        # --- 如果是工具调用 ---
        if tool_call_info:
            tool_calls = tool_call_info["tool_calls"]
            batches = partition_tool_calls(tool_calls)

            mode_label = "串行" if all(not b["safe"] or len(b["calls"]) == 1 for b in batches) else "分批并发"
            print(f"\n  [轮次 {round_num}] {mode_label}执行 {len(tool_calls)} 个工具 ({len(batches)} 批)")

            # assistant 消息只追加一次
            messages.append(assistant_msg)

            # 收集所有图片/PDF 的 media block
            media_blocks = []

            for batch_idx, batch in enumerate(batches):
                tag = f"并发×{len(batch['calls'])}" if batch["safe"] and len(batch["calls"]) > 1 else "串行"
                print(f"    批次 {batch_idx + 1} [{tag}]: {', '.join(tc['function']['name'] for tc in batch['calls'])}")

                for tc, result in execute_batch(batch):
                    _append_tool_result(tc, result, messages, media_blocks)

            # 有图片/PDF 内容时，合并为一条 user 消息注入
            if media_blocks:
                media_blocks.append({"type": "text", "text": "[系统注入] 以上是请求读取的图片/PDF内容"})
                messages.append({"role": "user", "content": media_blocks})

            continue

        # --- 文本回答 ---
        if not assistant_msg:
            # 流意外结束（比如 token 耗尽），用已收集的内容兜底
            assistant_msg = {"role": "assistant", "content": content_accum or "(回复被截断)"}
        messages.append(assistant_msg)
        print()  # 最后补一个换行
        return assistant_msg["content"]

# ============================================================
# 7. 消息压缩（借鉴 Claude Code 的多层上下文管理）
# ============================================================
import tempfile

_PERSIST_DIR = os.path.join(tempfile.gettempdir(), "miniclaude_analysis")
os.makedirs(_PERSIST_DIR, exist_ok=True)


def _persist_analysis(filename: str, analysis: str) -> str:
    """将模型对文件的图片/PDF分析结果持久化到临时文件，返回文件路径"""
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    path = os.path.join(_PERSIST_DIR, f"{safe_name}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(analysis)
    return path


def compact_media_messages(messages: list):
    """将模型已处理过的图片/PDF消息替换为带上下文的轻量文本摘要，分析结果持久化到磁盘"""
    compacted = 0
    for i, msg in enumerate(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        has_media = any(isinstance(b, dict) and b.get("type") == "image_url" for b in content)
        if not has_media:
            continue

        # 收集上下文
        tool_info = ""
        for j in range(i - 1, -1, -1):
            if messages[j].get("role") == "tool":
                tool_info = messages[j].get("content", "")
                break

        assistant_analysis = ""
        for j in range(i + 1, len(messages)):
            if messages[j].get("role") == "assistant":
                text = messages[j].get("content") or ""
                assistant_analysis = text[:1000]
                break

        # 持久化完整分析到磁盘
        persist_path = ""
        if assistant_analysis:
            # 从 tool_info 中提取文件名
            fname = "media"
            for word in tool_info.split():
                if "." in word and "/" in word:
                    fname = os.path.basename(word.rstrip("，。)")
                    )
                    break
            persist_path = _persist_analysis(fname, f"{tool_info}\n\n{assistant_analysis}")

        # 组合摘要：关键信息 + 磁盘引用
        parts = []
        if tool_info:
            parts.append(tool_info)
        if assistant_analysis:
            parts.append(f"模型分析摘要: {assistant_analysis[:300]}")
        if persist_path:
            parts.append(f"完整分析已保存至 {persist_path}，可用 read_file 查看")
        summary = " | ".join(parts) if parts else "[已处理的媒体内容]"
        messages[i] = {"role": "user", "content": summary}
        compacted += 1
    if compacted:
        print(f"  [压缩] 已清理 {compacted} 条媒体消息，分析结果已持久化到 {_PERSIST_DIR}")


def compact_old_tool_results(messages: list, keep_recent: int = 6):
    """
    清理旧的文本工具结果（借鉴 Claude Code 的 microcompact）。
    只保留最近 keep_recent 条 tool 消息的原始内容，更早的替换为摘要。
    """
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    if len(tool_indices) <= keep_recent:
        return
    compacted = 0
    for idx in tool_indices[:-keep_recent]:
        content = messages[idx].get("content", "")
        if len(content) > 200 and "[已压缩]" not in content:
            preview = content[:150]
            messages[idx]["content"] = f"{preview}... [已压缩，原始内容共{len(content)}字符]"
            compacted += 1
    if compacted:
        print(f"  [microcompact] 已压缩 {compacted} 条旧的文本工具结果")


# ============================================================
# 8. 多轮对话主循环
# ============================================================
def main():
    messages = [
        {"role": "system", "content": """你是一个有用的 AI 助手，可以操作用户的电脑。你有以下工具：
- run_bash: 执行 shell 命令
- read_file: 读取文件（支持文本、图片、PDF）
- write_file: 写入文件
- list_dir: 列出目录
- calculate: 数学表达式计算（三角函数、对数、阶乘、排列组合等）

根据用户需求选择合适的工具。用中文回答。"""},
    ]

    print("Agent Step4（流式输出）")
    print("输入 q 退出")
    print("=" * 40)

    while True:
        user_input = input("\n你: ").strip()
        if user_input.lower() == "q":
            print("再见！")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        print()  # 换行后开始流式输出
        process_user_turn(messages)
        compact_media_messages(messages)
        compact_old_tool_results(messages)

if __name__ == "__main__":
    main()
