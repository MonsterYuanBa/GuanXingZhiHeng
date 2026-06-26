
<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../components/TopNav.vue'
import { tcmQuestionDefs } from '../constants/tcmAndProfileLabels'
import { parseAgentText } from '../services/structuredText'
import {
  fetchTestModFileBlob,
  fetchTestModSample,
  pickRandomTestModSampleId,
  fetchPostureReportStatus,
  fetchProfile,
  fetchTongueReportStatus,
  runPostureAgentFromSample,
  runTongueAgentFromSample,
  saveProfile,
  saveTcmTenQuestions,
  submitHealthData,
  submitTongueData,
  updateProfile,
} from '../services/api'
import {
  getCollectorImage,
  getPostureResultDisplay,
  removeCollectorImage,
  saveCollectorImage,
  savePostureResultDisplay,
} from '../services/collectorImageDb'
import {
  getPendingPosture,
  getPendingTongue,
  clearPendingPosture,
  clearPendingTongue,
  omitStorageHeavyFields,
  saveLatestJointReport,
  savePendingPosture,
  savePendingTongue,
} from '../services/reportStore'

const router = useRouter()

const basicSectionRef = ref(null)
const tcmSectionRef = ref(null)
const postureSectionRef = ref(null)
const tongueSectionRef = ref(null)
const collectorScrollRef = ref(null)

const profileLoading = ref(false)
const tcmSaving = ref(false)
const profileNotice = ref('')
const profileNoticeType = ref('ok')
const tcmNotice = ref('')
const tcmNoticeType = ref('ok')

const postureLoading = ref(false)
const postureError = ref('')
const postureSuccess = ref('')
const postureAgentStatus = ref('idle') // idle | analyzing | done | failed

const tongueLoading = ref(false)
const tongueError = ref('')
const tongueSuccess = ref('')
const tongueAgentStatus = ref('idle') // idle | analyzing | done | failed

const jointLoading = ref(false)
const jointError = ref('')
const jointSuccess = ref('')
const autoFilledFromTest = ref(false)
const autoFillNotice = ref('')

const posturePreviewUrls = reactive({
  front: '',
  side: '',
})
const tonguePreviewUrl = ref('')
const showMetricDialog = ref(false)
const metricDefs = [
  { name: '高低肩指数', meaning: '反映左右肩高度差异，数值越接近 0 通常表示越对称。' },
  { name: '骨盆倾斜指数', meaning: '反映骨盆左右倾斜程度，绝对值越大表示倾斜更明显。' },
  { name: '头前伸指数', meaning: '反映头部前引趋势，数值越大通常表示前伸更明显。' },
  { name: '膝关节对齐指数', meaning: '反映下肢力线与膝关节对齐情况，偏离越大对齐越差。' },
  { name: '上下身面积比', meaning: '用于评估上半身与下半身轮廓比例变化。' },
  { name: '腿身比', meaning: '反映腿部相对身高比例变化。' },
  { name: '腹部前突指数', meaning: '反映侧面腹部前突趋势，数值升高通常提示前突更明显。' },
  { name: '大腿小腿比', meaning: '反映大腿与小腿轮廓比例变化。' },
  { name: '头身比', meaning: '反映头部与身体整体比例。' },
  { name: '躯干身高比', meaning: '反映躯干长度与身高比例。' },
  { name: '头肩比', meaning: '反映头部宽度与肩部宽度比例。' },
]

const form = reactive({
  nickname: (typeof localStorage !== 'undefined' && localStorage.getItem('mask_user_id')) || 'admin',
  age: '',
  gender: 'male',
  height: '',
  weight: '',
  allergyHistory: '',
  medicalHistory: 'none',
  workHabit: 'normal',
  tcmTenQuestions: Object.fromEntries(tcmQuestionDefs.map((item) => [item.key, item.options[0]?.value || ''])),
  tcmTenQuestionOthers: Object.fromEntries(tcmQuestionDefs.map((item) => [item.key, ''])),
  postureImages: {
    front: null,
    side: null,
  },
  tongueImage: null,
})

const postureImageSlots = [
  { key: 'front', label: '正面影像（必传）', required: true },
  { key: 'side', label: '侧面影像（必传）', required: true },
]

const postureAnalysis = ref({
  imageUrl: '',
  imageTransform: 'none',
  metrics: [],
  report: '',
  raw: null,
  recordId: null,
})

const tongueResult = ref({
  report: '',
  createdAt: '',
  raw: null,
})

const testSampleData = ref(null)
const testProcessedPreviewUrl = ref('')
const testAutoFillMarkPrefix = 'mask_test_autofill_used_'

const structuredPostureReport = computed(() => parseAgentText(postureAnalysis.value?.report || ''))
const structuredTongueReport = computed(() => parseAgentText(tongueResult.value?.report || ''))

function getCurrentUserId() {
  return localStorage.getItem('mask_user_id') || 'admin'
}

function _testAutoFillMarkKey() {
  return `${testAutoFillMarkPrefix}${getCurrentUserId()}`
}

function markTestAutoFillUsed() {
  try {
    sessionStorage.setItem(_testAutoFillMarkKey(), '1')
  } catch {
    // ignore
  }
}

function consumeTestAutoFillMark() {
  try {
    const k = _testAutoFillMarkKey()
    const used = sessionStorage.getItem(k) === '1'
    if (used) sessionStorage.removeItem(k)
    return used
  } catch {
    return false
  }
}

/** 昵称框预填服务端展示名；占位仅提示可改后保存 */
const nicknameFieldPlaceholder = computed(() => '修改昵称后请与下方信息一并保存')

function getProfileKey() {
  return `mask_profile_${getCurrentUserId()}`
}

function setProfileNotice(type, text) {
  profileNoticeType.value = type
  profileNotice.value = text
}

function setTcmNotice(type, text) {
  tcmNoticeType.value = type
  tcmNotice.value = text
}

function readLocalProfileCache() {
  try {
    return JSON.parse(localStorage.getItem(getProfileKey()) || '{}')
  } catch {
    return {}
  }
}

function applyProfile(profile) {
  const uid = getCurrentUserId()
  // 展示名来自接口 effective_nickname（无自定义时等于账号 ID），不得留空假装让用户「现填」
  if (profile) {
    const raw = profile.nickname
    if (raw != null && String(raw).trim() !== '') {
      form.nickname = String(raw).trim()
    } else {
      form.nickname = uid
    }
  }
  form.age = profile?.age ?? ''
  form.gender = profile?.gender || 'male'
  form.height = profile?.height ?? ''
  form.weight = profile?.weight ?? ''
  {
    const ah = profile?.allergyHistory
    const t = ah != null ? String(ah).trim() : ''
    form.allergyHistory = t && t !== '无过敏史' ? t : ''
  }
  form.medicalHistory = profile?.medicalHistory || 'none'
  form.workHabit = profile?.workHabit || 'normal'

  const local = readLocalProfileCache()
  const incoming = profile?.tcmTenQuestions ?? local.tcmTenQuestions ?? {}

  for (const item of tcmQuestionDefs) {
    const fallback = item.options[0]?.value || ''
    const incomingValue = incoming[item.key]
    const allowedValues = new Set(item.options.map((opt) => opt.value))
    const normalizedOtherValue = item.key === 'pain' ? 'other_custom' : 'other'

    if (typeof incomingValue === 'string' && incomingValue.startsWith('other:')) {
      form.tcmTenQuestions[item.key] = normalizedOtherValue
      form.tcmTenQuestionOthers[item.key] = incomingValue.slice(6).trim()
      continue
    }

    if (allowedValues.has(incomingValue)) {
      form.tcmTenQuestions[item.key] = incomingValue
      if (incomingValue !== normalizedOtherValue) form.tcmTenQuestionOthers[item.key] = ''
      continue
    }

    if (incomingValue != null && String(incomingValue).trim()) {
      form.tcmTenQuestions[item.key] = normalizedOtherValue
      form.tcmTenQuestionOthers[item.key] = String(incomingValue).trim()
      continue
    }

    form.tcmTenQuestions[item.key] = form.tcmTenQuestions[item.key] || fallback
  }
}

