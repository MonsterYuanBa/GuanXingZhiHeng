// 可通过环境变量覆盖，便于你切换 Python 后端端口
// 例如：VITE_API_BASE_URL=http://localhost:8000/api
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8081/api'
//const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://8.138.233.123:1145'

async function request(path, options = {}) {
  const token = localStorage.getItem('mask_token')
  const headers = new Headers(options.headers || {})
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json()
  }
  return response.blob()
}

export function login(payload) {
  return request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function register(payload) {
  return request('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function submitHealthData(formData) {
  return request('/posture/analyze', {
    method: 'POST',
    body: formData,
  })
}

export function fetchPostureReportStatus(recordId, userId) {
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/posture/report-status?recordId=${encodeURIComponent(recordId)}&userId=${encodeURIComponent(uid)}`)
}

export function fetchHistory(userId) {
  return request(`/reports/history?userId=${encodeURIComponent(userId)}`).then((data) => {
    if (Array.isArray(data)) return data
    if (Array.isArray(data?.items)) return data.items
    return []
  })
}

export function downloadReportPdf(reportId) {
  return request(`/reports/${reportId}/pdf`)
}

export function fetchProcessedPostureImage(recordId, userId) {
  if (!recordId) throw new Error('recordId required')
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/reports/${encodeURIComponent(recordId)}/processed-image?userId=${encodeURIComponent(uid)}`)
}

export function fetchMosaicPostureImage(recordId, userId) {
  if (!recordId) throw new Error('recordId required')
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/reports/${encodeURIComponent(recordId)}/mosaic-image?userId=${encodeURIComponent(uid)}`)
}

export function fetchTongueImage(recordId, userId) {
  if (!recordId) throw new Error('recordId required')
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/reports/${encodeURIComponent(recordId)}/tongue-image?userId=${encodeURIComponent(uid)}`)
}

export function deleteHistoryRecord(recordId, userId) {
  return request(`/reports/${encodeURIComponent(recordId)}?userId=${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  })
}

export function fetchProfile(userId) {
  return request(`/profile?userId=${encodeURIComponent(userId)}`)
}

export function uploadProfile(payload) {
  return request('/profile/upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateProfile(payload) {
  return request('/profile/update', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function saveProfile(payload) {
  return request('/profile/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function saveTcmTenQuestions(payload) {
  return request('/profile/save-tcm-ten-questions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateUserNickname(payload) {
  return request('/profile/nickname', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function submitTongueData(formData) {
  return request('/tongue/analyze', {
    method: 'POST',
    body: formData,
  })
}

export function fetchTongueReportStatus(recordId, userId) {
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/tongue/report-status?recordId=${encodeURIComponent(recordId)}&userId=${encodeURIComponent(uid)}`)
}

export function generateJointReport(payload) {
  return request('/joint-report/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function fetchJointUserRequirements({ userId, recordId }) {
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  const q = new URLSearchParams({ userId: uid })
  if (recordId != null && Number(recordId) > 0) {
    q.set('recordId', String(recordId))
  }
  return request(`/joint-report/user-requirements?${q.toString()}`)
}

/** 删除一条需求：POST 同一 URL，序号用查询参数 removeSeq（不依赖 body 扩展字段，避免旧服务忽略 action） */
export function deleteJointUserRequirement({ userId, recordId, seq }) {
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  const rid = Number(recordId)
  const ds = Number(seq)
  if (!Number.isFinite(rid) || rid <= 0) {
    return Promise.reject(new Error('recordId 无效'))
  }
  if (!Number.isFinite(ds) || ds < 1) {
    return Promise.reject(new Error('序号无效'))
  }
  const qs = new URLSearchParams()
  qs.set('removeSeq', String(ds))
  return request(`/joint-report/user-requirement?${qs.toString()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      userId: uid,
      recordId: rid,
      text: '',
      clearExisting: false,
    }),
  })
}

export function appendJointUserRequirement(payload) {
  return request('/joint-report/user-requirement', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function clearJointUserRequirements(payload) {
  const { userId, recordId } = payload
  return request('/joint-report/user-requirement', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      userId,
      clearExisting: true,
      text: '',
      ...(recordId != null && Number(recordId) > 0 ? { recordId } : {}),
    }),
  })
}

export function fetchJointReportStatus(userId) {
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/joint-report/status?userId=${encodeURIComponent(uid)}`)
}

export function clearJointReportStatus(userId) {
  const uid = userId || localStorage.getItem('mask_user_id') || 'admin'
  return request(`/joint-report/status/clear?userId=${encodeURIComponent(uid)}`, {
    method: 'POST',
  })
}

export function runJointDetailedAnalysis(payload) {
  return request('/joint-report/detailed-analysis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function fetchTestModSampleIds() {
  return request('/reports/test-mod/sample-ids')
}

/** 从 4_test_mod 现有样本中随机选一个 ID；无可用样本时抛出（由 request 封装为 Error） */
export async function pickRandomTestModSampleId() {
  const data = await fetchTestModSampleIds()
  const ids = Array.isArray(data?.sampleIds) ? data.sampleIds.filter(Boolean) : []
  if (!ids.length) {
    throw new Error('4_test_mod 下没有可用的测试样本（需要含 manifest.json 的目录）。')
  }
  return ids[Math.floor(Math.random() * ids.length)]
}

export function fetchTestModSample(sampleId) {
  return request(`/reports/test-mod/sample?sampleId=${encodeURIComponent(sampleId)}`)
}

export function fetchTestModFileBlob(sampleId, relPath) {
  return request(
    `/reports/test-mod/file?sampleId=${encodeURIComponent(sampleId)}&relPath=${encodeURIComponent(relPath)}`
  )
}

export function runPostureAgentFromSample(payload) {
  return request('/reports/test-mod/run-posture-agent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function runTongueAgentFromSample(payload) {
  return request('/reports/test-mod/run-tongue-agent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function runJointAgentFromSample(payload) {
  return request('/reports/test-mod/run-joint-agent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function generateHistoryAnalysis(payload) {
  return request('/history-analysis/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
