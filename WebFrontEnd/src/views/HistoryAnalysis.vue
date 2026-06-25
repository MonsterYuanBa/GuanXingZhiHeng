<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import TopNav from '../components/TopNav.vue'
import { getLatestHistoryAnalysis } from '../services/reportStore'
import { parseAgentText } from '../services/structuredText'

const result = ref(null)
const analyzingDots = ref('.')
const dotsTimer = ref(null)
const statusTimer = ref(null)
const activeUserCard = ref('profile') // 'profile' | 'trend'

function parseBackendDate(value) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (typeof value === 'number') {
    const byNumber = new Date(value)
    return Number.isNaN(byNumber.getTime()) ? null : byNumber
  }
  const raw = String(value).trim()
  if (!raw) return null
  const hasTimezone = /([zZ]|[+-]\d{2}:\d{2})$/.test(raw)
  const normalized = hasTimezone ? raw : `${raw}Z`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return null
  return date
}

function toRows(data) {
  if (!Array.isArray(data)) return []
  return data.map((item, idx) => {
    // 兼容两种结构：
    // 1) 旧结构：{ metric, change, comment }
    // 2) 新结构：{ key, first, last, delta, direction }
    const metric = cleanMetricLabel(item?.metric || item?.key || `指标${idx + 1}`)
    const hasOld = item?.change != null || item?.comment != null
    if (hasOld) {
      return {
        id: `${idx}-${metric}`,
        metric,
        change: item?.change || '--',
        comment: item?.comment || '暂无说明',
      }
    }

    const first = toNumber(item?.first)
    const last = toNumber(item?.last)
    const delta = toNumber(item?.delta)
    const dir = String(item?.direction || '').toLowerCase()
    const trendText = dir === 'up' ? '上升' : dir === 'down' ? '下降' : '基本持平'
    const change =
      delta === null
        ? '--'
        : `${delta >= 0 ? '+' : ''}${delta.toFixed(4)} (${trendText})`
    const commentParts = []
    if (first !== null) commentParts.push(`起点: ${first.toFixed(4)}`)
    if (last !== null) commentParts.push(`终点: ${last.toFixed(4)}`)
    if (!commentParts.length) commentParts.push('暂无说明')
    return {
      id: `${idx}-${metric}`,
      metric,
      change,
      comment: commentParts.join('，'),
    }
  })
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function computeBmiValue(height, weight) {
  const h = toNumber(height)
  const w = toNumber(weight)
  if (h === null || w === null) return null
  if (h <= 0 || w <= 0) return null

  // 常见约定：身高可能是 cm 或 m；做个宽松判断
  const hMeters = h > 10 ? h / 100 : h
  if (hMeters <= 0) return null

  const bmi = w / (hMeters * hMeters)
  if (!Number.isFinite(bmi)) return null

  return Number(bmi.toFixed(4))
}

function cleanMetricLabel(value) {
  const raw = String(value || '').trim()
  if (!raw) return '未知指标'
  const lastDot = raw.lastIndexOf('.')
  if (lastDot >= 0 && lastDot < raw.length - 1) return raw.slice(lastDot + 1)
  return raw
}

function normalizeSourceItems(sourceItems) {
  if (!Array.isArray(sourceItems)) return []
  // 重要：不要再按 createdAt(ts) 排序
  // 否则“勾选顺序”会被时间打乱，导致折线图点位顺序不符合用户选择顺序。
  return sourceItems.map((item, idx) => {
    const rawId = item?.id
    const normalizedId = Number.isFinite(Number(rawId)) ? Number(rawId) : null
    const created = item?.createdAt || item?.timestamp
    const date = parseBackendDate(created)
    const ts = date ? date.getTime() : idx
    // 兼容两种结构：
    // 1) 旧结构：{ createdAt, metrics: {k:v} }
    // 2) 新结构：{ timestamp, k1:v1, k2:v2, ... }
    const rawMetrics =
      item?.metrics && typeof item.metrics === 'object'
        ? item.metrics
        : Object.fromEntries(
            Object.entries(item || {}).filter(
              ([k]) =>
                k !== 'id' &&
                k !== 'createdAt' &&
                k !== 'timestamp' &&
                k !== 'profileMeta' &&
                k !== 'userData',
            ),
          )
    const metrics = {}
    for (const [key, value] of Object.entries(rawMetrics)) {
      const n = toNumber(value)
      if (n !== null) metrics[key] = n
    }
    const profileMeta =
      item?.userData && typeof item.userData === 'object'
        ? item.userData
        : item?.profileMeta && typeof item.profileMeta === 'object'
          ? item.profileMeta
          : {}
    const bmi = toNumber(profileMeta?.bmi) ?? computeBmiValue(profileMeta?.height, profileMeta?.weight)
    if (bmi !== null && metrics.BMI === undefined) {
      metrics.BMI = bmi
    }
    const dateLabel = date
      ? date.toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        })
      : null
    const idLabel = normalizedId !== null ? `#${normalizedId}` : `序号${idx + 1}`
    return {
      id: normalizedId,
      ts,
      label: dateLabel ? `${dateLabel} ${idLabel}` : idLabel,
      metrics,
      userData: profileMeta,
    }
  })
}