function buildTcmTenQuestionsPayload() {
  const tcmTenQuestions = {}
  for (const item of tcmQuestionDefs) {
    const selected = form.tcmTenQuestions[item.key]
    const isOther = selected === 'other' || selected === 'other_custom'
    const customText = (form.tcmTenQuestionOthers[item.key] || '').trim()
    tcmTenQuestions[item.key] = isOther ? (customText ? `other:${customText}` : 'other:未填写') : selected
  }
  return tcmTenQuestions
}

function normalizeNicknameForApi() {
  const uid = getCurrentUserId()
  const t = String(form.nickname || '').trim()
  if (!t) return null
  if (t === uid) return null
  return t
}

function buildProfileApiPayload() {
  return {
    userId: getCurrentUserId(),
    nickname: normalizeNicknameForApi(),
    age: form.age === '' ? null : Number(form.age),
    gender: form.gender || null,
    height: form.height === '' ? null : Number(form.height),
    weight: form.weight === '' ? null : Number(form.weight),
    allergyHistory: (form.allergyHistory || '').trim() || null,
    medicalHistory: form.medicalHistory || null,
    workHabit: form.workHabit || null,
  }
}

function pushDisplayName(name) {
  if (name) {
    localStorage.setItem('mask_display_name', name)
    window.dispatchEvent(new CustomEvent('mask-display-name-changed', { detail: name }))
  }
}

function buildLocalProfileSnapshot() {
  return {
    ...buildProfileApiPayload(),
    tcmTenQuestions: buildTcmTenQuestionsPayload(),
  }
}

async function loadProfile() {
  profileLoading.value = true
  setTcmNotice('ok', '')
  const fallbackUid = getCurrentUserId()
  form.nickname = fallbackUid
  try {
    const userId = getCurrentUserId()
    const res = await fetchProfile(userId)
    if (res?.success) {
      if (res.nickname) {
        pushDisplayName(res.nickname)
      }
      if (res?.profile) {
        applyProfile({ ...res.profile, tcmTenQuestions: readLocalProfileCache().tcmTenQuestions })
        localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
        setProfileNotice('ok', '已加载数据库中的个人信息。')
        return
      }
      if (res.nickname) {
        applyProfile({ nickname: res.nickname })
        setProfileNotice('warn', '数据库暂无扩展档案，已同步昵称。')
        return
      }
    }

    const raw = localStorage.getItem(getProfileKey())
    if (raw) {
      applyProfile(JSON.parse(raw))
      setProfileNotice('warn', '数据库暂无记录，已加载本地缓存。')
    } else {
      form.nickname = fallbackUid
      setProfileNotice('warn', '当前账号还没有上传个人信息。')
    }
  } catch {
    const raw = localStorage.getItem(getProfileKey())
    if (raw) {
      applyProfile(JSON.parse(raw))
      setProfileNotice('warn', '个人信息接口暂不可用，已加载本地缓存。')
    } else {
      form.nickname = fallbackUid
      setProfileNotice('error', '个人信息接口暂不可用，请稍后重试。')
    }
  } finally {
    profileLoading.value = false
  }
}

async function onSaveProfile() {
  profileLoading.value = true
  setProfileNotice('ok', '')
  try {
    const payload = buildProfileApiPayload()
    const res = await saveProfile(payload)
    if (!res?.success) {
      setProfileNotice('error', res?.message || '上传失败，请稍后重试。')
      return
    }
    if (res.nickname) {
      pushDisplayName(res.nickname)
    }
    localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    setProfileNotice('ok', res?.message || '个人信息上传成功。')
  } catch (err) {
    setProfileNotice('error', err.message || '上传失败，请检查后端接口。')
  } finally {
    profileLoading.value = false
  }
}

async function onUpdateProfile() {
  profileLoading.value = true
  setProfileNotice('ok', '')
  try {
    const payload = buildProfileApiPayload()
    const res = await updateProfile(payload)
    if (!res?.success) {
      setProfileNotice('error', res?.message || '修改失败，请稍后重试。')
      return
    }
    if (res.nickname) {
      pushDisplayName(res.nickname)
    }
    localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    setProfileNotice('ok', res?.message || '个人信息修改成功。')
  } catch (err) {
    setProfileNotice('error', err.message || '修改失败，请检查后端接口。')
  } finally {
    profileLoading.value = false
  }
}

async function onSaveTcmTen() {
  tcmSaving.value = true
  setTcmNotice('ok', '')
  try {
    const res = await saveTcmTenQuestions({
      userId: getCurrentUserId(),
      tcmTenQuestions: buildTcmTenQuestionsPayload(),
    })
    if (!res?.success) {
      setTcmNotice('error', res?.message || '保存失败，请稍后重试。')
      return
    }
    localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    setTcmNotice('ok', res?.message || `中医十问已保存（记录 #${res.recordId}）。`)
  } catch (err) {
    setTcmNotice('error', err.message || '保存失败，请检查后端接口。')
  } finally {
    tcmSaving.value = false
  }
}
function isBasicProfileComplete() {
  const numOk = (v) => v !== '' && v != null && String(v).trim() !== '' && !Number.isNaN(Number(v))
  return !!(numOk(form.age) && form.gender && numOk(form.height) && numOk(form.weight))
}

function isTcmTenComplete() {
  return tcmQuestionDefs.every((item) => {
    const selected = form.tcmTenQuestions[item.key]
    if (!selected || !String(selected).trim()) return false
    if (selected === 'other' || selected === 'other_custom') {
      return !!(form.tcmTenQuestionOthers[item.key] || '').trim()
    }
    return true
  })
}

const stepBasicDone = computed(() => isBasicProfileComplete())
const stepTcmDone = computed(() => isTcmTenComplete())
const stepPostureDone = computed(() => !!(postureAnalysis.value.report || getPendingPosture()?.report))
const stepTongueDone = computed(() => !!(tongueResult.value.report || getPendingTongue()?.report))
const canGenerateJoint = computed(
  () => stepBasicDone.value && stepTcmDone.value && stepPostureDone.value && stepTongueDone.value,
)

function scrollTo(refDom) {
  const target = refDom?.value ?? refDom
  const container = collectorScrollRef.value
  if (!target) return

  if (!container) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }

  const targetRect = target.getBoundingClientRect()
  const containerRect = container.getBoundingClientRect()
  const nextTop = container.scrollTop + (targetRect.top - containerRect.top)
  container.scrollTo({ top: nextTop, behavior: 'smooth' })
}

function setPosturePreviewUrl(position, file) {
  if (posturePreviewUrls[position]) URL.revokeObjectURL(posturePreviewUrls[position])
  posturePreviewUrls[position] = file ? URL.createObjectURL(file) : ''
}

function collectorSlotForPosture(position) {
  return position === 'front' ? 'posture_front' : 'posture_side'
}

function onPostureImageChange(position, event) {
  const file = event.target.files?.[0]
  if (!file) return

  // 选择新体态图：开始新一轮分析，避免继续使用旧的 pending（旧 recordId/旧报告会污染联合报告与需求关联）
  clearPendingPosture()
  postureAnalysis.value = {
    imageUrl: '',
    imageTransform: 'none',
    metrics: [],
    report: '',
    raw: null,
    recordId: null,
  }
  postureAgentStatus.value = 'idle'
  postureError.value = ''
  postureSuccess.value = ''

  form.postureImages[position] = file
  setPosturePreviewUrl(position, file)
  void saveCollectorImage(getCurrentUserId(), collectorSlotForPosture(position), file)
}

