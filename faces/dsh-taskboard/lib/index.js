/**
 * dsh-taskboard 宿主半边 —— 内核适配版（2026-11-20，D-041）
 *
 * 设计：**界面用 taskboard 原版客户端（lib/client.js 未改），宿主换成内核实现**。
 * 客户端只认 /dsh-taskboard/* 的 HTTP 契约；这里把这些路由逐条映射到
 * aII-work-together 内核（事件流账本 / 租约 / 证据）。
 *
 * ⛔ 本文件不持有任何账本：每次请求都读内核。laptop 崩了不会丢数据。
 * ⛔ apply 不抛：加载失败只降级面板，不影响 GUI 启动。
 */
import { spawn } from 'node:child_process'

export const name = 'dsh-taskboard'
export const inject = []

const REPO = process.env.BOARD_REPO || 'E:\\GithubClone\\aII-work-together'
const PORT = Number(process.env.BOARD_PORT || 8790)
const TOKEN = process.env.BOARD_API_TOKEN || 'dsh-board-local'
const KERNEL = 'http://127.0.0.1:' + PORT
const PREFIX = '/dsh-taskboard'
const PANEL_SEAT = 'panel'
let starting = null

async function ping() {
  try {
    const r = await fetch(KERNEL + '/api/state', { headers: { 'X-Board-Token': TOKEN } })
    return r.ok
  } catch { return false }
}

function ensureKernel() {
  if (starting) return starting
  starting = (async () => {
    if (await ping()) return true
    try {
      const child = spawn(process.env.BOARD_PYTHON || 'python',
        [REPO + '\\tools\\server.py', '--port', String(PORT)],
        { cwd: REPO, env: { ...process.env, BOARD_API_TOKEN: TOKEN },
          detached: true, stdio: 'ignore', windowsHide: true })
      child.unref()
    } catch { return false }
    for (let i = 0; i < 40; i++) {
      await new Promise(r => setTimeout(r, 250))
      if (await ping()) return true
    }
    return false
  })()
  return starting
}

async function kget(path) {
  await ensureKernel()
  const r = await fetch(KERNEL + path, { headers: { 'X-Board-Token': TOKEN } })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error((j.error && j.error.message) || j.error || ('HTTP ' + r.status))
  return j
}

