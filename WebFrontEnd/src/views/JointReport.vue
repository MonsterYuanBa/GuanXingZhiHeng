<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import TopNav from '../components/TopNav.vue'
import {
  formatBasicProfileRows,
  tcmRowsForDisplay,
} from '../constants/tcmAndProfileLabels'
import { clearLatestJointReport, getLatestJointReport, saveLatestJointReport } from '../services/reportStore'
import {
  appendJointUserRequirement,
  clearJointReportStatus,
  deleteJointUserRequirement,
  fetchHistory,
  fetchJointReportStatus,
  fetchJointUserRequirements,
  fetchMosaicPostureImage,
  fetchProcessedPostureImage,
  fetchTongueImage,
  generateJointReport,
  pickRandomTestModSampleId,
  runJointAgentFromSample,
  runJointDetailedAnalysis,
} from '../services/api'
import { clearCollectorImages, getCollectorImage, getPostureResultDisplay } from '../services/collectorImageDb'
import { parseAgentText } from '../services/structuredText'
import { formatReportSerialLabel, pickReportSerial } from '../utils/reportNumber'
import { clearPendingPosture, clearPendingTongue } from '../services/reportStore'

const report = ref(null)
const postureRows = ref([])
const showMetricDialog = ref(false)
const activeTopCard = ref('profile') // 'profile' | 'tcm' | 'metrics'
/** 单项分析报告卡片：体态 / 舌苔 / 用户需求（库中已保存条目） */
const RIGHT_CARD_ORDER = ['posture', 'tongue', 'requirements']
const activeRightCard = ref('posture')
const humanImageUrl = ref('')
const humanImageLoading = ref(false)
const humanImageError = ref('')
const humanImageIsObjectUrl = ref(false)
const humanBaseImageUrl = ref('')
const humanBaseImageIsObjectUrl = ref(false)
// PDF 导出时的舌苔图片：导出后即可展示；图片创建的 object URL 用于跨窗口引用
const tongueImageUrlForPdf = ref('')
const tongueImageIsObjectUrl = ref(false)
const compareRevealPct = ref(62)
const compareDragging = ref(false)
const reportPollingTimer = ref(null)
const statusPollingTimer = ref(null)
const systemPanelOpen = ref(false)
const detailLoading = ref(false)
const detailedFlowUnlocked = ref(false)
const activeFlowCard = ref('joint') // 'joint' | 'full'
const analyzingDots = ref('.')
const analyzingDotsTimer = ref(null)
const detailedUserRequirement = ref('')
const userRequirementEntries = ref([])
const requirementSubmitting = ref(false)
const requirementDeletingSeq = ref(null)
const initialSystemMessages = () => [
  { text: '[系统] 控制台已就绪', color: '' },
  { text: '[提示] 你可以在这里展示多智能体流程输出', color: '' },
]
const systemMessages = ref(initialSystemMessages())
const metricDefs = [
  { name: '高低肩指数', meaning: '反映左右肩高度差异，数值越接近 0 通常表示越对称。' },
  { name: '骨盆倾斜指数', meaning: '反映骨盆左右倾斜程度，绝对值越大表示倾斜更明显。' },
  { name: '头前伸指数', meaning: '反映头部前引趋势，数值越大通常表示前伸越明显。' },
  { name: '膝关节对齐指数', meaning: '反映下肢力线与膝关节对齐情况，偏离越大对齐越差。' },
  { name: '上下身面积比', meaning: '用于评估上半身与下半身轮廓比例变化。' },
  { name: '腿身比', meaning: '反映腿部相对身高比例变化。' },
  { name: '腹部前突指数', meaning: '反映侧面腹部前突趋势，数值升高通常提示前突更明显。' },
  { name: '大腿小腿比', meaning: '反映大腿与小腿轮廓比例变化。' },
  { name: '头身比', meaning: '反映头部与身体整体比例。' },
  { name: '躯干身高比', meaning: '反映躯干长度与身高比例。' },
  { name: '头肩比', meaning: '反映头部宽度与肩部宽度比例。' },
]

const METRIC_SKIP_KEYS = new Set(['type', 'sourcePostureRecordId', 'sourceTongueRecordId'])
const isAgentAnalyzing = computed(() => {
  if (detailLoading.value || report.value?.isGenerating) return true
  const lines = systemMessages.value
  const latest = lines.length ? String(lines[lines.length - 1]?.text || '') : ''
  return /正在|分析中|迭代|调用AI/.test(latest)
})
const systemFloatBtnText = computed(() => {
  if (isAgentAnalyzing.value) return `智能体\n分析中${analyzingDots.value}`
  return systemPanelOpen.value ? '隐藏\n系统输出台' : '系统\n输出台'
})
const hasDetailedFlowData = computed(() =>
  systemMessages.value.some((x) => String(x?.text || '').includes('专家深度分析-')),
)
const canSwitchFullFlow = computed(() => detailedFlowUnlocked.value || hasDetailedFlowData.value)
const flowState = computed(() => {
  const lines = systemMessages.value.map((x) => String(x?.text || ''))
  const has = (kw) => lines.some((t) => t.includes(kw))
  const hasAny = (arr) => arr.some((kw) => has(kw))
  const latest = lines.length ? lines[lines.length - 1] : ''

  const postureDone = hasAny([
    '专家深度分析-体态体型报告：评估通过',
    '专家深度分析-体态体型报告：结束',
  ])
  const tongueDone = hasAny([
    '专家深度分析-舌苔报告：评估通过',
    '专家深度分析-舌苔报告：结束',
  ])
  // 专家深度分析流程（完整流程图）只看“专家深度分析-*”消息，和普通常规分析完全隔离
  const detailedJointDone = hasAny([
    '专家深度分析-综合报告：评估通过',
    '专家深度分析-综合报告：结束',
    '专家深度分析完成并已更新记录',
  ])

  const postureActive = latest.includes('专家深度分析-体态体型报告：') && !postureDone
  const tongueActive = latest.includes('专家深度分析-舌苔报告：') && !tongueDone
  const jointActive =
    postureDone &&
    tongueDone &&
    latest.includes('专家深度分析-综合报告：') &&
    !detailedJointDone

  // 普通常规分析流程（简版卡片）
  const miniJointDone = hasAny([
    '常规分析：分析完成',
    '常规分析：报告已保存',
  ])
  const miniJointActive = has('常规分析：正在分析中') && !miniJointDone

  return {
    postureDone,
    tongueDone,
    jointDone: detailedJointDone,
    postureActive,
    tongueActive,
    jointActive,
    miniJointDone,
    miniJointActive,
  }
})

/** 输出台仅展示后端状态流，不混入用户需求正文（需求在单项分析卡片中展示） */
const jointConsoleLines = computed(() =>
  systemMessages.value.map((line, idx) => ({
    text: String(line?.text || ''),
    color: line?.color || '',
    key: `sys-${idx}`,
  })),
)

function nodeClass(active, done, alwaysGreen = false) {
  if (alwaysGreen) return 'flow-node done'
  if (active) return 'flow-node active'
  if (done) return 'flow-node done'
  return 'flow-node idle'
}

function edgeClass(active, done) {
  if (active) return 'flow-edge active'
  if (done) return 'flow-edge done'
  return 'flow-edge idle'
}

function formatMetricValue(value) {
  if (value === null || value === undefined || value === '') return '--'
  if (typeof value === 'number') return Number.isFinite(value) ? value.toFixed(6) : '--'

  const raw = String(value).trim()
  if (!raw) return '--'

  const asNum = Number(raw)
  if (Number.isFinite(asNum)) return asNum.toFixed(6)
  return raw
}

function readLocalProfile() {
  try {
    const uid = localStorage.getItem('mask_user_id') || 'admin'
    return JSON.parse(localStorage.getItem(`mask_profile_${uid}`) || '{}')
  } catch {
    return {}
  }
}

/** 报告内快照优先；缺项用本机 mask_profile（与页内提示「当前本机档案」一致） */
function mergeBasicProfileForReportView(reportObj) {
  const snap = resolveBasicProfileSnapshot(reportObj)
  const local = readLocalProfile()
  const keys = ['age', 'gender', 'height', 'weight', 'allergyHistory', 'medicalHistory', 'workHabit']
  const out = {}
  for (const k of keys) {
    const s = snap?.[k]
    const l = local?.[k]
    const sOk = s != null && s !== ''
    const lOk = l != null && l !== ''
    if (sOk) out[k] = s
    else if (lOk) out[k] = l
    else out[k] = ''
  }
  return out
}

function mergeTcmTenQuestionsForReportView(reportObj) {
  const snap = resolveTcmTenQuestionsSnapshot(reportObj)
  const local = readLocalProfile()?.tcmTenQuestions
  const loc = local && typeof local === 'object' ? local : {}
  const sn = snap && typeof snap === 'object' ? snap : {}
  const keys = [...new Set([...Object.keys(loc), ...Object.keys(sn)])]
  const out = {}
  for (const k of keys) {
    const sv = sn[k]
    const lv = loc[k]
    if (sv != null && sv !== '') out[k] = sv
    else out[k] = lv ?? sv ?? ''
  }
  return out
}

function resolveBasicProfileSnapshot(source) {
  if (!source || typeof source !== 'object') return null
  const meta =
    source?.meta || source?.meta_json || source?.payload?.meta || source?.payload?.meta_json || {}
  const profile =
    source?.basicProfile ||
    source?.userData ||
    source?.profileMeta ||
    meta?.profileMeta ||
    source?.payload?.profileMeta ||
    null
  if (!profile || typeof profile !== 'object') return null
  return profile
}

function resolveTcmTenQuestionsSnapshot(source) {
  if (!source || typeof source !== 'object') return null
  const t = source?.tcmTenQuestions || source?.payload?.tcmTenQuestions || null
  if (!t || typeof t !== 'object') return null
  return t
}

async function fetchRecordSnapshots({ userId, recordId }) {
  const rid = Number(recordId)
  if (!Number.isFinite(rid) || rid <= 0) return { basicProfile: null, tcmTenQuestions: null }
  try {
    const list = await fetchHistory(userId)
    const rec = Array.isArray(list) ? list.find((x) => Number(x?.id) === rid) : null
    return {
      basicProfile: resolveBasicProfileSnapshot(rec),
      tcmTenQuestions: resolveTcmTenQuestionsSnapshot(rec),
    }
  } catch {
    return { basicProfile: null, tcmTenQuestions: null }
  }
}

function toMetricRows(source, groupLabel) {
  if (!source || typeof source !== 'object') return []
  return Object.entries(source)
    .filter(([key]) => !METRIC_SKIP_KEYS.has(key))
    .map(([key, value]) => ({
      group: groupLabel,
      key,
      value: formatMetricValue(value),
    }))
}

