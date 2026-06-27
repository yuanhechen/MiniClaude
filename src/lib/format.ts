// 纯函数辅助（移植 ui.py 的 fmt_size/fmt_dur）

export function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function fmtDur(s: number | null | undefined): string {
  if (s === null || s === undefined) return 'N/A';
  return s < 1 ? `${Math.round(s * 1000)}ms` : `${s.toFixed(2)}s`;
}
