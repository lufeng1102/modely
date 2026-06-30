import { useState, useEffect, useCallback } from 'react'
import { getWatchTargets, checkWatchDrift, getWatchHistory } from '../api/client'
import type { WatchTarget, DriftResultItem, WatchHistoryEvent } from '../api/types'

const DEFAULT_WATCH_CONFIG = '~/.modely/voice-models-watch.json'

function statusBadge(status: string | undefined) {
  const color = status === 'error' ? '#f44336' : '#4caf50'
  return <span style={{ color, fontWeight: 600, fontSize: '0.85rem' }}>{status || 'unknown'}</span>
}

function timeAgo(iso?: string): string {
  if (!iso) return '-'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function Watch() {
  const [targets, setTargets] = useState<WatchTarget[]>([])
  const [drift, setDrift] = useState<DriftResultItem[]>([])
  const [history, setHistory] = useState<WatchHistoryEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [selectedKey, setSelectedKey] = useState('')

  const fetchTargets = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await getWatchTargets(DEFAULT_WATCH_CONFIG)
      setTargets(res.data.targets)
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }, [])

  const fetchHistory = useCallback(async (targetKey?: string) => {
    try {
      const res = await getWatchHistory(targetKey || undefined)
      setHistory(res.data.events)
    } catch { /* history is optional; ignore errors */ }
  }, [])

  useEffect(() => { fetchTargets(); fetchHistory() }, [fetchTargets, fetchHistory])

  const handleCheck = async () => {
    setChecking(true); setError('')
    try {
      const res = await checkWatchDrift(DEFAULT_WATCH_CONFIG)
      setDrift(res.data.results)
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setChecking(false) }
  }

  const handleTargetClick = (key: string) => {
    setSelectedKey(key === selectedKey ? '' : key)
    fetchHistory(key)
  }

  return (
    <div>
      <h2>Watch — ModelScope Monitoring</h2>
      <p style={{ color: '#666', marginBottom: 16 }}>
        Monitored ModelScope speech-model repositories. Drift check compares remote fingerprints
        without downloading.
      </p>

      {error && <div style={{ color: '#f44336', marginBottom: 12, padding: '8px 12px', background: '#ffeef0', borderRadius: 6 }}>{error}</div>}

      {loading ? <p>Loading...</p> : (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
          {/* Left column: targets table */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>Targets ({targets.length})</h3>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={fetchTargets} style={{ padding: '6px 14px', cursor: 'pointer', border: 'none', borderRadius: 6, background: '#1976d2', color: '#fff' }}>
                  Refresh
                </button>
                <button onClick={handleCheck} disabled={checking} style={{
                  padding: '6px 14px', cursor: checking ? 'wait' : 'pointer', border: 'none', borderRadius: 6,
                  background: '#1976d2', color: '#fff', opacity: checking ? 0.7 : 1,
                }}>
                  {checking ? 'Checking...' : 'Check Drift'}
                </button>
              </div>
            </div>

            {targets.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#999', border: '1px dashed #ddd', borderRadius: 8 }}>
                No watch targets configured. Run <code>modely-ai watch init</code> to create a config.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ background: '#f9f9f9' }}>
                    {['Source', 'Type', 'Repo ID', 'Revision', 'Last Checked', 'Status'].map(h => (
                      <th key={h} style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {targets.map(t => {
                    const driftItem = drift.find(d => d.key === t.key)
                    const displayStatus = driftItem ? driftItem.status : (t.error ? 'error' : 'idle')
                    return (
                      <tr key={t.key} onClick={() => handleTargetClick(t.key)} style={{
                        cursor: 'pointer',
                        background: selectedKey === t.key ? '#e3f2fd' : 'transparent',
                      }}>
                        <td style={{ padding: 10, borderBottom: '1px solid #eee' }}><code>{t.source}</code></td>
                        <td style={{ padding: 10, borderBottom: '1px solid #eee' }}><code>{t.repo_type || 'model'}</code></td>
                        <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>{t.repo_id}</td>
                        <td style={{ padding: 10, borderBottom: '1px solid #eee' }}><code>{t.revision}</code></td>
                        <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>{timeAgo(t.last_checked_at)}</td>
                        <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>{statusBadge(displayStatus)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}

            {/* Drift results detail */}
            {drift.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h4>Latest Drift Check Results</h4>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ background: '#f9f9f9' }}>
                      {['Repo ID', 'Status', 'Previous Fingerprint', 'Current Fingerprint'].map(h => (
                        <th key={h} style={{ textAlign: 'left', padding: 8, borderBottom: '2px solid #ddd' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {drift.map(d => (
                      <tr key={d.key} style={{ background: d.status === 'drifted' ? '#fff8e1' : d.status === 'error' ? '#ffeef0' : 'transparent' }}>
                        <td style={{ padding: 8, borderBottom: '1px solid #eee' }}>{d.repo_id}</td>
                        <td style={{ padding: 8, borderBottom: '1px solid #eee' }}>{statusBadge(d.status)}</td>
                        <td style={{ padding: 8, borderBottom: '1px solid #eee', fontFamily: 'monospace', fontSize: '0.75rem' }}>{d.previous_fingerprint ? d.previous_fingerprint.slice(0, 12) + '...' : '-'}</td>
                        <td style={{ padding: 8, borderBottom: '1px solid #eee', fontFamily: 'monospace', fontSize: '0.75rem' }}>{d.current_fingerprint ? d.current_fingerprint.slice(0, 12) + '...' : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Right column: history timeline */}
          <div>
            <h3 style={{ marginTop: 0 }}>
              {selectedKey ? `Change History` : 'Recent Changes'}
            </h3>
            {selectedKey && (
              <div style={{ marginBottom: 8, fontSize: '0.85rem', color: '#666', wordBreak: 'break-all' }}>
                {selectedKey}
              </div>
            )}
            {history.length === 0 ? (
              <p style={{ color: '#999', fontSize: '0.9rem' }}>
                {selectedKey ? 'No change history for this target.' : 'Select a target to see its change history.'}
              </p>
            ) : (
              <div style={{ maxHeight: 500, overflowY: 'auto' }}>
                {history.map((evt, idx) => (
                  <div key={idx} style={{
                    padding: '10px 12px', marginBottom: 8, borderLeft: `3px solid ${evt.event === 'downloaded' ? '#4caf50' : evt.event === 'error' ? '#f44336' : '#ff9800'}`,
                    background: '#fff', borderRadius: '0 6px 6px 0', fontSize: '0.85rem',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{evt.event}</span>
                      <span style={{ color: '#999' }}>{timeAgo(evt.timestamp)}</span>
                    </div>
                    <div style={{ color: '#666', wordBreak: 'break-all' }}>{evt.repo_id}</div>
                    {evt.error && <div style={{ color: '#f44336', marginTop: 4 }}>{evt.error}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