function hydrateReport(latest) {
  report.value = latest
  const postureData = resolvePostureMetrics(latest)
  postureRows.value = [
    ...toMetricRows(postureData?.titai_fb || postureData?.titaiFb, '体态指标'),
    ...toMetricRows(postureData?.tixing_fb || postureData?.tixingFb, '体型指标'),
    ...toMetricRows(postureData?.titai_lr || postureData?.titaiLr, '侧面体态'),
    ...toMetricRows(postureData?.tixing_lr || postureData?.tixingLr, '侧面体型'),
  ]
}

function resolvePostureMetrics(latest) {
  const meta = latest?.payload?.meta || latest?.payload?.meta_json || latest?.meta || {}
  if (meta.postureMetricsSnapshot && typeof meta.postureMetricsSnapshot === 'object') {
    return meta.postureMetricsSnapshot
  }
  const pd = latest?.postureData
  if (!pd || typeof pd !== 'object') return {}
  const tf = pd.titai_fb || pd.titaiFb
  if (tf && typeof tf === 'object' && tf.type === 'joint_final' && tf.postureData) {
    return typeof tf.postureData === 'object' ? tf.postureData : {}
  }
  return pd
}

const basicProfileSource = computed(() => mergeBasicProfileForReportView(report.value))

const basicProfileRows = computed(() => formatBasicProfileRows(basicProfileSource.value))

const profileFallbackHint = computed(() => {
  const snap = resolveBasicProfileSnapshot(report.value)
  return !(snap && (snap.age != null && snap.age !== '' || snap.gender))
})

const tcmSource = computed(() => mergeTcmTenQuestionsForReportView(report.value))

const tcmRows = computed(() => tcmRowsForDisplay(tcmSource.value))

const tcmFallbackHint = computed(() => {
  const t = resolveTcmTenQuestionsSnapshot(report.value)
  return !(t && Object.keys(t).length)
})

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
  // 兼容后端 naive datetime：按 UTC 解释（后端多处 utcnow().isoformat()），再按上海时区展示
  const normalized = hasTimezone ? raw : `${raw}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatDateTimeCn(value) {
  const date = parseBackendDate(value)
  if (!date) return ''
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

const createdAtDisplay = computed(() => {
  const date = parseBackendDate(report.value?.createdAt)
  if (!date) return report.value?.createdAt || '未知时间'
  return date.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
})
const reportPageTitle = computed(() => '综合分析报告')

const reportSerialLabel = computed(() => formatReportSerialLabel(report.value))

/** Mock 下仅普通常规分析（非专家落库报告）在卡片内额外列出需求；专家深度分析 Mock 的需求已拼在综合报告正文中。 */
const jointCardUserRequirementLines = computed(() => {
  const lines = []
  for (const e of userRequirementEntries.value || []) {
    const body = String(e.text || '').trim()
    if (!body) continue
    const seqRaw = e.seq
    const n = Number.isFinite(Number(seqRaw)) && Number(seqRaw) > 0 ? Number(seqRaw) : lines.length + 1
    const ts = String(e.at || '').trim()
    lines.push(ts ? `#${n} [${ts}] ${body}` : `#${n} ${body}`)
  }
  const extra = String(report.value?.mockSupplementalRequirement || '').trim()
  if (extra) lines.push(`（本次请求补充说明）${extra}`)
  return lines
})

const showMockJointUserReq = computed(
  () =>
    Boolean(report.value?.mockAi) &&
    report.value?.analysisType !== 'joint_detailed' &&
    jointCardUserRequirementLines.value.length > 0,
)

const structuredPostureReport = computed(() => parseAgentText(report.value?.postureReport || ''))
const structuredTongueReport = computed(() => parseAgentText(report.value?.tongueReport || ''))
const structuredJointReport = computed(() => parseAgentText(report.value?.report || report.value?.summary || ''))

function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

function renderStructuredItemsForPdf(items) {
  if (!Array.isArray(items) || !items.length) return ''
  const list = items
    .map((item) => {
      const title = item?.title ? `<strong class="item-title">${escapeHtml(item.title)}</strong>` : ''
      const body = item?.body ? `<p class="item-body">${escapeHtml(item.body)}</p>` : ''
      const children = Array.isArray(item?.children) && item.children.length
        ? `<ul class="nested-list">${renderStructuredItemsForPdf(item.children)}</ul>`
        : ''
      return `<li class="struct-item">${title}${body}${children}</li>`
    })
    .join('')
  return list
}