const FIXED_METRICS = [
  { id: 'bmi', title: 'BMI', aliases: ['BMI', 'bmi'] },
  { id: 'shoulder', title: '高低肩指数', aliases: ['高低肩指数', 'titai_fb.高低肩指数'] },
  { id: 'pelvis', title: '骨盆倾斜指数', aliases: ['骨盆倾斜指数', 'titai_fb.骨盆倾斜指数'] },
  { id: 'headForward', title: '头前伸指数', aliases: ['头前伸指数', 'titai_fb.头前伸指数'] },
  { id: 'knee', title: '膝关节对齐指数', aliases: ['膝关节对齐指数', 'titai_fb.膝关节对齐指数'] },
  { id: 'upperLowerArea', title: '上下身面积比', aliases: ['上下身面积比', 'tixing_fb.上下身面积比'] },
  { id: 'legBody', title: '腿身比', aliases: ['腿身比', 'tixing_fb.腿身比'] },
  { id: 'abdomen', title: '腹部前突指数', aliases: ['腹部前突指数', 'tixing_fb.腹部前突指数'] },
  { id: 'thighCalf', title: '大腿小腿比', aliases: ['大腿小腿比', 'tixing_fb.大腿小腿比'] },
]

function resolveMetricKey(rows, aliases) {
  const allKeys = new Set()
  for (const row of rows) {
    Object.keys(row.metrics).forEach((k) => allKeys.add(k))
  }
  if (!allKeys.size) return null

  const lowerMap = new Map(Array.from(allKeys).map((k) => [k.toLowerCase(), k]))
  for (const alias of aliases) {
    if (allKeys.has(alias)) return alias
    const exactLower = lowerMap.get(String(alias).toLowerCase())
    if (exactLower) return exactLower
  }
  for (const alias of aliases) {
    const suffix = `.${alias}`
    const found = Array.from(allKeys).find((k) => k.endsWith(suffix))
    if (found) return found
  }
  return null
}

