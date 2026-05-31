/** 本地中文日期时间展示（DB 存 UTC，加 Z 标记后自动转本地时区） */
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
