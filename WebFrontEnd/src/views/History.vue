<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../components/TopNav.vue'
import { deleteHistoryRecord, fetchHistory, generateHistoryAnalysis } from '../services/api'
import { parseAgentText } from '../services/structuredText'
import {
  getLocalHistory,
  removeLocalHistoryRecord,
  saveHistoryRecord,
  saveLatestHistoryAnalysis,
  saveLatestJointReport,
} from '../services/reportStore'
import { formatReportSerialLabel, pickReportSerial } from '../utils/reportNumber'

const router = useRouter()
const loading = ref(false)
const deletingId = ref(null)
const analyzing = ref(false)
const error = ref('')
const records = ref([])
const selectedIds = ref([])

function getSelectedSeq(item) {
  if (!item?.id) return null
  const idx = selectedIds.value.indexOf(item.id)
  return idx >= 0 ? idx + 1 : null
}

function normalizeRecordId(value) {
  if (value === null || value === undefined) return null
  const raw = String(value).trim()
  if (!raw) return null
  if (/^\d+$/.test(raw)) return Number(raw)
  return raw
}

function recordIdsEqual(a, b) {
  return String(normalizeRecordId(a)) === String(normalizeRecordId(b))
}

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
  // 后端常返回不带时区的 isoformat（naive datetime）。
  // 这里按 UTC 解释（后端多处使用 datetime.utcnow().isoformat()），再由前端按本地/上海时区展示。
  const normalized = hasTimezone ? raw : `${raw}Z`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return null
  return date
}

