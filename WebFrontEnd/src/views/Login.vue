<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '../services/api'
import brandLogo from '../materials/logo.png'
/** 全页背景图：文件放在 `src/materials/background.jpg`（或改名为 .jpg 与这里一致） */
import pageBackground from '../materials/background2.png'
/** 核心功能与亮点卡片配图（五张各不相同，可换成自己的图） */
import featureCoverBody from '../materials/renti.png'
import featureCoverTcm from '../materials/zhongyi.png'
import featureCoverMulti from '../materials/multiDim.png'
import featureCoverAgents from '../materials/multiAI.png'
import featureCoverTrend from '../materials/fangbian.png'
import overviewChartImg from '../materials/chart.png'
import overviewPolicyImg from '../materials/policy.png'
/** 登录页仅展示：与演示页「满血原版」同源 */
import fullVersionVideoSrc from '../materials/demo1.mp4'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const success = ref('')
const authMode = ref('login')
const accountInputRef = ref(null)
const agreedNotice = ref(false)
const showNoticeDialog = ref(false)

/** 首屏与顶栏主标题（顶栏副标题为 projectSubtitle） */
const heroTitle = '观形智衡'
/** 页脚一行文案（独立维护） */
const footerLine = '观形智衡 · 多维数据驱动的肥胖与体态管理智能助手'
const projectSubtitle = '多维数据驱动的肥胖与体态管理智能助手'
const heroDescription = '基于视觉分析算法 | 搭建多智能体协同流程 | 实现体态识别、健康评估与趋势跟踪'

/**
 * 核心功能与亮点：一行五卡。
 * coverImage：标题上方配图，每项对应独立 import。
 * bullets：分点；有 head 为小标题，body 为说明。
 */
const coreFeatures = [
  {
    title: '体态数据分析',
    coverImage: featureCoverBody,
    bullets: [
      { head: '视觉算法', body: '自动分析提取体型体态指标。' },
      { head: '体态画像', body: '全方位构建体态画像——脂肪分布结构、体态问题等。' },
      { head: '隐私保护', body: '处理图像前自动面部打码，保护用户隐私。' },
    ],
  },
  {
    title: '中医知识辩证',
    coverImage: featureCoverTcm,
    bullets: [
      { head: '中医体质分析', body: '中医十问 + 舌苔信息，从中医角度全方位评估体质。' },
      { head: '中医对肥胖的认知', body: '肥胖乃脏腑功能失调、痰湿瘀滞、气血阴阳失衡所导致。' },
      { head: '「阳化气，阴成形」', body: '肥胖本质是阴邪积聚，阳气不足。' },
    ],
  },
  {
    title: '多维度协同分析 & 建议',
    coverImage: featureCoverMulti,
    bullets: [
      { head: '中西医结合', body: '体态指标 + 中医辩证，多维度、全方位分析体态体质问题与成因。' },
      { head: '多维可行建议', body: '饮食、作息、锻炼...提供全面可行建议。' },
    ],
  },
  {
    title: '多智能体协同分析',
    coverImage: featureCoverAgents,
    bullets: [
      { head:'多智能体各司其职', body: '智能体分工协作，基于不同的知识库，对不同维度数据进行整合分析。' },
      { head:'内置专家模式', body: '一键开启专家模式，迭代优化各智能体分析与建议，得到更加详细专业的分析。' },
      { head:'统筹智能体', body: '设置统筹智能体，统筹各智能体的调用进程，评估各专项智能体的输出、提供优化建议。' },
    ],
  },
  {
    title: '便捷的持续跟踪与复查',
    coverImage: featureCoverTrend,
    bullets: [
      { head:'低成本持续监测', body: '支持阶段性记录与健康数据对比，观察变化趋势，便于复查与长期管理，形成闭环。' },
      { head:'历史分析记录复查', body: '分析过去的分析报告，结合健康变化情况，提供针对性的分析与可持续性建议。' },
    ],
  },
]

const processSteps = [
  {
    title: '基本数据建档',
    lines: ['填写基本信息', '回答中医十问'],
  },
  {
    title: '分析体型体态',
    lines: ['上传正面/侧面影像', '检测关键点' ,'分割人体掩码', '计算体态/体型指标'],
  },
  {
    title: '分析中医体质',
    lines: ['上传舌苔图像', '结合中医十问，辩证分析体质'],
  },
  {
    title: '生成体态报告',
    lines: [
      '接收用户个性化需求',
      '生成综合分析报告（含常规与专家深度分析）',
      '提供全方位可行性建议',
      '提供专家深度分析进阶功能',
    ],
  },
  {
    title: '持续跟踪复查',
    lines: ['分析历史分析报告', '监测体态指标与体质变化', '提供长期化动态建议'],
  },
]

const techTags = [
  '专注肥胖问题与体型管理',
  '视觉分析驱动',
  '多维度数据协同分析',
  '多智能体协同分析',
  '专家深度分析迭代优化',
  '定制化分析与建议',
  '中西医结合',
]

const form = reactive({
  account: '',
  password: '',
  nickname: '',
})

/** 用户须知 PDF：放在项目根目录 `Mask-Project/agreement.pdf` */
const noticePdfSrc = new URL('../../agreement.pdf', import.meta.url).href

