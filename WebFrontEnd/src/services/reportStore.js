const HISTORY_KEY = 'mask_report_history'
/** 旧版曾写入 localStorage 的 pending，迁移到 sessionStorage 后删除 */
const LEGACY_PENDING_POSTURE_KEY = 'mask_pending_posture'
const LEGACY_PENDING_TONGUE_KEY = 'mask_pending_tongue'

function _currentUserId() {
  if (typeof localStorage === 'undefined') return 'admin'
  return localStorage.getItem('mask_user_id') || 'admin'
}

function pendingPostureKey(userId = _currentUserId()) {
  return `mask_pending_posture_${userId}`
}

function pendingTongueKey(userId = _currentUserId()) {
  return `mask_pending_tongue_${userId}`
}

/** 体态/舌苔 pending 用 sessionStorage：关闭标签页即清空；同标签刷新仍保留 */
function _sessionGet(key) {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(key) : null
  } catch {
    return null
  }
}

function _sessionSet(key, value) {
  try {
    sessionStorage.setItem(key, value)
  } catch (e) {
    console.warn('[reportStore] sessionStorage.setItem failed', e)
  }
}

function _sessionRemove(key) {
  try {
    sessionStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}
const LATEST_JOINT_REPORT_KEY = 'mask_latest_joint_report'
const LATEST_HISTORY_ANALYSIS_KEY = 'mask_latest_history_analysis'

function safeParse(raw, fallback) {
  try {
    return JSON.parse(raw)
  } catch {
    return fallback
  }
}

/** localStorage 约 5MB；体态接口的 resultImageUrl（整图 base64）会撑爆配额 */
const STORAGE_STRIP_KEYS = ['resultImageUrl', 'imageUrl', 'result_image_url']

/** 深度遍历时直接丢弃的键（含嵌套对象内） */
const STORAGE_HEAVY_KEYS = new Set([
  'resultImageUrl',
  'imageUrl',
  'result_image_url',
  'image_url',
  'previewUrl',
  'dataUrl',
  'frontImage',
  'sideImage',
])

function isDataUrlBase64(s) {
  return typeof s === 'string' && s.startsWith('data:') && s.includes('base64,')
}

/**
 * 深度剔除易撑爆 localStorage 的字段（data: 大图、已知图片键等）。
 * 用于 postureData / trendData 等嵌套结构。
 */
export function stripHeavyForStorage(value, depth = 0) {
  if (value == null || depth > 8) return value
  if (typeof value === 'string') {
    if (isDataUrlBase64(value)) return undefined
    return value
  }
  if (typeof value !== 'object') return value
  if (Array.isArray(value)) {
    const next = value
      .map((x) => stripHeavyForStorage(x, depth + 1))
      .filter((x) => x !== undefined)
    return next
  }
  const out = {}
  for (const [k, v] of Object.entries(value)) {
    if (STORAGE_HEAVY_KEYS.has(k)) continue
    if (typeof v === 'string' && isDataUrlBase64(v)) continue
    const nested = stripHeavyForStorage(v, depth + 1)
    if (nested !== undefined) out[k] = nested
  }
  return out
}

/** 联合报告页只需要正文 + 体态指标，不要存完整 API/历史 item（易含整页 base64） */
export function slimJointReportForStorage(data) {
  if (!data || typeof data !== 'object') return {}
  const {
    id,
    createdAt,
    type,
    analysisType,
    isGenerating,
    generationError,
    sourcePostureRecordId,
    sourceTongueRecordId,
    postureReport,
    tongueReport,
    report,
    summary,
    postureData,
    basicProfile,
    tcmTenQuestions,
    testSampleId,
  } = data
  return {
    id,
    createdAt,
    type,
    analysisType,
    isGenerating: Boolean(isGenerating),
    generationError: generationError || '',
    sourcePostureRecordId,
    sourceTongueRecordId,
    postureReport,
    tongueReport,
    report,
    summary,
    postureData: stripHeavyForStorage(postureData),
    basicProfile:
      basicProfile && typeof basicProfile === 'object' ? { ...basicProfile } : undefined,
    tcmTenQuestions:
      tcmTenQuestions && typeof tcmTenQuestions === 'object' ? { ...tcmTenQuestions } : undefined,
    testSampleId: testSampleId || null,
  }
}

export function slimHistoryAnalysisForStorage(data) {
  if (!data || typeof data !== 'object') return {}
  const {
    id,
    createdAt,
    type,
    analysisType,
    isGenerating,
    generationError,
    trendData,
    sourceItems,
    report,
    summary,
    historyAnalysisReport,
  } = data
  return {
    id,
    createdAt,
    type,
    analysisType,
    isGenerating: Boolean(isGenerating),
    generationError: generationError || '',
    trendData: stripHeavyForStorage(trendData),
    sourceItems: stripHeavyForStorage(sourceItems),
    report: report || historyAnalysisReport,
    summary: summary || report || historyAnalysisReport,
  }
}

export function omitStorageHeavyFields(obj) {
  if (!obj || typeof obj !== 'object') return obj
  const out = { ...obj }
  for (const k of STORAGE_STRIP_KEYS) {
    if (k in out) delete out[k]
  }
  return out
}

function trySetItem(key, json) {
  localStorage.setItem(key, json)
}

function isQuotaError(e) {
  return (
    e &&
    (e.name === 'QuotaExceededError' ||
      e.code === 22 ||
      (typeof DOMException !== 'undefined' && e instanceof DOMException && e.name === 'QuotaExceededError'))
  )
}

export function getLocalHistory() {
  const raw = localStorage.getItem(HISTORY_KEY)
  if (!raw) return []
  const data = safeParse(raw, [])
  return Array.isArray(data) ? data : []
}

export function saveHistoryRecord(record) {
  const history = getLocalHistory()
  history.unshift(record)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 100)))
}

