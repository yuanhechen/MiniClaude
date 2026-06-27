// 命令执行验证（直接调 handleCommand，绕过 stdin/TextInput 时序）
import { handleCommand } from '../commands.js';
import { getState, toggleCtx, togglePerf, toggleThinking } from '../store.js';
import { clearMessages } from '../agent.js';

const ctx = () => ({
  showCtx: getState().showCtx,
  showPerf: getState().showPerf,
  showThinking: getState().showThinking,
  toggleCtx, togglePerf, toggleThinking, clearMessages,
  getMessages: () => [], setMessages: () => {},
});

console.log('--- /context toggle ---');
console.log('  before showCtx:', getState().showCtx);
console.log('  result:', handleCommand('context', [], ctx()));
console.log('  after  showCtx:', getState().showCtx);

console.log('--- /perf toggle ---');
console.log('  result:', handleCommand('perf', [], ctx()));
console.log('  after  showPerf:', getState().showPerf);

console.log('--- /verbose toggle ---');
console.log('  result:', handleCommand('verbose', [], ctx()));

console.log('--- /help ---');
console.log('  result:', handleCommand('help', [], ctx()).output?.slice(0, 60));

console.log('--- /q (exit) ---');
console.log('  result:', handleCommand('q', [], ctx()));

console.log('--- /unknown ---');
console.log('  result:', handleCommand('foobar', [], ctx()));
