// 配置常量（移植 config.py）。密钥只从 env 读，绝不硬编码。

export const API_BASE_URL = 'https://dashscope.aliyuncs.com/apps/anthropic'; // SDK 自动追加 /v1/messages
export const MODEL = 'qwen3.7-plus';
export const MAX_TOKENS = 131072;
export const CONTEXT_WINDOW = 131072;
export const TEMPERATURE = 0.7;
export const TOP_P: number | null = null;
export const TOP_K: number | null = null;
export const MAX_CONCURRENT_TOOLS = 10;
export const MAX_TOOL_RESULT_CHARS = 8000;
export const MAX_TOOL_ROUNDS = 100;
export const API_TIMEOUT = 600; // 秒

export const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'];
export const IMAGE_MAX_WIDTH = 2000;
export const IMAGE_MAX_HEIGHT = 2000;
export const IMAGE_TARGET_RAW_SIZE = 3_750_000;

export const SKILL_DIR = 'skill';
export const SYSTEM_PROMPT = '';

// CC 风格符号 + 主色
export const SYM_USER = '❯';
export const SYM_TOOL = '⏺';
export const SYM_RESULT = '⎿';
export const SYM_THINK = '✻';
export const ACCENT = '#D97757';

export function getApiKey(): string {
  const k = process.env.DASHSCOPE_API_KEY;
  if (!k) throw new Error('请设置 DASHSCOPE_API_KEY 环境变量');
  return k;
}