function onTongueImageChange(event) {
  const file = event.target.files?.[0]
  if (!file) return

  // 选择新舌苔图：开始新一轮分析，避免继续使用旧的 pending 舌苔报告/时间
  clearPendingTongue()
  tongueResult.value = { report: '', createdAt: '', raw: null }
  tongueAgentStatus.value = 'idle'
  tongueError.value = ''
  tongueSuccess.value = ''

  if (tonguePreviewUrl.value) URL.revokeObjectURL(tonguePreviewUrl.value)
  form.tongueImage = file
  tonguePreviewUrl.value = URL.createObjectURL(file)
  void saveCollectorImage(getCurrentUserId(), 'tongue', file)
}

function openMetricGuide() {
  showMetricDialog.value = true
}

function closeMetricGuide() {
  showMetricDialog.value = false
}

function buildMetricsList(res) {
  const rows = []
  const titai = res?.titai_fb || {}
  const tixing = res?.tixing_fb || {}
  const titaiSide = res?.titai_lr || {}
  const tixingSide = res?.tixing_lr || {}

  for (const [key, value] of Object.entries(titai)) rows.push({ group: '体态指标', key, value })
  for (const [key, value] of Object.entries(tixing)) rows.push({ group: '体型指标', key, value })
  for (const [key, value] of Object.entries(titaiSide)) rows.push({ group: '侧面指标', key, value })
  for (const [key, value] of Object.entries(tixingSide)) rows.push({ group: '侧面体型', key, value })
  return rows
}

function buildMeta() {
  return {
    userId: getCurrentUserId(),
    age: form.age === '' ? null : Number(form.age),
    gender: form.gender || null,
    height: form.height === '' ? null : Number(form.height),
    weight: form.weight === '' ? null : Number(form.weight),
    allergyHistory: (form.allergyHistory || '').trim() || null,
    medicalHistory: form.medicalHistory || null,
    workHabit: form.workHabit || null,
    tcmTenQuestions: buildTcmTenQuestionsPayload(),
  }
}

function _fileNameFromUrl(url, fallback) {
  try {
    const u = new URL(url, window.location.origin)
    const p = u.pathname.split('/').filter(Boolean)
    return p[p.length - 1] || fallback
  } catch {
    return fallback
  }
}

async function _loadRemoteImageAsFile({ sampleId, relPath, fallbackName }) {
  if (!sampleId || !relPath) return null
  const blob = await fetchTestModFileBlob(sampleId, relPath)
  const name = _fileNameFromUrl(relPath, fallbackName)
  return new File([blob], name, { type: blob.type || 'image/jpeg' })
}

async function onAutoFillFromTestSample() {
  autoFillNotice.value = ''
  postureError.value = ''
  try {
    const chosenId = await pickRandomTestModSampleId()
    const sample = await fetchTestModSample(chosenId)
    testSampleData.value = sample
    const p = sample?.posture || {}
    const files = sample?.manifest?.files || {}
    const sid = sample?.sampleId || chosenId

    const frontFile = await _loadRemoteImageAsFile({
      sampleId: sid,
      relPath: files.postureFront,
      fallbackName: 'test_posture_front.jpg',
    })
    const sideFile = await _loadRemoteImageAsFile({
      sampleId: sid,
      relPath: files.postureSide,
      fallbackName: 'test_posture_side.jpg',
    })
    if (frontFile) {
      form.postureImages.front = frontFile
      setPosturePreviewUrl('front', frontFile)
      await removeCollectorImage(getCurrentUserId(), 'posture_front')
    }
    if (sideFile) {
      form.postureImages.side = sideFile
      setPosturePreviewUrl('side', sideFile)
      await removeCollectorImage(getCurrentUserId(), 'posture_side')
    }
    let processedImageUrl = ''
    if (files.postureProcessed) {
      try {
        const blob = await fetchTestModFileBlob(sid, files.postureProcessed)
        if (testProcessedPreviewUrl.value) URL.revokeObjectURL(testProcessedPreviewUrl.value)
        processedImageUrl = URL.createObjectURL(blob)
        testProcessedPreviewUrl.value = processedImageUrl
      } catch {
        processedImageUrl = ''
      }
    }

    const metrics = buildMetricsList({
      titai_fb: p.titai_fb || {},
      tixing_fb: p.tixing_fb || {},
      titai_lr: p.titai_lr || {},
      tixing_lr: p.tixing_lr || {},
    })
    postureAnalysis.value = {
      imageUrl: processedImageUrl || posturePreviewUrls.front || '',
      imageTransform: 'none',
      metrics,
      report: '',
      raw: {
        titai_fb: p.titai_fb || {},
        tixing_fb: p.tixing_fb || {},
        titai_lr: p.titai_lr || {},
        tixing_lr: p.tixing_lr || {},
        sampleId: sample?.sampleId || chosenId,
      },
      recordId: null,
    }
    postureAgentStatus.value = 'idle'
    autoFilledFromTest.value = true
    markTestAutoFillUsed()
    autoFillNotice.value = ''
  } catch (err) {
    autoFillNotice.value = err.message || '自动填充失败，请检查测试样本。'
  }
}

async function onAutoFillTongueFromTestSample() {
  autoFillNotice.value = ''
  tongueError.value = ''
  try {
    const chosenId = testSampleData.value?.sampleId || (await pickRandomTestModSampleId())
    const sample = await fetchTestModSample(chosenId)
    testSampleData.value = sample
    const files = sample?.manifest?.files || {}
    const sid = sample?.sampleId || chosenId
    const tongueFile = await _loadRemoteImageAsFile({
      sampleId: sid,
      relPath: files.tongueImage,
      fallbackName: 'test_tongue.jpg',
    })
    if (!tongueFile) {
      tongueError.value = '当前样本没有舌苔图片，请先检查 4_test_mod 对应文件。'
      return
    }
    form.tongueImage = tongueFile
    if (tonguePreviewUrl.value) URL.revokeObjectURL(tonguePreviewUrl.value)
    tonguePreviewUrl.value = URL.createObjectURL(tongueFile)
    await removeCollectorImage(getCurrentUserId(), 'tongue')
    tongueAgentStatus.value = 'idle'
    autoFilledFromTest.value = true
    markTestAutoFillUsed()
    autoFillNotice.value = ''
  } catch (err) {
    tongueError.value = err.message || '舌苔自动填充失败，请检查测试样本。'
  }
}

async function onTestPostureAgent() {
  postureError.value = ''
  postureSuccess.value = ''
  if (!autoFilledFromTest.value || !testSampleData.value) {
    postureError.value = '请先点击自动填充测试样本。'
    return
  }
  postureLoading.value = true
  try {
    const userId = getCurrentUserId()
    const res = await runPostureAgentFromSample({
      userId,
      sampleId: testSampleData.value.sampleId,
      fakeAgent: true,
      analysisMode: 'normal',
    })
    postureAgentStatus.value = 'done'
    postureAnalysis.value.report = res?.report || ''
    postureAnalysis.value.recordId = res?.recordId || null
    savePendingPosture({
      recordId: res?.recordId || null,
      createdAt: new Date().toISOString(),
      report: res?.report || '',
      metrics: postureAnalysis.value.metrics,
      raw: omitStorageHeavyFields(postureAnalysis.value.raw || {}),
    })
    postureSuccess.value = '测试智能体已读取样本报告并保存为新历史记录。'
  } catch (err) {
    postureAgentStatus.value = 'failed'
    postureError.value = err.message || '测试智能体调用失败。'
  } finally {
    postureLoading.value = false
  }
}