function renderStructuredSectionsForPdf(structured, fallbackText) {
  const sections = Array.isArray(structured?.sections) ? structured.sections : []
  if (!sections.length) {
    return `<p class="empty-block">${escapeHtml(fallbackText)}</p>`
  }
  return sections
    .map((sec) => {
      const title = sec?.title ? `<h3 class="section-title">${escapeHtml(sec.title)}</h3>` : ''
      const intro = sec?.intro ? `<p class="section-intro">${escapeHtml(sec.intro)}</p>` : ''
      const items = Array.isArray(sec?.items) && sec.items.length
        ? `<ul class="struct-list">${renderStructuredItemsForPdf(sec.items)}</ul>`
        : ''
      return `<section class="structured-section">${title}${intro}${items}</section>`
    })
    .join('')
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    if (!blob) {
      resolve('')
      return
    }
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

async function urlToDataUrlForPdf(url) {
  const u = String(url || '').trim()
  if (!u) return ''
  if (u.startsWith('data:')) return u
  try {
    const res = await fetch(u)
    if (!res.ok) return ''
    return blobToDataUrl(await res.blob())
  } catch {
    return ''
  }
}

function resolveTongueRecordIdForImage(r) {
  if (!r) return null
  const meta = r?.payload?.meta || r?.payload?.meta_json || r?.meta || {}
  const tixingFb = r?.tixingFb || r?.tixing_fb || r?.payload?.tixingFb || r?.payload?.tixing_fb
  const tongueData = r?.tongueData ?? r?.payload?.tongueData
  return (
    _positiveRecordId(r.sourceTongueRecordId) ||
    _positiveRecordId(meta.sourceTongueRecordId) ||
    _positiveRecordId(tixingFb?.sourceTongueRecordId) ||
    (tongueData && typeof tongueData === 'object'
      ? _positiveRecordId(tongueData.recordId ?? tongueData.record_id)
      : null) ||
    _positiveRecordId(r.id)
  )
}

async function fetchTongueImageBlob(uid, recordId) {
  const rid = _positiveRecordId(recordId)
  if (rid == null) return null
  try {
    const blob = await fetchTongueImage(rid, uid)
    return blob || null
  } catch {
    return null
  }
}

async function cacheTongueImageBlob(blob) {
  if (!blob) return
  if (tongueImageUrlForPdf.value && tongueImageIsObjectUrl.value) {
    URL.revokeObjectURL(tongueImageUrlForPdf.value)
  }
  tongueImageUrlForPdf.value = URL.createObjectURL(blob)
  tongueImageIsObjectUrl.value = true
}

async function resolveTongueImageDataUrlForPdf(uid, r) {
  if (tongueImageUrlForPdf.value) {
    const fromCache = await urlToDataUrlForPdf(tongueImageUrlForPdf.value)
    if (fromCache) return fromCache
  }

  try {
    const tongueFile = await getCollectorImage(uid, 'tongue')
    if (tongueFile) {
      await cacheTongueImageBlob(tongueFile)
      return blobToDataUrl(tongueFile)
    }
  } catch {
    /* ignore */
  }

  const tongueRid = resolveTongueRecordIdForImage(r)
  const jointRid = _positiveRecordId(r?.id)
  const candidateIds = []
  if (tongueRid != null) candidateIds.push(tongueRid)
  if (jointRid != null && jointRid !== tongueRid) candidateIds.push(jointRid)

  for (const rid of candidateIds) {
    const blob = await fetchTongueImageBlob(uid, rid)
    if (blob) {
      await cacheTongueImageBlob(blob)
      return blobToDataUrl(blob)
    }
  }
  return ''
}

function waitForPopupImages(popup, timeoutMs = 4000) {
  return new Promise((resolve) => {
    const imgs = Array.from(popup.document?.images || [])
    if (!imgs.length) {
      resolve()
      return
    }
    let done = false
    const finish = () => {
      if (done) return
      done = true
      resolve()
    }
    let pending = 0
    imgs.forEach((img) => {
      if (img.complete) return
      pending += 1
      img.addEventListener('load', () => {
        pending -= 1
        if (pending <= 0) finish()
      }, { once: true })
      img.addEventListener('error', () => {
        pending -= 1
        if (pending <= 0) finish()
      }, { once: true })
    })
    if (pending <= 0) finish()
    window.setTimeout(finish, timeoutMs)
  })
}

async function preloadTongueImageForPdf(uid, r) {
  if (tongueImageUrlForPdf.value) return
  try {
    const tongueFile = await getCollectorImage(uid, 'tongue')
    if (tongueFile) {
      await cacheTongueImageBlob(tongueFile)
      return
    }
  } catch {
    /* ignore */
  }
  const tongueRid = resolveTongueRecordIdForImage(r)
  const jointRid = _positiveRecordId(r?.id)
  const candidateIds = []
  if (tongueRid != null) candidateIds.push(tongueRid)
  if (jointRid != null && jointRid !== tongueRid) candidateIds.push(jointRid)
  for (const rid of candidateIds) {
    const blob = await fetchTongueImageBlob(uid, rid)
    if (blob) {
      await cacheTongueImageBlob(blob)
      return
    }
  }
}

async function exportPdf() {
  if (!report.value) return

  const uid = localStorage.getItem('mask_user_id') || 'admin'
  const [processedImageDataUrl, tongueImageDataUrl] = await Promise.all([
    urlToDataUrlForPdf(humanImageUrl.value || humanBaseImageUrl.value || ''),
    resolveTongueImageDataUrlForPdf(uid, report.value),
  ])

  const popup = window.open('', '_blank')
  if (!popup) return

  const basicHtml = basicProfileRows.value
    .map((row) => `<li><strong>${escapeHtml(row.k)}：</strong>${escapeHtml(row.v)}</li>`)
    .join('')
  const tcmHtml = tcmRows.value
    .map((row) => `<li><strong>${escapeHtml(row.label)}：</strong>${escapeHtml(row.text)}</li>`)
    .join('')
  const metricsHtml = postureRows.value
    .map((row) => `<tr><td>${escapeHtml(row.group)}</td><td>${escapeHtml(row.key)}</td><td>${escapeHtml(row.value)}</td></tr>`)
    .join('')
  const postureStructuredHtml = renderStructuredSectionsForPdf(structuredPostureReport.value, '暂无体态报告')
  const tongueStructuredHtml = renderStructuredSectionsForPdf(structuredTongueReport.value, '暂无舌苔报告')
  const jointStructuredHtml = renderStructuredSectionsForPdf(structuredJointReport.value, '暂无分析与建议')
  const processedImageCardHtml = processedImageDataUrl
    ? `<img class="processed-img" src="${escapeHtml(processedImageDataUrl)}" alt="处理后图像" />`
    : '<p class="muted">暂无处理后图像</p>'
  const tongueImageCardHtml = tongueImageDataUrl
    ? `<img class="processed-img" src="${escapeHtml(tongueImageDataUrl)}" alt="舌苔图像" />`
    : '<p class="muted">暂无舌苔图像</p>'
  const statsCards = [
    { label: '体态体型指标数', value: postureRows.value.length || 0 },
    { label: '中医十问条目数', value: tcmRows.value.length || 0 },
    { label: '用户需求条目数', value: userRequirementEntries.value.length || 0 },
  ]
    .map((card) => `<div class="stat-card"><p class="stat-label">${escapeHtml(card.label)}</p><p class="stat-value">${escapeHtml(card.value)}</p></div>`)
    .join('')

  popup.document.write(`
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>${escapeHtml(reportPageTitle.value)}</title>
        <style>
          @page { size: A4 landscape; margin: 10mm; }
          :root { color-scheme: light; }
          * { box-sizing: border-box; }
          html, body { width: 100%; }
          body {
            font-family: "Microsoft YaHei", sans-serif;
            margin: 0;
            padding: 8mm;
            color: #1f2937;
            background: #f8fafc;
            min-width: 1280px;
          }
          h1, h2, h3 { margin: 0; }
          .header { background: linear-gradient(135deg, #dbeafe, #ecfeff); border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px; margin-bottom: 14px; }
          .header-sub { color: #475569; margin-top: 8px; font-size: 13px; }
          .stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
          .stat-card { border: 1px solid #cbd5e1; border-radius: 10px; background: #ffffff; padding: 10px 12px; }
          .stat-label { margin: 0; color: #64748b; font-size: 12px; }
          .stat-value { margin: 6px 0 0; color: #0f172a; font-size: 22px; font-weight: 700; }
          .overview-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 12px; margin-bottom: 12px; align-items: stretch; }
          .overview-left { display: grid; gap: 12px; }
          .images-row { display: flex; gap: 12px; align-items: stretch; }
          .image-card { display: flex; flex-direction: column; flex: 1; }
          .image-wrap { border: 1px solid #dbe4f1; border-radius: 10px; background: #f8fafc; min-height: 430px; display: flex; align-items: center; justify-content: center; padding: 8px; }
          .processed-img { width: 100%; max-height: 520px; object-fit: contain; border-radius: 8px; display: block; }
          .card { border: 1px solid #cbd5e1; border-radius: 12px; background: #ffffff; padding: 14px; margin-bottom: 12px; }
          .card h2 { font-size: 17px; margin-bottom: 10px; color: #0f172a; }
          .card ul { margin: 0; padding-left: 18px; }
          .card li { margin: 4px 0; }
          table { width: 100%; border-collapse: collapse; background: #fff; }
          th, td { border: 1px solid #cbd5e1; padding: 7px 8px; text-align: left; font-size: 12px; vertical-align: top; }
          th { background: #eff6ff; color: #1e3a8a; font-weight: 700; }
          tr:nth-child(even) td { background: #f8fafc; }
          .structured-section + .structured-section { margin-top: 12px; border-top: 1px dashed #cbd5e1; padding-top: 10px; }
          .section-title { font-size: 15px; color: #0f172a; margin-bottom: 6px; }
          .section-intro { margin: 0 0 6px; color: #475569; font-size: 13px; line-height: 1.6; }
          .struct-list, .nested-list { margin: 0; padding-left: 18px; }
          .struct-item { margin: 6px 0; }
          .item-title { color: #0f172a; }
          .item-body { margin: 4px 0 0; color: #334155; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }
          .empty-block { margin: 0; color: #64748b; }
          .muted { color: #64748b; }
          @media print {
            body { background: #ffffff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          }
        </style>
      </head>
      <body>
        <section class="header">
          <h1>${escapeHtml(reportPageTitle.value)}</h1>
          <p class="header-sub">${escapeHtml(reportSerialLabel.value ? `${reportSerialLabel.value} · ` : '')}生成时间（北京时间）：${escapeHtml(createdAtDisplay.value || '未知时间')}</p>
        </section>
        <section class="stats">${statsCards}</section>
        <section class="overview-grid">
          <div class="overview-left">
            <div class="card"><h2>基本信息</h2><ul>${basicHtml}</ul></div>
            <div class="card"><h2>中医十问</h2><ul>${tcmHtml}</ul></div>
          </div>
          <div class="images-row">
            <div class="card image-card">
              <h2>处理后图像</h2>
              <div class="image-wrap">${processedImageCardHtml}</div>
            </div>
            <div class="card image-card">
              <h2>舌苔图像</h2>
              <div class="image-wrap">${tongueImageCardHtml}</div>
            </div>
          </div>
        </section>
        <div class="card">
          <h2>体态与体型数据</h2>
          <table>
            <thead><tr><th>类别</th><th>指标</th><th>值</th></tr></thead>
            <tbody>${metricsHtml || '<tr><td colspan="3">暂无体态体型数据</td></tr>'}</tbody>
          </table>
        </div>
        <div class="card"><h2>体态体型报告</h2>${postureStructuredHtml}</div>
        <div class="card"><h2>舌苔报告</h2>${tongueStructuredHtml}</div>
        <div class="card"><h2>分析与建议</h2>${jointStructuredHtml}${
          showMockJointUserReq.value
            ? `<h3 style="margin:12px 0 6px;font-size:14px;color:#64748b;">本条关联的用户需求（模拟输出）</h3><ul>${jointCardUserRequirementLines.value
                .map((l) => `<li>${escapeHtml(l)}</li>`)
                .join('')}</ul>`
            : ''
        }</div>
      </body>
    </html>
  `)
  popup.document.close()
  await waitForPopupImages(popup)
  popup.focus()
  popup.print()
}

function openMetricGuide() {
  showMetricDialog.value = true
}

function closeMetricGuide() {
  showMetricDialog.value = false
}

function setActiveTopCard(next) {
  activeTopCard.value = next
}

function goPrevTopCard() {
  activeTopCard.value =
    activeTopCard.value === 'profile'
      ? 'metrics'
      : activeTopCard.value === 'tcm'
        ? 'profile'
        : 'tcm'
}

function goNextTopCard() {
  activeTopCard.value =
    activeTopCard.value === 'profile'
      ? 'tcm'
      : activeTopCard.value === 'tcm'
        ? 'metrics'
        : 'profile'
}

function setActiveRightCard(next) {
  activeRightCard.value = next
}

function toggleSystemPanel() {
  if (!systemPanelOpen.value) activeFlowCard.value = 'joint'
  systemPanelOpen.value = !systemPanelOpen.value
  if (systemPanelOpen.value) {
    void loadUserRequirements()
  }
}

function _positiveRecordId(v) {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : null
}

/** 已落库的常规分析记录 id；草稿阶段用体态/舌苔源记录 id（与后端 merge 逻辑一致） */
function getJointRequirementQuery() {
  const r = report.value
  if (!r) return null
  const jointId = _positiveRecordId(r.id)
  if (jointId != null) return { recordId: jointId }

  const fromTop = _positiveRecordId(r.sourcePostureRecordId) || _positiveRecordId(r.sourceTongueRecordId)
  if (fromTop != null) return { recordId: fromTop }

  const pd = r.postureData
  if (pd && typeof pd === 'object') {
    const fromPd = _positiveRecordId(pd.recordId ?? pd.record_id)
    if (fromPd != null) return { recordId: fromPd }
  }
  const td = r.tongueData ?? r?.payload?.tongueData
  if (td && typeof td === 'object') {
    const fromTd = _positiveRecordId(td.recordId ?? td.record_id)
    if (fromTd != null) return { recordId: fromTd }
  }
  return null
}

const jointRequirementContext = computed(() => getJointRequirementQuery())

async function loadUserRequirements() {
  const uid = localStorage.getItem('mask_user_id') || 'admin'
  const q = getJointRequirementQuery()
  if (!q) {
    userRequirementEntries.value = []
    return
  }
  try {
    const res = await fetchJointUserRequirements({
      userId: uid,
      recordId: q.recordId,
    })
    const raw = Array.isArray(res?.entries) ? res.entries : []
    userRequirementEntries.value = raw.map((e) => {
      const atRaw = e?.at
      const atDisplay = atRaw ? formatDateTimeCn(atRaw) : ''
      return { ...e, atDisplay: atDisplay || String(atRaw || '') }
    })
  } catch {
    userRequirementEntries.value = []
  }
}

async function onSubmitUserRequirement() {
  const text = detailedUserRequirement.value.trim()
  if (!text) return
  const q = getJointRequirementQuery()
  if (!q) {
    systemPanelOpen.value = true
    systemMessages.value = [
      ...systemMessages.value,
      {
        text: '[系统] 未关联到体态/舌苔分析记录，无法保存需求。请从数据采集完成分析后再试。',
        color: '#f59e0b',
      },
    ]
    return
  }
  requirementSubmitting.value = true
  try {
    const uid = localStorage.getItem('mask_user_id') || 'admin'
    const body = { userId: uid, text, recordId: q.recordId }
    const res = await appendJointUserRequirement(body)
    if (!res?.success) throw new Error(res?.message || '保存失败')
    const raw = Array.isArray(res?.entries) ? res.entries : []
    userRequirementEntries.value = raw.map((e) => {
      const atRaw = e?.at
      const atDisplay = atRaw ? formatDateTimeCn(atRaw) : ''
      return { ...e, atDisplay: atDisplay || String(atRaw || '') }
    })
    detailedUserRequirement.value = ''
    await syncSystemMessages()
  } catch (e) {
    systemPanelOpen.value = true
    systemMessages.value = [
      ...systemMessages.value,
      { text: `[系统] 需求提交失败：${e?.message || e}`, color: '#ef4444' },
    ]
  } finally {
    requirementSubmitting.value = false
  }
}

async function onDeleteUserRequirement(seq) {
  const q = getJointRequirementQuery()
  if (!q?.recordId || seq == null) return
  const n = Number(seq)
  if (!Number.isFinite(n) || n <= 0) return
  requirementDeletingSeq.value = n
  try {
    const uid = localStorage.getItem('mask_user_id') || 'admin'
    const res = await deleteJointUserRequirement({
      userId: uid,
      recordId: q.recordId,
      seq: n,
    })
    if (!res?.success) throw new Error(res?.message || '删除失败')
    const raw = Array.isArray(res?.entries) ? res.entries : []
    userRequirementEntries.value = raw.map((e) => {
      const atRaw = e?.at
      const atDisplay = atRaw ? formatDateTimeCn(atRaw) : ''
      return { ...e, atDisplay: atDisplay || String(atRaw || '') }
    })
    await syncSystemMessages()
  } catch (e) {
    systemPanelOpen.value = true
    systemMessages.value = [
      ...systemMessages.value,
      { text: `[系统] 删除需求失败：${e?.message || e}`, color: '#ef4444' },
    ]
  } finally {
    requirementDeletingSeq.value = null
  }
}

function setActiveFlowCard(next) {
  activeFlowCard.value = next
}

/** 联合报告已成功落库后：清空采集页 pending 与 IDB，避免返回上传页仍显示旧体态/舌苔分析；清 IDB 前为 PDF 暂存舌苔 object URL */
async function clearCollectorAfterJointSuccess(uid) {
  clearPendingPosture()
  clearPendingTongue()
  try {
    const tongueFile = await getCollectorImage(uid, 'tongue')
    if (tongueFile) {
      if (tongueImageUrlForPdf.value && tongueImageIsObjectUrl.value) {
        URL.revokeObjectURL(tongueImageUrlForPdf.value)
      }
      tongueImageUrlForPdf.value = URL.createObjectURL(tongueFile)
      tongueImageIsObjectUrl.value = true
    }
  } catch {
    /* ignore */
  }
  await clearCollectorImages(uid)
}

async function onRunJointAnalysis() {
  if (!report.value || report.value.isGenerating || detailLoading.value) return
  const uid = localStorage.getItem('mask_user_id') || 'admin'
  const payload = {
    userId: uid,
    analysisMode: 'normal',
    postureReport: report.value.postureReport || '',
    tongueReport: report.value.tongueReport || '',
    postureAt: report.value.postureAt || report.value.createdAt || null,
    tongueAt: report.value.tongueAt || report.value.createdAt || null,
    postureData: report.value.postureData || null,
    tongueData: report.value.tongueData || report.value?.payload?.tongueData || null,
    tcmTenQuestions: report.value.tcmTenQuestions || null,
  }
  if (!payload.postureReport || !payload.tongueReport) {
    const next = {
      ...(report.value || {}),
      isGenerating: false,
      generationError: '请先完成体态与舌苔分析，再执行常规分析。',
    }
    saveLatestJointReport(next)
    hydrateReport(next)
    return
  }

  const pending = {
    ...(report.value || {}),
    isGenerating: true,
    generationError: '',
    report: '',
    summary: '',
  }
  saveLatestJointReport(pending)
  hydrateReport(pending)
  try {
    const res = await generateJointReport(payload)
    if (!res?.success) throw new Error(res?.message || '常规分析失败')
    const snaps = await fetchRecordSnapshots({ userId: uid, recordId: res.recordId })
    const next = {
      ...(report.value || {}),
      id: res.recordId,
      reportSerial: res.reportSerial ?? report.value?.reportSerial ?? null,
      createdAt: res.createdAt || new Date().toISOString(),
      type: 'joint',
      analysisType: 'joint',
      analysisMode: 'normal',
      mockAi: Boolean(res.mockAi),
      mockSupplementalRequirement: null,
      isGenerating: false,
      generationError: '',
      sourcePostureRecordId:
        res.sourcePostureRecordId ||
        report.value?.sourcePostureRecordId ||
        payload?.postureData?.recordId ||
        payload?.postureData?.record_id ||
        null,
      sourceTongueRecordId:
        res.sourceTongueRecordId ||
        report.value?.sourceTongueRecordId ||
        payload?.tongueData?.recordId ||
        payload?.tongueData?.record_id ||
        null,
      postureReport: res.postureReport || payload.postureReport,
      tongueReport: res.tongueReport || payload.tongueReport,
      report: res.jointReport || '',
      summary: res.jointReport || '',
      postureData: payload.postureData || null,
      payload: res,
      basicProfile: snaps.basicProfile || report.value?.basicProfile || null,
      tcmTenQuestions: snaps.tcmTenQuestions || payload.tcmTenQuestions || report.value?.tcmTenQuestions || null,
    }
    saveLatestJointReport(next)
    hydrateReport(next)
    // 报告已成功落库：清理数据收集页缓存，避免下次复用旧舌苔/体态导致“旧需求”串入
    await clearCollectorAfterJointSuccess(uid)
  } catch (e) {
    const failed = {
      ...(report.value || {}),
      isGenerating: false,
      generationError: e?.message || '常规分析失败，请稍后重试。',
      report: '',
      summary: '',
    }
    saveLatestJointReport(failed)
    hydrateReport(failed)
  }
}

async function onTestJointAgent() {
  if (!report.value || report.value.isGenerating || detailLoading.value) return
  const uid = localStorage.getItem('mask_user_id') || 'admin'
  let sampleId = String(report.value?.testSampleId || '').trim()
  if (!sampleId) {
    try {
      sampleId = await pickRandomTestModSampleId()
    } catch (e) {
      const failed = {
        ...(report.value || {}),
        isGenerating: false,
        generationError: e?.message || '无法获取测试样本列表，请检查 4_test_mod。',
      }
      saveLatestJointReport(failed)
      hydrateReport(failed)
      return
    }
  }
  const pending = {
    ...(report.value || {}),
    isGenerating: true,
    generationError: '',
  }
  saveLatestJointReport(pending)
  hydrateReport(pending)
  try {
    const res = await runJointAgentFromSample({
      userId: uid,
      sampleId,
      fakeAgent: true,
      analysisMode: 'normal',
    })
    const next = {
      ...(report.value || {}),
      id: res.recordId,
      reportSerial: res.reportSerial ?? report.value?.reportSerial ?? null,
      createdAt: res.createdAt || new Date().toISOString(),
      type: 'joint',
      analysisType: 'joint',
      analysisMode: 'normal',
      isGenerating: false,
      generationError: '',
      postureReport: res.postureReport || report.value?.postureReport || '',
      tongueReport: res.tongueReport || report.value?.tongueReport || '',
      report: res.jointReport || '',
      summary: res.jointReport || '',
      sourcePostureRecordId:
        res.sourcePostureRecordId ||
        report.value?.sourcePostureRecordId ||
        null,
      sourceTongueRecordId:
        res.sourceTongueRecordId ||
        report.value?.sourceTongueRecordId ||
        null,
      testSampleId: sampleId,
    }
    saveLatestJointReport(next)
    hydrateReport(next)
    // 与常规分析一致：测试样本联合报告落库后同样清理 pending/IDB，避免返回上传页仍显示旧分析
    await clearCollectorAfterJointSuccess(uid)
  } catch (e) {
    const failed = {
      ...(report.value || {}),
      isGenerating: false,
      generationError: e?.message || '测试智能体失败，请稍后重试。',
    }
    saveLatestJointReport(failed)
    hydrateReport(failed)
  }
}

watch(
  () => [
    report.value?.id,
    report.value?.sourcePostureRecordId,
    report.value?.sourceTongueRecordId,
    report.value?.postureData?.recordId,
    report.value?.postureData?.record_id,
  ],
  () => {
    void loadUserRequirements()
  },
)

async function onRunDetailedAnalysis() {
  if (!report.value) return
  const recordId = Number(report.value.id)
  if (!Number.isFinite(recordId) || recordId <= 0) {
    systemPanelOpen.value = true
    systemMessages.value = [...systemMessages.value, { text: '[系统] 当前报告尚未落库，暂不可执行专家深度分析', color: '#f59e0b' }]
    return
  }
  detailLoading.value = true
  detailedFlowUnlocked.value = true
  try {
    const uid = localStorage.getItem('mask_user_id') || 'admin'
    await loadUserRequirements()
    const res = await runJointDetailedAnalysis({
      userId: uid,
      analysisMode: 'expert',
      recordId,
      maxRounds: 3,
      userRequirement: detailedUserRequirement.value.trim(),
    })
    if (!res?.success) {
      throw new Error(res?.message || '专家深度分析失败')
    }
    const next = {
      ...(report.value || {}),
      id: res.recordId,
      reportSerial: res.reportSerial ?? report.value?.reportSerial ?? null,
      createdAt: res.createdAt || new Date().toISOString(),
      type: 'joint_detailed',
      analysisType: 'joint_detailed',
      analysisMode: 'expert',
      mockAi: Boolean(res.mockAi),
      mockSupplementalRequirement: res.mockSupplementalRequirement || null,
      postureReport: res.postureReport || report.value.postureReport || '',
      tongueReport: res.tongueReport || report.value.tongueReport || '',
      report: res.jointReport || report.value.report || '',
      summary: res.jointReport || report.value.summary || '',
    }
    saveLatestJointReport(next)
    hydrateReport(next)
    systemPanelOpen.value = true
    activeFlowCard.value = 'full'
  } catch (e) {
    systemPanelOpen.value = true
    systemMessages.value = [
      ...systemMessages.value,
      { text: `[系统] 专家深度分析失败：${e?.message || e}`, color: '#ef4444' },
    ]
    activeFlowCard.value = 'joint'
  } finally {
    detailLoading.value = false
  }
}

async function syncSystemMessages() {
  try {
    const uid = localStorage.getItem('mask_user_id') || 'admin'
    const res = await fetchJointReportStatus(uid)
    const lines = Array.isArray(res?.lines) ? res.lines : []
    if (lines.length) {
      systemMessages.value = lines.map((line) => {
        if (typeof line === 'string') return { text: line, color: '' }
        return { text: String(line?.text || ''), color: String(line?.color || '') }
      })
    }
  } catch {
    // 忽略状态拉取失败，避免影响报告页主流程
  }
}

function goPrevRightCard() {
  let i = RIGHT_CARD_ORDER.indexOf(activeRightCard.value)
  if (i < 0) i = 0
  activeRightCard.value =
    RIGHT_CARD_ORDER[(i - 1 + RIGHT_CARD_ORDER.length) % RIGHT_CARD_ORDER.length]
}

function goNextRightCard() {
  let i = RIGHT_CARD_ORDER.indexOf(activeRightCard.value)
  if (i < 0) i = 0
  activeRightCard.value = RIGHT_CARD_ORDER[(i + 1) % RIGHT_CARD_ORDER.length]
}

function clampPct(x) {
  const n = Number(x)
  if (!Number.isFinite(n)) return 0
  return Math.min(100, Math.max(0, n))
}

function updateCompareFromPointer(e) {
  const el = e.currentTarget
  if (!el) return
  const rect = el.getBoundingClientRect()
  const y = e.clientY - rect.top
  const pct = (y / Math.max(1, rect.height)) * 100
  compareRevealPct.value = clampPct(pct)
}

function onComparePointerDown(e) {
  if (!e || !e.currentTarget) return
  compareDragging.value = true
  updateCompareFromPointer(e)
}

function onComparePointerUp() {
  compareDragging.value = false
}

function onGlobalPointerMove(e) {
  if (!compareDragging.value) return
  // 这里没有 currentTarget，直接找 .human-compare 的 DOM
  const el = document.querySelector('.human-compare')
  if (!el) return
  updateCompareFromPointer({ clientY: e.clientY, currentTarget: el })
}

function onGlobalPointerUp() {
  compareDragging.value = false
}

onMounted(async () => {
  window.addEventListener('pointermove', onGlobalPointerMove, { passive: true })
  window.addEventListener('pointerup', onGlobalPointerUp, { passive: true })
  window.addEventListener('pointercancel', onGlobalPointerUp, { passive: true })
  analyzingDotsTimer.value = window.setInterval(() => {
    analyzingDots.value = analyzingDots.value === '...' ? '.' : `${analyzingDots.value}.`
  }, 450)

  await syncSystemMessages()
  statusPollingTimer.value = window.setInterval(() => {
    if (systemPanelOpen.value || isAgentAnalyzing.value || detailLoading.value || report.value?.isGenerating) {
      void syncSystemMessages()
    }
  }, 1200)

  const latest = getLatestJointReport()
  hydrateReport(latest)
  void loadUserRequirements()
  console.debug('[JointReport] latest joint report (from localStorage)', {
    id: latest?.id,
    createdAt: latest?.createdAt,
    analysisType: latest?.analysisType,
    sourcePostureRecordId: latest?.sourcePostureRecordId || null,
    sourceTongueRecordId: latest?.sourceTongueRecordId || null,
    payloadKeys: latest?.payload ? Object.keys(latest.payload) : null,
  })

  const uid = localStorage.getItem('mask_user_id') || 'admin'
  const sourcePostureRecordId =
    latest?.sourcePostureRecordId ||
    latest?.payload?.sourcePostureRecordId ||
    latest?.payload?.meta?.sourcePostureRecordId ||
    latest?.payload?.meta_json?.sourcePostureRecordId ||
    null
  console.debug('[JointReport] resolve sourcePostureRecordId', {
    uid,
    resolved: sourcePostureRecordId,
    fromLatest: latest?.sourcePostureRecordId || null,
    fromPayload: latest?.payload?.sourcePostureRecordId || null,
    fromPayloadMeta: latest?.payload?.meta?.sourcePostureRecordId || null,
    fromPayloadMetaJson: latest?.payload?.meta_json?.sourcePostureRecordId || null,
  })

  const setHumanImage = (nextUrl, isObjectUrl) => {
    if (humanImageUrl.value && humanImageIsObjectUrl.value) {
      URL.revokeObjectURL(humanImageUrl.value)
    }
    humanImageUrl.value = nextUrl || ''
    humanImageIsObjectUrl.value = Boolean(isObjectUrl)
  }

  const setHumanBaseImage = (nextUrl, isObjectUrl) => {
    if (humanBaseImageUrl.value && humanBaseImageIsObjectUrl.value) {
      URL.revokeObjectURL(humanBaseImageUrl.value)
    }
    humanBaseImageUrl.value = nextUrl || ''
    humanBaseImageIsObjectUrl.value = Boolean(isObjectUrl)
  }

  const tryLoadFromIdb = async () => {
    console.debug('[JointReport] tryLoadFromIdb start')
    const idbUrl = await getPostureResultDisplay(uid)
    console.debug('[JointReport] tryLoadFromIdb result', {
      hasUrl: Boolean(idbUrl),
      urlPrefix: typeof idbUrl === 'string' ? idbUrl.slice(0, 24) : null,
    })
    if (idbUrl) {
      setHumanImage(idbUrl, false)
      return true
    }
    return false
  }

  reportPollingTimer.value = window.setInterval(() => {
    const next = getLatestJointReport()
    if (!next) return
    if (JSON.stringify(next) !== JSON.stringify(report.value)) {
      hydrateReport(next)
    }
  }, 1200)

  if (!sourcePostureRecordId) {
    // 兜底：如果综合报告没有关联体态记录ID，则尝试用“数据收集页”缓存的结果图（同一会话内常见）
    humanImageLoading.value = true
    humanImageError.value = ''
    try {
      const ok = await tryLoadFromIdb()
      if (!ok) {
        humanImageError.value = '暂无人体图像（未找到体态记录关联，且本机会话缓存也为空）'
      }
    } catch (e) {
      humanImageError.value = e?.message || '人体图像加载失败'
    } finally {
      humanImageLoading.value = false
    }
    void preloadTongueImageForPdf(uid, latest)
    return
  }

  humanImageLoading.value = true
  humanImageError.value = ''
  console.debug('[JointReport] fetchProcessedPostureImage start', { sourcePostureRecordId, uid })
  Promise.allSettled([
    fetchProcessedPostureImage(sourcePostureRecordId, uid),
    fetchMosaicPostureImage(sourcePostureRecordId, uid),
  ])
    .then((results) => {
      const processed = results[0]
      const base = results[1]
      if (processed.status === 'fulfilled') {
        const blob = processed.value
        console.debug('[JointReport] processed image ok', { type: blob?.type, size: blob?.size })
        setHumanImage(URL.createObjectURL(blob), true)
      }
      if (base.status === 'fulfilled') {
        const blob = base.value
        console.debug('[JointReport] mosaic base image ok', { type: blob?.type, size: blob?.size })
        setHumanBaseImage(URL.createObjectURL(blob), true)
      }
      if (processed.status === 'rejected') {
        throw processed.reason
      }
    })
    .catch(async (e) => {
      console.debug('[JointReport] fetchProcessedPostureImage failed', { message: e?.message })
      // 后端图片接口不可用/路径丢失时，再兜底到 IDB（仅能兜底一张）
      try {
        const ok = await tryLoadFromIdb()
        if (!ok) {
          humanImageError.value = e?.message || '人体图像加载失败'
        }
      } catch (e2) {
        humanImageError.value = e2?.message || e?.message || '人体图像加载失败'
      }
    })
    .finally(() => {
      humanImageLoading.value = false
    })

  void preloadTongueImageForPdf(uid, latest)
})

onUnmounted(() => {
  window.removeEventListener('pointermove', onGlobalPointerMove)
  window.removeEventListener('pointerup', onGlobalPointerUp)
  window.removeEventListener('pointercancel', onGlobalPointerUp)
  if (analyzingDotsTimer.value) {
    window.clearInterval(analyzingDotsTimer.value)
    analyzingDotsTimer.value = null
  }
  if (statusPollingTimer.value) {
    window.clearInterval(statusPollingTimer.value)
    statusPollingTimer.value = null
  }
  if (reportPollingTimer.value) {
    window.clearInterval(reportPollingTimer.value)
    reportPollingTimer.value = null
  }
  if (humanImageUrl.value && humanImageIsObjectUrl.value) {
    URL.revokeObjectURL(humanImageUrl.value)
  }
  if (humanBaseImageUrl.value && humanBaseImageIsObjectUrl.value) {
    URL.revokeObjectURL(humanBaseImageUrl.value)
  }
  if (tongueImageUrlForPdf.value && tongueImageIsObjectUrl.value) {
    URL.revokeObjectURL(tongueImageUrlForPdf.value)
  }
  clearLatestJointReport()
  report.value = null
  postureRows.value = []
  showMetricDialog.value = false
  activeTopCard.value = 'profile'
  activeRightCard.value = 'posture'
  humanImageUrl.value = ''
  humanImageLoading.value = false
  humanImageError.value = ''
  humanImageIsObjectUrl.value = false
  humanBaseImageUrl.value = ''
  humanBaseImageIsObjectUrl.value = false
  tongueImageUrlForPdf.value = ''
  tongueImageIsObjectUrl.value = false
  compareRevealPct.value = 62
  systemPanelOpen.value = false
  detailLoading.value = false
  detailedFlowUnlocked.value = false
  activeFlowCard.value = 'joint'
  analyzingDots.value = '.'
  systemMessages.value = initialSystemMessages()
  const uid = localStorage.getItem('mask_user_id') || 'admin'
  void clearJointReportStatus(uid)
})
</script>

<template>
  <section class="page-wrap">
    <TopNav active="joint-report" />

    <main class="content">
      <section v-if="report" class="card report-shell">
        <div class="top-actions">
          <button
            type="button"
            class="export-btn secondary"
            :disabled="detailLoading || report.isGenerating"
            @click="onRunJointAnalysis"
          >
            {{ report.isGenerating ? '常规分析中...' : '常规分析' }}
          </button>
          <button type="button" class="export-btn secondary" :disabled="detailLoading || report.isGenerating" @click="onRunDetailedAnalysis">
            {{ detailLoading ? '专家深度分析中...' : '专家深度分析' }}
          </button>
          <button type="button" class="export-btn" @click="exportPdf">导出 PDF</button>
          <button
            type="button"
            class="export-btn subtle"
            :disabled="detailLoading || report.isGenerating"
            @click="onTestJointAgent"
          >
            测试智能体
          </button>
        </div>
        <h2 class="page-title">{{ reportPageTitle }}</h2>
        <p v-if="reportSerialLabel" class="report-serial">{{ reportSerialLabel }}</p>
        <p class="muted">生成时间（北京时间）：{{ createdAtDisplay }}</p>
        <p v-if="report.isGenerating" class="muted">AI 正在生成分析与建议，完成后会自动展示。</p>
        <p v-else-if="report.generationError" class="warn">{{ report.generationError }}</p>

        <div class="layer-one">
          <section class="card-block">
            <div class="card-titlebar">
              <h3 class="card-title">用户数据</h3>
            </div>
            <article class="sub-card compact-card switch-card">
              <header class="switch-head">
              <div class="switch-tabs">
                <button
                  type="button"
                  class="switch-tab"
                  :class="{ active: activeTopCard === 'profile' }"
                  @click="setActiveTopCard('profile')"
                >
                  基本信息
                </button>
                <button
                  type="button"
                  class="switch-tab"
                  :class="{ active: activeTopCard === 'tcm' }"
                  @click="setActiveTopCard('tcm')"
                >
                  中医十问
                </button>
                <button
                  type="button"
                  class="switch-tab"
                  :class="{ active: activeTopCard === 'metrics' }"
                  @click="setActiveTopCard('metrics')"
                >
                  体态与体型数据
                </button>
              </div>

              <div class="switch-arrows">
                <button type="button" class="arrow-btn" aria-label="上一项" @click="goPrevTopCard">
                  ‹
                </button>
                <button type="button" class="arrow-btn" aria-label="下一项" @click="goNextTopCard">
                  ›
                </button>
              </div>
              </header>

              <section v-if="activeTopCard === 'profile'" class="switch-body">
              <p v-if="profileFallbackHint" class="hint">
                本报告未附带档案快照，下列为当前本机档案；若从历史进入且档案已改，可能与生成时不一致。
              </p>
              <dl class="kv-list">
                <div v-for="row in basicProfileRows" :key="row.k" class="kv-row">
                  <dt>{{ row.k }}</dt>
                  <dd>{{ row.v }}</dd>
                </div>
              </dl>
              </section>

              <section v-else-if="activeTopCard === 'tcm'" class="switch-body switch-tcm">
              <p v-if="tcmFallbackHint" class="hint">
                本记录未附带十问快照，下列为当前本机档案中的十问（若有）。
              </p>
              <div class="tcm-scroll">
                <dl class="kv-list tcm-list">
                  <div v-for="(row, idx) in tcmRows" :key="idx" class="kv-row">
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.text }}</dd>
                  </div>
                </dl>
              </div>
              </section>

              <section v-else class="switch-body metric-panel">
              <div class="metric-head">
                <p class="metric-title">体态与体型数据</p>
                <button type="button" class="help-btn" @click="openMetricGuide">?</button>
              </div>
              <div class="metric-wrap">
                <table class="metric-table">
                  <thead>
                    <tr>
                      <th>类别</th>
                      <th>指标</th>
                      <th>值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in postureRows" :key="`${item.group}-${item.key}`">
                      <td>{{ item.group }}</td>
                      <td>{{ item.key }}</td>
                      <td>{{ item.value }}</td>
                    </tr>
                    <tr v-if="!postureRows.length">
                      <td colspan="3">暂无体态体型数据</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              </section>
            </article>
          </section>

          <section class="card-block">
            <div class="card-titlebar">
              <h3 class="card-title">人体图像</h3>
            </div>
            <article class="sub-card compact-card mid-empty-card">
              <div
                v-if="humanImageUrl && humanBaseImageUrl"
                class="human-compare"
                aria-label="处理前后人体图像对比"
                @pointerdown.prevent.stop="onComparePointerDown"
                @pointerup="onComparePointerUp"
                @pointercancel="onComparePointerUp"
              >
                <img
                  class="human-image human-image--base"
                  :src="humanBaseImageUrl"
                  alt="处理前（仅马赛克）人体图像"
                  draggable="false"
                />
                <img
                  class="human-image human-image--top"
                  :src="humanImageUrl"
                  alt="处理后（关键点/Mask）人体图像"
                  :style="{ clipPath: `inset(0 0 ${100 - compareRevealPct}% 0)` }"
                  draggable="false"
                />
                <div class="compare-handle" :style="{ top: `${compareRevealPct}%` }">
                  <span class="compare-handle__line" />
                  <span class="compare-handle__pill">拖动</span>
                </div>
              </div>
              <div v-else-if="humanImageUrl" class="human-image-wrap">
                <img class="human-image" :src="humanImageUrl" alt="人体图像" />
              </div>
              <div v-else class="empty-body">
                <p v-if="humanImageLoading" class="muted">正在加载人体图像...</p>
                <p v-else-if="humanImageError" class="warn">{{ humanImageError }}</p>
                <p v-else class="muted">暂无人体图像</p>
              </div>
            </article>
          </section>

          <section class="card-block">
            <div class="card-titlebar">
              <h3 class="card-title">单项分析报告</h3>
            </div>
            <article class="sub-card compact-card right-switch-card">
              <header class="switch-head">
              <div class="switch-tabs">
                <button
                  type="button"
                  class="switch-tab"
                  :class="{ active: activeRightCard === 'posture' }"
                  @click="setActiveRightCard('posture')"
                >
                  体态体型报告
                </button>
                <button
                  type="button"
                  class="switch-tab"
                  :class="{ active: activeRightCard === 'tongue' }"
                  @click="setActiveRightCard('tongue')"
                >
                  舌苔报告
                </button>
                <button
                  type="button"
                  class="switch-tab"
                  :class="{ active: activeRightCard === 'requirements' }"
                  @click="setActiveRightCard('requirements')"
                >
                  用户补充情况&amp;需求
                </button>
              </div>

              <div class="switch-arrows">
                <button type="button" class="arrow-btn" aria-label="上一项" @click="goPrevRightCard">
                  ‹
                </button>
                <button type="button" class="arrow-btn" aria-label="下一项" @click="goNextRightCard">
                  ›
                </button>
              </div>
              </header>

              <section v-if="activeRightCard === 'posture'" class="switch-body">
                <div v-if="report.postureReport" class="structured-wrap">
                  <section
                    v-for="(sec, sIdx) in structuredPostureReport.sections"
                    :key="`psec-${sIdx}-${sec.title || ''}`"
                    class="structured-sec"
                  >
                    <h4 v-if="sec.title" class="structured-title">{{ sec.title }}</h4>
                    <p v-if="sec.intro" class="structured-intro">{{ sec.intro }}</p>
                    <ul v-if="sec.items && sec.items.length" class="structured-list">
                      <li v-for="(it, iIdx) in sec.items" :key="`pit-${sIdx}-${iIdx}`" class="structured-item">
                        <strong v-if="it.title" class="structured-item-title">{{ it.title }}</strong>
                        <p class="structured-item-body">{{ it.body }}</p>
                        <ul v-if="it.children && it.children.length" class="structured-sublist">
                          <li v-for="(sub, j) in it.children" :key="`psub-${sIdx}-${iIdx}-${j}`" class="structured-subitem">
                            <strong v-if="sub.title" class="structured-subtitle">{{ sub.title }}</strong>
                            <p class="structured-subbody">{{ sub.body }}</p>
                          </li>
                        </ul>
                      </li>
                    </ul>
                  </section>
                </div>
                <p v-else class="text-block">暂无体态报告</p>
              </section>

              <section v-else-if="activeRightCard === 'tongue'" class="switch-body">
                <div v-if="report.tongueReport" class="structured-wrap">
                  <section
                    v-for="(sec, sIdx) in structuredTongueReport.sections"
                    :key="`tsec-${sIdx}-${sec.title || ''}`"
                    class="structured-sec"
                  >
                    <h4 v-if="sec.title" class="structured-title">{{ sec.title }}</h4>
                    <p v-if="sec.intro" class="structured-intro">{{ sec.intro }}</p>
                    <ul v-if="sec.items && sec.items.length" class="structured-list">
                      <li v-for="(it, iIdx) in sec.items" :key="`tit-${sIdx}-${iIdx}`" class="structured-item">
                        <strong v-if="it.title" class="structured-item-title">{{ it.title }}</strong>
                        <p class="structured-item-body">{{ it.body }}</p>
                        <ul v-if="it.children && it.children.length" class="structured-sublist">
                          <li v-for="(sub, j) in it.children" :key="`tsub-${sIdx}-${iIdx}-${j}`" class="structured-subitem">
                            <strong v-if="sub.title" class="structured-subtitle">{{ sub.title }}</strong>
                            <p class="structured-subbody">{{ sub.body }}</p>
                          </li>
                        </ul>
                      </li>
                    </ul>
                  </section>
                </div>
                <p v-else class="text-block">暂无舌苔报告</p>
              </section>

              <section v-else class="switch-body switch-body-user-req">
                <p v-if="!jointRequirementContext" class="muted text-block">
                  当前会话未关联到体态/舌苔分析记录，无法读写需求。请从数据采集页完成分析并进入本页后再试。
                </p>
                <div v-else-if="userRequirementEntries.length" class="ureq-mini-cards">
                  <article
                    v-for="(e, idx) in userRequirementEntries"
                    :key="`${e.seq ?? idx}-${e.at ?? ''}`"
                    class="ureq-mini-card"
                  >
                    <header class="ureq-mini-card-head">
                      <span class="ureq-mini-seq">#{{ e.seq ?? idx + 1 }}</span>
                      <span v-if="e.atDisplay" class="ureq-mini-at">{{ e.atDisplay }}</span>
                      <button
                        type="button"
                        class="ureq-mini-del"
                        :disabled="
                          requirementDeletingSeq === Number(e.seq ?? idx + 1) ||
                          requirementSubmitting
                        "
                        @click="onDeleteUserRequirement(e.seq ?? idx + 1)"
                      >
                        {{ requirementDeletingSeq === Number(e.seq ?? idx + 1) ? '…' : '删除' }}
                      </button>
                    </header>
                    <p class="ureq-mini-text">{{ e.text || '' }}</p>
                  </article>
                </div>
                <p v-else class="muted text-block">暂无已保存的用户需求</p>
              </section>
            </article>
          </section>
        </div>

        <div class="layer-two" />

        <section class="card-block wide-block">
          <div class="card-titlebar">
            <h3 class="card-title">分析与建议</h3>
          </div>
          <article class="final-card layer-three">
            <div v-if="report.report || report.summary" class="structured-wrap structured-wrap--final">
              <section
                v-for="(sec, sIdx) in structuredJointReport.sections"
                :key="`jsec-${sIdx}-${sec.title || ''}`"
                class="structured-sec"
              >
                <h4 v-if="sec.title" class="structured-title">{{ sec.title }}</h4>
                <p v-if="sec.intro" class="structured-intro">{{ sec.intro }}</p>
                <ul v-if="sec.items && sec.items.length" class="structured-list">
                  <li v-for="(it, iIdx) in sec.items" :key="`jit-${sIdx}-${iIdx}`" class="structured-item">
                    <strong v-if="it.title" class="structured-item-title">{{ it.title }}</strong>
                    <p class="structured-item-body">{{ it.body }}</p>
                    <ul v-if="it.children && it.children.length" class="structured-sublist">
                      <li v-for="(sub, j) in it.children" :key="`jsub-${sIdx}-${iIdx}-${j}`" class="structured-subitem">
                        <strong v-if="sub.title" class="structured-subtitle">{{ sub.title }}</strong>
                        <p class="structured-subbody">{{ sub.body }}</p>
                      </li>
                    </ul>
                  </li>
                </ul>
              </section>
            </div>
            <p v-else class="text-block">暂无分析与建议</p>
            <div v-if="showMockJointUserReq" class="mock-joint-user-req">
              <p class="mock-joint-user-req-title">本条关联的用户需求（模拟输出）</p>
              <ul class="mock-joint-user-req-list">
                <li v-for="(line, idx) in jointCardUserRequirementLines" :key="idx">{{ line }}</li>
              </ul>
            </div>
          </article>
        </section>

      </section>

      <section v-else class="card empty-shell">
        <h2 class="page-title">综合分析报告</h2>
        <p class="muted">当前没有可展示的综合分析报告（含常规分析与专家深度分析）。请先完成体态与舌苔数据采集，或从历史记录打开。</p>
      </section>

      <div v-if="showMetricDialog" class="help-mask" @click.self="closeMetricGuide">
        <article class="help-dialog">
          <header class="help-head">
            <h3>体态/体型指标说明</h3>
            <button type="button" class="help-close" @click="closeMetricGuide">关闭</button>
          </header>
          <table class="help-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>含义说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in metricDefs" :key="item.name">
                <td>{{ item.name }}</td>
                <td>{{ item.meaning }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>
    </main>

    <button
      type="button"
      class="system-float-btn"
      :aria-expanded="systemPanelOpen ? 'true' : 'false'"
      @click="toggleSystemPanel"
    >
      {{ systemFloatBtnText }}
    </button>

    <section v-if="systemPanelOpen" class="system-panel card" role="region" aria-label="系统输出台">
      <div class="flow-switch">
        <button
          type="button"
          class="flow-switch-btn"
          :class="{ active: activeFlowCard === 'joint' }"
          @click="setActiveFlowCard('joint')"
        >
          常规分析
        </button>
        <button
          type="button"
          class="flow-switch-btn"
          :class="{ active: activeFlowCard === 'full' }"
          @click="setActiveFlowCard('full')"
        >
          专家深度分析流程
        </button>
      </div>

      <div v-if="activeFlowCard === 'joint'" class="flow-wrap">
        <svg viewBox="0 0 520 220" class="flow-svg flow-svg--mini" aria-label="常规分析流程卡片">
          <defs>
            <marker id="arrowGreenMini" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#22c55e" />
            </marker>
            <marker id="arrowBlueMini" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#3b82f6" />
            </marker>
            <marker id="arrowGrayMini" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#94a3b8" />
            </marker>
          </defs>
          <line
            x1="210"
            y1="110"
            x2="310"
            y2="110"
            :class="
              flowState.miniJointActive
                ? 'flow-edge-mini active'
                : flowState.miniJointDone
                  ? 'flow-edge-mini done'
                  : 'flow-edge-mini idle'
            "
            :marker-end="
              flowState.miniJointActive
                ? 'url(#arrowBlueMini)'
                : flowState.miniJointDone
                  ? 'url(#arrowGreenMini)'
                  : 'url(#arrowGrayMini)'
            "
          />
          <rect x="40" y="56" width="170" height="108" :class="nodeClass(flowState.miniJointActive, flowState.miniJointDone)" />
          <text x="140" y="110" class="flow-text flow-text--mini">
            <tspan x="125" dy="-12">常规分析</tspan>
            <tspan x="125" dy="24">智能体</tspan>
          </text>
          <rect x="310" y="56" width="170" height="108" :class="nodeClass(false, flowState.miniJointDone)" />
          <text x="395" y="110" class="flow-text flow-text--mini">
            <tspan x="395" dy="-12">常规分析</tspan>
            <tspan x="395" dy="24">报告</tspan>
          </text>
        </svg>
      </div>

      <div v-else class="flow-wrap">
        <svg viewBox="0 0 980 460" class="flow-svg" aria-label="智能体流程图">
          <defs>
            <marker id="arrowGreen" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#22c55e" />
            </marker>
            <marker id="arrowBlue" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#3b82f6" />
            </marker>
            <marker id="arrowGray" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#94a3b8" />
            </marker>
          </defs>

          <line x1="210" y1="230" x2="300" y2="64" :class="edgeClass(flowState.postureActive, flowState.postureDone)" />
          <line x1="210" y1="230" x2="300" y2="404" :class="edgeClass(flowState.tongueActive, flowState.tongueDone)" />
          <line x1="210" y1="234" x2="420" y2="234" :class="edgeClass(flowState.jointActive, flowState.jointDone)" />

          <line x1="500" y1="64" x2="640" y2="64" :class="edgeClass(false, flowState.postureDone)" />
          <line x1="500" y1="404" x2="640" y2="404" :class="edgeClass(false, flowState.tongueDone)" />
          <line x1="740" y1="118" x2="620" y2="180" :class="edgeClass(false, flowState.postureDone)" />
          <line x1="740" y1="350" x2="620" y2="288" :class="edgeClass(false, flowState.tongueDone)" />
          <line x1="620" y1="234" x2="750" y2="234" :class="edgeClass(false, flowState.jointDone)" />

          <rect x="30" y="176" width="180" height="108" :class="nodeClass(false, true, true)" />
          <text x="120" y="233" class="flow-text">统筹智能体</text>

          <rect x="300" y="10" width="200" height="108" :class="nodeClass(flowState.postureActive, flowState.postureDone)" />
          <text x="400" y="65" class="flow-text">
            <tspan x="400" dy="-19">体态分析</tspan>
            <tspan x="400" dy="38">智能体</tspan>
          </text>

          <rect x="640" y="10" width="200" height="108" :class="nodeClass(false, flowState.postureDone)" />
          <text x="740" y="65" class="flow-text">
            <tspan x="740" dy="-19">体态分析</tspan>
            <tspan x="740" dy="38">报告</tspan>
          </text>

          <rect x="300" y="350" width="200" height="108" :class="nodeClass(flowState.tongueActive, flowState.tongueDone)" />
          <text x="400" y="407" class="flow-text">
            <tspan x="400" dy="-19">舌苔分析</tspan>
            <tspan x="400" dy="38">智能体</tspan>
          </text>

          <rect x="640" y="350" width="200" height="108" :class="nodeClass(false, flowState.tongueDone)" />
          <text x="740" y="407" class="flow-text">
            <tspan x="740" dy="-19">舌苔分析</tspan>
            <tspan x="740" dy="38">报告</tspan>
          </text>

          <rect x="420" y="180" width="200" height="108" :class="nodeClass(flowState.jointActive, flowState.jointDone)" />
          <text x="520" y="236" class="flow-text">
            <tspan x="520" dy="-19">专家深度分析</tspan>
            <tspan x="520" dy="38">智能体</tspan>
          </text>

          <rect x="750" y="180" width="200" height="108" :class="nodeClass(false, flowState.jointDone)" />
          <text x="850" y="236" class="flow-text">
            <tspan x="850" dy="-19">专家深度分析</tspan>
            <tspan x="850" dy="38">报告</tspan>
          </text>
        </svg>
      </div>
      <div class="system-panel-body">
        <p
          v-for="line in jointConsoleLines"
          :key="line.key"
          class="system-line"
          :style="{ color: line.color || '#e2e8f0' }"
        >
          {{ line.text }}
        </p>
      </div>
      <div class="user-requirement-wrap">
        <label class="user-requirement-label" for="joint-detail-requirement">
          请输入补充情况&amp;个性化需求
        </label>
        <div class="user-requirement-row">
          <textarea
            id="joint-detail-requirement"
            v-model="detailedUserRequirement"
            class="user-requirement-input"
            rows="2"
            maxlength="1200"
            placeholder="写下您需要补充的特殊状况、健康信息、个性化分析与建议需求，例如【我有先天性疾病】【我最近来月经了】【我希望侧重锻炼方面的建议】"
          />
          <div class="user-req-buttons">
            <button
              type="button"
              class="user-req-submit-btn"
              :disabled="requirementSubmitting || !jointRequirementContext"
              title="提交本条需求到数据库"
              @click="onSubmitUserRequirement"
            >
              {{ requirementSubmitting ? '…' : '提交' }}
            </button>
          </div>
        </div>
        <p v-if="!jointRequirementContext" class="user-req-warn">
          未关联到体态/舌苔分析记录时无法提交。常规分析落库后，需求会随报告一并保存在该条联合记录上。
        </p>
      </div>
    </section>
  </section>
</template>

<style scoped>
.page-wrap { min-height: 100vh; }
.content { padding: 16px; }

/* 覆盖全局 .card 的 max-width: 980px，提升页面左右利用率 */
.report-shell,
.empty-shell {
  width: min(1680px, calc(100% - 32px));
  max-width: none;
  margin: 16px auto;
}

.report-shell {
  padding: 18px;
}
.top-actions {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.empty-shell {
  padding: 18px;
}
.report-shell h2, .empty-shell h2 { margin-top: 0; color: #1e293b; }
.page-title {
  text-align: center;
  margin-bottom: 6px;
  font-size: 34px;
  line-height: 1.15;
  font-weight: 900;
}
.report-serial {
  margin: 4px 0 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f766e;
}
.muted { color: #64748b; font-size: 14px; }
.warn { color: #b91c1c; font-size: 14px; }
.hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

.card-titlebar {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px;
  border: 1px solid #dbe4f1;
  border-radius: 10px;
  background: rgba(239, 246, 255, 0.75);
  flex-shrink: 0;
  width: fit-content;
  max-width: 100%;
}

.card-title {
  margin: 0;
  font-size: 18px;
  font-weight: 900;
  color: #0f172a;
}

.card-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.wide-block {
  margin-top: 8px;
}

/* 底部大卡片块：与上方卡片保持一致间距 */
.wide-block {
  gap: 6px;
}

.layer-one {
  display: grid;
  /* 左右两张卡同宽，中间卡占位更窄 */
  /* 中间与右侧交换宽度：右侧更宽 */
  grid-template-columns: 0.8fr 0.7fr 1.5fr;
  gap: 14px;
  margin-top: 12px;
}
.compact-card {
  padding: 10px;
  /* 固定高度：切换内容不会改变卡片高度 */
  height: 360px;
}
.compact-card h3 { margin-bottom: 6px; font-size: 16px; }

.profile-card .kv-list,
.tcm-card .kv-list {
  margin: 0;
}

.tcm-card {
  display: flex;
  flex-direction: column;
}
.kv-row {
  display: grid;
  grid-template-columns: minmax(100px, 38%) 1fr;
  gap: 8px 12px;
  padding: 6px 0;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
}
.kv-row:last-child { border-bottom: none; }
.kv-row dt {
  margin: 0;
  color: #475569;
  font-weight: 600;
}
.kv-row dd {
  margin: 0;
  color: #1e293b;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.tcm-scroll {
  max-height: none;
  overflow-y: auto;
  margin-top: 4px;
  flex: 1;
}

.layer-two { display: none; }
.sub-card, .final-card { border: 1px solid #dbe4f1; border-radius: 10px; padding: 12px; background: #f8fafc; min-width: 0; overflow: hidden; }
.sub-card h3, .final-card h3 { margin: 0 0 8px; color: #1e293b; }
.layer-three { margin-top: 12px; }
.text-block { margin: 0; line-height: 1.75; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; }
.mock-joint-user-req { margin-top: 14px; padding-top: 12px; border-top: 1px solid #e2e8f0; }
.mock-joint-user-req-title { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: #64748b; }
.mock-joint-user-req-list { margin: 0; padding-left: 1.25rem; color: #334155; font-size: 14px; line-height: 1.65; }
.mock-joint-user-req-list li { margin: 4px 0; }

.structured-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.structured-wrap--final {
  margin-top: 2px;
}

.structured-sec {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  padding: 10px 10px 8px;
}

.structured-title {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: 0.01em;
}

.structured-intro {
  margin: 0;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  color: #334155;
  font-size: 15.5px;
}

.structured-list {
  margin: 8px 0 0;
  padding-left: 1.15rem;
  color: #334155;
}

.structured-item {
  margin: 8px 0;
}

.structured-item-title {
  display: inline-block;
  margin-bottom: 4px;
  color: #1e293b;
  font-size: 17px;
  font-weight: 800;
}

.structured-item-body {
  margin: 0;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 15.5px;
  color: #334155;
}

.structured-sublist {
  margin-top: 10px;
  padding-left: 1.15rem;
  border-left: 3px solid rgba(37, 99, 235, 0.22);
}

.structured-subitem {
  margin: 8px 0;
}

.structured-subtitle {
  display: inline-block;
  margin-bottom: 0;
  font-size: 15.5px;
  font-weight: 800;
  color: #0f172a;
}

.structured-subbody {
  margin: 0;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 15px;
  color: #334155;
}

/* 底部大卡片：标题在外部时去掉自身上边距 */
.wide-block .layer-three {
  margin-top: 0;
}
.switch-card {
  display: flex;
  flex-direction: column;
  padding: 10px;
}

.switch-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.switch-tabs {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.switch-tab {
  margin: 0;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #334155;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 13px;
  font-weight: 800;
}

.switch-tab.active {
  border-color: #2563eb;
  background: #dbeafe;
  color: #1e3a8a;
}

.switch-arrows {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.arrow-btn {
  margin: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  font-weight: 900;
  line-height: 1;
}

.switch-body {
  min-height: 0;
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: auto;
}

.switch-body-user-req {
  padding-top: 2px;
}

.ureq-mini-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 2px 0 4px;
}

.ureq-mini-card {
  border: 1px solid #dbe4f1;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  padding: 8px 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}

.ureq-mini-card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin-bottom: 6px;
}

.ureq-mini-seq {
  font-weight: 800;
  font-size: 12px;
  color: #1e40af;
}

.ureq-mini-at {
  font-size: 11px;
  color: #64748b;
  flex: 1;
  min-width: 0;
}

.ureq-mini-del {
  margin-left: auto;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 6px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #b91c1c;
  cursor: pointer;
}

.ureq-mini-del:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ureq-mini-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.mid-empty-card {
  background: rgba(248, 250, 252, 0.55);
  border-style: dashed;
  display: flex;
  flex-direction: column;
}

.right-switch-card {
  background: rgba(248, 250, 252, 0.55);
  display: flex;
  flex-direction: column;
}

.empty-body {
  flex: 1;
  border-radius: 10px;
  border: 1px dashed #cbd5e1;
  background: rgba(255, 255, 255, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  text-align: center;
  overflow: hidden;
}

.human-image-wrap {
  flex: 1;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #dbe4f1;
  background: rgba(255, 255, 255, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
}

.human-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.human-compare {
  position: relative;
  flex: 1;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #dbe4f1;
  background: rgba(255, 255, 255, 0.65);
}

.human-image--base,
.human-image--top {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.human-compare {
  touch-action: none;
  user-select: none;
  cursor: row-resize;
}

.compare-handle {
  position: absolute;
  left: 0;
  right: 0;
  transform: translateY(-50%);
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.compare-handle__line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: rgba(37, 99, 235, 0.95);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.6);
}

.compare-handle__pill {
  position: relative;
  z-index: 1;
  font-size: 12px;
  font-weight: 900;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.92);
  color: #eff6ff;
  border: 1px solid rgba(191, 219, 254, 0.75);
}

.switch-tcm {
  display: flex;
  flex-direction: column;
}

.metric-panel { display: flex; flex-direction: column; }
.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.metric-head h3 { margin: 0; }

.metric-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: #1e293b;
}
.help-btn {
  margin: 0;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 800;
  padding: 0;
  line-height: 1;
}
.metric-wrap { overflow: auto; max-height: none; flex: 1; }
.metric-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.metric-table th, .metric-table td { border: 1px solid #dbe4f1; padding: 6px; text-align: left; font-size: 12px; word-break: break-word; overflow-wrap: anywhere; }
.metric-table th { background: #eff6ff; color: #1e3a8a; }
.export-btn {
  margin: 0;
  background: #0f766e;
  color: #f0fdfa;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 700;
}
.export-btn.secondary {
  background: #1d4ed8;
  color: #eff6ff;
}
.export-btn.subtle {
  background: #f8fafc;
  color: #64748b;
  border: 1px solid #cbd5e1;
}
.export-btn.subtle:hover {
  background: #f1f5f9;
  color: #475569;
}
.help-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.help-dialog {
  width: min(920px, 100%);
  max-height: min(80vh, 760px);
  overflow: auto;
  border-radius: 14px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  padding: 14px;
}
.help-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.help-head h3 { margin: 0; color: #1e293b; }
.help-close {
  margin: 0;
  border: 1px solid #d1d5db;
  background: #f3f4f6;
  color: #1f2937;
  border-radius: 8px;
  padding: 8px 12px;
}
.help-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
}
.help-table th, .help-table td {
  border: 1px solid #dbe4f1;
  padding: 8px;
  text-align: left;
  vertical-align: top;
}
.help-table th {
  background: #eff6ff;
  color: #1e3a8a;
}

.system-float-btn {
  position: fixed;
  right: 18px;
  top: 86px;
  z-index: 70;
  margin: 0;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 50%;
  width: 88px;
  height: 88px;
  padding: 0;
  background:
    radial-gradient(circle at 30% 28%, rgba(255, 255, 255, 0.26), rgba(255, 255, 255, 0) 38%),
    linear-gradient(145deg, #2563eb 0%, #0ea5a8 55%, #0f766e 100%);
  color: #f8fafc;
  font-weight: 800;
  box-shadow: 0 10px 28px rgba(14, 116, 144, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.22);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1.2;
  font-size: 17px;
  text-align: center;
  white-space: pre-line;
  word-break: break-word;
  padding: 10px;
  backdrop-filter: blur(4px);
  transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
}

.system-float-btn:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 14px 34px rgba(14, 116, 144, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  filter: saturate(1.05);
}

.system-float-btn:active {
  transform: translateY(0) scale(0.98);
}

.system-panel {
  position: fixed;
  right: 18px;
  top: 102px;
  z-index: 69;
  width: min(560px, calc(100vw - 24px));
  height: min(76vh, 700px);
  margin: 0;
  padding: 10px;
  border: 1px solid #cbd5e1;
  background: rgba(11, 18, 32, 0.82);
  color: #e2e8f0;
  backdrop-filter: blur(3px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.flow-wrap {
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.36);
  margin-bottom: 8px;
  overflow: hidden;
}

.flow-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.flow-switch-btn {
  margin: 0;
  border: 1px solid #334155;
  background: rgba(15, 23, 42, 0.55);
  color: #cbd5e1;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
}

.flow-switch-btn.active {
  border-color: #38bdf8;
  background: rgba(30, 64, 175, 0.35);
  color: #e0f2fe;
}

.flow-switch-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.flow-svg {
  width: 100%;
  min-width: 0;
  height: 280px;
  display: block;
}

.flow-svg--mini {
  height: 180px;
}

.flow-node {
  rx: 10;
  ry: 10;
  stroke-width: 2;
}

.flow-node.idle {
  fill: #4b5563;
  stroke: #64748b;
}

.flow-node.active {
  fill: #1d4ed8;
  stroke: #60a5fa;
}

.flow-node.done {
  fill: #22c55e;
  stroke: #86efac;
}

.flow-text {
  fill: #f8fafc;
  font-size: 30px;
  font-weight: 700;
  text-anchor: middle;
  dominant-baseline: middle;
}

.flow-text--mini {
  font-size: 20px;
}

.flow-edge {
  stroke-width: 3.2;
  fill: none;
}

.flow-edge.idle {
  stroke: #94a3b8;
  marker-end: url(#arrowGray);
}

.flow-edge.done {
  stroke: #22c55e;
  marker-end: url(#arrowGreen);
}

.flow-edge.active {
  stroke: #3b82f6;
  marker-end: url(#arrowBlue);
  stroke-dasharray: 10 8;
  animation: flowMove 0.85s linear infinite;
}

.flow-edge-mini {
  stroke-width: 3.2;
  fill: none;
}

.flow-edge-mini.idle {
  stroke: #94a3b8;
}

.flow-edge-mini.done {
  stroke: #22c55e;
}

.flow-edge-mini.active {
  stroke: #3b82f6;
  stroke-dasharray: 10 8;
  animation: flowMove 0.85s linear infinite;
}

@keyframes flowMove {
  to {
    stroke-dashoffset: -36;
  }
}

.system-panel-body {
  overflow: auto;
  flex: 1;
  min-height: 0;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  padding: 8px;
  background: rgba(2, 6, 23, 0.74);
}

.system-line {
  margin: 0 0 6px;
  font-family: Consolas, Monaco, monospace;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.system-line:last-child {
  margin-bottom: 0;
}

.user-requirement-wrap {
  flex-shrink: 0;
  margin-top: 8px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  padding: 6px 8px 8px;
  background: rgba(2, 6, 23, 0.74);
}

.user-requirement-row {
  display: flex;
  gap: 6px;
  align-items: flex-end;
}

.user-req-buttons {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
  align-self: stretch;
  justify-content: flex-end;
}

.user-req-submit-btn {
  flex-shrink: 0;
  margin: 0;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid #38bdf8;
  background: rgba(56, 189, 248, 0.22);
  color: #e0f2fe;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
  cursor: pointer;
  min-width: 44px;
}

.user-req-submit-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.user-req-warn {
  margin: 8px 0 0;
  font-size: 12px;
  color: #fcd34d;
}

.user-requirement-label {
  display: block;
  margin: 0 0 4px;
  color: #bfdbfe;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.35;
}

.user-requirement-input {
  flex: 1;
  min-width: 0;
  width: auto;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 6px 8px;
  background: rgba(15, 23, 42, 0.7);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.4;
  resize: vertical;
  min-height: 44px;
  max-height: 120px;
}

.user-requirement-input::placeholder {
  color: #94a3b8;
}

@media (min-width: 1400px) {
  .content { padding: 18px; }
  .layer-one {
    grid-template-columns: minmax(340px, 0.8fr) minmax(300px, 0.7fr) minmax(640px, 1.5fr);
  }
  .compact-card { height: 400px; }
  .metric-wrap { max-height: none; }
}

@media (max-width: 1100px) {
  .layer-one { grid-template-columns: 1fr; }
  .layer-two { grid-template-columns: 1fr; }
}
</style>
