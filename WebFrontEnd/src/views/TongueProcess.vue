<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopNav from '../components/TopNav.vue'
import { submitTongueData } from '../services/api'
import { getCollectorImage, saveCollectorImage } from '../services/collectorImageDb'
import { parseAgentText } from '../services/structuredText'
import {
  getPendingTongue,
  getPendingPosture,
  clearPendingTongue,
  savePendingTongue,
  saveLatestJointReport,
} from '../services/reportStore'

const router = useRouter()
const loading = ref(false)
const jointLoading = ref(false)
const error = ref('')
const jointError = ref('')
const success = ref('')
const aiReport = ref('')
const analyzedAt = ref('')

const state = reactive({
  file: null,
  previewUrl: '',
})

function getCurrentUserId() {
  return localStorage.getItem('mask_user_id') || 'admin'
}

function getProfileKey() {
  return `mask_profile_${getCurrentUserId()}`
}

const profile = computed(() => {
  try {
    return JSON.parse(localStorage.getItem(getProfileKey()) || '{}')
  } catch {
    return {}
  }
})

const structuredTongueReport = computed(() => parseAgentText(aiReport.value || getPendingTongue()?.report || ''))

onMounted(async () => {
  const pendingPosture = getPendingPosture()
  if (!pendingPosture) {
    error.value = '请先完成体态分析，再进行舌苔上传。'
  }

  const pendingTongue = getPendingTongue()
  if (pendingTongue?.report) {
    aiReport.value = pendingTongue.report
    analyzedAt.value = pendingTongue.createdAt || ''
  }

  const uid = getCurrentUserId()
  const saved = await getCollectorImage(uid, 'tongue')
  if (saved) {
    state.file = saved
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl)
    state.previewUrl = URL.createObjectURL(saved)
  }
})

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return

  // 用户选择新舌苔图：清掉旧的 pending（否则可能继续使用上一次缓存的舌苔报告/recordId）
  clearPendingTongue()
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl)
  state.file = file
  state.previewUrl = URL.createObjectURL(file)
  void saveCollectorImage(getCurrentUserId(), 'tongue', file)
  error.value = ''
  success.value = ''
  aiReport.value = ''
  analyzedAt.value = ''
}

async function onProcess() {
  error.value = ''
  success.value = ''
  aiReport.value = ''
  analyzedAt.value = ''

  const pendingPosture = getPendingPosture()
  if (!pendingPosture) {
    error.value = '请先完成体态分析，再进行舌苔上传。'
    return
  }

  if (!state.file) {
    error.value = '请先上传舌苔图片'
    return
  }

  const userId = getCurrentUserId()
  const nowIso = new Date().toISOString()
  const metaPayload = {
    userId,
    age: Number(profile.value.age || 0),
    gender: profile.value.gender || 'male',
    height: Number(profile.value.height || 0),
    weight: Number(profile.value.weight || 0),
    allergyHistory:
      (profile.value.allergyHistory && String(profile.value.allergyHistory).trim()) || null,
    medicalHistory: profile.value.medicalHistory || 'none',
    workHabit: profile.value.workHabit || 'normal',
    tcmTenQuestions: profile.value.tcmTenQuestions || null,
  }

  const formData = new FormData()
  formData.append('meta', new Blob([JSON.stringify(metaPayload)], { type: 'application/json' }))
  formData.append('userId', userId)
  formData.append('tongueImage', state.file, state.file.name)

  loading.value = true
  try {
    const tongueRes = await submitTongueData(formData)
    const tongueReport = tongueRes?.aiReport || tongueRes?.msg || '暂无舌苔报告'
    aiReport.value = tongueReport
    analyzedAt.value = nowIso

    savePendingTongue({
      createdAt: nowIso,
      report: tongueReport,
      raw: tongueRes,
    })

    success.value = '舌苔分析完成。请在页面底部生成联合报告。'
  } catch (err) {
    error.value = err.message || '处理失败，请检查后端接口'
  } finally {
    loading.value = false
  }
}

