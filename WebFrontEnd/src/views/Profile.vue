<script setup>
import { onMounted, reactive, ref } from 'vue'
import TopNav from '../components/TopNav.vue'
import { tcmQuestionDefs } from '../constants/tcmAndProfileLabels'
import { fetchProfile, saveProfile, saveTcmTenQuestions, updateProfile } from '../services/api'

const loading = ref(false)
const tcmSaving = ref(false)
const notice = ref('')
const noticeType = ref('ok')
/** 中医十问保存提示，单独显示在十问卡片内，避免占用个人信息区的 notice */
const tcmNotice = ref('')
const tcmNoticeType = ref('ok')

const form = reactive({
  age: '',
  gender: 'male',
  height: '',
  weight: '',
  allergyHistory: '',
  medicalHistory: 'none',
  workHabit: 'normal',
  tcmTenQuestions: {
    coldHeat: 'neutral',
    sweat: 'normal',
    sleep: 'normal',
    appetite: 'normal',
    stool: 'normal',
    urination: 'normal',
    emotion: 'stable',
    energy: 'normal',
    thirst: 'normal',
    pain: 'none',
  },
  tcmTenQuestionOthers: {
    coldHeat: '',
    sweat: '',
    sleep: '',
    appetite: '',
    stool: '',
    urination: '',
    emotion: '',
    energy: '',
    thirst: '',
    pain: '',
  },
})

function setNotice(type, text) {
  noticeType.value = type
  notice.value = text
}

function setTcmNotice(type, text) {
  tcmNoticeType.value = type
  tcmNotice.value = text
}

function getCurrentUserId() {
  return localStorage.getItem('mask_user_id') || 'admin'
}

function getProfileKey() {
  return `mask_profile_${getCurrentUserId()}`
}

function readLocalProfileCache() {
  try {
    return JSON.parse(localStorage.getItem(getProfileKey()) || '{}')
  } catch {
    return {}
  }
}

