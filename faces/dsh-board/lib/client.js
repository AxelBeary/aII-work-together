/**
 * dsh-board 浏览器半边（2026-11-19，D-040）
 *
 * 手写模块（不经构建链）：DSH 的模块加载器就是
 *   window.__ModuleLoader__.load({ id, factory })
 * factory 拿到 require，可以取 react / react-dom。
 *
 * 面板本身很薄：全部读写走同源 /board/api/*（宿主代理到内核）。
 * ⛔ 不在浏览器里存任何账本副本；刷新即重新拉。
 */
window.__ModuleLoader__.load({
  id: 'dsh-board',
  factory: function (require) {
    const React = require('react')
    const h = React.createElement
    const ID = 'dsh-board'

    const COLORS = {
      '待认领': '#6c7683', '进行中': '#2f80ed', '待验收': '#9b51e0',
      '核验中': '#f2994a', '完成': '#27ae60', '待返工': '#eb5757',
      '阻塞': '#c0392b', '拍板中': '#d4a017', '已取消': '#95a5a6',
      'trash': '#7f8c8d'
    }

    async function getJSON(url, opt) {
      const r = await fetch(url, opt)
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        const e = j.error
        throw new Error((e && e.message) || (typeof e === 'string' ? e : 'HTTP ' + r.status))
      }
      return j
    }

    function Button(props) {
      return h('button', {
        onClick: props.onClick,
        style: {
          padding: '4px 10px', marginRight: 6, marginTop: 4, cursor: 'pointer',
          borderRadius: 6, border: '1px solid ' + (props.danger ? '#eb5757' : '#d0d7de'),
          background: props.primary ? '#2f80ed' : (props.danger ? '#fff5f5' : '#fff'),
          color: props.primary ? '#fff' : (props.danger ? '#c0392b' : '#24292f'),
          fontSize: 12
        }
      }, props.children)
    }

    function Card(props) {
      const t = props.task
      return h('div', {
        onClick: props.onClick,
        style: {
          padding: '8px 10px', marginBottom: 8, borderRadius: 8, cursor: 'pointer',
          border: '1px solid #e1e4e8', background: '#fff',
          borderLeft: '4px solid ' + (COLORS[t.state] || '#ccc')
        }
      },
        h('div', { style: { fontSize: 13, fontWeight: 600 } }, t.title || t.id),
        h('div', { style: { fontSize: 11, color: '#6c7683', marginTop: 3 } },
          t.id + ' · ' + t.state + (t.holder ? ' · ' + t.holder : '')),
        t.goal ? h('div', { style: { fontSize: 11, color: '#8b949e', marginTop: 2 } },
          String(t.goal).slice(0, 60)) : null
      )
    }

    function Detail(props) {
      const c = props.card
      if (!c) return h('div', { style: { color: '#8b949e', fontSize: 12 } }, '选一张卡看详情')
      const reload = props.onChanged
      async function post(path, body) {
        try {
          await getJSON('/board' + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(Object.assign({ id: c.id, project: props.project }, body || {}))
          })
          await reload()
        } catch (e) { alert(e.message || '失败') }
      }
      return h('div', { style: { padding: '4px 0' } },
        h('div', { style: { fontSize: 15, fontWeight: 700 } }, c.title),
        h('div', { style: { fontSize: 11, color: '#6c7683', margin: '4px 0 10px' } },
          c.id + ' · ' + c.state + ' · v' + (c.version || 1) + (c.holder ? ' · 持有 ' + c.holder : '')),
        h('div', null,
          h(Button, { onClick: () => {
            const body = prompt('评论内容（同一句重发不会产生第二条）')
            if (body) post('/api/card/comment', { body, actor: 'human' })
          } }, '评论'),
          h(Button, { onClick: () => {
            const title = prompt('新标题', c.title)
            if (title) post('/api/card/edit', { fields: { title }, ifVersion: c.version || 1 })
          } }, '改标题'),
          c.state === '进行中' ? h(Button, { danger: true, onClick: () => {
            const reason = prompt('回退原因', '执行失败')
            if (reason) post('/api/card/revert', { reason, actor: 'system' })
          } }, '回退') : null,
          (c.state === '待认领' || c.state === '待返工') ? h(Button, { primary: true, onClick: () => {
            post('/api/card/move', { to: '进行中', actor: 'human' })
          } }, '开始') : null,
          (c.state === '进行中') ? h(Button, { onClick: () => {
            post('/api/card/move', { to: '已取消', actor: 'human', reason: '界面取消' })
          } }, '取消') : null,
          !c.trashed_at ? h(Button, { danger: true, onClick: () => {
            if (confirm('移到回收站？事件流保留，可恢复。')) post('/api/card/trash', {})
          } }, '删除') : h(Button, { onClick: () => post('/api/card/trash', { restore: true }) }, '恢复')
        ),
        c.comments && c.comments.length ? h('div', { style: { marginTop: 12 } },
          h('div', { style: { fontSize: 12, fontWeight: 600 } }, '评论 ' + c.comments.length),
          c.comments.slice(-6).map(x => h('div', { key: x.id, style: { fontSize: 12, marginTop: 4 } },
            h('b', null, (x.author || '') + ' '), String(x.body || '').slice(0, 300)))
        ) : null,
        c.checklist && c.checklist.length ? h('div', { style: { marginTop: 12 } },
          h('div', { style: { fontSize: 12, fontWeight: 600 } },
            '验收清单 ' + c.checklist.filter(x => x.checked).length + '/' + c.checklist.length),
          c.checklist.map(x => h('div', {
            key: x.id,
            onClick: () => post('/api/card/checklist', { action: x.checked ? 'uncheck' : 'check', item: x.id }),
            style: { fontSize: 12, marginTop: 3, cursor: 'pointer' }
          }, (x.checked ? '☑ ' : '☐ ') + x.text))
        ) : null,
        c.executions && c.executions.length ? h('div', { style: { marginTop: 12, fontSize: 12 } },
          h('div', { style: { fontWeight: 600 } }, '执行记录 ' + c.executions.length),
          c.executions.slice(-3).map(e => h('div', { key: e.id, style: { marginTop: 3, color: '#6c7683' } },
            (e.outcome || '') + ' / ' + (e.trigger || '') + (e.error ? ' · ' + String(e.error).slice(0, 60) : '')))
        ) : null,
        c.trashed_at ? h('div', { style: { marginTop: 10, fontSize: 12, color: '#c0392b' } }, '已在回收站') : null
      )
    }

    function App() {
      const [state, setState] = React.useState(null)
      const [cards, setCards] = React.useState([])
      const [sel, setSel] = React.useState(null)
      const [detail, setDetail] = React.useState(null)
      const [err, setErr] = React.useState('')

      async function load() {
        try {
          const s = await getJSON('/board/api/state')
          setState(s)
          const proj = s.current || ''
          const cs = await getJSON('/board/api/cards?project=' + encodeURIComponent(proj))
          setCards(cs.cards || [])
          if (sel) {
            const d = await getJSON('/board/api/card?project=' + encodeURIComponent(proj) + '&id=' + encodeURIComponent(sel))
            setDetail(d)
          }
          setErr('')
        } catch (e) { setErr(e.message || String(e)) }
      }

      React.useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t) }, [sel])

      const groups = {}
      for (const c of cards) { (groups[c.state] = groups[c.state] || []).push(c) }
      const order = ['待认领', '进行中', '待验收', '核验中', '待返工', '阻塞', '拍板中', '完成']

      return h('div', { style: { display: 'flex', height: '100%', fontFamily: 'system-ui, sans-serif', background: '#f6f8fa' } },
        h('div', { style: { width: 300, borderRight: '1px solid #e1e4e8', overflow: 'auto', padding: 10, background: '#fff' } },
          h('div', { style: { display: 'flex', alignItems: 'center', marginBottom: 8 } },
            h('b', { style: { fontSize: 14, flex: 1 } }, '看板'),
            h(Button, { onClick: load }, '刷新')),
          err ? h('div', { style: { color: '#c0392b', fontSize: 12, marginBottom: 8 } }, err) : null,
          order.map(st => groups[st] ? h('div', { key: st, style: { marginBottom: 10 } },
            h('div', { style: { fontSize: 12, color: COLORS[st] || '#666', fontWeight: 700, margin: '6px 0' } },
              st + '（' + groups[st].length + '）'),
            groups[st].map(c => h(Card, { key: c.id, task: c, onClick: () => setSel(c.id) }))
          ) : null)
        ),
        h('div', { style: { flex: 1, overflow: 'auto', padding: 16 } },
          h(Detail, { card: detail, project: state && state.current, onChanged: load })
        )
      )
    }

    function Icon() {
      return h('span', { style: { fontSize: 14 } }, '▦')
    }

    function apply(ctx) {
      try {
        const slots = ctx.get ? ctx.get('slots') : undefined
        if (!slots) return
        ctx.effect ? ctx.effect(() => {
          const d1 = slots.inject('main', () => slots.register({ name: 'main', key: ID }, App))
          const d2 = slots.inject('sidebar.panellist', () => slots.register(
            { name: 'sidebar.panellist', id: ID, order: 11, label: () => '看板' }, Icon))
          return () => { d1(); d2() }
        }, 'dsh-board: mount') : null
      } catch (e) {
        console.error('[dsh-board] client mount failed:', e)
      }
    }

    return { name: 'dsh-board/client', inject: ['slots'], apply: apply }
  }
})
