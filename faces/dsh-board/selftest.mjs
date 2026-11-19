/**
 * dsh-board 自测：不依赖 DSH 宿主，验证「宿主半边真的能代理到内核」。
 * 跑法：node selftest.mjs
 * 期望：最后一行 SELFTEST PASS
 */
import { apply } from './lib/index.js'

const captured = []
const ctx = {
  webServer: {
    register(arg) { captured.push(arg) }
  }
}

apply(ctx)
if (captured.length !== 1) {
  console.error('FAIL: 没有注册路由', captured.length)
  process.exit(1)
}
const { kind, path, handler } = captured[0]
if (kind !== 'prefix' || path !== '/board') {
  console.error('FAIL: 路由形状不对', kind, path)
  process.exit(1)
}

async function call(url) {
  const chunks = []
  const req = {
    method: 'GET',
    url,
    headers: {},
    [Symbol.asyncIterator]() {
      return { next: async () => ({ done: true, value: undefined }) }
    }
  }
  const res = {
    statusCode: 0,
    headers: {},
    setHeader(k, v) { this.headers[k] = v },
    end(buf) { chunks.push(buf) }
  }
  await handler(req, res)
  const text = Buffer.concat(chunks).toString('utf8')
  return { status: res.statusCode, text }
}

const t0 = Date.now()
let state
for (let i = 0; i < 60; i++) {
  state = await call('/board/api/state')
  if (state.status === 200) break
  await new Promise(r => setTimeout(r, 500))
}
if (state.status !== 200) {
  console.error('FAIL: 代理未就绪', state.status, state.text.slice(0, 200))
  process.exit(1)
}
let parsed
try { parsed = JSON.parse(state.text) } catch (e) {
  console.error('FAIL: 返回不是 JSON', state.text.slice(0, 200))
  process.exit(1)
}
if (!parsed.projects) {
  console.error('FAIL: 缺少 projects', JSON.stringify(parsed).slice(0, 200))
  process.exit(1)
}
console.log('代理耗时', Date.now() - t0, 'ms；项目数', parsed.projects.length)

// 反向：写接口无令牌前缀也不能被随便写（代理自己加令牌是设计，但路径必须存在）
const bad = await call('/board/api/nope')
if (bad.status !== 404) {
  console.error('FAIL: 未知路径应 404，实际', bad.status)
  process.exit(1)
}
console.log('SELFTEST PASS')
