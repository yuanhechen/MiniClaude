// 状态管理：createStore + useSyncExternalStore（复刻 CC state/store.ts）
// 核心契约：committed 只增（喂 <Static> 进原生 scrollback）；动态区字段每帧整体替换（ink diff）。

import { useSyncExternalStore } from 'react';
import type { CommittedItem, Usage, Timing } from './types.js';

export type Phase = 'idle' | 'thinking' | 'streaming' | 'tool_running' | 'ask_pending';

export interface State {
  committed: CommittedItem[];      // 只增 → <Static> → 原生 scrollback
  streamingText: string;           // 动态区当前流式文本
  streamingThinking: string;       // 动态区当前思考流（/verbose 时显示）
  phase: Phase;
  usage: Usage | null;
  timing: Timing | null;
  showCtx: boolean;
  showPerf: boolean;
  showThinking: boolean;
  askResolver: ((s: string) => void) | null;  // ask 工具的临时 resolver
  error: string | null;
}

const initial: State = {
  committed: [], streamingText: '', streamingThinking: '', phase: 'idle',
  usage: null, timing: null, showCtx: true, showPerf: false, showThinking: false,
  askResolver: null, error: null,
};

let state: State = initial;
const listeners = new Set<() => void>();

function set(patch: Partial<State> | ((s: State) => Partial<State>)) {
  const p = typeof patch === 'function' ? patch(state) : patch;
  state = { ...state, ...p };
  for (const l of listeners) l();
}

export const getState = () => state;

// actions
export const commit = (item: CommittedItem) => set(s => ({ committed: [...s.committed, item] }));
export const commitMany = (items: CommittedItem[]) => set(s => ({ committed: [...s.committed, ...items] }));
export const appendText = (d: string) => set(s => ({ streamingText: s.streamingText + d, phase: 'streaming' }));
export const appendThinking = (d: string) => set(s => ({ streamingThinking: s.streamingThinking + d }));
export const resetStream = () => set({ streamingText: '', streamingThinking: '' });
export const setPhase = (phase: Phase) => set({ phase });
export const setUsageTiming = (usage: Usage | null, timing: Timing | null) => set({ usage, timing });
export const toggleCtx = () => set(s => ({ showCtx: !s.showCtx }));
export const togglePerf = () => set(s => ({ showPerf: !s.showPerf }));
export const toggleThinking = () => set(s => ({ showThinking: !s.showThinking }));
export const setCtx = (v: boolean) => set({ showCtx: v });
export const setPerf = (v: boolean) => set({ showPerf: v });
export const setAskResolver = (r: ((s: string) => void) | null) => set({ askResolver: r });
export const setError = (e: string | null) => set({ error: e });

export function useStore(): State {
  return useSyncExternalStore(
    (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    getState,
    getState,
  );
}