function scrollToSection(sectionId) {
  const target = document.getElementById(sectionId)
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function switchMode(mode) {
  authMode.value = mode
  error.value = ''
  success.value = ''
}

function openNoticeDialog() {
  showNoticeDialog.value = true
}

function closeNoticeDialog() {
  showNoticeDialog.value = false
}

async function onSubmit() {
  error.value = ''
  success.value = ''

  if (!agreedNotice.value) {
    error.value = '请先勾选“我已阅读用户须知”'
    return
  }

  if (!form.account || !form.password) {
    error.value = '请输入账号和密码'
    return
  }

  loading.value = true
  try {
    const payload = {
      account: form.account.trim(),
      password: form.password,
    }

    if (authMode.value === 'login' && payload.account === 'admin' && payload.password === '123456') {
      localStorage.setItem('mask_token', 'debug-admin-token')
      localStorage.setItem('mask_user_id', 'admin')
      localStorage.setItem('mask_display_name', 'admin')
      await router.push('/posture')
      return
    }

    if (authMode.value === 'register') {
      const nn = form.nickname.trim()
      const res = await register({
        ...payload,
        ...(nn ? { nickname: nn } : {}),
      })
      if (!res?.success) {
        error.value = res?.message || '创建账号失败'
        return
      }
      success.value = '账号创建成功，请登录'
      authMode.value = 'login'
      form.password = ''
      return
    }

    const res = await login(payload)
    if (!res?.success) {
      error.value = res?.message || '账号或密码错误'
      return
    }

    localStorage.setItem('mask_token', res.token || `mask-token-${payload.account}`)
    localStorage.setItem('mask_user_id', res.userId || payload.account)
    if (res.nickname) {
      localStorage.setItem('mask_display_name', res.nickname)
    } else {
      localStorage.removeItem('mask_display_name')
    }
    await router.push('/posture')
  } catch (err) {
    error.value = err.message || '请求失败，请检查后端服务'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="login-page" :style="{ '--login-page-bg-image': `url(${pageBackground})` }">
    <header class="top-nav intro-flow intro-1">
      <div class="brand-cluster">
        <img class="brand-logo" :src="brandLogo" width="56" height="56" :alt="`${heroTitle} logo`" />
        <div class="brand-text-stack">
          <p class="brand-main">{{ heroTitle }}</p>
          <p class="brand-sub">{{ projectSubtitle }}</p>
        </div>
      </div>
      <nav class="nav-actions" aria-label="页面导航">
        <button type="button" class="nav-item" @click="scrollToSection('login-demo-video-section')">演示视频</button>
        <button type="button" class="nav-item" @click="scrollToSection('overview-section')">概述与背景</button>
        <button type="button" class="nav-item" @click="scrollToSection('feature-section')">核心功能与亮点</button>
        <button type="button" class="nav-item" @click="scrollToSection('process-section')">体态分析流程</button>
        <button type="button" class="nav-item" @click="scrollToSection('team-section')">团队详情&amp;联系我们</button>
      </nav>
    </header>

    <div class="landing-body">
      <div class="landing-parallel">
        <section id="hero-section" class="hero intro-flow intro-2">
          <h1 class="main-title">{{ heroTitle }}</h1>
          <p class="sub-title">{{ projectSubtitle }}</p>
          <hr class="hero-sub-rule" aria-hidden="true" />
          <p class="hero-desc">{{ heroDescription }}</p>
          <div class="hero-tech">
            <div class="hero-tag-list">
              <span v-for="tag in techTags" :key="tag" class="hero-tech-tag">{{ tag }}</span>
            </div>
          </div>
        </section>

        <aside id="login-panel" class="landing-parallel__aside" aria-label="登录与注册">
        <div class="login-panel">
          <h3>{{ authMode === 'login' ? '账号登录' : '创建账号' }}</h3>
          <p class="panel-muted">{{ authMode === 'login' ? '登录后进入系统首页' : '创建成功后请使用新账号登录' }}</p>

          <div class="auth-switch">
            <button type="button" :class="['switch-btn', { active: authMode === 'login' }]" @click="switchMode('login')">
              登录
            </button>
            <button
              type="button"
              :class="['switch-btn', { active: authMode === 'register' }]"
              @click="switchMode('register')"
            >
              创建账号
            </button>
          </div>

          <form @submit.prevent="onSubmit">
            <label>账号</label>
            <input
              ref="accountInputRef"
              v-model.trim="form.account"
              type="text"
              :placeholder="authMode === 'login' ? '公用账号admin' : '请输入账号'"
              autocomplete="username"
            />

            <label>密码</label>
            <input
              v-model="form.password"
              type="password"
              :placeholder="authMode === 'login' ? '公用账号密码123456' : '请设置密码'"
              autocomplete="current-password"
            />

            <template v-if="authMode === 'register'">
              <label>昵称（可选）</label>
              <input v-model.trim="form.nickname" type="text" placeholder="不填则与账号相同" autocomplete="nickname" />
            </template>

            <p v-if="error" class="error">{{ error }}</p>
            <p v-if="success" class="success">{{ success }}</p>
            <button :disabled="loading || !agreedNotice" type="submit">
              {{
                loading
                  ? authMode === 'login'
                    ? '登录中...'
                    : '创建中...'
                  : authMode === 'login'
                    ? '登录'
                    : '创建账号'
              }}
            </button>
          </form>

          <div class="panel-footer">
            <label class="notice-agree">
              <input v-model="agreedNotice" type="checkbox" />
              <span>我已阅读</span>
              <button type="button" class="notice-link" @click="openNoticeDialog">用户须知</button>
            </label>
          </div>
        </div>
        </aside>
      </div>

      <div class="landing-centered">
        <section id="overview-section" class="overview-section intro-flow intro-3">
          <h3>概述与背景</h3>
          <div class="overview-grid">
            <div class="overview-col overview-col--pain">
              <article class="overview-card">
                <p class="overview-card__q">
                  <span class="overview-emoji" aria-hidden="true">😢</span>
                  <strong class="text-warn">不知如何评估</strong>肥胖与体态；去医院不便，<strong class="text-warn">缺乏便捷评估工具</strong>？
                </p>
                <p class="overview-card__a">
                  <span class="overview-emoji" aria-hidden="true">😊</span>
                  便捷的肥胖与体态改善助手；<strong class="text-ok">仅需数分钟</strong>上传数据，在家即可获得科学体态分析！
                </p>
              </article>
              <article class="overview-card">
                <p class="overview-card__q">
                  <span class="overview-emoji" aria-hidden="true">🤔</span>
                  在家只有 <strong class="text-warn">BMI 单一指标</strong> 评估体型？
                </p>
                <p class="overview-card__a">
                  <span class="overview-emoji" aria-hidden="true">😎</span>
                  视觉体型体态指标 + 舌苔评估 + 中医问诊；<strong class="text-ok">多维度评估</strong>体型与中医体质！
                </p>
              </article>
              <article class="overview-card">
                <p class="overview-card__q">
                  <span class="overview-emoji" aria-hidden="true">😢</span>
                  不知如何<strong class="text-warn">改善</strong>肥胖与体态？
                </p>
                <p class="overview-card__a">
                  <span class="overview-emoji" aria-hidden="true">🤔</span>
                  多智能体协同，结合各领域知识分析；提供<strong class="text-ok">科学、全面且可持续可行</strong>的建议！
                </p>
              </article>
            </div>

            <div class="overview-col overview-col--stats">
              <div class="overview-col-head overview-col-head--stats">
                <span class="overview-col-icon overview-col-icon--chart" aria-hidden="true">📊</span>
                <h4 class="overview-col-title">中国肥胖状况不容乐观</h4>
              </div>
              <div class="overview-chart">
                <img
                  class="overview-chart__img"
                  :src="overviewChartImg"
                  alt="中国成年人肥胖率折线图（1991—2020）"
                  loading="lazy"
                />
              </div>
              <ul class="overview-bullets">
                <li>
                  《柳叶刀·糖尿病与内分泌学》研究指出，30 年间肥胖率增长<strong class="text-warn">超过 4 倍</strong>。
                </li>
                <li>
                  肥胖是心血管、糖尿病、癌症等<strong class="text-warn">慢性疾病</strong>的<strong class="text-warn">首要危险因素</strong>。
                </li>
              </ul>
            </div>

            <div class="overview-col overview-col--policy">
              <div class="overview-col-head overview-col-head--policy">
                <span class="overview-col-icon overview-col-icon--gov" aria-hidden="true">🏛️</span>
                <h4 class="overview-col-title">肥胖问题列入国家战略</h4>
              </div>
              <div class="overview-press-visual">
                <img
                  class="overview-press-img"
                  :src="overviewPolicyImg"
                  alt="健康中国行动（2019—2030）新闻发布会现场"
                  loading="lazy"
                />
              </div>
              <ul class="overview-bullets">
                <li>
                  肥胖已从个人健康问题上升为<strong class="text-warn">【国家公共卫生战略】</strong>层面。
                </li>
                <li>
                  国家印发《健康中国行动（2019—2030）》，将健康体重列为<strong class="text-warn">15 项重大专项行动</strong>之一。
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section id="feature-section" class="feature-section intro-flow intro-4">
          <h3>核心功能与亮点</h3>
          <div class="feature-grid">
            <article v-for="item in coreFeatures" :key="item.title" class="feature-card">
              <div class="feature-card__media">
                <img
                  v-if="item.coverImage"
                  class="feature-card__img"
                  :src="item.coverImage"
                  :alt="`${item.title} 配图`"
                  loading="lazy"
                />
                <div v-else class="feature-card__media-placeholder" aria-hidden="true"></div>
              </div>
              <h4>{{ item.title }}</h4>
              <div class="feature-card__bullets">
                <div v-for="(b, i) in item.bullets" :key="i" class="feature-bullet">
                  <p v-if="b.head" class="feature-bullet__head">{{ b.head }}</p>
                  <p class="feature-bullet__body">{{ b.body }}</p>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section id="process-section" class="process-section intro-flow intro-5">
          <h3>体态分析流程</h3>
          <div class="process-strip-list">
            <div
              v-for="(step, index) in processSteps"
              :key="step.title"
              class="process-strip-block"
            >
              <article class="process-strip">
                <div class="process-strip__left">
                  <span class="process-strip__index">{{ String(index + 1).padStart(2, '0') }}</span>
                  <h4 class="process-strip__title">{{ step.title }}</h4>
                </div>
                <ul class="process-strip__right">
                  <li v-for="(line, i) in step.lines" :key="i" class="process-strip__seg">{{ line }}</li>
                </ul>
              </article>
              <div
                v-if="index < processSteps.length - 1"
                class="process-strip-join"
                aria-hidden="true"
              >
                <svg
                  class="process-strip-join__v"
                  viewBox="0 0 40 12"
                  xmlns="http://www.w3.org/2000/svg"
                  focusable="false"
                >
                  <path
                    d="M4 2.5 L20 9 L36 2.5"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="4.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </div>
            </div>
          </div>
        </section>
      </div>

      <section id="login-demo-video-section" class="login-demo-video-section intro-flow intro-6">
        <h3>满血原版操作演示</h3>
        <p class="login-demo-video-desc">完整功能下的系统操作流程（与登录后「演示 & 评委必看」中满血原版视频同源）。</p>
        <div class="login-demo-video-frame">
          <video
            class="login-demo-video-el"
            controls
            playsinline
            preload="metadata"
            :src="fullVersionVideoSrc"
          >
            您的浏览器不支持视频播放。
          </video>
        </div>
      </section>

      <section id="team-section" class="team-section intro-flow intro-7">
        <h3>团队详情&amp;联系我们</h3>
        <div class="team-section__card">
          <p class="team-section__lead">
            「观形智衡」背靠武汉大学遥感信息工程学院，团队成员研究背景多样化；<br />
            项目精准切入中国日益严重的肥胖问题，以视觉分析处理为技术核心，创新性地将体态信息与中医辨证结合；<br />
            团队构建了多智能体协同流程，为用户提供便捷、科学全面的肥胖问题与体态管理的分析与建议。
          </p>
          <ul class="team-section__list">
            <li><span class="team-section__label">开发团队</span>武汉大学 观形智衡项目团队</li>
            <li><span class="team-section__label">项目负责人</span>张添翼</li>
            <li><span class="team-section__label">指导专家</span>姚永祥 万一</li>
            <li><span class="team-section__label">团队成员</span>杨子涵 周怡 侯子亦 任铭博</li>
            <li><span class="team-section__label">组织架构</span>视觉计算组/智能分析组/前端设计组</li>
            <li><span class="team-section__label">发布时间</span>2026年4月</li>
            <li>
              <span class="team-section__label">联系方式</span>
              <a class="team-section__mail" href="mailto:1096159060@qq.com">1096159060@qq.com</a>
            </li>
          </ul>
        </div>
      </section>
    </div>

    <footer class="page-footer intro-flow intro-8">
      <p>{{ footerLine }}</p>
    </footer>

    <div v-if="showNoticeDialog" class="notice-mask" @click.self="closeNoticeDialog">
      <article class="notice-dialog notice-dialog--pdf" @click.stop>
        <header class="notice-dialog-head">
          <h4>用户须知</h4>
          <div class="notice-dialog-actions">
            <a :href="noticePdfSrc" class="notice-open-tab" target="_blank" rel="noopener noreferrer">新窗口打开</a>
            <button type="button" class="notice-close-x" aria-label="关闭" @click="closeNoticeDialog">×</button>
          </div>
        </header>
        <iframe class="notice-pdf-frame" :src="noticePdfSrc" title="用户须知" />
        <button type="button" class="dialog-close-btn" @click="closeNoticeDialog">关闭</button>
      </article>
    </div>
  </section>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  color: #2f3e5b;
  --mh-title: #33435f;
  --mh-subtitle: #607394;
  --mh-body: #61728e;
  --mh-primary: #2dc466;
  --mh-primary-hover: #22b358;
  /* 白色半透明膜（统一调透明度改这里） */
  --film-pill: rgba(255, 255, 255, 0.82);
  --film-card: rgba(255, 255, 255, 0.92);
  --film-step: rgba(255, 255, 255, 0.9);
  /* 登录页「体态分析流程」长条：左右同色相，左侧为右侧 (#f0fdf4 系) 加深一档半 */
  --process-strip-left-bg: linear-gradient(160deg, #d1fae5 0%, #c4f3dd 48%, #b6efd4 100%);
  --process-strip-right-bg: rgba(240, 253, 244, 0.94);
  --process-strip-border: rgba(134, 239, 172, 0.32);
  /* 五条流程长条整体透明度：1 为完全不透明 */
  --process-strip-opacity: 0.75;
  --process-strip-join-color: #2f6a4a;
  --film-panel: rgba(255, 255, 255, 0.9);
  --film-switch: rgba(255, 255, 255, 0.88);
  --mh-surface: var(--film-card);
  --mh-surface-strong: rgba(255, 255, 255, 0.92);
  --mh-border: rgba(255, 255, 255, 0.55);
  --mh-glass-border: rgba(255, 255, 255, 0.65);
  /* 盖在背景照片上的白膜透明度：0 全透、1 全白；越大背景图越看不清 */
  --bg-film-opacity: 0.8;
  /* 底色：图片上下超出或不足时露底 */
  background-color: #c5d4e2;
  background-image:
    linear-gradient(
      165deg,
      rgb(255 255 255 / var(--bg-film-opacity)) 0%,
      rgb(236 241 247 / var(--bg-film-opacity)) 45%,
      rgb(210 222 234 / var(--bg-film-opacity)) 100%
    ),
    var(--login-page-bg-image);
  /* 渐变铺满；图片宽度始终 100% 视口（左右铺满），高度按比例，上下可多可少 */
  background-size: 100% 100%, 100% auto;
  background-position: 0 0, center top;
  background-attachment: fixed, fixed;
  background-repeat: no-repeat;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.top-nav {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  /* 左窄右略宽：Logo 更贴左缘 */
  padding: 12px clamp(14px, 3vw, 36px) 12px clamp(2px, 0.55vw, 10px);
  border-bottom: 1px solid rgba(51, 67, 95, 0.09);
  background-image:
    linear-gradient(180deg, rgb(255 255 255 / 0.42) 0%, transparent 48%),
    linear-gradient(
      122deg,
      rgb(214 245 228 / 0.88) 0%,
      rgb(255 255 255 / 0.72) 40%,
      rgb(228 238 252 / 0.82) 72%,
      rgb(210 230 246 / 0.78) 100%
    );
  background-color: rgb(255 255 255 / 0.25);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow:
    0 1px 0 rgb(255 255 255 / 0.55) inset,
    0 8px 28px rgb(40 60 90 / 0.08);
  overflow: visible;
}

.brand-cluster {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  flex: 1;
}

.brand-text-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
}

.brand-main {
  margin: 0;
  font-size: clamp(20px, 1.9vw, 26px);
  font-weight: 800;
  letter-spacing: 0.02em;
  color: var(--mh-title);
  line-height: 1.2;
}

.brand-sub {
  margin: 0;
  font-size: clamp(11px, 1vw, 13px);
  font-weight: 500;
  letter-spacing: 0.03em;
  color: var(--mh-subtitle);
  line-height: 1.4;
  max-width: min(26em, 100%);
  opacity: 0.92;
}

.brand-logo {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  object-fit: contain;
  display: block;
  transform: scale(1.8);
  transform-origin: center left;
  /* 在顶栏左 padding 已收窄基础上再略向左贴 */
  margin-left: clamp(-4px, -0.3vw, 0px);
  margin-right: calc(56px * (1.8 - 1));
}

.nav-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.nav-item {
  margin: 0;
  border: 0;
  padding: 8px 14px;
  border-radius: 999px;
  background: transparent;
  font-size: clamp(13px, 1.05vw, 15px);
  font-weight: 600;
  color: #3d4f5c;
  cursor: pointer;
  letter-spacing: 0.02em;
  transition:
    color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.nav-item:hover {
  color: #14532d;
  background: rgb(45 196 102 / 0.12);
  box-shadow: 0 0 0 1px rgb(45 196 102 / 0.15);
}

.nav-item:active {
  background: rgb(45 196 102 / 0.18);
}

.landing-body {
  width: min(1720px, calc(100% - 24px));
  margin: 0 auto;
  padding: clamp(36px, 7vh, 72px) 0 clamp(56px, 8vh, 96px);
  box-sizing: border-box;
}

/* 首屏+登录行向右“撑”到视口右缘：登录框贴屏幕右侧，左列吃掉中间空白 */
.landing-parallel {
  /* 登录区离屏幕右缘留白，勿贴死；想再宽就加大 40px */
  --login-edge: max(40px, calc(20px + env(safe-area-inset-right, 0px)));
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(480px, min(42vw, 620px));
  gap: clamp(20px, 2.5vw, 36px);
  align-items: start;
  box-sizing: border-box;
  width: calc(100% + (100vw - 100%) / 2 - var(--login-edge));
  max-width: none;
  margin-right: calc(-1 * ((100vw - 100%) / 2) + var(--login-edge));
}

.landing-parallel__aside {
  min-width: 0;
  width: 100%;
  justify-self: stretch;
}

.landing-centered {
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
}

.landing-centered .overview-section h3,
.landing-centered .feature-section h3,
.landing-centered .process-section h3,
.team-section h3 {
  text-align: center;
}

.landing-centered .feature-card {
  text-align: left;
}

.landing-centered .feature-card h4 {
  text-align: center;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  padding: clamp(24px, 5vh, 56px) 0 clamp(40px, 6vh, 72px);
  scroll-margin-top: 100px;
}

.main-title {
  margin: 0;
  font-size: clamp(48px, 7vw, 84px);
  line-height: 1.04;
  letter-spacing: -0.02em;
  color: var(--mh-title);
  font-weight: 900;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.75), 0 8px 28px rgba(255, 255, 255, 0.45);
}

.sub-title {
  margin: 22px 0 0;
  font-size: clamp(24px, 2.7vw, 36px);
  line-height: 1.3;
  color: var(--mh-subtitle);
  font-weight: 700;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.7);
}

.hero-sub-rule {
  border: none;
  width: 100%;
  max-width: 42em;
  height: 3px;
  margin: 20px 0 0;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    rgba(51, 67, 95, 0.45) 0%,
    rgba(51, 67, 95, 0.26) 65%,
    rgba(51, 67, 95, 0.1) 100%
  );
}

.hero-desc {
  margin: 18px 0 0;
  max-width: 42em;
  color: var(--mh-body);
  font-size: clamp(15px, 1.25vw, 19px);
  line-height: 1.7;
}

.hero-tech {
  margin-top: 26px;
  width: 100%;
  max-width: min(760px, 100%);
}

.hero-tag-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 14px;
}