async function onTestTongueAgent() {
  tongueError.value = ''
  tongueSuccess.value = ''
  if (!autoFilledFromTest.value || !testSampleData.value) {
    tongueError.value = '请先点击自动填充测试样本。'
    return
  }
  tongueLoading.value = true
  try {
    const userId = getCurrentUserId()
    const nowIso = new Date().toISOString()
    const res = await runTongueAgentFromSample({
      userId,
      sampleId: testSampleData.value.sampleId,
      fakeAgent: true,
      analysisMode: 'normal',
    })
    tongueAgentStatus.value = 'done'
    tongueResult.value = { report: res?.report || '', createdAt: nowIso, raw: { ...(tongueResult.value.raw || {}), recordId: res?.recordId || null } }
    savePendingTongue({
      createdAt: nowIso,
      report: res?.report || '',
      raw: { ...(tongueResult.value.raw || {}), recordId: res?.recordId || null },
    })
    tongueSuccess.value = '测试智能体已读取样本报告并保存为新历史记录。'
  } catch (err) {
    tongueAgentStatus.value = 'failed'
    tongueError.value = err.message || '测试智能体调用失败。'
  } finally {
    tongueLoading.value = false
  }
}

async function pollPostureReportUntilDone(recordId, userId, baseRes, metrics) {
  for (let i = 0; i < 120; i += 1) {
    const state = await fetchPostureReportStatus(recordId, userId)
    if (state?.status === 'failed') {
      postureAgentStatus.value = 'failed'
      postureError.value = state?.error || '体态智能体分析失败。'
      return
    }
    if (state?.done && state?.report) {
      postureAgentStatus.value = 'done'
      postureAnalysis.value = {
        imageUrl: baseRes?.resultImageUrl || '',
        imageTransform: baseRes?.resultImageTransform ?? 'none',
        metrics,
        report: state.report,
        raw: baseRes,
        recordId,
      }
      savePendingPosture({
        recordId,
        createdAt: new Date().toISOString(),
        report: state.report,
        metrics,
        raw: omitStorageHeavyFields(baseRes),
      })
      postureSuccess.value = '体态分析完成。可继续进行舌苔分析。'
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 1500))
  }
  postureAgentStatus.value = 'failed'
  postureError.value = '体态报告生成超时，请稍后重试。'
}

async function pollTongueReportUntilDone(recordId, userId, baseRes, nowIso) {
  for (let i = 0; i < 120; i += 1) {
    const state = await fetchTongueReportStatus(recordId, userId)
    if (state?.status === 'failed') {
      tongueAgentStatus.value = 'failed'
      tongueError.value = state?.error || '舌苔智能体分析失败。'
      return
    }
    if (state?.done && state?.report) {
      tongueAgentStatus.value = 'done'
      tongueResult.value = {
        report: state.report,
        createdAt: nowIso,
        raw: baseRes,
      }
      savePendingTongue({
        createdAt: nowIso,
        report: state.report,
        raw: baseRes,
      })
      tongueSuccess.value = '舌苔分析完成。左侧可生成综合报告。'
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 1500))
  }
  tongueAgentStatus.value = 'failed'
  tongueError.value = '舌苔报告生成超时，请稍后重试。'
}

function restoreSessionFromStorage() {
  const pp = getPendingPosture()
  if (pp?.report) {
    const metrics = Array.isArray(pp.metrics) && pp.metrics.length ? pp.metrics : buildMetricsList(pp.raw || {})
    postureAnalysis.value = {
      imageUrl: pp.raw?.resultImageUrl || '',
      imageTransform: pp.raw?.resultImageTransform ?? 'none',
      metrics,
      report: pp.report,
      raw: pp.raw || null,
      recordId: pp.recordId || pp.raw?.recordId || pp.raw?.record_id || null,
    }
    postureSuccess.value = '已恢复上次体态分析结果（缓存）。'
    postureAgentStatus.value = 'done'
  }

  const pt = getPendingTongue()
  if (pt?.report) {
    tongueResult.value = {
      report: pt.report,
      createdAt: pt.createdAt || '',
      raw: pt.raw || null,
    }
    tongueSuccess.value = '已恢复上次舌苔分析结果（缓存）。'
    tongueAgentStatus.value = 'done'
  }
}

function getPostureForJoint() {
  if (postureAnalysis.value.report) {
    const pp = getPendingPosture()
    return {
      createdAt: pp?.createdAt || new Date().toISOString(),
      report: postureAnalysis.value.report,
      raw: postureAnalysis.value.raw,
      recordId:
        postureAnalysis.value.recordId ||
        pp?.recordId ||
        postureAnalysis.value.raw?.recordId ||
        postureAnalysis.value.raw?.record_id ||
        pp?.raw?.recordId ||
        pp?.raw?.record_id ||
        null,
    }
  }
  const pp = getPendingPosture()
  if (pp?.report) {
    return {
      createdAt: pp.createdAt || null,
      report: pp.report,
      raw: pp.raw,
      recordId: pp.recordId || pp.raw?.recordId || pp.raw?.record_id || null,
    }
  }
  return null
}

function getTongueForJoint() {
  if (tongueResult.value.report) {
    return {
      createdAt: tongueResult.value.createdAt || new Date().toISOString(),
      report: tongueResult.value.report,
      raw: tongueResult.value.raw,
    }
  }
  const pt = getPendingTongue()
  if (pt?.report) return { createdAt: pt.createdAt || null, report: pt.report, raw: pt.raw }
  return null
}

async function restoreImagesFromDb() {
  const uid = getCurrentUserId()
  const front = await getCollectorImage(uid, 'posture_front')
  if (front) {
    form.postureImages.front = front
    setPosturePreviewUrl('front', front)
  }
  const side = await getCollectorImage(uid, 'posture_side')
  if (side) {
    form.postureImages.side = side
    setPosturePreviewUrl('side', side)
  }
  const tongue = await getCollectorImage(uid, 'tongue')
  if (tongue) {
    form.tongueImage = tongue
    if (tonguePreviewUrl.value) URL.revokeObjectURL(tonguePreviewUrl.value)
    tonguePreviewUrl.value = URL.createObjectURL(tongue)
  }
}

async function restorePostureResultDisplayFromDb() {
  const pp = getPendingPosture()
  if (!pp?.report) return
  const url = await getPostureResultDisplay(getCurrentUserId())
  if (url) {
    postureAnalysis.value = { ...postureAnalysis.value, imageUrl: url }
  }
}

async function onSubmitPosture() {
  postureError.value = ''
  postureSuccess.value = ''
  jointSuccess.value = ''
  jointError.value = ''

  if (!form.postureImages.front) {
    postureError.value = '请先上传正面影像。'
    return
  }
  if (!form.postureImages.side) {
    postureError.value = '请先上传侧面影像。'
    return
  }

  const userId = getCurrentUserId()
  if (autoFilledFromTest.value && testSampleData.value) {
    postureLoading.value = true
    postureAgentStatus.value = 'analyzing'
    try {
      const res = await runPostureAgentFromSample({
        userId,
        sampleId: testSampleData.value.sampleId,
        fakeAgent: false,
        analysisMode: 'normal',
      })
      postureAgentStatus.value = 'done'
      postureAnalysis.value.report = res?.report || ''
      postureAnalysis.value.recordId = res?.recordId || null
      savePendingPosture({
        recordId: res?.recordId || null,
        createdAt: new Date().toISOString(),
        report: res?.report || '',
        metrics: postureAnalysis.value.metrics,
        raw: omitStorageHeavyFields(postureAnalysis.value.raw || {}),
      })
      postureSuccess.value = '体态指标已复用，已直接调用智能体并完成。'
    } catch (err) {
      postureAgentStatus.value = 'failed'
      postureError.value = err.message || '体态分析失败，请检查后端接口。'
    } finally {
      postureLoading.value = false
    }
    return
  }

  const formData = new FormData()
  formData.append('meta', new Blob([JSON.stringify(buildMeta())], { type: 'application/json' }))
  formData.append('userId', userId)
  formData.append('frontImage', form.postureImages.front, form.postureImages.front.name)
  formData.append('sideImage', form.postureImages.side, form.postureImages.side.name)

  postureLoading.value = true
  postureAgentStatus.value = 'idle'
  try {
    const res = await submitHealthData(formData)
    const metrics = buildMetricsList(res)
    const reportText = res?.deepseek_advice || ''
    const recordId = res?.recordId || res?.record_id || null

    postureAnalysis.value = {
      imageUrl: res?.resultImageUrl || '',
      imageTransform: res?.resultImageTransform ?? 'none',
      metrics,
      report: reportText,
      raw: res,
      recordId,
    }
    await savePostureResultDisplay(userId, res?.resultImageUrl || '')

    if (res?.aiPending && recordId) {
      postureAgentStatus.value = 'analyzing'
      postureSuccess.value = '体态数据已生成，智能体正在分析中...'
      void pollPostureReportUntilDone(recordId, userId, res, metrics)
    } else {
      postureAgentStatus.value = 'done'
      const fallbackText = reportText || res?.msg || '暂无体态报告内容'
      postureAnalysis.value.report = fallbackText
      savePendingPosture({
        recordId,
        createdAt: new Date().toISOString(),
        report: fallbackText,
        metrics,
        raw: omitStorageHeavyFields(res),
      })
      postureSuccess.value = '体态分析完成。可继续进行舌苔分析。'
    }
  } catch (err) {
    postureAgentStatus.value = 'failed'
    postureError.value = err.message || '体态分析失败，请检查后端接口。'
  } finally {
    postureLoading.value = false
  }
}