export function removeLocalHistoryRecord(recordId) {
  const target = String(recordId)
  const history = getLocalHistory().filter((item) => String(item?.id) !== target)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history))
}

export function savePendingPosture(data) {
  _sessionSet(pendingPostureKey(), JSON.stringify(data || {}))
}

/** 首次读取：把旧版 localStorage 里的 pending 迁到 sessionStorage 并删除旧键 */
function _migrateLegacyPendingPosture(uid) {
  const k = pendingPostureKey(uid)
  if (_sessionGet(k)) return
  const fromLs = (() => {
    try {
      return localStorage.getItem(k)
    } catch {
      return null
    }
  })()
  if (fromLs) {
    _sessionSet(k, fromLs)
    try {
      localStorage.removeItem(k)
    } catch {
      /* ignore */
    }
    return
  }
  const legacy = (() => {
    try {
      return localStorage.getItem(LEGACY_PENDING_POSTURE_KEY)
    } catch {
      return null
    }
  })()
  if (!legacy) return
  const parsed = safeParse(legacy, null)
  if (parsed?.report) {
    _sessionSet(k, legacy)
  }
  try {
    localStorage.removeItem(LEGACY_PENDING_POSTURE_KEY)
  } catch {
    /* ignore */
  }
}

export function getPendingPosture() {
  const uid = _currentUserId()
  _migrateLegacyPendingPosture(uid)
  const raw = _sessionGet(pendingPostureKey(uid))
  return raw ? safeParse(raw, null) : null
}

export function clearPendingPosture() {
  const uid = _currentUserId()
  _sessionRemove(pendingPostureKey(uid))
  try {
    localStorage.removeItem(pendingPostureKey(uid))
    localStorage.removeItem(LEGACY_PENDING_POSTURE_KEY)
  } catch {
    /* ignore */
  }
}

export function savePendingTongue(data) {
  _sessionSet(pendingTongueKey(), JSON.stringify(data || {}))
}

