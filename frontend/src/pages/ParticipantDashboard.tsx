import { useState, useEffect, Component, ErrorInfo, ReactNode } from 'react'
import { api } from '../services/api'
import VSCodeIDE from '../components/VSCodeIDE'
import './Dashboard.css'

/* Error boundary to prevent IDE crashes from losing user code */
class IDEErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('IDE crash:', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#1e1e1e', color: '#ccc', fontFamily: 'Poppins, sans-serif' }}>
          <div style={{ textAlign: 'center' }}>
            <h3 style={{ color: '#f14c4c', marginBottom: 12 }}>IDE encountered an error</h3>
            <p style={{ color: '#888', marginBottom: 16 }}>Your code has been auto-saved.</p>
            <button
              onClick={() => this.setState({ hasError: false })}
              style={{ padding: '8px 24px', background: '#007acc', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontFamily: 'Poppins, sans-serif', fontWeight: 600 }}
            >
              Reload IDE
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

interface ParticipantDashboardProps {
  user: any
  onLogout: () => void
}

export default function ParticipantDashboard({ user, onLogout }: ParticipantDashboardProps) {
  const [activeTab, setActiveTab] = useState('challenges')
  const [challenges, setChallenges] = useState<any[]>([])
  const [selectedChallenge, setSelectedChallenge] = useState<any>(null)
  const [language, setLanguage] = useState('python')
  const [code, setCode] = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  const [mySubmissions, setMySubmissions] = useState<any[]>([])

  useEffect(() => {
    loadChallenges()
    loadMySubmissions()
  }, [])

  useEffect(() => {
    if (selectedChallenge && language) {
      loadDraft()
    }
  }, [selectedChallenge, language])

  useEffect(() => {
    if (selectedChallenge && language && code) {
      const timer = setTimeout(() => saveDraft(), 2000)
      return () => clearTimeout(timer)
    }
  }, [code])

  const loadChallenges = async () => {
    try {
      const response = await api.get('/challenges')
      setChallenges(response.data || [])
    } catch (error) {
      console.error('Failed to load challenges', error)
    }
  }

  const loadMySubmissions = async () => {
    try {
      const response = await api.get('/submissions/my-submissions')
      setMySubmissions(response.data || [])
    } catch (error) {
      console.error('Failed to load submissions', error)
    }
  }

  const loadDraft = async () => {
    if (!selectedChallenge) return
    try {
      const response = await api.post('/drafts/load', {
        question_id: selectedChallenge.id,
        language
      })
      setCode(response.data?.code || getDefaultCode(language, selectedChallenge.function_name))
    } catch (error) {
      setCode(getDefaultCode(language, selectedChallenge.function_name))
    }
  }

  const saveDraft = async () => {
    if (!selectedChallenge || !code) return
    try {
      await api.post('/drafts/save', {
        question_id: selectedChallenge.id,
        language,
        code
      })
    } catch (error) {
      console.error('Failed to save draft', error)
    }
  }

  const handleTestRun = async () => {
    if (!selectedChallenge || !code) return
    setLoading(true)
    setOutput('Running tests...')
    try {
      const response = await api.post('/submissions/test-run', {
        question_id: selectedChallenge.id,
        language,
        code
      })
      const result = response.data
      const lines: string[] = []
      lines.push(`Exit Code: ${result?.exit_code ?? 0}`)
      lines.push(`Execution: ${result?.execution_time_ms ?? 0} ms`)
      if (result?.error_type) lines.push(`Error Type: ${result.error_type}`)
      if (result?.stdout) {
        lines.push('--- STDOUT ---')
        lines.push(result.stdout)
      }
      if (result?.stderr) {
        lines.push('--- STDERR ---')
        lines.push(result.stderr)
      }
      if (!result?.stdout && !result?.stderr) lines.push('(No output)')
      setOutput(lines.join('\n'))
    } catch (error: any) {
      setOutput('Error: ' + (error.response?.data?.error || 'Test run failed'))
    } finally {
      setLoading(false)
    }
  }

  const handleTerminalCommand = async (cmd: string): Promise<string> => {
    try {
      const response = await api.post('/terminal/execute', { command: cmd })
      return response.data?.output || ''
    } catch (e: any) {
      throw new Error(e.response?.data?.error || 'Command failed')
    }
  }

  const handleSubmit = async () => {
    if (!selectedChallenge || !code) return
    setLoading(true)
    setOutput('Submitting solution...')
    try {
      const response = await api.post('/submissions/submit', {
        question_id: selectedChallenge.id,
        language,
        code
      })
      const result = response.data || {}
      const submissionId = result?.submission_id
      setOutput(`Submission queued (ID: ${submissionId}). Waiting for judge...`)

      if (submissionId) {
        let done = false
        for (let i = 0; i < 60; i++) {
          await new Promise(resolve => setTimeout(resolve, 1000))
          const statusResp = await api.get(`/submissions/${submissionId}`)
          const sub = statusResp.data
          if (sub?.status === 'queued' || sub?.status === 'running' || sub?.status === 'pending') {
            setOutput(`Submission ${submissionId}: ${sub.status}...`)
            continue
          }
          done = true
          const lines: string[] = []
          lines.push(`Submission ${submissionId}: ${sub?.status || 'unknown'}`)
          if (typeof sub?.score === 'number') lines.push(`Score: ${sub.score}/${sub.max_score ?? 100}`)
          if (sub?.execution_time !== undefined && sub?.execution_time !== null) {
            lines.push(`Execution Time: ${sub.execution_time}s`)
          }
          if (sub?.error_type) lines.push(`Error Type: ${sub.error_type}`)
          if (sub?.error_message) lines.push(`Error: ${sub.error_message}`)
          setOutput(lines.join('\n'))
          break
        }
        if (!done) {
          setOutput(`Submission ${submissionId} is still in queue. Check Submissions tab for updates.`)
        }
      }
      await loadMySubmissions()
    } catch (error: any) {
      setOutput('Error: ' + (error.response?.data?.error || 'Submission failed'))
    } finally {
      setLoading(false)
    }
  }

  const downloadPDF = async (questionId: string) => {
    try {
      const response = await api.get(`/challenges/${questionId}/pdf`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${questionId}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (error) {
      alert('Failed to download PDF')
    }
  }

  const getDefaultCode = (lang: string, functionName: string = 'solution') => {
    const templates: any = {
      python: `def ${functionName}(*args):\n    # Add parameters as per problem statement\n    pass\n`,
      java: 'public class Solution {\n    public static void main(String[] args) {\n        // Write your solution here\n    }\n}\n',
      c: '#include <stdio.h>\n\nint main() {\n    // Write your solution here\n    return 0;\n}\n',
      cpp: '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Write your solution here\n    return 0;\n}\n',
      javascript: `function ${functionName}(...args) {\n    // Add parameters as per problem statement\n}\n`,
      csharp: 'using System;\n\nclass Program {\n    static void Main() {\n        // Write your solution here\n    }\n}\n'
    }
    return templates[lang] || ''
  }

  const getBestScore = (questionId: string) => {
    const subs = mySubmissions.filter(s => s.question_id === questionId && s.status === 'completed')
    if (subs.length === 0) return null
    return Math.max(...subs.map(s => s.score || 0))
  }

  const solvedCount = challenges.filter(c => getBestScore(c.id) !== null).length

  return (
    <div className="p-layout">
      {/* Sidebar */}
      <aside className="p-sidebar">
        <div className="p-sidebar-header">
          <div className="p-logo">CC</div>
          <div className="p-brand-text">
            <span className="p-brand-name">Creative Clash</span>
            <span className="p-brand-sub">Algorithm Battle 2026</span>
          </div>
        </div>

        <div className="p-user-card">
          <div className="p-user-avatar">{user.username.charAt(0).toUpperCase()}</div>
          <div className="p-user-info">
            <span className="p-user-name">{user.username}</span>
            <span className="p-user-stats">{solvedCount}/{challenges.length} solved</span>
          </div>
        </div>

        <nav className="p-nav">
          <button
            className={`p-nav-btn ${activeTab === 'challenges' && !selectedChallenge ? 'active' : ''}`}
            onClick={() => { setActiveTab('challenges'); setSelectedChallenge(null) }}
          >
            <span className="p-nav-label">Challenges</span>
            <span className="p-nav-badge">{challenges.length}</span>
          </button>
          <button
            className={`p-nav-btn ${activeTab === 'submissions' ? 'active' : ''}`}
            onClick={() => { setActiveTab('submissions'); setSelectedChallenge(null) }}
          >
            <span className="p-nav-label">Submissions</span>
            <span className="p-nav-badge">{mySubmissions.length}</span>
          </button>
        </nav>

        {/* Challenge list */}
        {activeTab === 'challenges' && !selectedChallenge && (
          <div className="p-challenge-list">
            {challenges.map(c => {
              const best = getBestScore(c.id)
              return (
                <button
                  key={c.id}
                  className={`p-challenge-row ${best !== null ? 'solved' : ''}`}
                  onClick={() => setSelectedChallenge(c)}
                >
                  <span className="p-challenge-num">#{c.number}</span>
                  <span className="p-challenge-title">{c.title}</span>
                  {best !== null ? (
                    <span className={`p-challenge-badge done ${best === c.max_score ? 'perfect' : ''}`}>{best}/{c.max_score}</span>
                  ) : (
                    <span className="p-challenge-badge open">Open</span>
                  )}
                </button>
              )
            })}
          </div>
        )}

        {/* Active challenge */}
        {selectedChallenge && (
          <div className="p-active-section">
            <div className="p-active-info">
              <span className="p-active-label">Current Challenge</span>
              <span className="p-active-name">#{selectedChallenge.number} {selectedChallenge.title}</span>
              <span className="p-active-meta">{selectedChallenge.function_name}()</span>
            </div>
            <button className="p-action-btn" onClick={() => downloadPDF(selectedChallenge.id)}>
              Download PDF
            </button>
            <button className="p-action-btn secondary" onClick={() => setSelectedChallenge(null)}>
              Back to challenges
            </button>
          </div>
        )}

        <div className="p-sidebar-bottom">
          <button onClick={onLogout} className="p-logout">Log out</button>
        </div>
      </aside>

      {/* Main */}
      <main className="p-main">
        {/* Challenges grid */}
        {activeTab === 'challenges' && !selectedChallenge && (
          <div className="p-content">
            <div className="p-content-header">
              <div>
                <h1 className="p-heading">Challenges</h1>
                <p className="p-subtext">{challenges.length} problems &middot; {solvedCount} solved</p>
              </div>
              <div className="p-progress">
                <div className="p-progress-track">
                  <div className="p-progress-fill" style={{ width: challenges.length > 0 ? `${(solvedCount / challenges.length) * 100}%` : '0%' }} />
                </div>
                <span className="p-progress-label">{challenges.length > 0 ? Math.round((solvedCount / challenges.length) * 100) : 0}%</span>
              </div>
            </div>
            <div className="p-grid">
              {challenges.map(c => {
                const best = getBestScore(c.id)
                const isPerfect = best === c.max_score
                return (
                  <div key={c.id} className={`p-card ${isPerfect ? 'perfect' : ''} ${best !== null && !isPerfect ? 'partial' : ''}`}>
                    <div className="p-card-header">
                      <span className="p-card-number">Q{c.number}</span>
                      {best !== null ? (
                        <span className={`p-card-status ${isPerfect ? 'perfect' : 'partial'}`}>
                          {best}/{c.max_score}
                        </span>
                      ) : (
                        <span className="p-card-status new">New</span>
                      )}
                    </div>
                    <h3 className="p-card-name">{c.title}</h3>
                    <div className="p-card-info">
                      <code>{c.function_name}()</code>
                    </div>
                    <div className="p-card-footer">
                      <button onClick={() => downloadPDF(c.id)} className="p-card-btn secondary">PDF</button>
                      <button onClick={() => setSelectedChallenge(c)} className="p-card-btn primary">
                        {best !== null ? 'Retry' : 'Solve'}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* IDE */}
        {activeTab === 'challenges' && selectedChallenge && (
          <IDEErrorBoundary>
            <VSCodeIDE
              code={code}
              onChange={(v) => setCode(v)}
              language={language}
              onLanguageChange={(lang) => setLanguage(lang)}
              onTestRun={handleTestRun}
              onSubmit={handleSubmit}
              loading={loading}
              output={output}
              onTerminalCommand={handleTerminalCommand}
              functionName={selectedChallenge.function_name}
            />
          </IDEErrorBoundary>
        )}

        {/* Submissions */}
        {activeTab === 'submissions' && (
          <div className="p-content">
            <div className="p-content-header">
              <div>
                <h1 className="p-heading">Submissions</h1>
                <p className="p-subtext">{mySubmissions.length} total submissions</p>
              </div>
            </div>
            <div className="p-table-wrap">
              <table className="p-table">
                <thead>
                  <tr>
                    <th>Challenge</th>
                    <th>Language</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {mySubmissions.map(s => (
                    <tr key={s.id}>
                      <td className="p-td-main">{s.question_id}</td>
                      <td><span className="p-td-lang">{s.language}</span></td>
                      <td><span className={`p-td-status ${s.status}`}>{s.status}</span></td>
                      <td className="p-td-time">{new Date(s.submitted_at).toLocaleString()}</td>
                    </tr>
                  ))}
                  {mySubmissions.length === 0 && (
                    <tr><td colSpan={4} className="p-td-empty">No submissions yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