.hero-tech-tag {
  border-radius: 999px;
  border: 1.5px solid var(--mh-glass-border);
  background: var(--film-pill);
  box-shadow: 0 8px 22px rgba(40, 60, 90, 0.1);
  padding: 13px 22px;
  font-size: clamp(15px, 1.15vw, 17px);
  color: var(--mh-title);
  font-weight: 700;
  line-height: 1.35;
}

/* 与「体态分析流程」内 .process-strip-list 同宽：max-width min(1180px, 100%) */
.login-demo-video-section {
  box-sizing: border-box;
  width: 100%;
  max-width: min(1180px, 100%);
  margin: clamp(56px, 7vh, 96px) auto 0;
  scroll-margin-top: 110px;
  padding: clamp(20px, 2.4vw, 28px);
  border-radius: 16px;
  border: 1px solid rgba(51, 67, 95, 0.12);
  background: var(--film-card);
  box-shadow:
    0 10px 32px rgba(40, 60, 90, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.75);
}

.login-demo-video-section h3 {
  margin: 0 0 12px;
  font-size: clamp(28px, 3.4vw, 42px);
  color: var(--mh-title);
  text-align: center;
}

.login-demo-video-desc {
  margin: 0 auto 20px;
  max-width: 42em;
  text-align: center;
  font-size: clamp(14px, 1.15vw, 17px);
  color: var(--mh-body);
  line-height: 1.65;
}