function _migrateLegacyPendingTongue(uid) {
  const k = pendingTongueKey(uid)
  if (_sessionGet(k)) return
  const fromLs = (() => {
    try {
      return localStorage.getItem(k)
    } catch {
      return null
    }
  })()
  if (fromLs) {
    _sessionSet(k, fromLs)
    try {
      localStorage.removeItem(k)
    } catch {
      /* ignore */
    }
    return
  }
  const legacy = (() => {
    try {
      return localStorage.getItem(LEGACY_PENDING_TONGUE_KEY)
    } catch {
      return null
    }
  })()
  if (!legacy) return
  const parsed = safeParse(legacy, null)
  if (parsed?.report) {
    _sessionSet(k, legacy)
  }
  try {
    localStorage.removeItem(LEGACY_PENDING_TONGUE_KEY)
  } catch {
    /* ignore */
  }
}

export function getPendingTongue() {
  const uid = _currentUserId()
  _migrateLegacyPendingTongue(uid)
  const raw = _sessionGet(pendingTongueKey(uid))
  return raw ? safeParse(raw, null) : null
}

export function clearPendingTongue() {
  const uid = _currentUserId()
  _sessionRemove(pendingTongueKey(uid))
  try {
    localStorage.removeItem(pendingTongueKey(uid))
    localStorage.removeItem(LEGACY_PENDING_TONGUE_KEY)
  } catch {
    /* ignore */
  }
}

/** 退出登录时清空 session 内 pending，并清理可能残留的 localStorage 旧键 */
export function clearPendingForLogout() {
  const uid = _currentUserId()
  _sessionRemove(pendingPostureKey(uid))
  _sessionRemove(pendingTongueKey(uid))
  try {
    localStorage.removeItem(pendingPostureKey(uid))
    localStorage.removeItem(pendingTongueKey(uid))
    localStorage.removeItem(LEGACY_PENDING_POSTURE_KEY)
    localStorage.removeItem(LEGACY_PENDING_TONGUE_KEY)
  } catch {
    /* ignore */
  }
}

export function saveLatestJointReport(data) {
  const slim = slimJointReportForStorage(data || {})
  const json = JSON.stringify(slim)
  try {
    trySetItem(LATEST_JOINT_REPORT_KEY, json)
  } catch (e) {
    if (!isQuotaError(e)) throw e
    try {
      trySetItem(
        LATEST_JOINT_REPORT_KEY,
        JSON.stringify({
          ...slim,
          postureData: null,
        })
      )
    } catch (e2) {
      console.warn('[reportStore] saveLatestJointReport quota:', e2)
    }
  }
}

export function getLatestJointReport() {
  const raw = localStorage.getItem(LATEST_JOINT_REPORT_KEY)
  return raw ? safeParse(raw, null) : null
}

export function clearLatestJointReport() {
  localStorage.removeItem(LATEST_JOINT_REPORT_KEY)
}

export function saveLatestHistoryAnalysis(data) {
  const slim = slimHistoryAnalysisForStorage(data || {})
  try {
    trySetItem(LATEST_HISTORY_ANALYSIS_KEY, JSON.stringify(slim))
  } catch (e) {
    if (!isQuotaError(e)) throw e
    try {
      trySetItem(
        LATEST_HISTORY_ANALYSIS_KEY,
        JSON.stringify({
          ...slim,
          trendData: [],
        })
      )
    } catch (e2) {
      console.warn('[reportStore] saveLatestHistoryAnalysis quota:', e2)
    }
  }
}

export function getLatestHistoryAnalysis() {
  const raw = localStorage.getItem(LATEST_HISTORY_ANALYSIS_KEY)
  return raw ? safeParse(raw, null) : null
}

export function clearLatestHistoryAnalysis() {
  localStorage.removeItem(LATEST_HISTORY_ANALYSIS_KEY)
}