async function onSubmitTongue() {
  tongueError.value = ''
  tongueSuccess.value = ''
  jointSuccess.value = ''
  jointError.value = ''

  if (!postureAnalysis.value.report && !getPendingPosture()?.report) {
    tongueError.value = '请先完成体态分析。'
    scrollTo(postureSectionRef)
    return
  }

  if (!form.tongueImage) {
    tongueError.value = '请先上传舌苔图片。'
    return
  }

  const userId = getCurrentUserId()
  if (autoFilledFromTest.value && testSampleData.value) {
    tongueLoading.value = true
    tongueAgentStatus.value = 'analyzing'
    try {
      const nowIso = new Date().toISOString()
      const res = await runTongueAgentFromSample({
        userId,
        sampleId: testSampleData.value.sampleId,
        fakeAgent: false,
        analysisMode: 'normal',
      })
      tongueAgentStatus.value = 'done'
      tongueResult.value = { report: res?.report || '', createdAt: nowIso, raw: { ...(tongueResult.value.raw || {}), recordId: res?.recordId || null } }
      savePendingTongue({
        createdAt: nowIso,
        report: res?.report || '',
        raw: { ...(tongueResult.value.raw || {}), recordId: res?.recordId || null },
      })
      tongueSuccess.value = '舌苔数据已复用，已直接调用智能体并完成。'
    } catch (err) {
      tongueAgentStatus.value = 'failed'
      tongueError.value = err.message || '舌苔分析失败，请检查后端接口。'
    } finally {
      tongueLoading.value = false
    }
    return
  }

  const nowIso = new Date().toISOString()
  const formData = new FormData()
  formData.append('meta', new Blob([JSON.stringify(buildMeta())], { type: 'application/json' }))
  formData.append('userId', userId)
  formData.append('tongueImage', form.tongueImage, form.tongueImage.name)

  tongueLoading.value = true
  tongueAgentStatus.value = 'idle'
  try {
    const res = await submitTongueData(formData)
    const reportText = res?.aiReport || ''
    const recordId = res?.recordId || res?.record_id || null

    tongueResult.value = {
      report: reportText,
      createdAt: nowIso,
      raw: res,
    }
    if (res?.aiPending && recordId) {
      tongueAgentStatus.value = 'analyzing'
      tongueSuccess.value = '舌苔数据已生成，智能体正在分析中...'
      void pollTongueReportUntilDone(recordId, userId, res, nowIso)
    } else {
      tongueAgentStatus.value = 'done'
      const fallbackText = reportText || res?.msg || '暂无舌苔报告内容'
      tongueResult.value.report = fallbackText
      savePendingTongue({
        createdAt: nowIso,
        report: fallbackText,
        raw: res,
      })
      tongueSuccess.value = '舌苔分析完成。左侧可生成综合报告。'
    }
  } catch (err) {
    tongueAgentStatus.value = 'failed'
    tongueError.value = err.message || '舌苔分析失败，请检查后端接口。'
  } finally {
    tongueLoading.value = false
  }
}

async function onGenerateJointReport() {
  jointError.value = ''
  jointSuccess.value = ''

  if (!canGenerateJoint.value) {
    if (!stepBasicDone.value) {
      jointError.value = '请先完善个人信息。'
      scrollTo(basicSectionRef)
    } else if (!stepTcmDone.value) {
      jointError.value = '请先完善中医十问。'
      scrollTo(tcmSectionRef)
    } else if (!stepPostureDone.value) {
      jointError.value = '请先完成体态分析。'
      scrollTo(postureSectionRef)
    } else {
      jointError.value = '请先完成舌苔分析。'
      scrollTo(tongueSectionRef)
    }
    return
  }

  const pendingPosture = getPostureForJoint()
  const pendingTongue = getTongueForJoint()

  if (!pendingPosture?.report) {
    jointError.value = '请先完成体态分析。'
    scrollTo(postureSectionRef)
    return
  }
  if (!pendingTongue?.report) {
    jointError.value = '请先完成舌苔分析。'
    scrollTo(tongueSectionRef)
    return
  }

  jointLoading.value = true
  try {
    const payload = {
      userId: getCurrentUserId(),
      postureReport: pendingPosture.report || '',
      tongueReport: pendingTongue.report || '',
      postureAt: pendingPosture.createdAt || null,
      tongueAt: pendingTongue.createdAt || null,
      postureData: pendingPosture.raw || null,
      tongueData: pendingTongue.raw || null,
      tcmTenQuestions: buildTcmTenQuestionsPayload(),
    }
    const draftCreatedAt = new Date().toISOString()
    const draftSourcePostureRecordId =
      pendingPosture?.recordId || payload?.postureData?.recordId || payload?.postureData?.record_id || null
    const draftSourceTongueRecordId = payload?.tongueData?.recordId || payload?.tongueData?.record_id || null
    const basicProfileSnapshot = {
      age: form.age,
      gender: form.gender,
      height: form.height,
      weight: form.weight,
      allergyHistory: (form.allergyHistory || '').trim() || '无过敏史',
      medicalHistory: form.medicalHistory,
      workHabit: form.workHabit,
    }
    const tcmSnapshot = buildTcmTenQuestionsPayload()

    saveLatestJointReport({
      id: `pending-${Date.now()}`,
      createdAt: draftCreatedAt,
      type: 'joint',
      analysisType: 'joint',
      isGenerating: false,
      generationError: '',
      sourcePostureRecordId: draftSourcePostureRecordId,
      sourceTongueRecordId: draftSourceTongueRecordId,
      postureReport: payload.postureReport,
      tongueReport: payload.tongueReport,
      report: '',
      summary: '',
      postureData: payload.postureData || null,
      basicProfile: basicProfileSnapshot,
      tcmTenQuestions: tcmSnapshot,
      testSampleId: autoFilledFromTest.value ? testSampleData.value?.sampleId ?? null : null,
    })

    localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    jointSuccess.value = '已进入综合报告页，请点击「常规分析」开始生成。'
    await router.push('/joint-report')
  } catch (err) {
    jointError.value = err.message || '进入综合报告页失败，请稍后重试。'
  } finally {
    jointLoading.value = false
  }
}

