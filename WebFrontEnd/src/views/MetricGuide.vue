<script setup>
import TopNav from '../components/TopNav.vue'

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
</script>

<template>
  <section class="page-wrap">
    <TopNav active="collector" />
    <main class="content">
      <section class="card shell">
        <h2>体态/体型指标说明</h2>
        <p class="muted">以下含义用于报告解读参考，不作为医疗诊断依据。</p>

        <table class="metric-table">
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
      </section>
    </main>
  </section>
</template>

<style scoped>
.page-wrap { min-height: 100vh; }
.content { padding: 16px; }
.shell { max-width: 1100px; }
.shell h2 { margin-top: 0; color: #1e293b; }
.muted { color: #64748b; margin-bottom: 12px; }
.metric-table { width: 100%; border-collapse: collapse; }
.metric-table th, .metric-table td {
  border: 1px solid #dbe4f1;
  padding: 10px;
  text-align: left;
  vertical-align: top;
}
.metric-table th {
  width: 220px;
  background: #eff6ff;
  color: #1e3a8a;
}
</style>
