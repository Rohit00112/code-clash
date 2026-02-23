import { useState, useEffect, useMemo, useRef, Component, ErrorInfo, ReactNode } from 'react'
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

interface Challenge {
  id: string
  number: number
  title: string
  function_name: string
}

interface DraftLoadResult {
  id?: number
  code?: string
}

export default function ParticipantDashboard({ user, onLogout }: ParticipantDashboardProps) {
  const [activeTab, setActiveTab] = useState('challenges')
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [selectedChallengeId, setSelectedChallengeId] = useState<string | null>(null)
  const [language, setLanguage] = useState('python')
  const [code, setCode] = useState('')
  const [output, setOutput] = useState('')
  const [loading, setLoading] = useState(false)
  const [mySubmissions, setMySubmissions] = useState<any[]>([])
  const [isDraftSyncing, setIsDraftSyncing] = useState(false)

  const selectedChallenge = useMemo(
    () => challenges.find((challenge) => challenge.id === selectedChallengeId) || null,
    [challenges, selectedChallengeId]
  )

  const draftRequestRef = useRef(0)
  const activeDraftContextRef = useRef('')
  const autosaveEnabledRef = useRef(false)

  useEffect(() => {
    loadChallenges()
    loadMySubmissions()
  }, [])

  useEffect(() => {
    if (selectedChallengeId && !selectedChallenge) {
      autosaveEnabledRef.current = false
      setSelectedChallengeId(null)
      setCode('')
    }
  }, [selectedChallengeId, selectedChallenge])

  useEffect(() => {
    if (!selectedChallenge) {
      autosaveEnabledRef.current = false
      return
    }
    void loadDraftForContext(selectedChallenge.id, language, selectedChallenge.function_name)
  }, [selectedChallenge?.id, selectedChallenge?.function_name, language])

  useEffect(() => {
    if (!selectedChallenge || !language || !code) return
    if (isDraftSyncing || !autosaveEnabledRef.current) return

    const questionId = selectedChallenge.id
    const currentLanguage = language
    const codeSnapshot = code

    const timer = setTimeout(() => {
      if (!autosaveEnabledRef.current) return
      void saveDraft(questionId, currentLanguage, codeSnapshot)
    }, 2000)

    return () => clearTimeout(timer)
  }, [code, selectedChallenge?.id, language, isDraftSyncing])

  const loadChallenges = async () => {
    try {
      const response = await api.get('/challenges/')
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

  const loadDraftForContext = async (questionId: string, lang: string, functionName: string) => {
    const contextKey = `${questionId}:${lang}`
    const requestId = draftRequestRef.current + 1
    draftRequestRef.current = requestId
    activeDraftContextRef.current = contextKey
    autosaveEnabledRef.current = false
    setIsDraftSyncing(true)

    const templateCode = getDefaultCode(lang, functionName)

    try {
      const response = await api.post('/drafts/load', {
        question_id: questionId,
        language: lang,
      })

      if (draftRequestRef.current !== requestId || activeDraftContextRef.current !== contextKey) return

      const draft: DraftLoadResult = response.data || {}
      if ((draft.id || 0) > 0) {
        const useSavedDraft = window.confirm(
          `Saved ${lang} draft found for ${questionId}.\n\nPress OK to load saved draft.\nPress Cancel to start fresh (saved draft will be deleted).`
        )

        if (useSavedDraft) {
          setCode(draft.code || templateCode)
        } else {
          try {
            await api.delete(`/drafts/${questionId}/${lang}`)
          } catch (error) {
            console.error('Failed to delete existing draft before start fresh', error)
          }

          if (draftRequestRef.current !== requestId || activeDraftContextRef.current !== contextKey) return
          setCode(templateCode)
        }
      } else {
        setCode(draft.code || templateCode)
      }
    } catch (error) {
      if (draftRequestRef.current !== requestId || activeDraftContextRef.current !== contextKey) return
      setCode(templateCode)
    } finally {
      if (draftRequestRef.current === requestId && activeDraftContextRef.current === contextKey) {
        setIsDraftSyncing(false)
        autosaveEnabledRef.current = true
      }
    }
  }

  const saveDraft = async (questionId: string, lang: string, codeValue: string) => {
    if (!questionId || !codeValue || !autosaveEnabledRef.current || isDraftSyncing) return

    try {
      await api.post('/drafts/save', {
        question_id: questionId,
        language: lang,
        code: codeValue,
      })
    } catch (error) {
      console.error('Failed to save draft', error)
    }
  }

  const handleSelectChallenge = (challengeId: string) => {
    autosaveEnabledRef.current = false
    setSelectedChallengeId(challengeId)
  }

  const handleBackToChallenges = () => {
    autosaveEnabledRef.current = false
    setSelectedChallengeId(null)
  }

  const handleLanguageChange = (lang: string) => {
    autosaveEnabledRef.current = false
    setLanguage(lang)
  }

  const handleTestRun = async () => {
    if (!selectedChallenge || !code) return
    setLoading(true)
    setOutput('Running tests...')
    try {
      const response = await api.post('/submissions/test-run', {
        question_id: selectedChallenge.id,
        language,
        code,
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
        code,
      })
      const result = response.data || {}
      const submissionId = result?.submission_id
      setOutput(`Submission queued (ID: ${submissionId}). Waiting for judge...`)

      if (submissionId) {
        let done = false
        for (let i = 0; i < 60; i++) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
          const statusResp = await api.get(`/submissions/${submissionId}`)
          const sub = statusResp.data
          if (sub?.status === 'queued' || sub?.status === 'running' || sub?.status === 'pending') {
            setOutput(`Submission ${submissionId}: ${sub.status}...`)
            continue
          }
          done = true
          const lines: string[] = []
          lines.push(`Submission ${submissionId}: ${sub?.status || 'unknown'}`)
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
    const templates: Record<string, string> = {
      python: `def ${functionName}(*args):\n    # Add parameters as per problem statement\n    pass\n`,
      java:
        `public class Solution {\n` +
        `    public static Object ${functionName}(Object input) {\n` +
        `        // Add parameters as per problem statement and return expected output.\n` +
        `        return null;\n` +
        `    }\n\n` +
        `    public static void main(String[] args) {\n` +
        `        // Optional local testing entrypoint.\n` +
        `    }\n` +
        `}\n`,
      c:
        `#include <stdio.h>\n\n` +
        `// Update signature and implementation based on the problem statement.\n` +
        `int ${functionName}(void) {\n` +
        `    return 0;\n` +
        `}\n\n` +
        `int main(void) {\n` +
        `    // Optional local testing entrypoint.\n` +
        `    return 0;\n` +
        `}\n`,
      cpp:
        `#include <bits/stdc++.h>\n` +
        `using namespace std;\n\n` +
        `// Update signature and return type based on problem statement.\n` +
        `template <typename... Args>\n` +
        `int ${functionName}(Args... args) {\n` +
        `    return 0;\n` +
        `}\n\n` +
        `int main() {\n` +
        `    // Optional local testing entrypoint.\n` +
        `    return 0;\n` +
        `}\n`,
      javascript: `function ${functionName}(...args) {\n    // Add parameters as per problem statement\n}\n`,
      csharp:
        `using System;\n\n` +
        `class Solution\n` +
        `{\n` +
        `    public static object ${functionName}(object input)\n` +
        `    {\n` +
        `        // Add parameters as per problem statement and return expected output.\n` +
        `        return null;\n` +
        `    }\n\n` +
        `    static void Main()\n` +
        `    {\n` +
        `        // Optional local testing entrypoint.\n` +
        `    }\n` +
        `}\n`,
    }
    return templates[lang] || ''
  }

  const isQuestionSolved = (questionId: string) => {
    return mySubmissions.some((s) => s.question_id === questionId && s.status === 'completed')
  }

  const solvedCount = challenges.filter((challenge) => isQuestionSolved(challenge.id)).length

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
            onClick={() => { setActiveTab('challenges'); handleBackToChallenges() }}
          >
            <span className="p-nav-label">Challenges</span>
            <span className="p-nav-badge">{challenges.length}</span>
          </button>
          <button
            className={`p-nav-btn ${activeTab === 'submissions' ? 'active' : ''}`}
            onClick={() => { setActiveTab('submissions'); handleBackToChallenges() }}
          >
            <span className="p-nav-label">Submissions</span>
            <span className="p-nav-badge">{mySubmissions.length}</span>
          </button>
        </nav>

        {/* Challenge list */}
        {activeTab === 'challenges' && !selectedChallenge && (
          <div className="p-challenge-list">
            {challenges.map((challenge) => {
              const solved = isQuestionSolved(challenge.id)
              return (
                <button
                  key={challenge.id}
                  className={`p-challenge-row ${solved ? 'solved' : ''}`}
                  onClick={() => handleSelectChallenge(challenge.id)}
                >
                  <span className="p-challenge-num">#{challenge.number}</span>
                  <span className="p-challenge-title">{challenge.title}</span>
                  {solved ? (
                    <span className="p-challenge-badge done">Solved</span>
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
            <button className="p-action-btn secondary" onClick={handleBackToChallenges}>
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
              {challenges.map((challenge) => {
                const solved = isQuestionSolved(challenge.id)
                return (
                  <div key={challenge.id} className={`p-card ${solved ? 'partial' : ''}`}>
                    <div className="p-card-header">
                      <span className="p-card-number">Q{challenge.number}</span>
                      {solved ? (
                        <span className="p-card-status partial">Solved</span>
                      ) : (
                        <span className="p-card-status new">New</span>
                      )}
                    </div>
                    <h3 className="p-card-name">{challenge.title}</h3>
                    <div className="p-card-info">
                      <code>{challenge.function_name}()</code>
                    </div>
                    <div className="p-card-footer">
                      <button onClick={() => downloadPDF(challenge.id)} className="p-card-btn secondary">PDF</button>
                      <button onClick={() => handleSelectChallenge(challenge.id)} className="p-card-btn primary">
                        {solved ? 'Retry' : 'Solve'}
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
              onChange={(value) => setCode(value)}
              language={language}
              onLanguageChange={handleLanguageChange}
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
                  {mySubmissions.map((submission) => (
                    <tr key={submission.id}>
                      <td className="p-td-main">{submission.question_id}</td>
                      <td><span className="p-td-lang">{submission.language}</span></td>
                      <td><span className={`p-td-status ${submission.status}`}>{submission.status}</span></td>
                      <td className="p-td-time">{new Date(submission.submitted_at).toLocaleString()}</td>
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
