/**
 * 格式化工具函数
 * 主要导出：formatDateTime
 */

/**
 * 将 UTC 时间字符串格式化为本地中文日期时间
 * @param value ISO 或 "YYYY-MM-DD HH:mm:ss" 格式，空值返回占位符
 * @returns 本地化后的日期时间字符串
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const utc = value.endsWith('Z') ? value : value.replace(' ', 'T') + 'Z'
  const d = new Date(utc)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
