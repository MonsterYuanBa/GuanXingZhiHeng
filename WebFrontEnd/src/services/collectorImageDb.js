/**
 * 用 IndexedDB 暂存数据收集页上传的原图，避免切换路由后 File/blob URL 丢失。
 * 键按 userId 隔离；生成联合报告成功后可调用 clearCollectorImages 清空。
 */
const DB_NAME = 'mask_collector_v1'
const STORE = 'images'
const SLOTS = ['posture_front', 'posture_side', 'tongue', 'posture_result_display']

function idbOk() {
  return typeof indexedDB !== 'undefined'
}

function openDb() {
  return new Promise((resolve, reject) => {
    if (!idbOk()) {
      resolve(null)
      return
    }
    const req = indexedDB.open(DB_NAME, 1)
    req.onerror = () => reject(req.error)
    req.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE)
      }
    }
    req.onsuccess = () => resolve(req.result)
  })
}

function keyFor(userId, slot) {
  return `${userId}::${slot}`
}

/**
 * @param {string} userId
 * @param {'posture_front'|'posture_side'|'tongue'} slot
 * @param {File} file
 */
export async function saveCollectorImage(userId, slot, file) {
  if (!idbOk() || !file || !userId) return
  try {
    const db = await openDb()
    if (!db) return
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.oncomplete = () => {
        db.close()
        resolve()
      }
      tx.onerror = () => reject(tx.error)
      tx.objectStore(STORE).put(
        { blob: file, name: file.name || 'image', type: file.type || 'image/jpeg' },
        keyFor(userId, slot),
      )
    })
  } catch (e) {
    console.warn('[collectorImageDb] save failed', e)
  }
}

/**
 * @returns {Promise<File|null>}
 */
export async function getCollectorImage(userId, slot) {
  if (!idbOk() || !userId) return null
  try {
    const db = await openDb()
    if (!db) return null
    const record = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly')
      const rq = tx.objectStore(STORE).get(keyFor(userId, slot))
      rq.onsuccess = () => resolve(rq.result || null)
      rq.onerror = () => reject(rq.error)
    })
    db.close()
    if (!record?.blob) return null
    const blob = record.blob
    return new File([blob], record.name || 'image.jpg', { type: record.type || blob.type || 'image/jpeg' })
  } catch (e) {
    console.warn('[collectorImageDb] get failed', e)
    return null
  }
}

export async function clearCollectorImages(userId) {
  if (!idbOk() || !userId) return
  try {
    const db = await openDb()
    if (!db) return
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.oncomplete = () => {
        db.close()
        resolve()
      }
      tx.onerror = () => reject(tx.error)
      const store = tx.objectStore(STORE)
      for (const slot of SLOTS) {
        store.delete(keyFor(userId, slot))
      }
    })
  } catch (e) {
    console.warn('[collectorImageDb] clear failed', e)
  }
}

/**
 * 删除某个上传槽位缓存（例如 posture_front / posture_side / tongue）
 * @param {string} userId
 * @param {'posture_front'|'posture_side'|'tongue'|'posture_result_display'} slot
 */
export async function removeCollectorImage(userId, slot) {
  if (!idbOk() || !userId || !slot) return
  try {
    const db = await openDb()
    if (!db) return
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.oncomplete = () => {
        db.close()
        resolve()
      }
      tx.onerror = () => reject(tx.error)
      tx.objectStore(STORE).delete(keyFor(userId, slot))
    })
  } catch (e) {
    console.warn('[collectorImageDb] remove failed', e)
  }
}

/** 体态分析结果图（多为 data URL）过大，不写入 localStorage；单独存 IDB，供路由返回后恢复中间栏预览。 */
export async function savePostureResultDisplay(userId, dataUrl) {
  if (!idbOk() || !userId) return
  try {
    const db = await openDb()
    if (!db) return
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.oncomplete = () => {
        db.close()
        resolve()
      }
      tx.onerror = () => reject(tx.error)
      const store = tx.objectStore(STORE)
      if (dataUrl) {
        store.put({ dataUrl }, keyFor(userId, 'posture_result_display'))
      } else {
        store.delete(keyFor(userId, 'posture_result_display'))
      }
    })
  } catch (e) {
    console.warn('[collectorImageDb] save posture result display failed', e)
  }
}

/** @returns {Promise<string|null>} */
export async function getPostureResultDisplay(userId) {
  if (!idbOk() || !userId) return null
  try {
    const db = await openDb()
    if (!db) return null
    const record = await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly')
      const rq = tx.objectStore(STORE).get(keyFor(userId, 'posture_result_display'))
      rq.onsuccess = () => resolve(rq.result || null)
      rq.onerror = () => reject(rq.error)
    })
    db.close()
    const url = record?.dataUrl
    return typeof url === 'string' && url ? url : null
  } catch (e) {
    console.warn('[collectorImageDb] get posture result display failed', e)
    return null
  }
}
