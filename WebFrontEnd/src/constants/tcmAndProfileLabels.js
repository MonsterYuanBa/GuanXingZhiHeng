/**
 * 与 Profile 页选项一致，供联合报告等只读展示。
 */
export const tcmQuestionDefs = [
  {
    key: 'coldHeat',
    label: '一问寒热',
    options: [
      { value: 'cold', label: '怕冷为主' },
      { value: 'heat', label: '怕热为主' },
      { value: 'neutral', label: '寒热平和' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'sweat',
    label: '二问汗',
    options: [
      { value: 'little', label: '少汗' },
      { value: 'normal', label: '汗出正常' },
      { value: 'much', label: '多汗' },
      { value: 'night', label: '夜间易汗' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'sleep',
    label: '三问睡眠',
    options: [
      { value: 'good', label: '睡眠良好' },
      { value: 'normal', label: '一般' },
      { value: 'insomnia', label: '入睡困难' },
      { value: 'dreamy', label: '多梦易醒' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'appetite',
    label: '四问饮食',
    options: [
      { value: 'good', label: '食欲较好' },
      { value: 'normal', label: '食欲一般' },
      { value: 'poor', label: '食欲偏差' },
      { value: 'greasy', label: '偏嗜肥甘' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'stool',
    label: '五问大便',
    options: [
      { value: 'normal', label: '规律成形' },
      { value: 'dry', label: '偏干' },
      { value: 'loose', label: '偏稀' },
      { value: 'irregular', label: '不规律' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'urination',
    label: '六问小便',
    options: [
      { value: 'normal', label: '正常' },
      { value: 'frequent', label: '偏频' },
      { value: 'yellow', label: '色黄' },
      { value: 'night', label: '夜尿偏多' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'emotion',
    label: '七问情志',
    options: [
      { value: 'stable', label: '情绪稳定' },
      { value: 'stress', label: '压力偏大' },
      { value: 'anxious', label: '焦虑易烦' },
      { value: 'low', label: '情绪低落' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'energy',
    label: '八问劳倦',
    options: [
      { value: 'good', label: '精力充沛' },
      { value: 'normal', label: '一般' },
      { value: 'fatigue', label: '容易疲劳' },
      { value: 'exhausted', label: '经常乏力' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'thirst',
    label: '九问口渴',
    options: [
      { value: 'normal', label: '饮水正常' },
      { value: 'more', label: '口渴喜饮' },
      { value: 'less', label: '不渴少饮' },
      { value: 'dry', label: '口干明显' },
      { value: 'other', label: '其他（自行填写）' },
    ],
  },
  {
    key: 'pain',
    label: '十问疼痛',
    options: [
      { value: 'none', label: '无明显疼痛' },
      { value: 'neck_back', label: '颈肩腰背痛' },
      { value: 'joint', label: '关节疼痛' },
      { value: 'other', label: '其他疼痛' },
      { value: 'other_custom', label: '其他（自行填写）' },
    ],
  },
]

const GENDER_LABELS = { male: '男', female: '女' }
const MEDICAL_LABELS = {
  none: '无明确病史',
  hypertension: '高血压',
  diabetes: '糖尿病',
  lumbar_cervical: '颈椎/腰椎问题',
  joint_injury: '关节或运动损伤史',
  other: '其他',
}
const WORK_LABELS = {
  normal: '活动较均衡',
  sedentary: '久坐为主',
  standing: '久站为主',
  repetitive_labor: '重复性劳动',
  shift_work: '轮班/熬夜',
}

export function labelForTcmValue(key, raw) {
  if (raw == null || raw === '') return '—'
  const s = String(raw)
  if (s.startsWith('other:')) {
    const rest = s.slice(6).trim()
    return rest || '其他'
  }
  const def = tcmQuestionDefs.find((d) => d.key === key)
  if (!def) return s
  const opt = def.options.find((o) => o.value === s)
  return opt ? opt.label : s
}

export function formatBasicProfileRows(profile) {
  const p = profile && typeof profile === 'object' ? profile : {}
  const gender = p.gender != null && p.gender !== '' ? GENDER_LABELS[p.gender] || String(p.gender) : '—'
  const med = p.medicalHistory != null && p.medicalHistory !== ''
    ? MEDICAL_LABELS[p.medicalHistory] || String(p.medicalHistory)
    : '—'
  const work = p.workHabit != null && p.workHabit !== '' ? WORK_LABELS[p.workHabit] || String(p.workHabit) : '—'
  const allergy =
    p.allergyHistory != null && String(p.allergyHistory).trim() !== ''
      ? String(p.allergyHistory).trim()
      : '无过敏史'
  return [
    { k: '年龄', v: p.age != null && p.age !== '' ? String(p.age) : '—' },
    { k: '性别', v: gender },
    { k: '身高(cm)', v: p.height != null && p.height !== '' ? String(p.height) : '—' },
    { k: '体重(kg)', v: p.weight != null && p.weight !== '' ? String(p.weight) : '—' },
    { k: '过敏情况', v: allergy },
    { k: '既往病史', v: med },
    { k: '职业/工作习惯', v: work },
  ]
}

export function tcmRowsForDisplay(tcmObj) {
  const o = tcmObj && typeof tcmObj === 'object' ? tcmObj : {}
  return tcmQuestionDefs.map((d) => ({
    label: d.label,
    text: labelForTcmValue(d.key, o[d.key]),
  }))
}
