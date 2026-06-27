// Skill 加载器（移植 skills.py）。扫描 SKILL.md，frontmatter 解析 name/description。

import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';

export interface SkillInfo {
  name: string;
  description: string;
  content: string;
  path: string;
}

export const SKILLS_REGISTRY = new Map<string, SkillInfo>();

export function loadSkills(dir: string): void {
  SKILLS_REGISTRY.clear();
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return;

  // 格式 2：dir/SKILL.md 单文件
  const directMd = path.join(dir, 'SKILL.md');
  if (existsSync(directMd) && statSync(directMd).isFile()) {
    loadSkillFile(directMd, path.basename(path.resolve(dir)));
  }

  // 格式 1：dir/<sub>/SKILL.md
  for (const entry of readdirSync(dir).sort()) {
    if (entry === 'SKILL.md') continue;
    const md = path.join(dir, entry, 'SKILL.md');
    if (existsSync(md) && statSync(md).isFile()) loadSkillFile(md, entry);
  }
}

function loadSkillFile(md: string, fallback: string): void {
  let raw: string;
  try { raw = readFileSync(md, 'utf-8'); } catch { return; }
  const { name, description, content } = parseSkillMd(raw);
  const n = name || fallback;
  SKILLS_REGISTRY.set(n, {
    name: n,
    description: description || `Skill: ${n}`,
    content,
    path: md,
  });
}

function parseSkillMd(raw: string): { name: string; description: string; content: string } {
  let name = '';
  let description = '';
  let content = raw;
  const m = raw.match(/^---\s*\n(.*?)\n---\s*\n(.*)/s);
  if (m) {
    const fm = m[1];
    content = m[2];
    for (const line of fm.split('\n')) {
      const l = line.trim();
      if (l.startsWith('name:')) name = l.slice(5).trim().replace(/^["']|["']$/g, '');
      else if (l.startsWith('description:')) description = l.slice(12).trim().replace(/^["']|["']$/g, '');
    }
  }
  return { name, description, content: content.trim() };
}

export function getSkillListing(): string {
  if (!SKILLS_REGISTRY.size) return '';
  const lines = ['可用 skills:'];
  for (const [, info] of SKILLS_REGISTRY) lines.push(`  - ${info.name}: ${info.description}`);
  return lines.join('\n');
}

export function getSkillPrompt(name: string, args = ''): string | null {
  const s = SKILLS_REGISTRY.get(name);
  if (!s) return null;
  let p = s.content;
  if (args) p = p.replace(/\$ARGUMENTS/g, args);
  return p;
}
