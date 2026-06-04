/**
 * 格式化工具函数
 * 主要导出：formatDateTime
 */

/**
 * 将 UTC 时间字符串格式化为本地中文日期时间
 * @param value ISO 或 "YYYY-MM-DD HH:mm:ss" 格式，空值返回占位符
 * @returns 本地化后的日期时间字符串
 */
/** DB eval_runs.created_at 为 UTC naive，序列化后常无 Z；统一按 UTC 解析 */
function parseUtcDateTime(value: string): Date | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  if (/[zZ]|[+-]\d{2}:\d{2}$/.test(trimmed)) {
    const d = new Date(trimmed)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const iso = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  const d = new Date(`${iso}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const d = parseUtcDateTime(value)
  if (!d) return value
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