onMounted(async () => {
  if (consumeTestAutoFillMark()) {
    const uid = getCurrentUserId()
    await removeCollectorImage(uid, 'posture_front')
    await removeCollectorImage(uid, 'posture_side')
    await removeCollectorImage(uid, 'tongue')
  }
  await loadProfile()
  restoreSessionFromStorage()
  await restorePostureResultDisplayFromDb()
  await restoreImagesFromDb()
})

onUnmounted(() => {
  Object.values(posturePreviewUrls).forEach((url) => {
    if (url) URL.revokeObjectURL(url)
  })
  if (tonguePreviewUrl.value) URL.revokeObjectURL(tonguePreviewUrl.value)
  if (testProcessedPreviewUrl.value) URL.revokeObjectURL(testProcessedPreviewUrl.value)
})
</script>
<template>
  <section class="page-wrap">
    <TopNav active="collector" />

    <div class="collector-page">
      <aside class="progress-rail" aria-label="数据收集进度">
        <div class="progress-rail-card">
          <div class="rail-title">采集进度</div>
          <ol class="rail-steps">
            <li class="rail-step">
              <div class="rail-track">
                <span class="rail-dot" :class="{ 'rail-dot--done': stepBasicDone }" aria-hidden="true" />
                <span class="rail-line" :class="{ 'rail-line--done': stepBasicDone }" />
              </div>
              <button type="button" class="rail-label" @click="scrollTo(basicSectionRef)">
                <span class="rail-label-title">个人信息</span>
                <span class="rail-label-sub">{{ stepBasicDone ? '已完成' : '待填写' }}</span>
              </button>
            </li>

            <li class="rail-step">
              <div class="rail-track">
                <span class="rail-dot" :class="{ 'rail-dot--done': stepTcmDone }" aria-hidden="true" />
                <span class="rail-line" :class="{ 'rail-line--done': stepTcmDone }" />
              </div>
              <button type="button" class="rail-label" @click="scrollTo(tcmSectionRef)">
                <span class="rail-label-title">中医十问</span>
                <span class="rail-label-sub">{{ stepTcmDone ? '已完成' : '待填写' }}</span>
              </button>
            </li>

            <li class="rail-step">
              <div class="rail-track">
                <span class="rail-dot" :class="{ 'rail-dot--done': stepPostureDone }" aria-hidden="true" />
                <span class="rail-line" :class="{ 'rail-line--done': stepPostureDone }" />
              </div>
              <button type="button" class="rail-label" @click="scrollTo(postureSectionRef)">
                <span class="rail-label-title">体态收集</span>
                <span class="rail-label-sub">{{ stepPostureDone ? '已完成' : '待上传并分析' }}</span>
              </button>
            </li>

            <li class="rail-step">
              <div class="rail-track">
                <span class="rail-dot" :class="{ 'rail-dot--done': stepTongueDone }" aria-hidden="true" />
                <span class="rail-line rail-line--to-action" />
              </div>
              <button type="button" class="rail-label" @click="scrollTo(tongueSectionRef)">
                <span class="rail-label-title">舌苔收集</span>
                <span class="rail-label-sub">{{ stepTongueDone ? '已完成' : '待上传并分析' }}</span>
              </button>
            </li>

            <li class="rail-step rail-step--action">
              <div class="rail-track rail-track--last">
                <span class="rail-dot rail-dot--action" aria-hidden="true" />
              </div>
              <div class="rail-action-wrap">
                <button
                  class="joint-btn-main"
                  type="button"
                  :disabled="jointLoading || !canGenerateJoint"
                  @click="onGenerateJointReport"
                >
                  {{ jointLoading ? '生成中...' : '生成综合报告' }}
                </button>
                <p v-if="!canGenerateJoint" class="rail-action-hint">完成四项后可生成综合报告</p>
              </div>
            </li>
          </ol>

          <p v-if="jointError" class="rail-msg error">{{ jointError }}</p>
          <p v-if="jointSuccess" class="rail-msg ok">{{ jointSuccess }}</p>
        </div>
      </aside>

      <main ref="collectorScrollRef" class="collector-scroll">
        <section ref="basicSectionRef" class="step-section">
          <div class="step-shell">
            <h2>步骤一：个人数据收集</h2>
            <p class="muted">填写后可上传或修改；支持滚轮切换到下一模块。</p>
            <section class="card section-card">
              <div class="basic-grid">
                <label>
                  昵称
                  <input v-model.trim="form.nickname" type="text" :placeholder="nicknameFieldPlaceholder" />
                </label>
                <label>
                  年龄
                  <input v-model.number="form.age" type="number" placeholder="请输入年龄" />
                </label>
                <label>
                  性别
                  <select v-model="form.gender">
                    <option value="male">男</option>
                    <option value="female">女</option>
                  </select>
                </label>
                <label>
                  身高(cm)
                  <input v-model.number="form.height" type="number" placeholder="请输入身高" />
                </label>
                <label>
                  体重(kg)
                  <input v-model.number="form.weight" type="number" placeholder="请输入体重" />
                </label>
                <label>
                  过敏情况
                  <input
                    v-model.trim="form.allergyHistory"
                    type="text"
                    maxlength="500"
                    placeholder="选填；不填则保存为「无过敏史」"
                  />
                </label>
                <label>
                  既往病史
                  <select v-model="form.medicalHistory">
                    <option value="none">无明确病史</option>
                    <option value="hypertension">高血压</option>
                    <option value="diabetes">糖尿病</option>
                    <option value="lumbar_cervical">颈椎/腰椎问题</option>
                    <option value="joint_injury">关节或运动损伤史</option>
                    <option value="other">其他</option>
                  </select>
                </label>
                <label>
                  职业/工作习惯
                  <select v-model="form.workHabit">
                    <option value="normal">活动较均衡</option>
                    <option value="sedentary">久坐为主</option>
                    <option value="standing">久站为主</option>
                    <option value="repetitive_labor">重复性劳动</option>
                    <option value="shift_work">轮班/熬夜</option>
                  </select>
                </label>
              </div>

              <div class="action-row">
                <button type="button" class="btn-upload" :disabled="profileLoading" @click="onSaveProfile">
                  {{ profileLoading ? '处理中...' : '上传个人信息' }}
                </button>
                <button type="button" class="btn-update" :disabled="profileLoading" @click="onUpdateProfile">
                  {{ profileLoading ? '处理中...' : '修改个人信息' }}
                </button>
              </div>

              <p
                v-if="profileNotice"
                class="profile-notice"
                :class="profileNoticeType === 'error' ? 'error' : profileNoticeType === 'warn' ? 'warn' : 'ok'"
              >
                {{ profileNotice }}
              </p>
            </section>
          </div>
        </section>

        <section ref="tcmSectionRef" class="step-section">
          <div class="step-shell">
            <h2>步骤二：中医十问</h2>
            <p class="muted">请完成十问后保存，系统将用于联合分析。</p>
            <section class="card section-card">
              <div class="tcm-grid">
                <label v-for="item in tcmQuestionDefs" :key="item.key">
                  {{ item.label }}
                  <select v-model="form.tcmTenQuestions[item.key]">
                    <option v-for="opt in item.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                  <input
                    v-if="form.tcmTenQuestions[item.key] === 'other' || form.tcmTenQuestions[item.key] === 'other_custom'"
                    v-model.trim="form.tcmTenQuestionOthers[item.key]"
                    type="text"
                    placeholder="请输入其他情况"
                  />
                </label>
              </div>

              <div class="action-row">
                <button type="button" class="btn-tcm-save" :disabled="profileLoading || tcmSaving" @click="onSaveTcmTen">
                  {{ tcmSaving ? '保存中...' : '保存中医十问' }}
                </button>
              </div>

              <p
                v-if="tcmNotice"
                class="profile-notice"
                :class="tcmNoticeType === 'error' ? 'error' : tcmNoticeType === 'warn' ? 'warn' : 'ok'"
              >
                {{ tcmNotice }}
              </p>
            </section>
          </div>
        </section>
        <section ref="postureSectionRef" class="step-section">
          <div class="step-shell">
            <h2>步骤三：体态数据收集</h2>
            <p class="muted">左侧上传区域缩小，右侧报告区域加宽；中间指标框不超过结果显示区域。</p>

            <div class="content three-col">
              <section class="card left-panel">
                <div class="panel-title-row">
                  <h3>体态图片上传</h3>
                  <button type="button" class="btn-ghost" @click="onAutoFillFromTestSample">自动填充</button>
                </div>
                <p v-if="autoFillNotice" class="muted">{{ autoFillNotice }}</p>
                <div class="upload-list">
                  <label v-for="item in postureImageSlots" :key="item.key" class="image-slot">
                    <span>{{ item.label }}</span>
                    <input type="file" accept="image/*" :required="item.required" @change="(e) => onPostureImageChange(item.key, e)" />
                    <div class="slot-preview">
                      <img v-if="posturePreviewUrls[item.key]" :src="posturePreviewUrls[item.key]" :alt="item.label" />
                      <div v-else class="preview-empty">未上传</div>
                    </div>
                  </label>
                </div>

                <p v-if="postureError" class="error status-text">{{ postureError }}</p>
                <p v-if="postureSuccess" class="ok status-text">{{ postureSuccess }}</p>

                <button class="submit-btn" :disabled="postureLoading" @click="onSubmitPosture">
                  {{ postureLoading ? '处理中，请稍候...' : '提交体态分析' }}
                </button>
                <button class="submit-btn btn-ghost-action" :disabled="postureLoading" @click="onTestPostureAgent">
                  测试智能体
                </button>
              </section>

              <section class="card middle-panel">
                <div class="metric-head">
                  <h3>体态图与指标</h3>
                  <button type="button" class="help-btn" @click="openMetricGuide">?</button>
                </div>

                <div class="result-image-wrap">
                  <img
                    v-if="postureAnalysis.imageUrl"
                    :src="postureAnalysis.imageUrl"
                    alt="体态分布图"
                    class="result-image"
                    :style="{ transform: postureAnalysis.imageTransform || 'none' }"
                  />
                  <div v-else class="preview-empty">等待体态分析结果图</div>
                </div>

                <div class="metric-table-wrap">
                  <table class="metric-table">
                    <thead>
                      <tr>
                        <th>类别</th>
                        <th>指标</th>
                        <th>数值</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in postureAnalysis.metrics" :key="`${item.group}-${item.key}`">
                        <td>{{ item.group }}</td>
                        <td>{{ item.key }}</td>
                        <td>{{ item.value }}</td>
                      </tr>
                      <tr v-if="!postureAnalysis.metrics.length">
                        <td colspan="3">等待体态分析指标</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>

              <section class="card right-panel">
                <div class="report-head">
                  <h3>体态报告</h3>
                  <span
                    class="agent-pill"
                    :class="{
                      analyzing: postureAgentStatus === 'analyzing',
                      done: postureAgentStatus === 'done',
                      failed: postureAgentStatus === 'failed',
                    }"
                  >
                    {{
                      postureAgentStatus === 'analyzing'
                        ? '智能体正在分析中'
                        : postureAgentStatus === 'done'
                          ? '智能体分析完成'
                          : postureAgentStatus === 'failed'
                            ? '智能体分析失败'
                            : '等待分析'
                    }}
                  </span>
                </div>
                <div class="report-scroll report-scroll-wide">
                  <div v-if="postureAnalysis.report" class="structured-wrap">
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
                  <p v-else class="muted">等待体态分析报告内容</p>
                </div>
              </section>
            </div>
          </div>
        </section>

        <section ref="tongueSectionRef" class="step-section">
          <div class="step-shell">
            <h2>步骤四：舌苔数据收集</h2>
            <p class="muted">完成后可直接在左侧流程底部生成综合报告。</p>

            <div class="content two-col">
              <section class="card left-panel">
                <div class="panel-title-row">
                  <h3>舌苔图片上传</h3>
                  <button type="button" class="btn-ghost" @click="onAutoFillTongueFromTestSample">自动填充</button>
                </div>
                <label class="upload-label">
                  舌苔图片
                  <input type="file" accept="image/*" @change="onTongueImageChange" />
                </label>

                <div class="preview-wrap">
                  <img v-if="tonguePreviewUrl" :src="tonguePreviewUrl" alt="舌苔预览" />
                  <div v-else class="preview-empty">未上传图片</div>
                </div>

                <p v-if="tongueError" class="error">{{ tongueError }}</p>
                <p v-if="tongueSuccess" class="ok">{{ tongueSuccess }}</p>

                <button class="submit-btn" type="button" :disabled="tongueLoading" @click="onSubmitTongue">
                  {{ tongueLoading ? '分析中...' : '开始舌苔分析' }}
                </button>
                <button class="submit-btn btn-ghost-action" type="button" :disabled="tongueLoading" @click="onTestTongueAgent">
                  测试智能体
                </button>
              </section>

              <section class="card right-panel">
                <div class="report-head">
                  <h3>中医体质分析报告</h3>
                  <span
                    class="agent-pill"
                    :class="{
                      analyzing: tongueAgentStatus === 'analyzing',
                      done: tongueAgentStatus === 'done',
                      failed: tongueAgentStatus === 'failed',
                    }"
                  >
                    {{
                      tongueAgentStatus === 'analyzing'
                        ? '智能体正在分析中'
                        : tongueAgentStatus === 'done'
                          ? '智能体分析完成'
                          : tongueAgentStatus === 'failed'
                            ? '智能体分析失败'
                            : '等待分析'
                    }}
                  </span>
                </div>
                <div class="report-scroll report-scroll-wide">
                  <div v-if="tongueResult.report" class="structured-wrap">
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
                  <p v-else class="muted">等待中医体质分析报告内容</p>
                </div>
              </section>
            </div>
          </div>
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
    </div>
  </section>