async function onGenerateJointReport() {
  jointError.value = ''
  success.value = ''

  const pendingPosture = getPendingPosture()
  if (!pendingPosture?.report) {
    jointError.value = '请先完成体态分析。'
    return
  }

  const storedTongue = getPendingTongue()
  const tongueReportText = (aiReport.value || storedTongue?.report || '').trim()
  if (!tongueReportText) {
    jointError.value = '请先完成舌苔分析。'
    return
  }

  const userId = getCurrentUserId()
  const tongueAt = storedTongue?.createdAt || analyzedAt.value || new Date().toISOString()

  const jointPayload = {
    userId,
    postureReport: pendingPosture.report || '',
    tongueReport: tongueReportText,
    postureAt: pendingPosture.createdAt || null,
    tongueAt,
    postureData: pendingPosture.raw || null,
    tongueData: storedTongue?.raw || null,
    tcmTenQuestions: profile.value.tcmTenQuestions || null,
  }

  jointLoading.value = true
  try {
    const draftCreatedAt = new Date().toISOString()
    const draftSourcePostureRecordId =
      pendingPosture?.recordId || jointPayload?.postureData?.recordId || jointPayload?.postureData?.record_id || null
    const draftSourceTongueRecordId = jointPayload?.tongueData?.recordId || jointPayload?.tongueData?.record_id || null
    const basicProfileSnapshot = {
      age: profile.value.age,
      gender: profile.value.gender,
      height: profile.value.height,
      weight: profile.value.weight,
      allergyHistory:
        (profile.value.allergyHistory && String(profile.value.allergyHistory).trim()) || '无过敏史',
      medicalHistory: profile.value.medicalHistory,
      workHabit: profile.value.workHabit,
    }
    const tcmSnapshot = profile.value.tcmTenQuestions || jointPayload.tcmTenQuestions || null

    saveLatestJointReport({
      id: `pending-${Date.now()}`,
      createdAt: draftCreatedAt,
      type: 'joint',
      analysisType: 'joint',
      isGenerating: false,
      generationError: '',
      sourcePostureRecordId: draftSourcePostureRecordId,
      sourceTongueRecordId: draftSourceTongueRecordId,
      postureReport: jointPayload.postureReport,
      tongueReport: jointPayload.tongueReport,
      report: '',
      summary: '',
      postureData: jointPayload.postureData || null,
      basicProfile: basicProfileSnapshot,
      tcmTenQuestions: tcmSnapshot,
    })

    success.value = '已进入综合报告页，请点击「常规分析」开始生成。'
    await router.push('/joint-report')
  } catch (err) {
    jointError.value = err.message || '进入综合报告页失败，请检查后端接口'
  } finally {
    jointLoading.value = false
  }
}

onUnmounted(() => {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl)
})
</script>

<template>
  <section class="page-wrap">
    <TopNav active="collector" />

    <main class="tongue-main">
      <div class="content two-col">
        <section class="card left-panel">
          <h2>舌苔图片上传</h2>
          <p class="muted">
            需已在「数据收集」完成体态分析。本页上传的舌苔图会保存在本机，离开再回来仍会显示预览。
          </p>

          <label class="upload-label">
            舌苔图片
            <input type="file" accept="image/*" @change="onFileChange" />
          </label>

          <div class="preview-wrap">
            <img v-if="state.previewUrl" :src="state.previewUrl" alt="舌苔预览" />
            <div v-else class="empty">未上传图片</div>
          </div>

          <p v-if="error" class="error">{{ error }}</p>
          <p v-if="success" class="ok">{{ success }}</p>

          <button type="button" :disabled="loading" @click="onProcess">
            {{ loading ? '分析中...' : '开始舌苔分析' }}
          </button>

          <div class="joint-inline">
            <p v-if="jointError" class="error">{{ jointError }}</p>
            <button type="button" class="joint-btn-main" :disabled="jointLoading" @click="onGenerateJointReport">
              {{ jointLoading ? '生成中...' : '生成联合报告' }}
            </button>
            <p class="muted joint-hint">需先完成体态分析与上方舌苔分析。</p>
          </div>
        </section>

        <section class="card right-panel">
          <h2>舌苔报告</h2>
          <div v-if="aiReport" class="structured-wrap">
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
          <p v-else class="muted">等待后端返回舌苔报告</p>
        </section>
      </div>
    </main>
  </section>
</template>

<style scoped>
.page-wrap { min-height: 100vh; }
.tongue-main { padding: 16px; max-width: 1320px; margin: 0 auto; }
.content { padding: 0; }
.two-col { display: grid; grid-template-columns: 420px 1fr; gap: 14px; align-items: start; }
.left-panel, .right-panel { margin: 0; min-width: 0; overflow: hidden; }
.left-panel h2, .right-panel h2 { margin-top: 0; color: #1e293b; }
.upload-label { display: flex; flex-direction: column; gap: 6px; color: #334155; font-weight: 600; }
.preview-wrap { margin-top: 12px; width: 100%; height: 320px; }
.preview-wrap img, .empty { width: 100%; height: 320px; border-radius: 10px; }
.preview-wrap img { object-fit: contain; background: #f8fafc; border: 1px solid #cbd5e1; }
.empty { border: 1px dashed #cbd5e1; background: #fff; color: #94a3b8; display: flex; align-items: center; justify-content: center; }
.joint-inline {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #e2e8f0;
}
.joint-hint { margin: 8px 0 0; font-size: 13px; }
.joint-btn-main {
  margin-top: 8px;
  width: 100%;
  padding: 12px 16px;
  font-size: 15px;
  font-weight: 700;
  background: #0f766e;
  color: #f0fdfa;
  border-radius: 10px;
  border: none;
  cursor: pointer;
}
.joint-btn-main:disabled { opacity: 0.65; cursor: not-allowed; }
.report-text { margin: 0; line-height: 1.75; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; }

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
@media (max-width: 1100px) { .two-col { grid-template-columns: 1fr; } .preview-wrap, .preview-wrap img, .empty { height: 240px; } }
</style>