.login-demo-video-frame {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(51, 67, 95, 0.16);
  background: #0f172a;
  aspect-ratio: 16 / 9;
  width: 100%;
}

.login-demo-video-el {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  vertical-align: top;
}

.overview-section {
  margin-top: clamp(104px, 13vh, 160px);
  scroll-margin-top: 110px;
}

.feature-section {
  margin-top: clamp(72px, 9vh, 110px);
  scroll-margin-top: 110px;
}

.process-section {
  margin-top: clamp(72px, 9vh, 110px);
  scroll-margin-top: 110px;
}

.overview-section h3,
.feature-section h3,
.process-section h3 {
  margin: 0 0 26px;
  font-size: clamp(28px, 3.4vw, 42px);
  color: var(--mh-title);
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.48fr) minmax(0, 0.76fr) minmax(0, 0.76fr);
  gap: clamp(14px, 1.8vw, 22px);
  width: 100%;
  align-items: stretch;
}

.overview-col {
  border-radius: 16px;
  padding: clamp(20px, 2.2vw, 28px);
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 左栏：与右侧两列同高，三张子卡片均分垂直空间 */
.overview-col--pain {
  align-self: stretch;
  min-height: 0;
  height: 100%;
  gap: 14px;
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.overview-col--pain .overview-card {
  border-radius: 12px;
  border: 1px solid rgb(100 116 139 / 0.18);
  background: rgb(255 255 255 / 0.88);
  box-shadow:
    0 4px 16px rgb(51 65 85 / 0.08),
    inset 0 1px 0 rgb(255 255 255 / 0.95);
  padding: clamp(12px, 1.25vw, 16px) clamp(14px, 1.35vw, 18px);
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

/* 中、右两栏：数据 / 政策面板 — 统一青绿系，与左栏区分 */
.overview-col--stats,
.overview-col--policy {
  border: 1px solid rgb(45 196 102 / 0.28);
  background: linear-gradient(
    165deg,
    rgb(236 253 245 / 0.96) 0%,
    rgb(255 255 255 / 0.92) 55%,
    rgb(240 253 249 / 0.9) 100%
  );
  box-shadow: 0 10px 30px rgb(16 120 90 / 0.1);
}

.overview-card {
  border-radius: 10px;
  border: 1px solid rgba(51, 67, 95, 0.1);
  background: rgba(255, 255, 255, 0.55);
  padding: clamp(14px, 1.4vw, 18px) clamp(14px, 1.5vw, 18px);
  font-size: clamp(15px, 1.2vw, 18px);
  line-height: 1.72;
  color: var(--mh-body);
  flex: 0 0 auto;
}

.overview-card__q {
  margin: 0 0 8px;
}

.overview-card__a {
  margin: 0;
  padding-top: 8px;
  border-top: 1px dashed rgba(51, 67, 95, 0.12);
}

.overview-emoji {
  margin-right: 6px;
  font-size: 1.1em;
  vertical-align: -0.1em;
}

.text-warn {
  color: #c23d3d;
  font-weight: 700;
  font-size: 1.45em;
}

.text-ok {
  color: #1d8f4a;
  font-weight: 700;
  font-size: 1.45em;
}

.overview-col-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.overview-col-head--stats {
  padding: 12px 8px;
  border-radius: 12px;
  width: 100%;
  box-sizing: border-box;
  justify-content: center;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
  text-align: center;
  background: linear-gradient(
    145deg,
    rgb(254 242 242 / 0.85) 0%,
    rgb(255 255 255 / 0.72) 55%,
    rgb(255 255 255 / 0.55) 100%
  );
  border: 1px solid rgb(220 80 80 / 0.2);
  border-top: 3px solid #d85454;
  box-shadow: 0 2px 12px rgb(220 80 80 / 0.08);
}

.overview-col-head--policy {
  padding: 12px 8px;
  border-radius: 12px;
  width: 100%;
  box-sizing: border-box;
  justify-content: center;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
  text-align: center;
  background: linear-gradient(
    145deg,
    rgb(236 253 245 / 0.95) 0%,
    rgb(255 255 255 / 0.75) 55%,
    rgb(255 255 255 / 0.55) 100%
  );
  border: 1px solid rgb(26 155 138 / 0.28);
  border-top: 3px solid #1a9b8a;
  box-shadow: 0 2px 12px rgb(26 155 138 / 0.1);
}

.overview-col-head--stats .overview-col-title,
.overview-col-head--policy .overview-col-title {
  font-size: clamp(18px, 1.5vw, 23px);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.25;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 0 1 auto;
  max-width: calc(100% - 1.75rem);
}

.overview-col-head--stats .overview-col-icon,
.overview-col-head--policy .overview-col-icon {
  flex-shrink: 0;
  font-size: 1.15em;
}

.overview-col-title {
  margin: 0;
  font-size: clamp(17px, 1.35vw, 21px);
  font-weight: 800;
  color: var(--mh-title);
  line-height: 1.4;
}

.overview-col-icon {
  font-size: 1.35em;
  line-height: 1;
}

.overview-chart {
  border-radius: 8px;
  border: 1px solid rgba(51, 67, 95, 0.06);
  background: rgba(255, 255, 255, 0.45);
  padding: 3px 4px 2px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.overview-chart__img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 175px;
  object-fit: contain;
  object-position: center;
  flex: 0 1 auto;
  min-height: 0;
}

.overview-bullets {
  margin: 0;
  padding-left: 1.2em;
  font-size: clamp(15px, 1.12vw, 17px);
  line-height: 1.72;
  color: var(--mh-body);
}

.overview-bullets li + li {
  margin-top: 12px;
}

.overview-press-visual {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(30, 77, 139, 0.25);
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.overview-press-img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 165px;
  object-fit: cover;
  object-position: center top;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: clamp(10px, 1.4vw, 18px);
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  align-items: stretch;
}

.feature-card {
  border-radius: 14px;
  border: 1px solid var(--mh-glass-border);
  background: var(--film-card);
  box-shadow: 0 8px 24px rgba(40, 55, 80, 0.08);
  padding: 12px 10px 14px;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.feature-card__media {
  flex-shrink: 0;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(51, 67, 95, 0.12);
  background: rgba(255, 255, 255, 0.45);
  aspect-ratio: 4 / 3;
  margin-bottom: 8px;
}

.feature-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.feature-card__media-placeholder {
  width: 100%;
  height: 100%;
  min-height: 48px;
  background: linear-gradient(145deg, rgba(230, 236, 232, 0.9) 0%, rgba(200, 218, 208, 0.55) 100%);
}

.feature-card h4 {
  margin: 0;
  font-size: clamp(15px, 1.15vw, 18px);
  line-height: 1.35;
  color: var(--mh-title);
  word-break: break-word;
}

.feature-card__bullets {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feature-bullet {
  padding: 10px 9px;
  border-radius: 8px;
  border: 1px solid rgba(51, 67, 95, 0.1);
  background: rgba(255, 255, 255, 0.35);
}

.feature-bullet__head {
  margin: 0;
  font-size: clamp(13px, 1.02vw, 15px);
  font-weight: 700;
  color: var(--mh-title);
  line-height: 1.45;
  word-break: break-word;
}

.feature-bullet__body {
  margin: 0;
  font-size: clamp(13px, 0.95vw, 15px);
  color: var(--mh-body);
  line-height: 1.6;
  word-break: break-word;
}

.feature-bullet__head + .feature-bullet__body {
  margin-top: 7px;
}

.process-strip-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  max-width: min(1180px, 100%);
  margin-left: auto;
  margin-right: auto;
}

.process-strip-block {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 2px;
}

.process-strip-join {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 11px;
  flex-shrink: 0;
  color: var(--process-strip-join-color);
  opacity: 1;
  pointer-events: none;
}

.process-strip-join__v {
  width: 30px;
  height: 9px;
  display: block;
}

.process-strip {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  width: 100%;
  min-width: 0;
  border-radius: 14px;
  border: 1px solid var(--process-strip-border);
  background: var(--process-strip-right-bg);
  box-shadow: 0 6px 20px rgba(52, 120, 90, 0.08);
  overflow: hidden;
  opacity: var(--process-strip-opacity);
}

.process-strip__left {
  flex: 0 1 auto;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  padding: 12px 12px 12px 16px;
  max-width: min(320px, 41vw);
  background: var(--process-strip-left-bg);
}

.process-strip__index {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 3rem;
  height: 3rem;
  padding: 0 8px;
  border-radius: 12px;
  font-size: clamp(24px, 2.8vw, 32px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
  box-shadow:
    0 3px 12px rgba(15, 118, 110, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.process-strip:nth-child(1) .process-strip__index {
  background: linear-gradient(145deg, #2dd4bf 0%, #0d9488 100%);
}

.process-strip:nth-child(2) .process-strip__index {
  background: linear-gradient(145deg, #60a5fa 0%, #2563eb 100%);
}

.process-strip:nth-child(3) .process-strip__index {
  background: linear-gradient(145deg, #a78bfa 0%, #6d28d9 100%);
}

.process-strip:nth-child(4) .process-strip__index {
  background: linear-gradient(145deg, #4ade80 0%, #16a34a 100%);
}

.process-strip:nth-child(5) .process-strip__index {
  background: linear-gradient(145deg, #fbbf24 0%, #d97706 100%);
}

.process-strip:nth-child(n + 6) .process-strip__index {
  background: linear-gradient(145deg, #94a3b8 0%, #475569 100%);
}

.process-strip__title {
  margin: 0;
  font-size: clamp(19px, 1.95vw, 23px);
  line-height: 1.3;
  font-weight: 700;
  color: #14532d;
}

.process-strip__right {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 12px 15px 12px 12px;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  align-content: center;
  gap: 10px 12px;
  background: var(--process-strip-right-bg);
}

.process-strip__seg {
  margin: 0;
  padding: 6px 14px;
  border-radius: 10px;
  border: 1px solid rgba(34, 197, 94, 0.28);
  background: rgba(255, 255, 255, 0.88);
  font-size: clamp(15px, 1.25vw, 17px);
  line-height: 1.6;
  color: #2a3d34;
  max-width: 100%;
}

.team-section {
  width: min(1720px, 100%);
  margin: clamp(40px, 5vh, 64px) auto 0;
  padding: 0;
  scroll-margin-top: 110px;
}

.team-section h3 {
  margin: 0 0 22px;
  font-size: clamp(28px, 3.4vw, 42px);
  color: var(--mh-title);
}

.team-section__card {
  border-radius: 16px;
  border: 1px solid var(--mh-glass-border);
  background: var(--film-card);
  box-shadow: 0 10px 32px rgba(40, 55, 80, 0.1);
  padding: clamp(22px, 3vw, 32px) clamp(20px, 3vw, 36px);
}

.team-section__lead {
  margin: 0 0 18px;
  font-size: clamp(15px, 1.2vw, 17px);
  line-height: 1.75;
  color: var(--mh-body);
}

.team-section__list {
  margin: 0;
  padding-left: 1.15rem;
  color: var(--mh-body);
  font-size: clamp(14px, 1.1vw, 16px);
  line-height: 1.7;
}

.team-section__list li {
  margin: 10px 0 0;
}

.team-section__list li:first-child {
  margin-top: 0;
}

.team-section__label {
  display: inline-block;
  min-width: 6em;
  font-weight: 700;
  color: var(--mh-title);
}

.team-section__mail {
  color: var(--mh-primary);
  font-weight: 600;
  text-decoration: none;
}

.team-section__mail:hover {
  text-decoration: underline;
  color: var(--mh-primary-hover);
}

.page-footer {
  padding: 36px 24px 42px;
  text-align: center;
  color: #3d4f66;
  font-size: 13px;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.65);
}

.page-footer p {
  margin: 0;
}

.login-panel {
  width: 100%;
  max-width: none;
  margin: 0;
  box-sizing: border-box;
  background: var(--film-panel);
  color: var(--mh-title);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 16px 48px rgba(35, 55, 85, 0.14);
  border: 1px solid var(--mh-glass-border);
}

.login-panel h3 {
  margin: 0;
  font-size: 34px;
}

.panel-muted {
  margin: 8px 0 14px;
  color: #647895;
}

.auth-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}

.switch-btn {
  height: 40px;
  margin: 0;
  border: 1px solid rgba(51, 67, 95, 0.18);
  border-radius: 10px;
  background: var(--film-switch);
  color: #647895;
  font-weight: 700;
}

.switch-btn.active {
  border-color: rgba(45, 196, 102, 0.45);
  color: #1b3e61;
  background: rgba(45, 196, 102, 0.28);
}

form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

label {
  font-size: 15px;
  font-weight: 600;
}

input {
  height: 44px;
  border-radius: 10px;
  border: 1px solid rgba(51, 67, 95, 0.2);
  padding: 0 12px;
  font-size: 15px;
  background: rgba(255, 255, 255, 0.72);
}

form button {
  margin-top: 8px;
  height: 48px;
  border: 0;
  border-radius: 10px;
  background: var(--mh-primary);
  color: #122238;
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
}

form button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.error {
  margin: 2px 0 0;
  color: #dc2626;
  font-size: 14px;
}

.success {
  margin: 2px 0 0;
  color: #15803d;
  font-size: 14px;
}

.panel-footer {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 10px;
}

.notice-agree {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #556983;
  font-size: 14px;
}

.notice-agree input {
  width: 16px;
  height: 16px;
  margin: 0;
}

.notice-link {
  margin: 0;
  border: 0;
  background: transparent;
  color: #2f8961;
  text-decoration: underline;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
}

.notice-mask {
  position: fixed;
  inset: 0;
  background: rgba(29, 42, 59, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 50;
}

.notice-dialog {
  width: min(620px, 100%);
  max-height: min(72vh, 620px);
  overflow: auto;
  border-radius: 14px;
  border: 1px solid rgba(51, 67, 95, 0.2);
  background: #f9fcf8;
  color: var(--mh-title);
  padding: 16px;
}

.notice-dialog--pdf {
  display: flex;
  flex-direction: column;
  width: min(920px, calc(100vw - 32px));
  max-height: min(85vh, 880px);
  overflow: hidden;
  padding: 12px 16px 16px;
}

.notice-dialog h4 {
  margin: 0;
  font-size: 20px;
}

.notice-dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
  margin-bottom: 10px;
}

.notice-dialog-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.notice-open-tab {
  font-size: 13px;
  font-weight: 600;
  color: #2f8961;
  text-decoration: underline;
}

.notice-close-x {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(51, 67, 95, 0.2);
  background: rgba(255, 255, 255, 0.9);
  color: var(--mh-title);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.notice-pdf-frame {
  flex: 1;
  width: 100%;
  min-height: min(60vh, 560px);
  border: 1px solid rgba(51, 67, 95, 0.2);
  border-radius: 10px;
  background: #fff;
}

.notice-dialog--pdf .dialog-close-btn {
  margin-top: 12px;
  flex-shrink: 0;
}

.dialog-close-btn {
  margin-top: 14px;
  height: 40px;
  border: 1px solid rgba(51, 67, 95, 0.2);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--mh-title);
  font-weight: 700;
  cursor: pointer;
}

.intro-flow {
  opacity: 0;
  animation: flowFadeIn 0.95s ease forwards;
}

.intro-1 {
  animation-delay: 80ms;
}

.intro-2 {
  animation-delay: 220ms;
}

.intro-3 {
  animation-delay: 360ms;
}

.intro-4 {
  animation-delay: 500ms;
}

.intro-5 {
  animation-delay: 580ms;
}

.intro-6 {
  animation-delay: 720ms;
}

.intro-7 {
  animation-delay: 880ms;
}

.intro-8 {
  animation-delay: 1020ms;
}

@keyframes flowFadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 980px) {
  .login-page {
    background-attachment: scroll, scroll;
  }

  .landing-body {
    width: calc(100% - 32px);
    padding-top: 28px;
  }

  .landing-parallel {
    width: 100%;
    max-width: 100%;
    margin-right: 0;
    grid-template-columns: 1fr;
    justify-items: stretch;
  }

  .landing-parallel__aside {
    width: 100%;
    max-width: min(560px, 100%);
    margin: 0 auto;
  }

  .overview-grid {
    grid-template-columns: 1fr;
  }

  .overview-col--pain {
    height: auto;
  }

  .overview-col--pain .overview-card {
    flex: 0 0 auto;
    min-height: 0;
  }

  .overview-col-head--stats .overview-col-title,
  .overview-col-head--policy .overview-col-title {
    white-space: normal;
    max-width: none;
  }

  .overview-col {
    min-height: 0;
  }

  .overview-chart {
    min-height: 0;
  }

  .overview-chart__img {
    min-height: 0;
    max-height: 160px;
  }

  .overview-press-img {
    max-height: 150px;
  }

  .feature-grid {
    grid-template-columns: repeat(5, minmax(120px, 1fr));
    overflow-x: auto;
    padding-bottom: 8px;
    -webkit-overflow-scrolling: touch;
    scroll-snap-type: x proximity;
  }

  .feature-card {
    scroll-snap-align: start;
  }

  .process-strip {
    flex-direction: column;
  }

  .process-strip__left {
    flex: none;
    width: 100%;
    max-width: none;
  }

  .process-strip__right {
    padding: 12px 14px 12px 14px;
  }
}

@media (max-width: 640px) {
  .top-nav {
    padding: 14px 14px 14px 6px;
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }

  .brand-cluster {
    width: 100%;
  }

  .nav-actions {
    width: 100%;
    justify-content: flex-start;
    gap: 6px;
  }

  .nav-item {
    padding: 7px 12px;
    font-size: 13px;
  }

  .brand-logo {
    width: 48px;
    height: 48px;
    transform: scale(1.8);
    transform-origin: center left;
    margin-left: -2px;
    margin-right: calc(48px * (1.8 - 1));
  }

  .landing-body {
    width: calc(100% - 24px);
    padding-top: 20px;
  }

  .hero {
    padding: 32px 0 48px;
  }

}
</style>
