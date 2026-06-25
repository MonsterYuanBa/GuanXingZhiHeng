/**
 * 将智能体输出的“整段文本”解析成可渲染的结构（sections/items）。
 *
 * 目标：
 * - 数据库存整段不变；前端展示时做结构化。
 * - 同时兼容：
 *   1) 新协议：<<<SECTION|id|标题>>> 与 <<<ITEM|id|标题>>> / <<<ITEM>>> 分隔
 *   2) 旧文本：中文小标题（如“一、”“二、”）+ 数字分点（如“1.”“（1）”）
 */
const SECTION_RE = /^<<<SECTION\|([^|]*)\|([^>]*)>>>$/i
const GROUP_RE = /^<<<GROUP\|([^|]*)\|([^>]*)>>>$/i
const ITEM_RE = /^<<<ITEM(?:\|([^|]*)\|([^>]*)?)?>>>$/i

function normalizeLines(text) {
  if (text == null) return []
  const normalized = String(text)
    .replaceAll('\r\n', '\n')
    .replaceAll('\r', '\n')
    .split('\n')

  // 清理某些模型输出的 XML/HTML 风格标签（避免在 UI 中直出）
  // 例如：</ITEM> </GROUP> </SECTION> 或 <ITEM> <GROUP ...> 等
  const tagLineRe = /^\s*<\/?\s*(section|group|item)\b[^>]*>\s*$/i
  return normalized
    .map((line) => (tagLineRe.test(String(line ?? '')) ? '' : line))
}

function joinNonEmpty(lines) {
  return lines
    .map((x) => String(x ?? '').trimEnd())
    .join('\n')
    .trim()
}

function parseDelimited(text) {
  const lines = normalizeLines(text)
  const sections = []
  let cur = null
  let curGroup = null
  let curItem = null

  const pushItem = () => {
    if (!curItem || !cur) return
    const body = joinNonEmpty(curItem._lines || [])
    const title = String(curItem.title || '').trim()
    if (title || body) {
      if (curGroup) {
        curGroup.children.push({ id: curItem.id || '', title, body })
      } else {
        cur.items.push({ id: curItem.id || '', title, body })
      }
    }
    curItem = null
  }

  const pushGroup = () => {
    if (!cur || !curGroup) return
    // 清理空组
    const title = String(curGroup.title || '').trim()
    const intro = joinNonEmpty(curGroup._lines || [])
    const children = Array.isArray(curGroup.children) ? curGroup.children : []
    if (title || intro || children.length) {
      cur.items.push({
        id: curGroup.id || '',
        title,
        body: intro,
        children,
      })
    }
    curGroup = null
  }

  const pushSection = () => {
    if (!cur) return
    pushItem()
    pushGroup()
    const intro = joinNonEmpty(cur._lines || [])
    const title = String(cur.title || '').trim()
    const hasAny = title || intro || (cur.items && cur.items.length)
    if (hasAny) {
      sections.push({
        id: cur.id || '',
        title,
        intro,
        items: cur.items || [],
      })
    }
    cur = null
  }

  for (const rawLine of lines) {
    const line = String(rawLine ?? '').trim()
    if (!line) {
      if (curItem) curItem._lines.push('')
      else if (cur) cur._lines.push('')
      continue
    }

    const sm = line.match(SECTION_RE)
    if (sm) {
      pushSection()
      cur = { id: (sm[1] || '').trim(), title: (sm[2] || '').trim(), items: [], _lines: [] }
      continue
    }

    const gm = line.match(GROUP_RE)
    if (gm) {
      if (!cur) cur = { id: '', title: '', items: [], _lines: [] }
      pushItem()
      pushGroup()
      curGroup = { id: (gm[1] || '').trim(), title: (gm[2] || '').trim(), _lines: [], children: [] }
      continue
    }

    const im = line.match(ITEM_RE)
    if (im) {
      if (!cur) cur = { id: '', title: '', items: [], _lines: [] }
      pushItem()
      curItem = { id: (im[1] || '').trim(), title: (im[2] || '').trim(), _lines: [] }
      continue
    }

    if (!cur) cur = { id: '', title: '', items: [], _lines: [] }
    if (curItem) curItem._lines.push(rawLine)
    else if (curGroup) curGroup._lines.push(rawLine)
    else cur._lines.push(rawLine)
  }

  pushSection()
  return sections
}

