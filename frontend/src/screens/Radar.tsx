import { useState } from 'react'
import { api } from '../api/client'
import { Screen, Title } from '../app/Screen'
import { useStore } from '../app/store'
import { Badge } from '../components/Badge'
import { Card } from '../components/Card'
import { Disclosure } from '../components/Disclosure'
import { PillButton } from '../components/PillButton'
import { ErrorBox, Loading } from '../components/States'
import { useLang } from '../i18n'
import { useAsync } from '../lib/useAsync'

export function Radar() {
  const { t } = useLang()
  const { basket, runs } = useStore()
  const lastRun = Object.values(runs).sort((a, b) => ((a.closed_at ?? '') < (b.closed_at ?? '') ? 1 : -1))[0]
  const runId = (basket?.status === 'closed' ? basket.run_id : null) ?? lastRun?.run_id ?? null
  const g = useAsync(() => api.radarGraph(), [])
  const f = useAsync(async () => (runId ? api.radarFlags(runId) : null), [runId])
  const [disputed, setDisputed] = useState(false)
  const graph = g.data
  const flags = f.data?.flags ?? []
  const W = 340
  const H = 250
  const pos = new Map<string, { x: number; y: number }>()
  graph?.nodes.forEach((n, i) => {
    const a = (i / graph.nodes.length) * Math.PI * 2 - Math.PI / 2
    pos.set(n.id, { x: W / 2 + Math.cos(a) * (W / 2 - 24), y: H / 2 + Math.sin(a) * (H / 2 - 20) })
  })
  const hot = new Set<string>(flags.flatMap((fl) => fl.participants.map((p) => p.id)))
  return (
    <Screen wide>
      <div><Title sub={t('radar.sub')}>{t('radar.title')}</Title></div>
      <div><Badge kind="demo" testId="badge-demo-radar" text={t('radar.note')} /></div>
      {g.loading ? <Loading /> : null}
      {g.error ? <ErrorBox detail={g.error} onRetry={g.reload} /> : null}
      <div className="grid gap-4 lg:grid-cols-2 items-start">
      {graph ? (
        <Card>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label={t('radar.title')}>
            {graph.edges.map((e, i) => {
              const a = pos.get(e.from)
              const b = pos.get(e.to)
              if (!a || !b) return null
              const isHot = hot.has(e.from) && hot.has(e.to)
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={isHot ? 'var(--warn)' : 'var(--s3)'} strokeWidth={isHot ? 2 : 1.5} />
            })}
            {graph.nodes.map((n) => {
              const p = pos.get(n.id)!
              const isHot = hot.has(n.id)
              return (
                <g key={n.id}>
                  <title>{n.name}</title>
                  <circle cx={p.x} cy={p.y} r={isHot ? 12 : 10} fill={isHot ? 'var(--warn-bg)' : 'var(--s1)'} stroke={isHot ? 'var(--warn)' : 'var(--mute)'} strokeWidth="1.5" />
                  <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize="7.5" fontFamily="Geist, system-ui, sans-serif" fill={isHot ? 'var(--warn)' : 'var(--ink-3)'}>{n.id}</text>
                </g>
              )
            })}
          </svg>
        </Card>
      ) : null}
      <div className="flex flex-col gap-4">
      {runId && f.data && flags.length === 0 ? <p className="caption">{t('radar.none')}</p> : null}
      {!runId ? <p className="text-[14px] text-ink3" data-testid="radar-after-close">{t('radar.afterClose')}</p> : null}
      {flags.map((fl) => (
        <Card key={fl.flag_id}>
          <p className="text-[15px] text-warn">⚑ {t('radar.flag')}</p>
          <div className="caption mt-2">{t('radar.participants')}</div>
          <ul className="text-[13px] text-ink3 leading-[1.8]">
            {fl.participants.map((p) => <li key={p.id}><span className="mono text-ink">{p.id}</span> · {p.name.replace(/\s*\([^)]*\)/g, '')}</li>)}
          </ul>
          <Disclosure label={t('radar.facts')}>
            <ul className="mt-1">
              {fl.edges.map((e, i) => <li key={i} className="py-1"><span className="mono text-ink">{e.from}–{e.to}</span> · {e.fact}</li>)}
            </ul>
          </Disclosure>
          {disputed ? <p className="text-[13px] text-lime mt-2" role="status">{t('radar.disputeText')}</p> : <PillButton variant="ghost" className="mt-3" onClick={() => setDisputed(true)}>{t('radar.dispute')}</PillButton>}
        </Card>
      ))}
      {!runId && graph ? (
        <Card>
          <div className="caption mb-1">{t('radar.facts')}</div>
          <ul className="text-[13px] text-ink3">
            {graph.edges.slice(0, 6).map((e, i) => <li key={i} className="py-1"><span className="mono text-ink">{e.from}–{e.to}</span> · {e.fact}</li>)}
          </ul>
        </Card>
      ) : null}
      </div>
      </div>
    </Screen>
  )
}
