<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, updateUserNickname } from '../services/api'
import { clearPendingForLogout } from '../services/reportStore'

const props = defineProps({
  active: {
    type: String,
    default: 'collector',
  },
})

const router = useRouter()
const showUserDialog = ref(false)
const userWrapRef = ref(null)
const displayName = ref('')
const nicknameSaving = ref(false)
const nicknameError = ref('')

const navItems = [
  { key: 'collector', label: '数据收集', route: '/posture' },
  { key: 'joint-report', label: '综合分析报告', route: '/joint-report' },
  { key: 'history', label: '历史记录与跟踪复查', route: '/history' },
  { key: 'demo-video', label: '演示视频', route: '/demo-video' },
]

const userId = computed(() => localStorage.getItem('mask_user_id') || 'admin')
const userName = computed(() => displayName.value || userId.value)
const avatarText = computed(() => String(userName.value).trim().slice(0, 1).toUpperCase() || 'A')
const nicknameInputPlaceholder = computed(() => {
  const uid = userId.value
  return `留空则与账号 ID「${uid}」一致`
})

function syncDisplayNameFromStorage() {
  const uid = userId.value
  displayName.value = localStorage.getItem('mask_display_name') || uid
}

function onDisplayNameChanged(ev) {
  const v = ev?.detail
  if (v) {
    displayName.value = v
  } else {
    syncDisplayNameFromStorage()
  }
}

async function refreshDisplayNameFromServer() {
  const uid = userId.value
  try {
    const res = await fetchProfile(uid)
    if (res?.success && res.nickname) {
      displayName.value = res.nickname
      localStorage.setItem('mask_display_name', res.nickname)
    } else {
      syncDisplayNameFromStorage()
    }
  } catch {
    syncDisplayNameFromStorage()
  }
}

async function onSaveNickname() {
  nicknameError.value = ''
  const uid = userId.value
  const raw = String(displayName.value || '').trim()
  nicknameSaving.value = true
  try {
    const res = await updateUserNickname({
      userId: uid,
      nickname: raw === '' || raw === uid ? null : raw,
    })
    if (!res?.success) {
      nicknameError.value = res?.message || '保存失败'
      return
    }
    const next = res.nickname || uid
    displayName.value = next
    localStorage.setItem('mask_display_name', next)
    window.dispatchEvent(new CustomEvent('mask-display-name-changed', { detail: next }))
  } catch (e) {
    nicknameError.value = e?.message || '保存失败'
  } finally {
    nicknameSaving.value = false
  }
}

function go(route) {
  if (router.currentRoute.value.path === route) return
  router.push(route)
}

function toggleUserDialog() {
  showUserDialog.value = !showUserDialog.value
}

function closeDialog() {
  showUserDialog.value = false
}

function logout() {
  clearPendingForLogout()
  localStorage.removeItem('mask_token')
  localStorage.removeItem('mask_user_id')
  localStorage.removeItem('mask_display_name')
  closeDialog()
  router.push('/login')
}

function onDocClick(event) {
  if (!showUserDialog.value) return
  if (!userWrapRef.value?.contains(event.target)) {
    closeDialog()
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    closeDialog()
  }
}

onMounted(() => {
  syncDisplayNameFromStorage()
  refreshDisplayNameFromServer()
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
  window.addEventListener('mask-display-name-changed', onDisplayNameChanged)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('mask-display-name-changed', onDisplayNameChanged)
})
</script>

<template>
  <header class="topbar">
    <div class="left-actions">
      <button
        v-for="item in navItems"
        :key="item.key"
        type="button"
        class="nav-btn"
        :class="{ active: item.key === active }"
        :title="item.label"
        @click="go(item.route)"
      >
        {{ item.label }}
      </button>
    </div>

    <div ref="userWrapRef" class="right-user">
      <button type="button" class="avatar-btn" @click="toggleUserDialog">
        <span class="avatar">{{ avatarText }}</span>
        <span class="name">{{ userName }}</span>
      </button>

      <div v-if="showUserDialog" class="user-dialog">
        <p class="dialog-title">当前用户</p>
        <p class="dialog-sub">账号 {{ userId }}</p>
        <label class="nick-label">昵称</label>
        <input v-model.trim="displayName" type="text" class="nick-input" :placeholder="nicknameInputPlaceholder" />
        <p v-if="nicknameError" class="nick-err">{{ nicknameError }}</p>
        <button
          type="button"
          class="save-nick-btn"
          :disabled="nicknameSaving"
          @click="onSaveNickname"
        >
          {{ nicknameSaving ? '保存中...' : '保存昵称' }}
        </button>
        <button type="button" class="logout-btn" @click="logout">退出登录</button>
        <button type="button" class="close-btn" @click="closeDialog">关闭</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid #dbe4f1;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(6px);
}

.left-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.nav-btn {
  margin: 0;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #334155;
  border-radius: 10px;
  padding: 8px 12px;
  font-weight: 600;
  flex-shrink: 0;
  white-space: normal;
  text-align: center;
  max-width: min(100%, 22rem);
}

.nav-btn.active {
  border-color: #2563eb;
  background: #dbeafe;
  color: #1e3a8a;
}

.right-user {
  position: relative;
}

.avatar-btn {
  margin: 0;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #1f2937;
  border-radius: 999px;
  padding: 4px 10px 4px 6px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #2563eb;
  color: #eff6ff;
  font-weight: 800;
}

.name {
  font-size: 14px;
  font-weight: 700;
}

.user-dialog {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: 220px;
  border: 1px solid #dbe4f1;
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.15);
}

.dialog-title {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}

.dialog-sub {
  margin: 0 0 8px;
  font-size: 12px;
  color: #64748b;
  word-break: break-all;
}

.nick-label {
  display: block;
  margin: 8px 0 4px;
  font-size: 12px;
  color: #64748b;
}

.nick-input {
  width: 100%;
  box-sizing: border-box;
  margin: 0 0 6px;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
}

.nick-err {
  margin: 0 0 8px;
  font-size: 12px;
  color: #b91c1c;
}

.save-nick-btn {
  width: 100%;
  margin: 0 0 8px;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #eff6ff;
  font-weight: 600;
  cursor: pointer;
}

.save-nick-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.logout-btn,
.close-btn {
  width: 100%;
  margin: 0;
}

.logout-btn {
  background: #dc2626;
  color: #fff1f2;
}

.close-btn {
  margin-top: 8px;
  background: #e2e8f0;
  color: #1f2937;
}

@media (max-width: 980px) {
  .topbar {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
    padding-top: 10px;
    padding-bottom: 10px;
  }

  .right-user {
    align-self: flex-end;
  }
}
</style>
