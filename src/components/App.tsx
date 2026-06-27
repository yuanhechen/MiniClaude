import React from 'react';
import { Box, Text, Static, useInput, useApp } from 'ink';
import Spinner from 'ink-spinner';
import { useStore } from '../store.js';
import { SYM_THINK, ACCENT } from '../config.js';
import MessageList from './MessageList.js';
import Input from './Input.js';
import StatusBar from './StatusBar.js';
import { handleSubmit, abortRef } from '../agent.js';

export default function App() {
  const s = useStore();
  const { exit } = useApp();

  // ESC 中断流式（全局监听，任何 phase 都生效）
  useInput((_input, key) => {
    if (key.escape && abortRef.current) {
      abortRef.current.abort();
    }
  });

  const showInput = s.phase === 'idle' || s.phase === 'ask_pending';

  return (
    <Box flexDirection="column">
      {/* 已完成消息进原生 scrollback（只增） */}
      <Static items={s.committed}>
        {(item, i) => <MessageList key={i} item={item} />}
      </Static>

      {/* 动态区：每帧 diff */}
      {s.phase === 'thinking' ? (
        <Box gap={1}>
          <Text color={ACCENT}><Spinner type="dots" /></Text>
          <Text dimColor italic>{SYM_THINK} Thinking…</Text>
        </Box>
      ) : null}

      {s.streamingThinking ? (
        <Box><Text dimColor italic>{SYM_THINK} {s.streamingThinking}</Text></Box>
      ) : null}

      {s.streamingText ? (
        <Box><Text>{s.streamingText}</Text></Box>
      ) : null}

      {s.error ? (
        <Box><Text color="red">{s.error}</Text></Box>
      ) : null}

      {showInput ? (
        <Input
          promptLabel={s.phase === 'ask_pending' ? '❓' : undefined}
          onSubmit={(t, imgs) => handleSubmit(t, imgs, exit)}
        />
      ) : null}

      <StatusBar />
    </Box>
  );
}