function applyProfile(profile) {
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

/** 仅含后端 user_profiles 字段（中医十问随每次分析写入 assessment_records，由本地缓存带到上传流程） */
function buildApiPayload() {
  return {
    userId: getCurrentUserId(),
    age: form.age === '' ? null : Number(form.age),
    gender: form.gender || null,
    height: form.height === '' ? null : Number(form.height),
    weight: form.weight === '' ? null : Number(form.weight),
    allergyHistory: (form.allergyHistory || '').trim() || null,
    medicalHistory: form.medicalHistory || null,
    workHabit: form.workHabit || null,
  }
}

function buildLocalProfileSnapshot() {
  return {
    ...buildApiPayload(),
    tcmTenQuestions: buildTcmTenQuestionsPayload(),
  }
}

async function loadProfile() {
  loading.value = true
  setTcmNotice('ok', '')
  try {
    const userId = getCurrentUserId()
    const res = await fetchProfile(userId)
    if (res?.success && res?.profile) {
      applyProfile({ ...res.profile, tcmTenQuestions: readLocalProfileCache().tcmTenQuestions })
      localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
      setNotice('ok', '已加载数据库中的个人信息。')
      return
    }

    const raw = localStorage.getItem(getProfileKey())
    if (raw) {
      const localData = JSON.parse(raw)
      applyProfile(localData)
      setNotice('warn', '数据库暂无记录，已加载本地缓存。')
    } else {
      setNotice('warn', '当前账号还没有上传个人信息。')
    }
  } catch {
    const raw = localStorage.getItem(getProfileKey())
    if (raw) {
      const localData = JSON.parse(raw)
      applyProfile(localData)
      setNotice('warn', '个人信息接口暂不可用，已加载本地缓存。')
    } else {
      setNotice('error', '个人信息接口暂不可用，请稍后重试。')
    }
  } finally {
    loading.value = false
  }
}

async function onUpload() {
  loading.value = true
  setNotice('ok', '')
  setTcmNotice('ok', '')
  try {
    const payload = buildApiPayload()
    const res = await saveProfile(payload)
    if (!res?.success) {
      setNotice('error', res?.message || '上传失败，请稍后重试。')
      return
    }

    if (res.profile) {
      applyProfile({ ...res.profile, tcmTenQuestions: buildTcmTenQuestionsPayload() })
      localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    } else {
      localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    }
    setNotice('ok', res?.message || '上传成功。')
  } catch (err) {
    setNotice('error', err.message || '上传失败，请检查后端接口。')
  } finally {
    loading.value = false
  }
}

async function onUpdate() {
  loading.value = true
  setNotice('ok', '')
  setTcmNotice('ok', '')
  try {
    const payload = buildApiPayload()
    const res = await updateProfile(payload)
    if (!res?.success) {
      setNotice('error', res?.message || '修改失败，请稍后重试。')
      return
    }

    if (res.profile) {
      applyProfile({ ...res.profile, tcmTenQuestions: buildTcmTenQuestionsPayload() })
      localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    } else {
      localStorage.setItem(getProfileKey(), JSON.stringify(buildLocalProfileSnapshot()))
    }
    setNotice('ok', res?.message || '修改成功。')
  } catch (err) {
    setNotice('error', err.message || '修改失败，请检查后端接口。')
  } finally {
    loading.value = false
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

onMounted(loadProfile)
</script>

<template>
  <section class="page-wrap">
    <TopNav active="collector" />

    <main class="content">
      <div class="profile-layout">
        <section class="profile-block">
        <h2>个人信息填写</h2>
        <p class="muted">同一账号只需上传一次，后续按需修改即可。</p>

        <div class="grid-form">
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
          <button type="button" class="btn-upload" :disabled="loading" @click="onUpload">
            {{ loading ? '处理中...' : '上传个人数据' }}
          </button>
          <button type="button" class="btn-update" :disabled="loading" @click="onUpdate">
            {{ loading ? '处理中...' : '修改个人数据' }}
          </button>
        </div>

        <p
          v-if="notice"
          class="profile-notice"
          :class="noticeType === 'error' ? 'error' : noticeType === 'warn' ? 'warn' : 'ok'"
        >
          {{ notice }}
        </p>
        </section>

        <section class="profile-block tcm-block">
        <h3 class="tcm-title">中医十问</h3>
        <div class="grid-form tcm-grid">
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

        <div class="tcm-save-row">
          <button type="button" class="btn-tcm-save" :disabled="loading || tcmSaving" @click="onSaveTcmTen">
            {{ tcmSaving ? '保存中...' : '保存中医十问到数据库' }}
          </button>
          <span class="muted hint">写入一条评估记录，可在历史记录中查看；进行体态/舌苔分析时也会再次随请求保存。</span>
        </div>

        <p
          v-if="tcmNotice"
          class="tcm-notice"
          :class="tcmNoticeType === 'error' ? 'error' : tcmNoticeType === 'warn' ? 'warn' : 'ok'"
        >
          {{ tcmNotice }}
        </p>
        </section>
      </div>
    </main>
  </section>
</template>

<style scoped>
.page-wrap {
  min-height: 100vh;
}

.content {
  padding: 18px;
}

.profile-layout {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.profile-block {
  background: rgba(255, 255, 255, 0.92);
  border-radius: 14px;
  padding: 20px 22px;
  box-shadow: 0 8px 24px rgba(2, 6, 23, 0.08);
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.profile-block h2,
.profile-block .tcm-title {
  font-size: 1.5em;
  font-weight: 600;
  color: #1e293b;
}

.profile-block h2 {
  margin-top: 0;
}

.profile-notice {
  margin: 10px 0 0;
}

.tcm-notice {
  margin: 12px 0 0;
}

.tcm-block .tcm-title {
  margin: 0 0 12px;
}

.tcm-save-row {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.tcm-save-row .hint {
  flex: 1;
  min-width: 200px;
  font-size: 13px;
  line-height: 1.45;
}

.btn-tcm-save {
  margin: 0;
  min-width: 200px;
  background: #0d9488;
  color: #f0fdfa;
  font-weight: 600;
}

.grid-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 14px;
}

.tcm-grid {
  grid-template-columns: repeat(2, minmax(260px, 1fr));
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
}

.btn-upload,
.btn-update {
  margin: 0;
  min-width: 140px;
}

.btn-upload {
  background: #0f766e;
  color: #f0fdfa;
}

.btn-update {
  background: #2563eb;
  color: #eff6ff;
}

@media (max-width: 900px) {
  .content {
    padding: 12px;
  }

  .grid-form {
    grid-template-columns: 1fr;
  }

  .action-row {
    flex-direction: column;
  }
}
</style>

