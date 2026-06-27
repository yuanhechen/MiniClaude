import React from 'react';
import { Box, Text } from 'ink';
import { useStore } from '../store.js';
import { SYM_TOOL, ACCENT, CONTEXT_WINDOW } from '../config.js';
import { fmtDur } from '../lib/format.js';

// 底部常驻状态栏（动态区，不进 scrollback）。/context /perf 开启后显示对应行。
export default function StatusBar() {
  const s = useStore();
  const lines: string[] = [];

  if (s.showCtx) {
    if (s.usage) {
      const inTok = (s.usage.input_tokens ?? 0) as number;
      const pct = inTok / CONTEXT_WINDOW * 100;
      const filled = Math.max(0, Math.min(10, Math.round(pct / 10)));
      const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
      lines.push(`ctx ${inTok.toLocaleString()}/${CONTEXT_WINDOW.toLocaleString()} (${pct.toFixed(1)}%) ${bar}`);
    } else {
      lines.push('ctx 暂无（发一条消息后可见）');
    }
  }

  if (s.showPerf) {
    if (s.usage) {
      const inTok = (s.usage.input_tokens ?? 0) as number;
      const outTok = (s.usage.output_tokens ?? 0) as number;
      const parts = [`in ${inTok.toLocaleString()}`, `out ${outTok.toLocaleString()}`];
      if (s.timing?.ttft != null) parts.push(`TTFT ${fmtDur(s.timing.ttft / 1000)}`);
      if (s.timing?.decode_time != null && outTok > 1) {
        const tpot = s.timing.decode_time / (outTok - 1);
        parts.push(`TPOT ${(tpot).toFixed(0)}ms`);
        parts.push(`decode ${((outTok - 1) / (s.timing.decode_time / 1000)).toFixed(1)} tok/s`);
      }
      lines.push('perf ' + parts.join(' · '));
    } else {
      lines.push('perf 暂无');
    }
  }

  if (lines.length === 0) return null;
  return (
    <Box flexDirection="column" marginTop={0}>
      {lines.map((ln, i) => (
        <Box key={i}>
          <Text color={ACCENT}>{SYM_TOOL} </Text>
          <Text dimColor>{ln}</Text>
        </Box>
      ))}
    </Box>
  );
}