function parseChineseHeadings(text) {
  const lines = normalizeLines(text)
  const sections = []

  const headingRe = /^\s*([一二三四五六七八九十]+)[、.]\s*(.+?)\s*$/
  // 二级小标题：常见为“（一）体态指标分析”
  const subHeadingRe = /^\s*（([一二三四五六七八九十]+)）\s*(.+?)\s*$/
  // 三级分点：常见为“1.”、“（1）”
  const itemRe = /^\s*(?:\(?\d+\)?[.、]|（\d+）)\s*(.+?)\s*$/

  let cur = null
  let curItem = null // section 内的一条 item（可能是“组”）
  let curGroup = null // section 内的“二级小标题组”，其 children 存放三级分点

  const pushItem = () => {
    if (!curItem || !cur) return
    const body = joinNonEmpty(curItem._lines || [])
    const title = String(curItem.title || '').trim()
    const children = Array.isArray(curItem.children) ? curItem.children : []
    if (title || body || children.length) cur.items.push({ id: '', title, body, children })
    curItem = null
  }

  const pushSection = () => {
    if (!cur) return
    pushItem()
    const intro = joinNonEmpty(cur._lines || [])
    const title = String(cur.title || '').trim()
    const hasAny = title || intro || (cur.items && cur.items.length)
    if (hasAny) sections.push({ id: '', title, intro, items: cur.items || [] })
    cur = null
    curGroup = null
  }

  for (const rawLine of lines) {
    const line = String(rawLine ?? '').trim()
    if (!line) {
      if (curItem) curItem._lines.push('')
      else if (cur) cur._lines.push('')
      continue
    }

    const hm = rawLine.match(headingRe)
    if (hm) {
      pushSection()
      cur = { title: String(hm[2] || '').trim(), items: [], _lines: [] }
      curGroup = null
      continue
    }

    const shm = rawLine.match(subHeadingRe)
    if (shm) {
      if (!cur) cur = { title: '', items: [], _lines: [] }
      // 新二级组开始：结束上一条 item（如果正在写）
      pushItem()
      curItem = { title: String(shm[2] || '').trim(), _lines: [], children: [] }
      curGroup = curItem
      continue
    }

    const im = rawLine.match(itemRe)
    if (im) {
      if (!cur) cur = { title: '', items: [], _lines: [] }
      // 如果当前在二级组内，则把该条作为 children；否则作为一级 item
      if (curGroup && Array.isArray(curGroup.children)) {
        curGroup.children.push({ id: '', title: String(im[1] || '').trim(), body: '' })
      } else {
        pushItem()
        curItem = { title: String(im[1] || '').trim(), _lines: [] }
      }
      continue
    }

    if (!cur) cur = { title: '', items: [], _lines: [] }
    // 普通行：优先写到最近的 children body；其次写到 curItem body；否则写到 section intro
    if (curGroup && Array.isArray(curGroup.children) && curGroup.children.length) {
      const last = curGroup.children[curGroup.children.length - 1]
      const prev = String(last.body || '').trim()
      last.body = prev ? `${last.body}\n${rawLine}` : String(rawLine)
    } else if (curItem) {
      curItem._lines.push(rawLine)
    } else {
      cur._lines.push(rawLine)
    }
  }

  pushSection()
  return sections
}

export function parseAgentText(text) {
  const raw = String(text ?? '').trim()
  if (!raw) return { raw: '', sections: [] }

  const postProcessSections = (sections) => {
    if (!Array.isArray(sections) || !sections.length) return []
    return sections.map((sec) => {
      const title = String(sec?.title ?? '').trim()
      const intro = String(sec?.intro ?? '').trim()
      const items = Array.isArray(sec?.items) ? sec.items : []

      // 若未产生 ITEM，但正文有多段落，则将段落拆成多个 item，改善“整块长文本”观感。
      if (!items.length && intro) {
        const parts = intro
          .split(/\n{2,}/g)
          .map((p) => String(p ?? '').trim())
          .filter(Boolean)
        if (parts.length >= 2) {
          const first = parts[0]
          const rest = parts.slice(1).map((body, idx) => ({
            id: '',
            title: '',
            body,
            children: [],
            _fallbackIdx: idx,
          }))
          return { ...(sec || {}), title, intro: first, items: rest }
        }
      }

      return { ...(sec || {}), title, intro, items }
    })
  }

  // 优先新协议
  if (raw.includes('<<<SECTION|') || raw.includes('<<<ITEM')) {
    const sections = postProcessSections(parseDelimited(raw))
    if (sections.length) return { raw, sections }
  }

  // 兜底：中文标题/分点
  const fallback = postProcessSections(parseChineseHeadings(raw))
  if (fallback.length) return { raw, sections: fallback }

  // 最终兜底：整段放入一个 section
  return { raw, sections: postProcessSections([{ id: '', title: '', intro: raw, items: [] }]) }
}

