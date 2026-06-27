// 工具调度：分批、并发/串行执行、结果处理（移植 executor.py）

import { TOOLS_REGISTRY } from './tools.js';
import { MAX_TOOL_RESULT_CHARS } from './config.js';
import type { ToolCall, ToolResultBlock, MessageParam } from './types.js';

export interface ToolBatch { safe: boolean; calls: ToolCall[] }

export function partitionToolCalls(toolCalls: ToolCall[]): ToolBatch[] {
  const batches: ToolBatch[] = [];
  for (const tc of toolCalls) {
    const safe = TOOLS_REGISTRY[tc.name]?.concurrencySafe ?? false;
    const last = batches[batches.length - 1];
    if (last && last.safe && safe) last.calls.push(tc);
    else batches.push({ safe, calls: [tc] });
  }
  return batches;
}

export async function executeTool(name: string, args: Record<string, unknown>): Promise<unknown> {
  const def = TOOLS_REGISTRY[name];
  if (!def) return { type: 'error', message: `未知工具: ${name}` };
  try {
    return await def.function(args);
  } catch (e) {
    return { type: 'error', message: `工具执行错误: ${(e as Error).message}` };
  }
}

export async function executeBatch(batch: ToolBatch): Promise<Array<[ToolCall, unknown]>> {
  const calls = batch.calls;
  if (batch.safe && calls.length > 1) {
    const results = await Promise.all(
      calls.map(async tc => [tc, await executeTool(tc.name, tc.input)] as [ToolCall, unknown]),
    );
    return results; // Promise.all 保序
  }
  const out: Array<[ToolCall, unknown]> = [];
  for (const tc of calls) out.push([tc, await executeTool(tc.name, tc.input)]);
  return out;
}

export function buildToolResultBlock(tc: ToolCall, result: unknown): ToolResultBlock {
  const toolUseId = tc.id;
  const r = result as { type?: string; output?: string; path?: string; size?: string; media_type?: string; base64?: string; message?: string; content?: string };

  if (r && r.type === 'bash') {
    return { type: 'tool_result', tool_use_id: toolUseId, content: r.output ?? '(无输出)' };
  }
  if (r && r.type === 'image') {
    return {
      type: 'tool_result', tool_use_id: toolUseId,
      content: [
        { type: 'text', text: `已加载图片: ${r.path} (${r.size})` },
        { type: 'image', source: { type: 'base64', media_type: r.media_type ?? 'image/png', data: r.base64 ?? '' } },
      ],
    };
  }
  if (r && r.type === 'error') {
    return { type: 'tool_result', tool_use_id: toolUseId, content: r.message ?? '未知错误', is_error: true };
  }
  if (r && r.type === 'text') {
    let content = r.content ?? '';
    if (content.length > MAX_TOOL_RESULT_CHARS) {
      content = content.slice(0, MAX_TOOL_RESULT_CHARS) + `\n\n[文件内容过大，已截断。完整内容共 ${r.content?.length ?? 0} 字符]`;
    }
    return { type: 'tool_result', tool_use_id: toolUseId, content };
  }
  let raw = String(result);
  if (raw.length > MAX_TOOL_RESULT_CHARS) raw = raw.slice(0, MAX_TOOL_RESULT_CHARS) + '\n\n[输出已截断]';
  return { type: 'tool_result', tool_use_id: toolUseId, content: raw };
}

export function flushToolResults(blocks: ToolResultBlock[], messages: MessageParam[]): void {
  if (!blocks.length) return;
  messages.push({ role: 'user', content: blocks });
}