function buildChartMeta(points) {
  if (!Array.isArray(points) || !points.length) {
    return {
      path: '',
      circles: [],
      labels: [],
      yMin: 0,
      yMax: 0,
      xTicks: [],
      yTicks: [],
      width: 620,
      height: 260,
      padLeft: 66,
      padTop: 16,
      innerW: 514,
      innerH: 200,
    }
  }

  const width = 620
  const height = 208
  const padLeft = 66
  const padRight = 40
  const padTop = 12
  const padBottom = 32
  const innerW = width - padLeft - padRight
  const innerH = height - padTop - padBottom

  const values = points.map((p) => p.y)
  let minY = Math.min(...values)
  let maxY = Math.max(...values)
  if (minY === maxY) {
    minY -= 1
    maxY += 1
  }

  const xPos = (idx, total) => {
    if (total <= 1) return padLeft + innerW / 2
    return padLeft + (idx / (total - 1)) * innerW
  }
  const yPos = (value) => padTop + ((maxY - value) / (maxY - minY)) * innerH

  const circles = points.map((p, idx) => ({
    cx: xPos(idx, points.length),
    cy: yPos(p.y),
    label: p.x,
    value: p.y,
  }))

  const path = circles
    .map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.cx.toFixed(2)} ${p.cy.toFixed(2)}`)
    .join(' ')

  const yTicks = Array.from({ length: 5 }, (_, i) => {
    const value = minY + ((maxY - minY) * i) / 4
    return {
      value: value.toFixed(3),
      y: yPos(value),
    }
  })

  const xTicks = circles.map((p, idx) => ({
    label: p.label,
    x: p.cx,
    anchor: idx === 0 ? 'start' : idx === circles.length - 1 ? 'end' : 'middle',
  }))

  return { path, circles, xTicks, yTicks, width, height, padLeft, padTop, innerW, innerH }
}

const chartSeries = computed(() => {
  const sourceItems = result.value?.sourceItems || []
  const sorted = normalizeSourceItems(sourceItems)
  return FIXED_METRICS.map((metric) => {
    const key = resolveMetricKey(sorted, metric.aliases)
    const points = key
      ? sorted
          .map((item) => ({ x: item.label, y: item.metrics[key] ?? null }))
          .filter((p) => p.y !== null)
      : []

    return {
      key: metric.id,
      title: metric.title,
      sourceKey: key,
      points,
      chart: buildChartMeta(points),
    }
  })
})

const historyUserRows = computed(() =>
  normalizeSourceItems(result.value?.sourceItems || []).map((item, idx) => {
    const userData = item?.userData && typeof item.userData === 'object' ? item.userData : {}
    const bmi = toNumber(userData?.bmi) ?? computeBmiValue(userData?.height, userData?.weight)
    return {
      key: `${item.id ?? idx}-${item.label}`,
      label: item.label || `序号${idx + 1}`,
      age: userData?.age ?? '--',
      gender: userData?.gender || '--',
      height: userData?.height ?? '--',
      weight: userData?.weight ?? '--',
      bmi: bmi === null ? '--' : bmi.toFixed(4),
    }
  }),
)

const structuredReviewReport = computed(() => parseAgentText(result.value?.report || ''))
const hasStructuredReview = computed(() => (structuredReviewReport.value?.sections || []).length > 0)

const trendPageIndex = ref(0)
const trendPageSize = 4
const trendPageCount = computed(() => {
  const total = chartSeries.value.length
  if (!total) return 1
  return Math.ceil(total / trendPageSize)
})
const pagedChartSeries = computed(() => {
  const start = trendPageIndex.value * trendPageSize
  return chartSeries.value.slice(start, start + trendPageSize)
})

function goPrevTrendPage() {
  if (trendPageIndex.value <= 0) {
    trendPageIndex.value = trendPageCount.value - 1
    return
  }
  trendPageIndex.value -= 1
}

function goNextTrendPage() {
  if (trendPageIndex.value >= trendPageCount.value - 1) {
    trendPageIndex.value = 0
    return
  }
  trendPageIndex.value += 1
}

function hydrateLatest(latest) {
  if (!latest) return
  result.value = {
    createdAt: latest.createdAt || '',
    trendData: toRows(latest.trendData),
    sourceItems: Array.isArray(latest.sourceItems) ? latest.sourceItems : [],
    report: latest.report || latest.historyAnalysisReport || latest.summary || '暂无复查分析报告',
    isGenerating: Boolean(latest.isGenerating),
    generationError: latest.generationError || '',
    meta: latest.meta || latest.payload?.meta || {},
  }
}

function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

function exportPdf() {
  if (!result.value) return
  const popup = window.open('', '_blank')
  if (!popup) return

  const trendsHtml = (result.value.trendData || [])
    .map((row) => `<tr><td>${escapeHtml(row.metric)}</td><td>${escapeHtml(row.change)}</td><td>${escapeHtml(row.comment)}</td></tr>`)
    .join('')
  const chartListHtml = chartSeries.value
    .map((item) => `<li><strong>${escapeHtml(item.title)}</strong>：${item.points.map((p) => `${escapeHtml(p.x)}=${escapeHtml(p.y)}`).join('，')}</li>`)
    .join('')
  const userRowsHtml = historyUserRows.value
    .map(
      (row) =>
        `<tr><td>${escapeHtml(row.label)}</td><td>${escapeHtml(row.age)}</td><td>${escapeHtml(row.gender)}</td><td>${escapeHtml(row.height)}</td><td>${escapeHtml(row.weight)}</td><td>${escapeHtml(row.bmi)}</td></tr>`,
    )
    .join('')

  popup.document.write(`
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>历史分析报告</title>
        <style>
          body { font-family: "Microsoft YaHei", sans-serif; margin: 24px; color: #1f2937; }
          h1, h2 { margin: 0 0 8px 0; }
          .muted { color: #64748b; margin-bottom: 16px; }
          .card { border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #cbd5e1; padding: 6px; text-align: left; font-size: 12px; }
          ul { margin: 0; padding-left: 18px; }
          li { margin: 4px 0; }
          pre { white-space: pre-wrap; word-break: break-word; margin: 0; }
        </style>
      </head>
      <body>
        <h1>复查分析报告</h1>
        <div class="muted">分析时间：${escapeHtml(result.value.createdAt || '未知时间')}</div>
        <div class="card">
          <h2>历史记录用户数据</h2>
          <table>
            <thead><tr><th>记录</th><th>年龄</th><th>性别</th><th>身高</th><th>体重</th><th>BMI</th></tr></thead>
            <tbody>${userRowsHtml || '<tr><td colspan="6">暂无用户数据</td></tr>'}</tbody>
          </table>
        </div>
        <div class="card"><h2>趋势图数据</h2><ul>${chartListHtml || '<li>暂无趋势图数据</li>'}</ul></div>
        <div class="card">
          <h2>数据变化情况</h2>
          <table>
            <thead><tr><th>指标</th><th>变化</th><th>说明</th></tr></thead>
            <tbody>${trendsHtml || '<tr><td colspan="3">暂无趋势数据</td></tr>'}</tbody>
          </table>
        </div>
        <div class="card"><h2>复查分析报告内容</h2><pre>${escapeHtml(result.value.report || '暂无报告内容')}</pre></div>
      </body>
    </html>
  `)
  popup.document.close()
  popup.focus()
  setTimeout(() => popup.print(), 250)
}

onMounted(() => {
  const latest = getLatestHistoryAnalysis()
  if (!latest) return

  hydrateLatest(latest)

  dotsTimer.value = window.setInterval(() => {
    analyzingDots.value = analyzingDots.value === '...' ? '.' : `${analyzingDots.value}.`
  }, 420)
  statusTimer.value = window.setInterval(() => {
    const next = getLatestHistoryAnalysis()
    if (!next) return
    hydrateLatest(next)
    if (!next.isGenerating && statusTimer.value) {
      window.clearInterval(statusTimer.value)
      statusTimer.value = null
    }
  }, 1400)
})

onUnmounted(() => {
  if (dotsTimer.value) {
    window.clearInterval(dotsTimer.value)
    dotsTimer.value = null
  }
  if (statusTimer.value) {
    window.clearInterval(statusTimer.value)
    statusTimer.value = null
  }
})
</script>

<template>
  <section class="page-wrap">
    <TopNav active="history" />

    <main class="content">
      <section v-if="result" class="card shell">
        <h2>复查分析</h2>
        <p class="muted">分析时间：{{ result.createdAt || '未知时间' }}</p>
        <div v-if="result.isGenerating" class="agent-wait-row">
          <button type="button" class="agent-pill analyzing" disabled>
            等待智能体返回分析{{ analyzingDots }}
          </button>
        </div>
        <p v-if="result.generationError" class="warn">{{ result.generationError }}</p>

        <div class="analysis-row">
          <article class="sub-card chart-block">
            <header class="chart-title-row">
              <h3>体态/体型指标趋势（含 BMI）</h3>
              <div class="pager-wrap">
                <button type="button" class="pager-btn" aria-label="上一页指标趋势" @click="goPrevTrendPage">‹</button>
                <span class="pager-text">{{ trendPageIndex + 1 }} / {{ trendPageCount }}</span>
                <button type="button" class="pager-btn" aria-label="下一页指标趋势" @click="goNextTrendPage">›</button>
              </div>
            </header>

            <div class="chart-grid">
              <section v-for="item in pagedChartSeries" :key="item.key" class="chart-card">
                <header class="chart-head">
                  <strong>{{ item.title }}</strong>
                </header>

                <p v-if="!item.points.length" class="chart-empty">暂无该指标历史数据</p>
                <svg
                  v-else
                  class="line-svg"
                  :viewBox="`0 0 ${item.chart.width} ${item.chart.height}`"
                  xmlns="http://www.w3.org/2000/svg"
                  role="img"
                  :aria-label="`${item.title}折线图`"
                >
                  <g>
                    <line
                      v-for="(tick, idx) in item.chart.yTicks"
                      :key="`y-${idx}`"
                      :x1="item.chart.padLeft"
                      :y1="tick.y"
                      :x2="item.chart.padLeft + item.chart.innerW"
                      :y2="tick.y"
                      class="grid-line"
                    />
                  </g>

                  <path :d="item.chart.path" class="line-path" />

                  <circle
                    v-for="(dot, idx) in item.chart.circles"
                    :key="`dot-${idx}`"
                    :cx="dot.cx"
                    :cy="dot.cy"
                    r="3.5"
                    class="line-dot"
                  />

                  <text
                    v-for="(tick, idx) in item.chart.xTicks"
                    :key="`x-${idx}`"
                    :x="tick.x"
                    :y="item.chart.height - 10"
                    :text-anchor="tick.anchor"
                    class="axis-text axis-x"
                  >
                    {{ tick.label }}
                  </text>

                  <text
                    v-for="(tick, idx) in item.chart.yTicks"
                    :key="`v-${idx}`"
                    :x="item.chart.padLeft - 8"
                    :y="tick.y + 4"
                    class="axis-text axis-y"
                  >
                    {{ tick.value }}
                  </text>
                </svg>
              </section>
            </div>
          </article>

          <article class="sub-card mid-layer">
            <header class="card-head">
              <h3>用户数据</h3>
              <div class="segmented">
                <button
                  type="button"
                  class="seg-btn"
                  :class="{ active: activeUserCard === 'profile' }"
                  @click="activeUserCard = 'profile'"
                >
                  历史记录用户数据
                </button>
                <button
                  type="button"
                  class="seg-btn"
                  :class="{ active: activeUserCard === 'trend' }"
                  @click="activeUserCard = 'trend'"
                >
                  数据变化情况
                </button>
              </div>
            </header>

            <div v-if="activeUserCard === 'profile'" class="table-wrap">
              <table class="metric-table">
                <thead>
                  <tr>
                    <th>记录</th>
                    <th>年龄</th>
                    <th>性别</th>
                    <th>身高</th>
                    <th>体重</th>
                    <th>BMI</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in historyUserRows" :key="row.key">
                    <td>{{ row.label }}</td>
                    <td>{{ row.age }}</td>
                    <td>{{ row.gender }}</td>
                    <td>{{ row.height }}</td>
                    <td>{{ row.weight }}</td>
                    <td>{{ row.bmi }}</td>
                  </tr>
                  <tr v-if="!historyUserRows.length">
                    <td colspan="6">暂无用户数据</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-else class="table-wrap">
              <table class="metric-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>变化</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in result.trendData" :key="item.id">
                    <td>{{ item.metric }}</td>
                    <td>{{ item.change }}</td>
                    <td>{{ item.comment }}</td>
                  </tr>
                  <tr v-if="!result.trendData.length">
                    <td colspan="3">暂无趋势数据</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </article>
        </div>

        <article class="sub-card bottom-layer">
          <h3>复查分析报告</h3>
          <p v-if="result.isGenerating && !result.report" class="muted">等待智能体返回复查分析报告内容</p>
          <div v-else-if="hasStructuredReview" class="structured-wrap">
            <section
              v-for="(sec, sIdx) in structuredReviewReport.sections"
              :key="`hsec-${sIdx}`"
              class="structured-sec"
            >
              <h4 v-if="sec.title" class="structured-title">{{ sec.title }}</h4>
              <p v-if="sec.intro" class="structured-intro">{{ sec.intro }}</p>
              <ul v-if="sec.items && sec.items.length" class="structured-list">
                <li v-for="(it, iIdx) in sec.items" :key="`hit-${sIdx}-${iIdx}`" class="structured-item">
                  <strong v-if="it.title" class="structured-item-title">{{ it.title }}</strong>
                  <p class="structured-item-body">{{ it.body }}</p>
                  <ul v-if="it.children && it.children.length" class="structured-sublist">
                    <li v-for="(sub, j) in it.children" :key="`hsub-${sIdx}-${iIdx}-${j}`" class="structured-subitem">
                      <strong v-if="sub.title" class="structured-subtitle">{{ sub.title }}</strong>
                      <p class="structured-subbody">{{ sub.body }}</p>
                    </li>
                  </ul>
                </li>
              </ul>
            </section>
          </div>
          <p v-else class="text-block">{{ result.report }}</p>
        </article>

        <div class="export-row">
          <button type="button" class="export-btn" @click="exportPdf">导出 PDF</button>
        </div>
      </section>

      <section v-else class="card shell">
        <h2>复查分析</h2>
        <p class="muted">当前没有可展示的复查分析结果。请先在历史记录页面勾选常规分析报告并执行分析。</p>
      </section>
    </main>
  </section>
</template>

<style scoped>
.page-wrap { min-height: 100vh; }
.content { padding: 16px; }
.shell {
  width: min(1680px, calc(100% - 32px));
  max-width: none;
  margin: 16px auto;
}
.shell h2 { margin-top: 0; color: #1e293b; }
.warn { color: #b91c1c; font-size: 14px; margin-top: 8px; }
.sub-card { border: 1px solid #dbe4f1; border-radius: 10px; padding: 12px; background: #f8fafc; min-width: 0; overflow: hidden; }
.sub-card h3 { margin: 0 0 8px; color: #1e293b; }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.segmented { display: inline-flex; gap: 6px; flex-wrap: wrap; }
.seg-btn {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #334155;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.seg-btn.active { background: #0f766e; border-color: #0f766e; color: #f0fdfa; }
.agent-wait-row { margin-top: 8px; }
.agent-pill {
  margin: 0;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}
.agent-pill.analyzing {
  color: #1e40af;
  border-color: #bfdbfe;
  background: #dbeafe;
}
.analysis-row {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.chart-block,
.mid-layer {
  margin-top: 0;
}
.bottom-layer { margin-top: 12px; }
.structured-wrap { display: grid; gap: 10px; }
.structured-sec { padding: 10px; border: 1px solid #dbe4f1; border-radius: 10px; background: #ffffff; }
.structured-title { margin: 0 0 6px; font-size: 15px; font-weight: 900; color: #0f172a; }
.structured-intro { margin: 0 0 8px; color: #475569; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.structured-list { margin: 0; padding-left: 18px; }
.structured-item { margin: 6px 0; }
.structured-item-title { color: #0f172a; }
.structured-item-body { margin: 4px 0 0; color: #334155; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.structured-sublist { margin: 6px 0 0; padding-left: 18px; }
.structured-subitem { margin: 6px 0; }
.structured-subtitle { color: #0f172a; }
.structured-subbody { margin: 4px 0 0; color: #334155; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
.chart-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.chart-title-row h3 {
  margin: 0;
}
.pager-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pager-btn {
  margin: 0;
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  font-weight: 900;
  line-height: 1;
}
.pager-text {
  min-width: 46px;
  text-align: center;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}
.chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.chart-card { background: #ffffff; border: 1px solid #dbe4f1; border-radius: 10px; padding: 6px 8px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; color: #334155; font-size: 12px; gap: 8px; }
.chart-empty {
  margin: 0;
  min-height: 172px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  background: #f8fbff;
  border-radius: 8px;
}
.line-svg { width: 100%; height: 176px; display: block; background: #f8fbff; border-radius: 8px; }
.grid-line { stroke: #cbd5e1; stroke-width: 1; }
.line-path { fill: none; stroke: #1d4ed8; stroke-width: 2.4; }
.line-dot { fill: #1d4ed8; }
.axis-text { fill: #0f172a; font-size: 14px; font-weight: 700; }
.axis-y { text-anchor: end; }
.table-wrap { overflow: auto; max-width: 100%; }
.metric-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.metric-table th, .metric-table td { border: 1px solid #dbe4f1; padding: 8px; text-align: left; font-size: 13px; word-break: break-word; overflow-wrap: anywhere; }
.metric-table th { background: #eff6ff; color: #1e3a8a; }
.text-block { margin: 0; line-height: 1.75; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; }
.export-row { display: flex; justify-content: flex-end; margin-top: 12px; }
.export-btn {
  margin: 0;
  background: #0f766e;
  color: #f0fdfa;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 700;
}
@media (max-width: 1080px) {
  .analysis-row { grid-template-columns: 1fr; }
  .chart-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .chart-grid { grid-template-columns: 1fr; }
}
</style>
