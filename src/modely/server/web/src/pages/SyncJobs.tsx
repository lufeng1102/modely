import { useState, useEffect } from 'react'
import { createSyncJob, getSyncJob, getSyncLogs, listSyncJobs } from '../api/client'
import type { SyncJobData } from '../api/types'

export default function SyncJobs() {
  const [jobs, setJobs] = useState<SyncJobData[]>([])
  const [targetId, setTargetId] = useState('')
  const [resource, setResource] = useState('hf://models/test/model')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const loadJobs = async () => {
    setLoading(true)
    try {
      const r = await listSyncJobs()
      setJobs(r.data.jobs || [])
    } catch (e: unknown) { /* no jobs yet */ }
    finally { setLoading(false) }
  }

  useEffect(() => { loadJobs() }, [])

  // Auto-refresh when there are syncing jobs
  useEffect(() => {
    if (jobs.some(j => j.status === 'syncing')) {
      const t = setInterval(loadJobs, 2000)
      return () => clearInterval(t)
    }
  }, [jobs])

  const create = async () => {
    try {
      const r = await createSyncJob({ target_id: targetId || 'target-1', resource })
      setJobs(prev => [r.data, ...prev])
    } catch (e: unknown) { setError((e as Error).message) }
  }

  const [selectedJob, setSelectedJob] = useState<SyncJobData | null>(null)
  const [logs, setLogs] = useState('')

  const viewLogs = async (id: string) => {
    try {
      const j = await getSyncJob(id)
      setSelectedJob(j.data)
      // Build a readable summary from job metadata
      const wr = (j.data.metadata as Record<string,unknown> | null)?.worker_result as Record<string,unknown> | null
      if (wr) {
        const lines: string[] = []
        lines.push(`Status: ${wr.status}`)
        lines.push(`Asset ID: ${wr.asset_id || '-'}`)
        lines.push(`Version ID: ${wr.version_id || '-'}`)
        const manifest = wr.manifest as Record<string,unknown> | null
        if (manifest) {
          const mf = manifest.metadata as Record<string,unknown> | null
          lines.push(`Storage: ${manifest.local_path || '-'}`)
          const files = wr.files as Array<Record<string,unknown>> | null
          if (files && files.length > 0) {
            lines.push(`\nDownloaded files (${files.length}):`)
            for (const f of files) {
              const lp = (f.local_path as string) || (f.uri as string) || '-'
              lines.push(`  ${f.path}  (${lp})`)
            }
          }
        }
        setLogs(lines.join('\n'))
      } else {
        setLogs(JSON.stringify(j.data, null, 2))
      }
    } catch (e: unknown) { setError((e as Error).message) }
  }

  return (
    <div>
      <h2>Sync Jobs</h2>
      <div style={{ marginBottom: 16 }}>
        <input placeholder="Target ID" value={targetId} onChange={e => setTargetId(e.target.value)} style={{ marginRight: 8 }} />
        <input placeholder="Resource URI" value={resource} onChange={e => setResource(e.target.value)} style={{ marginRight: 8 }} />
        <button onClick={create}>Create Sync Job</button>
      </div>
      {loading && <p>Loading...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {!loading && jobs.length === 0 && (
        <p style={{ color: '#999', marginBottom: 16 }}>No sync jobs yet. Create one below.</p>
      )}
      {!loading && jobs.length > 0 && (
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['ID','Target','Status','Attempts','Error'].map(h => <th key={h} style={{textAlign:'left',padding:8,borderBottom:'1px solid #ddd'}}>{h}</th>)}</tr></thead>
        <tbody>{jobs.map(j => (
          <tr key={j.id} style={{ cursor: 'pointer' }} onClick={() => viewLogs(j.id)}>
            <td style={{padding:8,borderBottom:'1px solid #eee'}}>{j.id}</td>
            <td style={{padding:8}}>{j.target_id}</td>
            <td style={{padding:8}}>{j.status}</td>
            <td style={{padding:8}}>{j.attempts}</td>
            <td style={{padding:8,color:j.error?'red':'#999'}}>{j.error || '-'}</td>
          </tr>
        ))}</tbody>
      </table>
      )}
      {selectedJob && (
        <div style={{ marginTop: 16, padding: 16, background: '#fff', border: '1px solid #ddd' }}>
          <h4>Logs for {selectedJob.id}</h4>
          <pre style={{ fontSize: '0.85em', maxHeight: 300, overflow: 'auto' }}>{logs}</pre>
        </div>
      )}
    </div>
  )
}
