// 阶段 1 probe：验证 @anthropic-ai/sdk 配 dashscope 真实兼容（可行性闸门）
//   DASHSCOPE_API_KEY=xxx npm run probe
// 通过标准：看到 text 事件流 + done 含 usage/timing；abort 后 interrupted。
// 404=baseURL 错；401=authToken 未生效；200 无事件=SSE 解析问题。

import { callLLMStream } from '../llm.js';

async function main() {
  const ac = new AbortController();
  // 如需测中断：setTimeout(() => ac.abort(), 800);

  const messages = [{ role: 'user' as const, content: '用一句话介绍你自己，不要超过30字' }];

  console.log('--- probe start (model=qwen3.7-plus via dashscope) ---');
  for await (const ev of callLLMStream(messages, [], '', ac.signal)) {
    if (ev.type === 'thinking') {
      process.stdout.write(`\n[thinking] ${ev.text}`);
    } else if (ev.type === 'text') {
      process.stdout.write(ev.text);
    } else {
      const tools = ev.type === 'tool_call' ? ev.tool_calls.map(t => t.name) : [];
      console.log(`\n--- [${ev.type}] ---`);
      console.log('  usage :', JSON.stringify(ev.usage));
      console.log('  timing:', JSON.stringify(ev.timing));
      if (tools.length) console.log('  tools :', tools);
    }
  }
  console.log('\n--- probe done ---');
}

main().catch(e => {
  console.error('PROBE ERROR:', e);
  process.exit(1);
});