</template>
<style scoped>
.page-wrap { min-height: 100vh; }
.collector-page {
  display: flex;
  align-items: stretch;
  min-height: calc(100vh - 70px);
}
.progress-rail {
  flex: 0 0 176px;
  width: 176px;
  position: sticky;
  top: 70px;
  align-self: flex-start;
  max-height: calc(100vh - 70px);
  overflow-y: auto;
  padding: 12px 8px 12px 10px;
  background: transparent;
  border: none;
  box-sizing: border-box;
}
.progress-rail-card {
  border-radius: 14px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  background: linear-gradient(165deg, #ecfdf5 0%, #e6fffa 38%, #f1f5f9 100%);
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 118, 110, 0.08);
  padding: 12px 10px 14px;
  box-sizing: border-box;
}
.rail-title {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 12px;
  padding-left: 2px;
}
.rail-steps { list-style: none; margin: 0; padding: 0; }
.rail-step { display: flex; gap: 8px; align-items: stretch; min-height: 0; }
.rail-track {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
  flex-shrink: 0;
  padding-top: 4px;
}
.rail-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #94a3b8;
  background: rgba(255, 255, 255, 0.85);
  box-sizing: border-box;
  flex-shrink: 0;
}
.rail-dot--done {
  border-color: #0f766e;
  background: #0f766e;
  box-shadow: inset 0 0 0 2px #fff;
}
.rail-dot--action {
  width: 14px;
  height: 14px;
  border-color: #0d9488;
  background: #ccfbf1;
}
.rail-line {
  width: 3px;
  flex: 1;
  min-height: 18px;
  margin: 4px 0 0;
  border-radius: 2px;
  background: #e2e8f0;
}
.rail-line--done { background: #5eead4; }
.rail-line--to-action { background: #e2e8f0; }
.rail-track--last { padding-bottom: 4px; }
.rail-label {
  flex: 1;
  min-width: 0;
  margin: 0 0 4px;
  padding: 6px 6px 8px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.rail-label:hover {
  background: rgba(15, 118, 110, 0.09);
  border-color: rgba(15, 118, 110, 0.22);
}
.rail-label-title {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.3;
}
.rail-label-sub {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.35;
}
.rail-step--action { margin-top: 4px; align-items: flex-start; }
.rail-action-wrap { flex: 1; min-width: 0; padding-top: 0; }
.rail-action-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}
.rail-msg {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.45;
}
.rail-msg.error { color: #b91c1c; }
.rail-msg.ok { color: #0f766e; }

.collector-scroll {
  flex: 1;
  min-width: 0;
  height: calc(100vh - 70px);
  overflow-y: auto;
  scroll-snap-type: y mandatory;
}
.step-section {
  min-height: calc(100vh - 70px);
  scroll-snap-align: start;
  padding: 14px;
  display: flex;
  align-items: flex-start;
}

.step-shell { max-width: 1360px; margin: 0 auto; width: 100%; }
.step-shell h2 { margin: 0; color: #1e293b; }

.section-card {
  margin-top: 10px;
}

.basic-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 1fr));
  gap: 14px;
}

.tcm-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(260px, 1fr));
  gap: 14px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #334155;
  font-weight: 600;
}

