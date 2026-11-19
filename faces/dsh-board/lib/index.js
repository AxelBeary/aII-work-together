/**
 * dsh-board 宿主半边（2026-11-19，D-040）
 *
 * 职责只有两件：
 *   1. 确保内核 HTTP 服务在跑（不在就拉起，用固定令牌）；
 *   2. 把 /board/* 代理到内核（浏览器只访问同源 /board，不碰跨域）。
 *
 * ⛔ 不碰账本：所有读写都走内核 HTTP。宿主崩溃不会损坏数据。
 * ⛔ apply 绝不抛：DSH 的 web shell 在插件 apply 抛错时会整体起不来，
 *    所以这里全部 try/catch，失败只降级（面板空着），不影响 GUI。
 */
import { spawn } from 'node:child_process'

export const name = 'dsh-board'
export const inject = []

const REPO = process.env.BOARD_REPO || 'E:\\GithubClone\\aII-work-together'
const PORT = Number(process.env.BOARD_PORT || 8790)
const TOKEN = process.env.BOARD_API_TOKEN || 'dsh-board-local'
const BASE = `http://127.0.0.1:${PORT}`
const PREFIX = '/board'

let starting = null

async function ping() {
  try {
    const r = await fetch(BASE + '/api/state', { headers: { 'X-Board-Token': TOKEN } })
    return r.ok
  } catch { return false }
}

function startKernel() {
  if (starting) return starting
  starting = (async () => {
    if (await ping()) return true
    try {
      const child = spawn(process.env.BOARD_PYTHON || 'python',
        [REPO + '\\tools\\server.py', '--port', String(PORT)],
        { cwd: REPO, env: { ...process.env, BOARD_API_TOKEN: TOKEN },
          detached: true, stdio: 'ignore', windowsHide: true })
      child.unref()
    } catch (e) {
      console.warn('[dsh-board] 拉起内核失败：', e && e.message)
      return false
    }
    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 250))
      if (await ping()) return true
    }
    return false
  })()
  return starting
}

async function readBody(req) {
  const chunks = []
  for await (const c of req) chunks.push(c)
  return Buffer.concat(chunks)
}

function proxyHandler() {
  return async (req, res) => {
    try {
      await startKernel()
      const url = req.url || '/'
      const path = url.startsWith(PREFIX) ? url.slice(PREFIX.length) : url
      const target = BASE + (path.startsWith('/') ? path : '/' + path)
      const method = req.method || 'GET'
      const headers = { 'X-Board-Token': TOKEN }
      if (req.headers['content-type']) headers['Content-Type'] = req.headers['content-type']
      const init = { method, headers }
      if (method !== 'GET' && method !== 'HEAD') {
        const body = await readBody(req)
        if (body.length) init.body = body
      }
      const r = await fetch(target, init)
      const buf = Buffer.from(await r.arrayBuffer())
      res.statusCode = r.status
      res.setHeader('Content-Type', r.headers.get('content-type') || 'application/json')
      res.setHeader('Cache-Control', 'no-store')
      res.end(buf)
    } catch (e) {
      res.statusCode = 503
      res.setHeader('Content-Type', 'application/json; charset=utf-8')
      res.end(JSON.stringify({ ok: false, error: { code: 'internal', message: '内核未就绪：' + (e && e.message) } }))
    }
  }
}

export function apply(ctx) {
  try {
    void startKernel()
    ctx.webServer.register({ kind: 'prefix', path: PREFIX, handler: proxyHandler() })
  } catch (e) {
    console.warn('[dsh-board] 注册路由失败（面板降级，不影响 GUI）：', e && e.message)
  }
}
