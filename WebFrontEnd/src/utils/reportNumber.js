/** 用户可见报告的连续编号展示（与数据库内部 id 解耦） */
export function pickReportSerial(item) {
  if (!item || typeof item !== 'object') return null
  const raw = item.reportSerial ?? item.report_serial
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}

export function formatReportSerialLabel(item, { prefix = '报告编号' } = {}) {
  const n = pickReportSerial(item)
  if (n == null) return ''
  return `${prefix}：${n}`
}

export function formatReportSerialShort(item) {
  const n = pickReportSerial(item)
  if (n == null) return ''
  return `第${n}号`
}
