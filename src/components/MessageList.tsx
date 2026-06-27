import React from 'react';
import { Box, Text } from 'ink';
import type { CommittedItem, ContentBlock } from '../types.js';
import { SYM_USER, SYM_TOOL, SYM_RESULT, ACCENT } from '../config.js';

function renderBlock(b: ContentBlock, key: number): React.ReactNode {
  if (b.type === 'text') return <Text key={key}>{b.text}</Text>;
  if (b.type === 'thinking') return null; // 折叠（/verbose 时由动态区显示当前思考）
  // tool_use / tool_result 在独立的 tool_start/tool_result item 渲染，assistant content 内不重复显示
  return null;
}

export default function MessageList({ item }: { item: CommittedItem }) {
  switch (item.kind) {
    case 'user':
      return (
        <Box>
          <Text color={ACCENT} bold>{SYM_USER} </Text>
          <Text color={ACCENT}>{item.text}</Text>
        </Box>
      );
    case 'assistant':
      return (
        <Box flexDirection="column">
          {item.content.map((b, i) => renderBlock(b, i))}
        </Box>
      );
    case 'thinking':
      return null;
    case 'tool_start':
      return (
        <Box>
          <Text color={ACCENT} bold>{SYM_TOOL} {item.call.name}</Text>
          {' '}
          <Text dimColor>{summarizeInput(item.call.input)}</Text>
        </Box>
      );
    case 'tool_result':
      return (
        <Box>
          <Text dimColor>  {SYM_RESULT}  </Text>
          <Text dimColor>{summarizeResult(item.result)}</Text>
        </Box>
      );
    case 'system': {
      const color = item.tone === 'err' ? 'red' : item.tone === 'ok' ? 'green' : item.tone === 'warn' ? 'yellow' : undefined;
      return (
        <Box>
          <Text color={color} dimColor={item.tone === 'muted'}>{item.text}</Text>
        </Box>
      );
    }
  }
}

function summarizeInput(input: Record<string, unknown>): string {
  const s = JSON.stringify(input);
  return s.length > 70 ? s.slice(0, 67) + '...' : s;
}

function summarizeResult(result: unknown): string {
  let s: string;
  if (typeof result === 'string') s = result;
  else if (result && typeof result === 'object' && 'output' in result) s = String((result as { output: unknown }).output);
  else s = JSON.stringify(result);
  s = s.replace(/\n/g, ' ').slice(0, 120);
  return s;
}