.action-row {
  margin-top: 14px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin: 0 0 10px;
}
.panel-title-row h3 {
  margin: 0;
  flex: 1;
  min-width: 0;
}

.btn-upload,
.btn-update,
.btn-tcm-save,
.btn-ghost {
  margin: 0;
  min-width: 140px;
}

.btn-upload { background: #0f766e; color: #f0fdfa; }
.btn-update { background: #2563eb; color: #eff6ff; }
.btn-tcm-save { background: #0d9488; color: #f0fdfa; }
.btn-ghost {
  min-width: auto;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  background: #f8fafc;
  color: #64748b;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}
.btn-ghost:hover {
  background: #f1f5f9;
  color: #475569;
}
.btn-ghost-action {
  margin-top: 6px;
  min-height: 36px;
  font-size: 13px;
  font-weight: 600;
  background: #f8fafc;
  color: #64748b;
  border: 1px solid #cbd5e1;
}
.btn-ghost-action:hover {
  background: #f1f5f9;
  color: #475569;
}
.profile-notice { margin: 10px 0 0; }

.content { padding: 0; margin-top: 10px; }
.three-col {
  display: grid;
  grid-template-columns: 250px minmax(420px, 1fr) 620px;
  gap: 14px;
  align-items: stretch;
}
.two-col {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 14px;
  align-items: stretch;
}
.card h3 { margin-top: 0; color: #1e293b; }
.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.report-head h3 { margin: 0; }
.agent-pill {
  font-size: 12px;
  line-height: 1;
  border-radius: 999px;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  color: #64748b;
  background: #f8fafc;
  white-space: nowrap;
}
.agent-pill.analyzing {
  color: #1d4ed8;
  border-color: #93c5fd;
  background: #eff6ff;
  animation: agentPulse 1.2s ease-in-out infinite;
}
.agent-pill.done {
  color: #166534;
  border-color: #86efac;
  background: #f0fdf4;
}
.agent-pill.failed {
  color: #b91c1c;
  border-color: #fca5a5;
  background: #fef2f2;
}
@keyframes agentPulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.22); }
  50% { box-shadow: 0 0 0 7px rgba(59, 130, 246, 0); }
}
.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.metric-head h3 { margin: 0; }
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
.left-panel, .middle-panel, .right-panel {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  height: min(720px, calc(100vh - 150px));
  display: flex;
  flex-direction: column;
}
.middle-panel {
  display: flex;
  flex-direction: column;
}
.upload-list { display: grid; gap: 8px; }
.image-slot {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 8px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.image-slot span { color: #334155; font-weight: 600; }
.image-slot input[type="file"] {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  font-size: 13px;
}
.slot-preview, .slot-preview img, .preview-empty { width: 100%; height: 128px; }
.slot-preview img { border-radius: 8px; object-fit: contain; border: 1px solid #cbd5e1; background: #ffffff; }
.preview-empty {
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
  color: #94a3b8;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 0 8px;
}
.submit-btn { margin-top: 8px; width: 100%; }
.left-panel .submit-btn {
  min-height: 44px;
  padding: 0 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 16px;
}
.left-panel .status-text {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.35;
}
.joint-btn-main {
  width: 100%;
  padding: 10px 8px;
  font-size: 13px;
  font-weight: 700;
  background: #0f766e;
  color: #f0fdfa;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  line-height: 1.35;
}
.joint-btn-main:disabled { opacity: 0.55; cursor: not-allowed; }

.result-image-wrap { width: 100%; height: 310px; margin-bottom: 10px; flex: 0 0 auto; }
.result-image {
  width: 100%;
  height: 310px;
  object-fit: contain;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
}
.metric-table-wrap {
  overflow: auto;
  max-width: 100%;
  max-height: 270px;
  flex: 1 1 auto;
  min-height: 0;
  margin-top: 14px;
}
.metric-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.metric-table th, .metric-table td {
  border: 1px solid #dbe4f1;
  padding: 6px;
  text-align: left;
  font-size: 11px;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.metric-table th { background: #eff6ff; color: #1e3a8a; }

.report-scroll {
  height: 420px;
  overflow-y: auto;
  border: 1px solid #dbe4f1;
  border-radius: 10px;
  background: #f8fafc;
  padding: 12px;
}
.report-scroll-wide {
  height: auto;
  flex: 1 1 auto;
}
.report-text {
  margin: 0;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  max-width: 100%;
}

.structured-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.structured-sec {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.75);
  padding: 10px 10px 8px;
}

.structured-title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: 0.01em;
}

.structured-intro {
  margin: 0;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  color: #334155;
  font-size: 13.5px;
}

.structured-list {
  margin: 8px 0 0;
  padding-left: 1.15rem;
  color: #334155;
}

.structured-item {
  margin: 6px 0;
}

.structured-item-title {
  display: inline-block;
  margin-bottom: 4px;
  color: #1e293b;
  font-size: 13.5px;
  font-weight: 800;
}

.structured-item-body {
  margin: 0;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 13.5px;
  color: #334155;
}

.structured-sublist {
  margin: 10px 0 0;
  padding-left: 1.15rem;
  border-left: 3px solid rgba(37, 99, 235, 0.22);
}

.structured-subitem {
  margin: 6px 0;
}

.structured-subtitle {
  display: inline-block;
  margin-bottom: 4px;
  font-size: 13.5px;
  font-weight: 800;
  color: #0f172a;
}

.structured-subbody {
  margin: 0;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  font-size: 13.5px;
  color: #334155;
}
.upload-label { display: flex; flex-direction: column; gap: 6px; color: #334155; font-weight: 600; }
.preview-wrap { margin-top: 12px; width: 100%; height: 280px; }
.preview-wrap img {
  width: 100%;
  height: 280px;
  object-fit: contain;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
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

@media (max-width: 1300px) {
  .collector-page { flex-direction: column; }
  .progress-rail {
    position: relative;
    top: 0;
    max-height: none;
    width: 100%;
    flex: 0 0 auto;
    padding: 12px 12px 0;
  }
  .progress-rail-card {
    max-width: 520px;
    margin: 0 auto;
  }
  .collector-scroll { height: auto; overflow: visible; scroll-snap-type: none; }
  .step-section { min-height: auto; padding: 12px; }
  .three-col, .two-col, .basic-grid, .tcm-grid { grid-template-columns: 1fr; }
  .middle-panel { height: auto; }
  .result-image-wrap, .result-image, .preview-wrap, .preview-wrap img { height: 240px; }
  .report-scroll { height: 320px; }
  .report-scroll-wide { height: 360px; }
}
</style>
