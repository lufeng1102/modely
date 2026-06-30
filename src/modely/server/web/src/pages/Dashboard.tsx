import { useState, useEffect } from 'react'
import { getRiskTrends, getUsagePopularity } from '../api/client'
import type { RiskTrendsData, UsageStatsData } from '../api/types'

export default function Dashboard() {
  const [risk, setRisk] = useState<RiskTrendsData | null>(null)
  const [usage, setUsage] = useState<UsageStatsData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getRiskTrends(), getUsagePopularity()])
      .then(([r, u]) => { setRisk(r.data); setUsage(u.data) })
      .catch(e => setError((e as Error).message))
  }, [])

  return (
    <div>
      <h2>Dashboard</h2>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {risk && (
          <div style={{ padding: 16, background: '#fff', border: '1px solid #ddd', borderRadius: 8 }}>
            <h4>Risk Trends ({risk.period})</h4>
            <p>Total Findings: {risk.total_findings}</p>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ color: '#f44336' }}>High: {risk.high_severity}</span>
              <span style={{ color: '#ff9800' }}>Med: {risk.medium_severity}</span>
              <span style={{ color: '#4caf50' }}>Low: {risk.low_severity}</span>
            </div>
            <p>Trend: {risk.trend_direction}</p>
          </div>
        )}
        {usage && (
          <div style={{ padding: 16, background: '#fff', border: '1px solid #ddd', borderRadius: 8 }}>
            <h4>Usage Popularity</h4>
            {usage.assets.length === 0 ? <p>No usage data</p> : (
              <table style={{ width: '100%' }}>
                <thead><tr>{['Asset','Downloads','Score'].map(h => <th key={h} style={{textAlign:'left'}}>{h}</th>)}</tr></thead>
                <tbody>{usage.assets.slice(0, 10).map(a => (
                  <tr key={a.asset_id}><td>{a.asset_id}</td><td>{a.download_count}</td><td>{a.popularity_score}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