function formatDate(value) {
  const date = parseBackendDate(value)
  if (!date) return '未知时间'

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function summaryText(item) {
  const plain = (raw) => {
    const t = String(raw || '').trim()
    if (!t) return ''
    const parsed = parseAgentText(t)
    // 将结构化结果拼回“可读正文”，避免把 <<<SECTION/GROUP/ITEM>>> 暴露给用户
    const parts = []
    for (const sec of parsed.sections || []) {
      if (sec?.title) parts.push(String(sec.title).trim())
      if (sec?.intro) parts.push(String(sec.intro).trim())
      for (const it of sec?.items || []) {
        const title = String(it?.title || '').trim()
        const body = String(it?.body || '').trim()
        if (title && body) parts.push(`${title}\n${body}`)
        else if (title) parts.push(title)
        else if (body) parts.push(body)
        for (const sub of it?.children || []) {
          const st = String(sub?.title || '').trim()
          const sb = String(sub?.body || '').trim()
          if (st && sb) parts.push(`- ${st}\n${sb}`)
          else if (st) parts.push(`- ${st}`)
          else if (sb) parts.push(`- ${sb}`)
        }
      }
    }
    const merged = parts.filter(Boolean).join('\n\n').trim()
    return merged || t
  }

  if (typeof item?.comprehensiveAnalysisText === 'string' && item.comprehensiveAnalysisText.trim()) {
    return plain(item.comprehensiveAnalysisText)
  }
  if (typeof item?.summary === 'string' && item.summary.trim()) return plain(item.summary)
  if (typeof item?.message === 'string' && item.message.trim()) return plain(item.message)
  if (typeof item?.deepseekText === 'string' && item.deepseekText.trim()) return plain(item.deepseekText)
  if (typeof item?.deepseek_text === 'string' && item.deepseek_text.trim()) return plain(item.deepseek_text)
  return '分析记录'
}

function getAnalysisType(item) {
  const meta = item?.meta || item?.meta_json || item?.payload?.meta || {}
  const metaType = String(meta?.analysisType || '').toLowerCase()
  const titaiType = String(item?.titaiFb?.type || item?.titai_fb?.type || '').toLowerCase()
  const tixingType = String(item?.tixingFb?.type || item?.tixing_fb?.type || '').toLowerCase()

  if (metaType === 'history_analysis' || titaiType === 'history_analysis') return 'history_analysis'
  if (metaType === 'joint_detailed' || titaiType === 'joint_detailed') return 'joint_detailed'
  if (metaType === 'posture_only' || titaiType === 'posture_only') return 'posture_only'
  if (metaType === 'tongue_only' || tixingType === 'tongue_only') return 'tongue_only'
  if (metaType === 'tcm_ten_only' || titaiType === 'tcm_ten_only') return 'tcm_ten_only'
  if (metaType === 'joint_final' || titaiType === 'joint_final' || metaType === 'joint' || titaiType === 'joint') return 'joint'

  return 'joint'
}

/** 历史列表仅展示常规分析报告与复查分析（不展示单独体态/舌苔/仅十问等） */
const VISIBLE_HISTORY_TYPES = new Set(['joint', 'joint_detailed', 'history_analysis'])

function filterVisibleRecords(list) {
  return list
    .filter((r) => VISIBLE_HISTORY_TYPES.has(r.analysisType))
    .sort((a, b) => {
      const sa = pickReportSerial(a) ?? 0
      const sb = pickReportSerial(b) ?? 0
      if (sa !== sb) return sb - sa
      return String(b.createdAt || '').localeCompare(String(a.createdAt || ''))
    })
}

function pickCreatedAt(item, meta) {
  return (
    item?.createdAt ||
    item?.created_at ||
    item?.payload?.createdAt ||
    meta?.generatedAt ||
    meta?.createdAt ||
    null
  )
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function computeBmiValue(height, weight) {
  const h = toNumber(height)
  const w = toNumber(weight)
  if (h === null || w === null || h <= 0 || w <= 0) return null
  const hMeters = h > 10 ? h / 100 : h
  if (hMeters <= 0) return null
  const bmi = w / (hMeters * hMeters)
  return Number.isFinite(bmi) ? Number(bmi.toFixed(4)) : null
}

function resolveBasicProfile(item) {
  const meta = item?.meta || item?.meta_json || item?.payload?.meta || {}
  const profile =
    item?.basicProfile ||
    item?.userData ||
    item?.profileMeta ||
    meta?.profileMeta ||
    null
  if (!profile || typeof profile !== 'object') return null
  const bmi = computeBmiValue(profile?.height, profile?.weight)
  return bmi === null ? { ...profile } : { ...profile, bmi }
}

const METRIC_SKIP_KEYS = new Set(['type', 'sourcePostureRecordId', 'sourceTongueRecordId'])
const HISTORY_FIXED_METRICS = [
  { title: 'BMI', aliases: ['BMI', 'bmi'] },
  { title: '高低肩指数', aliases: ['高低肩指数', 'titai_fb.高低肩指数'] },
  { title: '骨盆倾斜指数', aliases: ['骨盆倾斜指数', 'titai_fb.骨盆倾斜指数'] },
  { title: '头前伸指数', aliases: ['头前伸指数', 'titai_fb.头前伸指数'] },
  { title: '膝关节对齐指数', aliases: ['膝关节对齐指数', 'titai_fb.膝关节对齐指数'] },
  { title: '上下身面积比', aliases: ['上下身面积比', 'tixing_fb.上下身面积比'] },
  { title: '腿身比', aliases: ['腿身比', 'tixing_fb.腿身比'] },
  { title: '腹部前突指数', aliases: ['腹部前突指数', 'tixing_fb.腹部前突指数'] },
  { title: '大腿小腿比', aliases: ['大腿小腿比', 'tixing_fb.大腿小腿比'] },
]

function collectNumericMetrics(source, prefix, out) {
  if (!source || typeof source !== 'object') return
  for (const [key, value] of Object.entries(source)) {
    if (METRIC_SKIP_KEYS.has(key)) continue
    const metricKey = `${prefix}.${key}`
    const num = toNumber(value)
    if (num !== null) {
      out[metricKey] = num
    }
  }
}

function extractNumericMetrics(item) {
  const postureData = buildPostureDataForJointReport(item)
  const metrics = {}
  collectNumericMetrics(postureData?.titai_fb || postureData?.titaiFb, 'titai_fb', metrics)
  collectNumericMetrics(postureData?.tixing_fb || postureData?.tixingFb, 'tixing_fb', metrics)
  collectNumericMetrics(postureData?.titai_lr || postureData?.titaiLr, 'titai_lr', metrics)
  collectNumericMetrics(postureData?.tixing_lr || postureData?.tixingLr, 'tixing_lr', metrics)
  return metrics
}

function resolveMetricKeyFromSourceItems(sourceItems, aliases) {
  const allKeys = new Set()
  for (const row of sourceItems) {
    const metrics = row?.metrics
    if (!metrics || typeof metrics !== 'object') continue
    Object.keys(metrics).forEach((k) => allKeys.add(k))
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

function buildTrendRowsFromSourceItems(sourceItems) {
  if (!Array.isArray(sourceItems) || sourceItems.length < 2) return []
  // 不要按 createdAt 排序：用户勾选顺序决定折线点位顺序（以及起点/终点）。
  const ordered = [...sourceItems]
  const first = ordered[0]?.metrics || {}
  const last = ordered[ordered.length - 1]?.metrics || {}

  return HISTORY_FIXED_METRICS.map((metric, idx) => {
    const key = resolveMetricKeyFromSourceItems(ordered, metric.aliases)
    const firstVal = key ? toNumber(first[key]) : null
    const lastVal = key ? toNumber(last[key]) : null
    const delta =
      firstVal === null || lastVal === null
        ? null
        : Number((lastVal - firstVal).toFixed(4))
    const trendText =
      delta === null ? '待智能体计算' : delta > 0 ? '上升' : delta < 0 ? '下降' : '基本持平'
    return {
      id: `pending-${idx}-${metric.title}`,
      metric: metric.title,
      change: delta === null ? '--' : `${delta >= 0 ? '+' : ''}${delta.toFixed(4)} (${trendText})`,
      comment:
        delta === null
          ? '等待智能体返回完整分析说明'
          : `起点: ${firstVal.toFixed(4)}，终点: ${lastVal.toFixed(4)}`,
    }
  })
}

function normalizeRecord(item) {
  const meta = item?.meta || item?.meta_json || item?.payload?.meta || {}
  const type = getAnalysisType(item)
  const normalizedId = normalizeRecordId(item?.id)

  const report =
    type === 'history_analysis'
      ? item?.historyAnalysisReport || item?.report || summaryText(item)
      : type === 'tongue_only'
        ? item?.tongueAnalysisText || summaryText(item)
        : type === 'posture_only'
          ? item?.postureAnalysisText || summaryText(item)
        : // 常规/专家联合报告：report 必须保留原始正文（含 <<<SECTION/GROUP/ITEM>>>），否则从历史进入会丢失结构化层级
          item?.comprehensiveAnalysisText ||
          item?.comprehensive_analysis_text ||
          item?.report ||
          item?.summary ||
          summaryText(item)

  return {
    ...item,
    id: normalizedId,
    reportSerial: pickReportSerial(item),
    analysisType: type,
    createdAt: pickCreatedAt(item, meta),
    report,
    postureReport:
      item?.postureAnalysisText || meta?.postureReport || item?.postureReport || '',
    tongueReport:
      item?.tongueAnalysisText || meta?.tongueReport || item?.tongueReport || '',
    trendData:
      item?.trendData ||
      item?.titaiFb?.trendData ||
      item?.titai_fb?.trendData ||
      meta?.trendData ||
      [],
    sourceItems:
      (Array.isArray(item?.historyChartData) && item.historyChartData) ||
      (Array.isArray(item?.history_chart_data) && item.history_chart_data) ||
      (Array.isArray(meta?.historyChartData) && meta.historyChartData) ||
      [],
    canAnalyze: type === 'joint',
  }
}

function loadFromLocalWithError() {
  records.value = filterVisibleRecords(getLocalHistory().map(normalizeRecord))
  error.value = '历史接口暂不可用，当前显示本地记录。'
}

function mergeRemoteAndLocal(remoteList) {
  const local = getLocalHistory().map(normalizeRecord)
  const merged = []
  const seen = new Set()

  const push = (r) => {
    if (r?.id === null || r?.id === undefined || r?.id === '') return
    if (seen.has(r.id)) return
    seen.add(r.id)
    merged.push(r)
  }

  ;(Array.isArray(remoteList) ? remoteList : []).forEach(push)
  // 兜底：远端可能短暂未返回“刚生成已保存”的记录，本地记录先并入，避免用户看到“消失”
  local.forEach(push)

  return merged
}

async function loadHistory() {
  loading.value = true
  error.value = ''
  const userId = localStorage.getItem('mask_user_id') || 'admin'

  try {
    const remote = await fetchHistory(userId)
    const list = Array.isArray(remote) ? remote.map(normalizeRecord) : []
    records.value = filterVisibleRecords(mergeRemoteAndLocal(list))
  } catch {
    loadFromLocalWithError()
  } finally {
    loading.value = false
  }
}

function isSelected(item) {
  return selectedIds.value.includes(item.id)
}

function onToggleSelect(item, checked) {
  if (!item?.canAnalyze || !item?.id) return
  if (checked) {
    if (!selectedIds.value.includes(item.id)) selectedIds.value.push(item.id)
    return
  }
  selectedIds.value = selectedIds.value.filter((id) => id !== item.id)
}

async function onAnalyzeSelected() {
  error.value = ''
  const userId = localStorage.getItem('mask_user_id') || 'admin'

  // 按“勾选顺序”生成 selected 列表（selectedIds 决定顺序）
  const selected = selectedIds.value
    .map((id) => records.value.find((r) => r?.id === id))
    .filter((item) => item?.canAnalyze)

  const selectedOrderIds = selected.map((item) => item.id)

  if (!selected.length) {
    error.value = '请至少勾选一条常规分析报告记录进行复查分析。'
    return
  }

  const payload = {
    userId,
    items: selected.map((item) => ({
      id: item.id,
      createdAt: item.createdAt || null,
      postureReport: item.postureReport || '',
      tongueReport: item.tongueReport || '',
      jointReport: item.report || '',
    })),
  }

  analyzing.value = true
  const pendingSourceItems = selected.map((item) => {
    const profileMeta = resolveBasicProfile(item)
    const metrics = extractNumericMetrics(item)
    const bmi = computeBmiValue(profileMeta?.height, profileMeta?.weight)
    if (bmi !== null) metrics.BMI = bmi
    return {
      id: item.id,
      reportSerial: item.reportSerial,
      createdAt: item.createdAt || null,
      metrics,
      profileMeta: profileMeta || {},
      userData: profileMeta || {},
    }
  })
  const pendingLatest = {
    id: `pending-${Date.now()}`,
    createdAt: new Date().toISOString(),
    type: 'history_analysis',
    analysisType: 'history_analysis',
    isGenerating: true,
    generationError: '',
    trendData: buildTrendRowsFromSourceItems(pendingSourceItems),
    report: '',
    summary: '',
    sourceItems: pendingSourceItems,
    payload: {
      isGenerating: true,
    },
  }
  saveLatestHistoryAnalysis(pendingLatest)
  await router.push('/history-analysis')

  try {
    const res = await generateHistoryAnalysis(payload)
    if (!res?.success) throw new Error(res?.msg || '复查分析失败')

    const rawChartData =
      (Array.isArray(res.historyChartData) && res.historyChartData) || pendingSourceItems

    // 后端可能按时间返回 historyChartData；这里按“勾选顺序”重排，保证折线图顺序一致。
    const reorderBySelected = (chartData, orderIds) => {
      if (!Array.isArray(chartData) || !orderIds?.length) return chartData
      const orderKeys = orderIds.map((id) => String(id))
      const map = new Map()
      for (const d of chartData) {
        const key = d?.id != null ? String(d.id) : null
        if (key) map.set(key, d)
      }
      const ordered = orderKeys.map((k) => map.get(k)).filter(Boolean)
      if (!ordered.length) return chartData
      const used = new Set(ordered.map((d) => String(d.id)))
      const rest = chartData.filter((d) => d?.id == null || !used.has(String(d.id)))
      return [...ordered, ...rest]
    }

    const latest = {
      id: res.recordId,
      reportSerial: res.reportSerial ?? null,
      createdAt: res.createdAt || new Date().toISOString(),
      type: 'history_analysis',
      analysisType: 'history_analysis',
      isGenerating: false,
      generationError: '',
      trendData: Array.isArray(res.trendData) ? res.trendData : [],
      report: res.historyAnalysisReport || '',
      summary: res.historyAnalysisReport || '',
      sourceItems:
        reorderBySelected(rawChartData, selectedOrderIds),
      payload: res,
    }
    saveLatestHistoryAnalysis(latest)

    saveHistoryRecord({
      id: latest.id,
      reportSerial: latest.reportSerial,
      createdAt: latest.createdAt,
      comprehensiveAnalysisText: latest.report,
      titaiFb: {
        type: 'history_analysis',
        trendData: latest.trendData,
      },
      historyChartData: latest.sourceItems,
      meta: {
        analysisType: 'history_analysis',
      },
    })

    selectedIds.value = []
    await loadHistory()
  } catch (err) {
    const msg = err?.message || '复查分析失败'
    error.value = msg
    saveLatestHistoryAnalysis({
      ...pendingLatest,
      isGenerating: false,
      generationError: msg,
      report: '',
      summary: '',
    })
  } finally {
    analyzing.value = false
  }
}

async function onDeleteRecord(item) {
  const recordId = item?.id
  if (!recordId) return

  const ok = window.confirm('确认删除这条历史记录吗？')
  if (!ok) return

  deletingId.value = recordId
  error.value = ''

  const userId = localStorage.getItem('mask_user_id') || 'admin'

  try {
    const res = await deleteHistoryRecord(recordId, userId)
    if (!res?.success) throw new Error('删除失败')
    records.value = records.value.filter((r) => r.id !== recordId)
    selectedIds.value = selectedIds.value.filter((id) => id !== recordId)
    removeLocalHistoryRecord(recordId)
  } catch {
    // 兼容早期仅在本地缓存中的记录：若远端确实不存在，则允许本地删除。
    try {
      const remote = await fetchHistory(userId)
      const remoteList = Array.isArray(remote) ? remote.map(normalizeRecord) : []
      const existsRemotely = remoteList.some((r) => recordIdsEqual(r?.id, recordId))
      if (!existsRemotely) {
        records.value = records.value.filter((r) => !recordIdsEqual(r?.id, recordId))
        selectedIds.value = selectedIds.value.filter((id) => !recordIdsEqual(id, recordId))
        removeLocalHistoryRecord(recordId)
        error.value = ''
        return
      }
    } catch {
      // 忽略兜底探测错误，走统一提示
    }
    error.value = '删除失败：该记录仍存在于数据库，请刷新后重试。'
    await loadHistory()
  } finally {
    deletingId.value = null
  }
}

function recordTypeLabel(t) {
  if (t === 'history_analysis') return '复查分析'
  if (t === 'joint_detailed') return '专家深度分析报告'
  return '常规分析报告'
}

function recordTypeTagClass(t) {
  if (t === 'history_analysis') return 'tag-history-analysis'
  if (t === 'joint_detailed') return 'tag-joint-detailed'
  return 'tag-joint'
}

/**
 * 联合报告记录在库中 titai_fb 常为 { type: joint_final, postureData }，指标在 meta.postureMetricsSnapshot 或 postureData 内层。
 */
function buildPostureDataForJointReport(item) {
  const meta = item?.meta || item?.meta_json || {}
  if (meta.postureMetricsSnapshot && typeof meta.postureMetricsSnapshot === 'object') {
    return meta.postureMetricsSnapshot
  }
  const titai = item?.titaiFb || item?.titai_fb
  if (titai && typeof titai === 'object' && titai.type === 'joint_final' && titai.postureData) {
    return titai.postureData
  }
  return {
    titai_fb: item?.titaiFb || item?.titai_fb || null,
    tixing_fb: item?.tixingFb || item?.tixing_fb || null,
    titai_lr: item?.titaiLr || item?.titai_lr || null,
    tixing_lr: item?.tixingLr || item?.tixing_lr || null,
  }
}

function openRecord(item) {
  if (item.analysisType === 'history_analysis') {
    saveLatestHistoryAnalysis({
      id: item.id,
      createdAt: item.createdAt,
      type: 'history_analysis',
      analysisType: 'history_analysis',
      trendData: item.trendData || [],
      sourceItems: item.sourceItems || [],
      report: item.report || '',
      summary: item.report || '',
      payload: item,
    })
    router.push('/history-analysis')
    return
  }

  saveLatestJointReport({
    id: item.id,
    reportSerial: pickReportSerial(item),
    createdAt: item.createdAt,
    type: item.analysisType === 'joint_detailed' ? 'joint_detailed' : 'joint',
    analysisType: item.analysisType || 'joint',
    sourcePostureRecordId:
      item?.titaiFb?.sourcePostureRecordId ||
      item?.titai_fb?.sourcePostureRecordId ||
      item?.meta?.sourcePostureRecordId ||
      item?.meta_json?.sourcePostureRecordId ||
      item?.payload?.meta?.sourcePostureRecordId ||
      item?.payload?.meta_json?.sourcePostureRecordId ||
      null,
    sourceTongueRecordId:
      item?.tixingFb?.sourceTongueRecordId ||
      item?.tixing_fb?.sourceTongueRecordId ||
      item?.meta?.sourceTongueRecordId ||
      item?.meta_json?.sourceTongueRecordId ||
      item?.payload?.meta?.sourceTongueRecordId ||
      item?.payload?.meta_json?.sourceTongueRecordId ||
      null,
    postureReport: item.postureReport || '',
    tongueReport: item.tongueReport || '',
    report: item.report || '',
    summary: item.report || '',
    postureData: buildPostureDataForJointReport(item),
    payload: item,
    // slimJointReportForStorage 会丢弃 payload，必须把 meta.profileMeta 提到顶层，否则进入联合报告页后档案丢失
    basicProfile: resolveBasicProfile(item) || item.basicProfile || null,
    tcmTenQuestions: item.tcmTenQuestions || null,
  })
  router.push('/joint-report')
}

onMounted(loadHistory)
</script>

<template>
  <section class="page-wrap">
    <TopNav active="history" />

    <main class="content">
      <section class="card history-card">
        <header class="history-header">
          <h2>历史记录与跟踪复查</h2>
          <p>勾选常规分析报告可进行复查分析；复查分析类型不可再次勾选分析。</p>
        </header>

        <div class="toolbar">
          <button type="button" class="analyze-btn" :disabled="analyzing" @click="onAnalyzeSelected">
            {{ analyzing ? '分析中...' : '复查分析' }}
          </button>
        </div>

        <p v-if="loading" class="muted">正在加载历史记录...</p>
        <p v-if="error" class="warn">{{ error }}</p>
        <p v-if="!loading && !records.length" class="muted">还没有历史记录</p>

        <div v-if="records.length" class="history-list">
          <article v-for="item in records" :key="item.id" class="history-row">
            <label class="select-box" :class="{ disabled: !item.canAnalyze }">
              <input
                type="checkbox"
                :disabled="!item.canAnalyze"
                :checked="isSelected(item)"
                @change="(e) => onToggleSelect(item, e.target.checked)"
              />
              <span class="select-circle" aria-hidden="true">
                <span v-if="isSelected(item)" class="select-circle-num">{{ getSelectedSeq(item) }}</span>
              </span>
            </label>

            <button type="button" class="history-item" @click="openRecord(item)">
              <small>
                {{ formatDate(item.createdAt) }}
                <span v-if="formatReportSerialLabel(item)" class="id-tag">{{ formatReportSerialLabel(item) }}</span>
                <span class="type-tag" :class="recordTypeTagClass(item.analysisType)">
                  {{ recordTypeLabel(item.analysisType) }}
                </span>
              </small>
              <div class="summary-box">{{ summaryText(item) }}</div>
            </button>

            <button type="button" class="delete-btn" :disabled="deletingId === item.id" @click="onDeleteRecord(item)">
              {{ deletingId === item.id ? '删除中...' : '删除' }}
            </button>
          </article>
        </div>
      </section>
    </main>
  </section>
</template>

<style scoped>
.page-wrap { min-height: 100vh; }
.content { padding: 18px; }
.history-card { max-width: 1100px; }
.history-header { text-align: center; }
.history-header h2 { margin: 0; color: #1e293b; }
.history-header p { margin: 8px 0 0; color: #64748b; }
.toolbar { display: flex; justify-content: flex-end; margin-top: 14px; }
.analyze-btn { margin: 0; height: 40px; background: #0f766e; color: #f0fdfa; border-radius: 10px; }
.history-list { display: grid; gap: 12px; margin-top: 14px; }
.history-row { display: grid; grid-template-columns: 30px minmax(0, 1fr) 84px; gap: 10px; align-items: center; }
.select-box { position: relative; display: inline-flex; justify-content: center; align-items: center; width: 30px; height: 30px; }
.select-box input { position: absolute; opacity: 0; pointer-events: none; }
.select-circle {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  border: 2px solid #cbd5e1;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.select-box:not(.disabled) .select-circle { cursor: pointer; }
.select-box:not(.disabled) input:checked + .select-circle {
  border-color: #0f766e;
  background: #0f766e;
}
.select-circle-num {
  color: #ffffff;
  font-size: 11px;
  font-weight: 900;
  line-height: 1;
}
.select-box.disabled { opacity: 0.45; }
.history-item { border: 0; background: transparent; text-align: left; padding: 0; cursor: pointer; width: 100%; margin: 0; min-width: 0; overflow: hidden; }
.history-item small { display: flex; align-items: center; gap: 8px; color: #94a3b8; margin-bottom: 6px; font-size: 12px; }
.id-tag { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; color: #64748b; }
.type-tag { border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 700; }
.tag-joint { background: #dcfce7; color: #166534; }
.tag-joint-detailed { background: #ede9fe; color: #5b21b6; }
.tag-posture { background: #dbeafe; color: #1d4ed8; }
.tag-tongue { background: #fef3c7; color: #b45309; }
.tag-history-analysis { background: #fee2e2; color: #991b1b; }
.summary-box { border: 1px solid #d1d5db; background: #f8fafc; border-radius: 10px; color: #334155; padding: 14px; line-height: 1.5; display: block; width: 100%; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.history-item:hover .summary-box { border-color: #94a3b8; }
.delete-btn { height: 42px; margin: 0; border: 1px solid #fecaca; border-radius: 10px; background: #fff1f2; color: #b91c1c; font-weight: 700; }
@media (max-width: 900px) {
  .content { padding: 12px; }
  .history-row { grid-template-columns: 30px 1fr; }
  .delete-btn { grid-column: 2; }
}
</style>