async function kpost(path, body) {
  await ensureKernel()
  const r = await fetch(KERNEL + path, {
    method: 'POST',
    headers: { 'X-Board-Token': TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) {
    const e = j.error
    const err = new Error((e && e.message) || (typeof e === 'string' ? e : ('HTTP ' + r.status)))
    err.code = (e && e.code) || 'invalid_input'
    throw err
  }
  return j
}

// ---------------- 映射：内核 → taskboard TaskRecord ----------------

const STATUS = {
  '待认领': 'todo', '进行中': 'in_progress', '待返工': 'todo',
  '阻塞': 'in_progress', '待验收': 'in_review', '核验中': 'in_review',
  '拍板中': 'in_review', '完成': 'done', '已取消': 'canceled'
}
const TO_KERNEL = {
  todo: '待认领', backlog: '待认领', in_progress: '进行中',
  in_review: '待验收', done: '完成', canceled: '已取消'
}

function ms(v) {
  if (!v) return Date.now()
  if (typeof v === 'number') return v
  const t = Date.parse(String(v).replace(' ', 'T'))
  return Number.isFinite(t) ? t : Date.now()
}

function workspaceOf(body) {
  const w = body && (body.workspaceId || body.project)
  return w || undefined
}

function recordFrom(card, detail) {
  const state = (detail && detail.state) || card.state || '待认领'
  const status = STATUS[state] || 'todo'
  const trashed = detail && detail.trashed_at
  const comments = ((detail && detail.comments) || []).map(c => ({
    id: c.id, body: c.body, threadId: c.thread_id || 'host',
    version: 1, createdAt: ms(c.at), deliveredAt: c.delivered_at ? ms(c.delivered_at) : undefined
  }))
  const checklist = ((detail && detail.checklist) || []).map(k => ({
    id: k.id, text: k.text, checked: !!k.checked,
    checkedBy: k.checked_by || undefined, checkedAt: k.checked_at ? ms(k.checked_at) : undefined,
    note: k.note || undefined
  }))
  return {
    id: card.id,
    title: card.title || card.id,
    description: card.goal || '',
    prompt: '',
    workspaceId: card.project_path || card.project || '',
    urgency: 'normal',
    status,
    blocked: state === '阻塞',
    execution: { mode: 'claim' },
    isolation: 'none',
    permission: 'workspace-write',
    version: (detail && detail.version) || card.version || 1,
    createdAt: ms(card.last_at),
    updatedAt: ms(card.last_at),
    createdBy: { kind: 'user' },
    updatedBy: { kind: 'user' },
    comments,
    executions: [],
    checklist,
    claimedBy: card.holder || undefined,
    trashedAt: trashed ? ms(trashed) : undefined,
    branches: (detail && detail.branches) || undefined
  }
}

// ---------------- HTTP 小工具 ----------------

async function readBody(req) {
  const chunks = []
  for await (const c of req) chunks.push(c)
  if (!chunks.length) return {}
  try { return JSON.parse(Buffer.concat(chunks).toString('utf8')) } catch { return {} }
}

function send(res, status, value) {
  const body = JSON.stringify({ ok: true, value })
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store')
  res.end(body)
}

function fail(res, e) {
  res.statusCode = 400
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify({ ok: false, error: { code: (e && e.code) || 'invalid_input', message: String((e && e.message) || e) } }))
}

async function projects() {
  const s = await kget('/api/state')
  return s.projects || []
}

function projectNameFrom(ws) {
  const ps = stateCache.projects || []
  const hit = ps.find(p => p.path === ws || p.name === ws)
  return hit ? hit.name : undefined
}

const stateCache = { projects: [] }
const cardProject = new Map()

/** 这张卡属于哪个项目（列表时记住；写操作必须带对项目，否则会打到别的库）。 */
function projOf(id, body) {
  return cardProject.get(id) || projectNameFrom(body && body.workspaceId) || undefined
}
function withProject(path, project) {
  if (!project) return path
  return path + (path.includes('?') ? '&' : '?') + 'project=' + encodeURIComponent(project)
}

async function listRecords(project) {
  stateCache.projects = await projects()
  const name = projectNameFrom(project) || undefined
  const q = name ? ('?project=' + encodeURIComponent(name)) : ''
  const r = await kget('/api/cards' + q)
  const out = (r.cards || []).map(c => recordFrom(c, null))
  for (const rec of out) cardProject.set(rec.id, name || '')
  return out
}

// ---------------- 路由 ----------------

function handler() {
  return async (req, res) => {
    try {
      const u = new URL(req.url || '/', 'http://x')
      const p = u.pathname.startsWith(PREFIX) ? u.pathname.slice(PREFIX.length) : u.pathname
      const method = (req.method || 'GET').toUpperCase()

      if (p === '/events') {
        res.writeHead(200, {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive'
        })
        res.write(': connected\n\n')
        const t = setInterval(() => { try { res.write(': ping\n\n') } catch {} }, 15000)
        req.on('close', () => clearInterval(t))
        return
      }

      if (method === 'GET' && p === '/state') {
        const ws = u.searchParams.get('workspaceId') || ''
        const tasks = await listRecords(ws)
        return send(res, 200, { schemaVersion: 1, revision: Date.now() % 2147483647, tasks, settings: {} })
      }
      if (method === 'GET' && p === '/workspaces') {
        const ps = await projects()
        stateCache.projects = ps
        return send(res, 200, ps.map(x => ({
          id: x.path, path: x.path, title: x.name, sessionCount: 0,
          gitAvailable: false, repoCount: 1
        })))
      }
      if (method === 'GET' && p === '/project-sessions') return send(res, 200, { sessions: [] })
      if (method === 'GET' && p === '/settings') return send(res, 200, {})
      if (method === 'GET' && p === '/templates') return send(res, 200, { templates: [] })
      if (method === 'GET' && p === '/model-catalog') return send(res, 200, { models: [], presets: [] })
      if (method === 'GET' && p === '/diagnostics') return send(res, 200, { tasks: 0, running: 0, orphans: [] })
      if (method === 'GET' && p === '/storage') return send(res, 200, { directory: '', configured: false })
      if (method === 'GET' && p === '/prompt-completions') return send(res, 200, { completions: [] })

      const mTask = p.match(/^\/tasks\/([^/]+)$/)
      if (method === 'GET' && mTask) {
        const id = decodeURIComponent(mTask[1])
        const d = await kget(withProject('/api/card?id=' + encodeURIComponent(id), projOf(id)))
        return send(res, 200, recordFrom(d, d))
      }

      if (method === 'POST' && p === '/tasks') {
        const body = await readBody(req)
        const proj = projectNameFrom(workspaceOf(body))
        const r = await kpost('/api/card', {
          project: proj, title: body.title || '未命名',
          goal: body.description || '', human_gate: 'none'
        })
        if (r.id) cardProject.set(r.id, proj || '')
        return send(res, 200, recordFrom({ id: r.id, title: body.title, goal: body.description }, null))
      }

      const mAct = p.match(/^\/tasks\/([^/]+)\/([\w-]+)$/)
      if (method === 'POST' && mAct) {
        const id = decodeURIComponent(mAct[1])
        const act = mAct[2]
        const body = await readBody(req)
        if (act === 'update') {
          const fields = {}
          if (body.title !== undefined) fields.title = body.title
          if (body.description !== undefined) fields.goal = body.description
          if (body.blockedBy !== undefined) fields.blocked_by = body.blockedBy
          if (Object.keys(fields).length) {
            await kpost('/api/card/edit', { id, fields, ifVersion: body.ifVersion, project: projOf(id, body) })
          }
          if (Array.isArray(body.checklist)) {
            for (const item of body.checklist) {
              const pr = projOf(id, body)
              if (item.id) await kpost('/api/card/checklist', { id, action: item.checked ? 'check' : 'uncheck', item: item.id, note: item.note, project: pr })
              else await kpost('/api/card/checklist', { id, action: 'add', text: item.text || '验收项', project: pr })
            }
          }
          const d = await kget(withProject('/api/card?id=' + encodeURIComponent(id), projOf(id, body)))
          return send(res, 200, recordFrom(d, d))
        }
        if (act === 'move') {
          const to = TO_KERNEL[body.to] || body.to
          if (to === '进行中') {
            const pr = projOf(id, body)
            // 内核认领会校验「卡的执行规格与你声明的一致」；面板按卡自己的规格声明，
            // 不硬写 dsh（否则项目默认 opencode 的卡一律被拒）。
            const d = await kget(withProject('/api/card?id=' + encodeURIComponent(id), pr))
            // /api/card 是扁平的：engine/model/effort 在顶层（不是 d.card）
            const card = (d && (d.card || d)) || {}
            const engine = card.engine && card.engine !== 'any' ? card.engine : 'dsh'
            const model = card.model && card.model !== 'any' ? card.model : undefined
            const effort = card.effort && card.effort !== 'any' ? card.effort : undefined
            const r = await kpost('/api/card/claim', { id, seat: PANEL_SEAT, engine, model, effort, project: pr })
            return send(res, 200, { id, status: 'in_progress', claimedBy: PANEL_SEAT, epoch: r.epoch })
          }
          await kpost('/api/card/move', { id, to, reason: body.reason, ifVersion: body.ifVersion, project: projOf(id, body) })
          return send(res, 200, { id, status: body.to })
        }
        if (act === 'comment') {
          await kpost('/api/card/comment', { id, body: body.body || '', actor: 'human', project: projOf(id, body) })
          return send(res, 200, { id })
        }
        if (act === 'delete') {
          await kpost('/api/card/trash', { id, project: projOf(id, body) })
          return send(res, 200, { id, trashed: true })
        }
        if (act === 'reject') {
          await kpost('/api/card/move', { id, to: '待返工', reason: body.reason || '复核打回', project: projOf(id, body) })
          return send(res, 200, { id })
        }
        if (act === 'cancel') {
          await kpost('/api/card/move', { id, to: '已取消', reason: '界面取消', project: projOf(id, body) })
          return send(res, 200, { id })
        }
        if (act === 'run') {
          const proj = projectNameFrom(body.workspaceId)
          await kpost('/api/run', { project: proj, max: 1, cards: [id] })
          return send(res, 200, { id, started: true })
        }
        throw new Error('这个动作还没接到内核：' + act)
      }

      if (method === 'POST' && p === '/settings/update') return send(res, 200, {})
      if (method === 'POST' && p === '/templates') return send(res, 200, {})
      if (method === 'POST' && p === '/templates/delete') return send(res, 200, {})
      if (method === 'POST' && p === '/queue/clear') return send(res, 200, { cleared: 0 })

      res.statusCode = 404
      res.end()
    } catch (e) {
      fail(res, e)
    }
  }
}

export function apply(ctx) {
  try {
    void ensureKernel()
    ctx.webServer.register({ kind: 'prefix', path: PREFIX, handler: handler() })
  } catch (e) {
    console.warn('[dsh-taskboard] 路由注册失败（面板降级）：', e && e.message)
  }
}
