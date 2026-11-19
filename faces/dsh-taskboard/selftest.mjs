/**
 * 适配层自测：不需要 DSH，验证 /dsh-taskboard/* 真的映射到内核。
 * 跑法：BOARD_PORT=8785 BOARD_API_TOKEN=t3 node selftest.mjs
 */
import { apply } from './lib/index.js'

const captured = []
apply({ webServer: { register(a) { captured.push(a) } } })
if (captured.length !== 1) { console.error('FAIL: 未注册路由'); process.exit(1) }
const handler = captured[0].handler

async function call(method, url, body) {
  const payload = body === undefined ? null : Buffer.from(JSON.stringify(body))
  const req = {
    method, url, headers: {},
    [Symbol.asyncIterator]() {
      let done = false
      return { next: async () => done ? { done: true, value: undefined } : (done = true, { done: false, value: payload }) }
    }
  }
  const chunks = []
  const res = { statusCode: 0, setHeader() {}, write() {}, end(b) { if (b) chunks.push(Buffer.from(b)) } }
  await handler(req, res)
  const text = Buffer.concat(chunks).toString('utf8')
  let json
  try { json = JSON.parse(text) } catch { json = null }
  return { status: res.statusCode, json, text }
}

async function wait() {
  for (let i = 0; i < 60; i++) {
    const r = await call('GET', '/dsh-taskboard/workspaces')
    if (r.status === 200) return r
    await new Promise(x => setTimeout(x, 500))
  }
  return null
}

const ws = await wait()
if (!ws) { console.error('FAIL: 内核未就绪'); process.exit(1) }
console.log('workspaces', ws.json.value.length)

const st = await call('GET', '/dsh-taskboard/state')
if (st.status !== 200 || !Array.isArray(st.json.value.tasks)) {
  console.error('FAIL: state 形状不对', st.status, st.text.slice(0, 150)); process.exit(1)
}
console.log('state tasks', st.json.value.tasks.length)

const wsPath = ws.json.value[0] ? ws.json.value[0].id : undefined
const created = await call('POST', '/dsh-taskboard/tasks', { title: '适配层自测卡', description: 'x', workspaceId: wsPath })
if (created.status !== 200 || !created.json.value.id) {
  console.error('FAIL: 建卡失败', created.status, created.text.slice(0, 200)); process.exit(1)
}
const id = created.json.value.id
console.log('created', id)

const moved = await call('POST', '/dsh-taskboard/tasks/' + id + '/move', { to: 'in_progress' })
if (moved.status !== 200 || moved.json.value.status !== 'in_progress') {
  console.error('FAIL: 移动到进行中失败', moved.status, moved.text.slice(0, 200)); process.exit(1)
}
console.log('moved in_progress OK')

const cmt = await call('POST', '/dsh-taskboard/tasks/' + id + '/comment', { body: '自测评论' })
if (cmt.status !== 200) { console.error('FAIL: 评论失败', cmt.status, cmt.text.slice(0, 200)); process.exit(1) }
const detail = await call('GET', '/dsh-taskboard/tasks/' + id)
if (!detail.json.value.comments.some(c => c.body === '自测评论')) {
  console.error('FAIL: 评论没落到内核'); process.exit(1)
}
console.log('comment roundtrip OK')

const del = await call('POST', '/dsh-taskboard/tasks/' + id + '/delete', {})
if (del.status !== 200) { console.error('FAIL: 删除失败'); process.exit(1) }
console.log('SELFTEST PASS')
