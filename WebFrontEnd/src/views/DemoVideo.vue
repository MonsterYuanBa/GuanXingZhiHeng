<script setup>
import TopNav from '../components/TopNav.vue'
import fullVersionVideoSrc from '../materials/demo1.mp4'
import testModeVideoSrc from '../materials/demo_test.mp4'
import testGuidePdfSrc from '../materials/test_guide.pdf'
</script>

<template>
  <section class="page-wrap">
    <TopNav active="demo-video" />
    <main class="content">
      <header class="page-head">
        <h1 class="page-title">演示 & 评委必看！！！</h1>
        <p class="muted">
          左：评委测试模式流程；右：满血原版操作。下方为评委说明 PDF。
        </p>
      </header>

      <div class="cards">
        <section class="card demo-card">
          <div class="video-dual">
            <div class="video-col">
              <h2>评委必看的测试模式流程</h2>
              <p class="muted card-desc">在没有GPU的服务器上，如何体验流程？教你使用自动填充、测试智能体等功能！</p>
              <div class="video-frame">
                <video
                  class="demo-video"
                  controls
                  playsinline
                  preload="metadata"
                  :src="testModeVideoSrc"
                >
                  您的浏览器不支持视频播放。
                </video>
              </div>
            </div>
            <div class="video-col">
              <h2>满血原版操作视频</h2>
              <p class="muted card-desc">有GPU时候，满血完整功能下的实际操作演示。</p>
              <div class="video-frame">
                <video
                  class="demo-video"
                  controls
                  playsinline
                  preload="metadata"
                  :src="fullVersionVideoSrc"
                >
                  您的浏览器不支持视频播放。
                </video>
              </div>
            </div>
          </div>
        </section>

        <section class="card demo-card">
          <div class="card-title-row">
            <h2>评委必看</h2>
            <a class="pdf-open-link" :href="testGuidePdfSrc" target="_blank" rel="noopener noreferrer">
              新窗口打开 PDF
            </a>
          </div>
          <p class="muted card-desc">测试与评审说明，和上面左侧的视频讲的是一个事情！</p>
          <div class="pdf-frame">
            <iframe
              class="pdf-embed"
              title="评委测试说明 PDF"
              :src="testGuidePdfSrc"
            />
          </div>
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
  box-sizing: border-box;
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 12px clamp(8px, 1vw, 14px);
}
.page-head {
  margin: 0 0 16px;
  padding: 0 clamp(4px, 0.5vw, 8px);
}
.page-title {
  margin: 0 0 8px;
  font-size: 1.35rem;
  color: #1e293b;
}
.muted {
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}
.demo-card {
  max-width: none;
  width: calc(100% - 16px);
  margin: 0 auto;
  padding: 16px clamp(10px, 1vw, 18px);
}
.demo-card h2 {
  margin: 0 0 6px;
  font-size: 1.05rem;
  color: #1e293b;
}
.card-desc {
  margin-bottom: 12px;
  font-size: 0.875rem;
}
.card-desc code {
  font-size: 0.78rem;
  word-break: break-all;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 6px;
  color: #334155;
}
.video-dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(12px, 2vw, 24px);
  align-items: start;
}
@media (max-width: 960px) {
  .video-dual {
    grid-template-columns: 1fr;
  }
}
.video-col {
  min-width: 0;
}
.card-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.card-title-row h2 {
  margin: 0;
}
.pdf-open-link {
  font-size: 0.875rem;
  color: #2563eb;
  text-decoration: none;
}
.pdf-open-link:hover {
  text-decoration: underline;
}
/* 须建立明确宽高，避免子级 height:100% 在部分浏览器里算成 0 → 有声音无画面 */
.video-frame {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #dbe4f1;
  background: #0f172a;
  aspect-ratio: 16 / 9;
  width: 100%;
}
.demo-video {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  vertical-align: top;
}
.video-codec-hint {
  margin-top: 8px;
  font-size: 0.8125rem;
  max-width: 72em;
}
.video-codec-hint strong {
  font-weight: 700;
  color: #475569;
}
.pdf-frame {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #dbe4f1;
  background: #f1f5f9;
  min-height: min(920px, 88vh);
  width: 100%;
}
.pdf-embed {
  display: block;
  width: 100%;
  min-height: min(900px, 86vh);
  height: 86vh;
  border: none;
  background: #fff;
}
</style>
