import { useState, useEffect, useRef } from 'react'
import { api } from '../services/api'
import Editor from '@monaco-editor/react'
import './Dashboard.css'

interface AdminDashboardProps {
  user: any
  onLogout: () => void
}

const NAV_ITEMS = [
  { key: 'statistics', label: 'Overview' },
  { key: 'challenges', label: 'Challenges' },
  { key: 'users', label: 'Users' },
  { key: 'submissions', label: 'Submissions' },
  { key: 'details', label: 'Code Review' },
  { key: 'leaderboard', label: 'Leaderboard' },
  { key: 'manage', label: 'Settings' },
]

const ADMIN_ACTIVE_TAB_KEY = 'admin.activeTab'

const getInitialAdminTab = () => {
  if (typeof window === 'undefined') return 'statistics'
  const savedTab = window.localStorage.getItem(ADMIN_ACTIVE_TAB_KEY)
  if (savedTab && NAV_ITEMS.some(item => item.key === savedTab)) return savedTab
  return 'statistics'
}

export default function AdminDashboard({ user, onLogout }: AdminDashboardProps) {
  const [activeTab, setActiveTab] = useState<string>(getInitialAdminTab)
  const [statistics, setStatistics] = useState<any>(null)
  const [users, setUsers] = useState<any[]>([])
  const [submissions, setSubmissions] = useState<any[]>([])
  const [leaderboard, setLeaderboard] = useState<any[]>([])
  const [submissionDetails, setSubmissionDetails] = useState<any[]>([])
  const [challenges, setChallenges] = useState<any[]>([])
  const [bulkUsernames, setBulkUsernames] = useState('')
  const [message, setMessage] = useState('')
  const [selectedSolution, setSelectedSolution] = useState<{user: string, question: string, code: string, language: string} | null>(null)
  const [selectedUser, setSelectedUser] = useState<any>(null)

  // Upload state
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploading, setUploading] = useState(false)
  const pdfInputRef = useRef<HTMLInputElement>(null)
  const jsonInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    window.localStorage.setItem(ADMIN_ACTIVE_TAB_KEY, activeTab)
  }, [activeTab])

  const loadData = async () => {
    loadStatistics()
    loadUsers()
    loadSubmissions()
    loadLeaderboard()
    loadSubmissionDetails()
    loadChallenges()
  }

  const loadStatistics = async () => {
    try {
      const response = await api.get('/admin/statistics')
      setStatistics(response.data)
    } catch (error) {
      console.error('Failed to load statistics', error)
    }
  }

  const loadUsers = async () => {
    try {
      const response = await api.get('/users')
      setUsers(response.data || [])
    } catch (error) {
      console.error('Failed to load users', error)
    }
  }

  const loadSubmissions = async () => {
    try {
      const response = await api.get('/submissions')
      setSubmissions(response.data || [])
    } catch (error) {
      console.error('Failed to load submissions', error)
    }
  }

  const loadLeaderboard = async () => {
    try {
      const response = await api.get('/submissions/leaderboard')
      setLeaderboard(response.data?.rankings || response.data || [])
    } catch (error) {
      setLeaderboard([])
    }
  }

  const loadSubmissionDetails = async () => {
    try {
      const response = await api.get('/admin/submission-details')
      setSubmissionDetails(response.data?.users || [])
    } catch (error) {
      setSubmissionDetails([])
    }
  }

  const loadChallenges = async () => {
    try {
      const response = await api.get('/challenges')
      setChallenges(response.data || [])
    } catch (error) {
      setChallenges([])
    }
  }

  const handleBulkImport = async () => {
    try {
      const rawNames = bulkUsernames.split(/[,;\n]/).map(u => u.trim()).filter(u => u.length >= 3)
      const usernames = [...new Set(rawNames)]
      if (usernames.length === 0) {
        setMessage('Enter at least one username (min 3 chars)')
        return
      }
      const response = await api.post('/admin/bulk-import', { usernames, auto_generate_passwords: true })
      const created = response.data?.users?.length ?? response.data?.created_count ?? 0
      setMessage(`Imported ${created} users`)
      setBulkUsernames('')
      loadData()
      setTimeout(() => setMessage(''), 4000)
    } catch (error: any) {
      setMessage(error.response?.data?.error || 'Import failed')
    }
  }

  const handleExportResults = async () => {
    try {
      const response = await api.get('/admin/export-results', { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `results_${new Date().toISOString().slice(0,10)}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setMessage('Results exported!')
      setTimeout(() => setMessage(''), 3000)
    } catch (error: any) {
      setMessage(error.response?.data?.error || 'Export failed')
    }
  }

  const handleResetEvent = async () => {
    if (!confirm('Reset entire event? This will delete all participants, submissions and drafts!')) return
    try {
      const response = await api.post('/admin/reset-event')
      const d = response.data?.deleted || {}
      setMessage(`Reset complete. Deleted: ${d.participants ?? 0} participants, ${d.submissions ?? 0} submissions`)
      loadData()
      setTimeout(() => setMessage(''), 5000)
    } catch (error: any) {
      setMessage(error.response?.data?.error || 'Reset failed')
    }
  }

  const handleDeleteSubmission = async (id: number) => {
    if (!confirm('Delete this submission?')) return
    try {
      await api.delete(`/submissions/${id}`)
      setMessage('Submission deleted')
      loadSubmissions()
      loadSubmissionDetails()
      loadLeaderboard()
      setTimeout(() => setMessage(''), 3000)
    } catch (error: any) {
      setMessage(error.response?.data?.error || 'Delete failed')
    }
  }

  const handleUploadChallenge = async () => {
    const pdfFile = pdfInputRef.current?.files?.[0]
    const jsonFile = jsonInputRef.current?.files?.[0]

    if (!pdfFile) {
      setMessage('Select a PDF file for the problem statement')
      return
    }
    if (!jsonFile) {
      setMessage('Select a JSON file for the test cases')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('pdf_file', pdfFile)
      formData.append('testcase_file', jsonFile)
      if (uploadTitle.trim()) {
        formData.append('title', uploadTitle.trim())
      }

      const response = await api.post('/admin/challenges/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setMessage(response.data?.message || 'Challenge uploaded!')
      setUploadTitle('')
      if (pdfInputRef.current) pdfInputRef.current.value = ''
      if (jsonInputRef.current) jsonInputRef.current.value = ''
      loadChallenges()
      setTimeout(() => setMessage(''), 4000)
    } catch (error: any) {
      setMessage(error.response?.data?.error || error.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteChallenge = async (questionId: string) => {
    if (!confirm(`Delete challenge ${questionId}? This removes the PDF and test cases. Existing submissions are kept.`)) return
    try {
      await api.delete(`/admin/challenges/${questionId}`)
      setMessage(`${questionId} deleted`)
      loadChallenges()
      setTimeout(() => setMessage(''), 3000)
    } catch (error: any) {
      setMessage(error.response?.data?.error || 'Delete failed')
    }
  }

  const activeNav = NAV_ITEMS.find(n => n.key === activeTab)

  return (
    <div className="admin-layout">
      {/* Left Sidebar */}
      <aside className="admin-sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">CC</div>
          <div className="sidebar-brand-text">
            <span className="sidebar-title">Creative Clash</span>
            <span className="sidebar-subtitle">Admin Panel</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Main</div>
          {NAV_ITEMS.slice(0, 4).map(item => (
            <button
              key={item.key}
              className={`sidebar-nav-item ${activeTab === item.key ? 'active' : ''}`}
              onClick={() => setActiveTab(item.key)}
            >
              <span className="nav-label">{item.label}</span>
            </button>
          ))}

          <div className="nav-section-label">Analysis</div>
          {NAV_ITEMS.slice(4, 6).map(item => (
            <button
              key={item.key}
              className={`sidebar-nav-item ${activeTab === item.key ? 'active' : ''}`}
              onClick={() => setActiveTab(item.key)}
            >
              <span className="nav-label">{item.label}</span>
            </button>
          ))}

          <div className="nav-section-label">System</div>
          {NAV_ITEMS.slice(6).map(item => (
            <button
              key={item.key}
              className={`sidebar-nav-item ${activeTab === item.key ? 'active' : ''}`}
              onClick={() => setActiveTab(item.key)}
            >
              <span className="nav-label">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">{user.username[0].toUpperCase()}</div>
            <div className="sidebar-user-info">
              <span className="sidebar-user-name">{user.username}</span>
              <span className="sidebar-user-role">Administrator</span>
            </div>
          </div>
          <button onClick={onLogout} className="sidebar-logout-btn">Logout</button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="admin-main">
        {/* Top Bar */}
        <header className="admin-topbar">
          <div className="topbar-left">
            <h1 className="topbar-title">{activeNav?.label || 'Dashboard'}</h1>
            <span className="topbar-breadcrumb">Admin / {activeNav?.label}</span>
          </div>
          <div className="topbar-right">
            <button onClick={() => loadData()} className="topbar-refresh-btn">↻ Refresh</button>
          </div>
        </header>

        {message && (
          <div className="admin-message">
            <span className="admin-message-icon">✓</span>
            {message}
            <button className="admin-message-close" onClick={() => setMessage('')}>✕</button>
          </div>
        )}

        <div className="admin-content">
          {/* Statistics / Overview */}
          {activeTab === 'statistics' && statistics && (
            <div className="admin-overview">
              <div className="overview-stats">
                <div className="overview-card">
                  <span className="overview-card-value">{statistics.total_users}</span>
                  <span className="overview-card-label">Total Users</span>
                </div>
                <div className="overview-card">
                  <span className="overview-card-value">{statistics.total_participants}</span>
                  <span className="overview-card-label">Participants</span>
                </div>
                <div className="overview-card">
                  <span className="overview-card-value">{statistics.total_submissions}</span>
                  <span className="overview-card-label">Submissions</span>
                </div>
                <div className="overview-card">
                  <span className="overview-card-value">{challenges.length}</span>
                  <span className="overview-card-label">Challenges</span>
                </div>
                <div className="overview-card">
                  <span className="overview-card-value">{statistics.average_score ?? 0}</span>
                  <span className="overview-card-label">Avg Score</span>
                </div>
              </div>

              {/* Quick Info Panels */}
              <div className="overview-panels">
                <div className="overview-panel">
                  <h3 className="panel-title">Active Challenges</h3>
                  <div className="panel-list">
                    {challenges.map(c => (
                      <div key={c.id} className="panel-list-item">
                        <span className="panel-item-label">Q{c.number}: {c.title}</span>
                        <span className="panel-item-value">{c.total_test_cases} tests</span>
                      </div>
                    ))}
                    {challenges.length === 0 && <div className="panel-empty">No challenges uploaded</div>}
                  </div>
                </div>
                <div className="overview-panel">
                  <h3 className="panel-title">Top Performers</h3>
                  <div className="panel-list">
                    {leaderboard.slice(0, 5).map((entry: any, idx: number) => (
                      <div key={entry.username || idx} className="panel-list-item">
                        <span className="panel-item-rank">#{idx + 1}</span>
                        <span className="panel-item-label">{entry.username}</span>
                        <span className="panel-item-value">{entry.total_score} pts</span>
                      </div>
                    ))}
                    {leaderboard.length === 0 && <div className="panel-empty">No submissions yet</div>}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Challenges */}
          {activeTab === 'challenges' && (
            <div className="challenges-manage">
              <div className="admin-card upload-section">
                <h3 className="admin-card-title">Upload New Challenge</h3>
                <div className="upload-form">
                  <div className="form-group">
                    <label>Title (optional)</label>
                    <input
                      type="text"
                      value={uploadTitle}
                      onChange={(e) => setUploadTitle(e.target.value)}
                      placeholder="e.g. Two Sum, Palindrome Check..."
                      className="admin-input"
                    />
                  </div>
                  <div className="upload-files-row">
                    <div className="form-group">
                      <label>Problem Statement (PDF)</label>
                      <input type="file" accept=".pdf" ref={pdfInputRef} className="admin-file-input" />
                    </div>
                    <div className="form-group">
                      <label>Test Cases (JSON)</label>
                      <input type="file" accept=".json" ref={jsonInputRef} className="admin-file-input" />
                    </div>
                  </div>
                  <div className="form-hint">
                    JSON: {`{"function_name": "solve", "title": "Name", "test_cases": [{"id": 1, "input": [...], "output": ..., "is_sample": true}]}`}
                  </div>
                  <button onClick={handleUploadChallenge} disabled={uploading} className="admin-btn primary">
                    {uploading ? 'Uploading...' : 'Upload Challenge'}
                  </button>
                </div>
              </div>

              <h3 className="section-subtitle">Current Challenges ({challenges.length})</h3>
              <div className="challenges-grid">
                {challenges.map(c => (
                  <div key={c.id} className="challenge-card">
                    <div className="challenge-card-top">
                      <span className="challenge-number">Q{c.number}</span>
                      <button onClick={() => handleDeleteChallenge(c.id)} className="challenge-delete-btn">✕</button>
                    </div>
                    <h4 className="challenge-title">{c.title}</h4>
                    <div className="challenge-meta">
                      <span>fn: <code>{c.function_name}</code></span>
                      <span>{c.sample_test_cases} sample + {c.total_test_cases - c.sample_test_cases} hidden = {c.total_test_cases} tests</span>
                      <span>Max: {c.max_score} pts</span>
                    </div>
                  </div>
                ))}
                {challenges.length === 0 && <p className="panel-empty">No challenges uploaded yet.</p>}
              </div>
            </div>
          )}

          {/* Users */}
          {activeTab === 'users' && (
            <div className="admin-card">
              <div className="admin-card-header">
                <h3 className="admin-card-title">Users ({users.length})</h3>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>ID</th><th>Username</th><th>Role</th><th>Status</th></tr></thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id}>
                        <td>{u.id}</td>
                        <td><strong>{u.username}</strong></td>
                        <td><span className={`admin-badge ${u.role}`}>{u.role}</span></td>
                        <td><span className={`admin-badge ${u.is_active ? 'active' : 'inactive'}`}>{u.is_active ? 'Active' : 'Inactive'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Submissions */}
          {activeTab === 'submissions' && (
            <div className="admin-card">
              <div className="admin-card-header">
                <h3 className="admin-card-title">All Submissions ({submissions.length})</h3>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>ID</th><th>User</th><th>Question</th><th>Lang</th><th>Score</th><th>Time</th><th>Status</th><th>Actions</th></tr></thead>
                  <tbody>
                    {submissions.map(s => (
                      <tr key={s.id}>
                        <td>{s.id}</td>
                        <td><strong>{s.username ?? s.user_id}</strong></td>
                        <td>{s.question_id}</td>
                        <td>{s.language}</td>
                        <td><span className="score-pill">{s.score}/{s.max_score}</span></td>
                        <td>{s.execution_time?.toFixed(2)}s</td>
                        <td><span className={`admin-badge ${s.status}`}>{s.status}</span></td>
                        <td><button className="admin-btn danger small" onClick={() => handleDeleteSubmission(s.id)}>Delete</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Code Review / Submission Details */}
          {activeTab === 'details' && (
            <div>
              {/* Viewing a specific solution */}
              {selectedSolution ? (
                <div className="admin-card">
                  <div className="admin-card-header">
                    <h3 className="admin-card-title">{selectedSolution.user} / {selectedSolution.question}</h3>
                    <button onClick={() => setSelectedSolution(null)} className="admin-btn secondary">Back</button>
                  </div>
                  <div className="code-review-viewer">
                    <div className="code-review-info">
                      <span>{selectedSolution.language}</span>
                    </div>
                    <Editor height="450px" language={selectedSolution.language} value={selectedSolution.code} options={{ readOnly: true, minimap: { enabled: false }, fontSize: 14, fontFamily: "'Fira Code', Consolas, monospace", padding: { top: 12 } }} theme="vs-dark" />
                  </div>
                </div>

              ) : selectedUser ? (
                /* Viewing a user's all submissions — titles only, click to open */
                <div className="admin-card">
                  <div className="admin-card-header">
                    <h3 className="admin-card-title">{selectedUser.username}</h3>
                    <button onClick={() => setSelectedUser(null)} className="admin-btn secondary">Back to all users</button>
                  </div>
                  <div className="cr-solutions-list">
                    {challenges.map(c => {
                      const sol = selectedUser.solutions?.[c.id]
                      return (
                        <div
                          key={c.id}
                          className={`cr-solution-row ${sol ? 'has-code' : 'empty'}`}
                          onClick={() => sol && setSelectedSolution({ user: selectedUser.username, question: `${c.id} (${c.title})`, code: sol.code, language: sol.language })}
                        >
                          <div className="cr-solution-left">
                            <span className="cr-question-num">Q{c.number}</span>
                            <span className="cr-question-title">{c.title}</span>
                          </div>
                          <div className="cr-solution-right">
                            {sol ? (
                              <>
                                <span className="cr-question-lang">{sol.language}</span>
                                <span className={`admin-badge ${sol.score >= c.max_score ? 'completed' : 'pending'}`}>{sol.score}/{c.max_score}</span>
                              </>
                            ) : (
                              <span className="cr-no-sub">No submission</span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

              ) : (
                /* User list — clickable rows */
                <div className="admin-card">
                  <div className="admin-card-header">
                    <h3 className="admin-card-title">Code Review ({submissionDetails.length} participants)</h3>
                  </div>
                  <div className="cr-user-list">
                    {submissionDetails.map(u => {
                      const solvedCount = challenges.filter(c => u.solutions?.[c.id]).length
                      return (
                        <div key={u.user_id} className="cr-user-row" onClick={() => setSelectedUser(u)}>
                          <div className="cr-user-left">
                            <div className="cr-user-avatar">{u.username.charAt(0).toUpperCase()}</div>
                            <span className="cr-user-name">{u.username}</span>
                          </div>
                          <div className="cr-user-right">
                            <span className="cr-user-solved">{solvedCount}/{challenges.length} solved</span>
                          </div>
                        </div>
                      )
                    })}
                    {submissionDetails.length === 0 && <div className="panel-empty">No participants yet</div>}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Leaderboard */}
          {activeTab === 'leaderboard' && (
            <div className="admin-card">
              <div className="admin-card-header">
                <h3 className="admin-card-title">Leaderboard</h3>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Username</th>
                      <th>Total</th>
                      {challenges.map(c => (
                        <th key={c.id}>Q{c.number}</th>
                      ))}
                      <th>Avg Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.map((entry: any, idx: number) => (
                      <tr key={entry.username || idx}>
                        <td>
                          <span className={`rank-badge rank-${idx < 3 ? idx + 1 : 'default'}`}>#{idx + 1}</span>
                        </td>
                        <td><strong>{entry.username}</strong></td>
                        <td><span className="score-pill total">{entry.total_score}</span></td>
                        {challenges.map(c => (
                          <td key={c.id}>{entry.question_scores?.[c.id] ?? '-'}</td>
                        ))}
                        <td>{entry.avg_execution_time?.toFixed(2)}s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Manage / Settings */}
          {activeTab === 'manage' && (
            <div className="manage-grid">
              <div className="admin-card">
                <h3 className="admin-card-title">Bulk Import Users</h3>
                <p className="admin-card-desc">Enter usernames separated by comma, semicolon, or newline. Passwords auto-generated as username@123</p>
                <textarea
                  value={bulkUsernames}
                  onChange={(e) => setBulkUsernames(e.target.value)}
                  placeholder="user1, user2, user3"
                  rows={4}
                  className="admin-textarea"
                />
                <button onClick={handleBulkImport} className="admin-btn primary">Import Users</button>
              </div>
              <div className="manage-actions">
                <div className="admin-card">
                  <h3 className="admin-card-title">Export Results</h3>
                  <p className="admin-card-desc">Download Excel with leaderboard, submissions, and statistics</p>
                  <button onClick={handleExportResults} className="admin-btn primary">Export Excel</button>
                </div>
                <div className="admin-card">
                  <h3 className="admin-card-title">Reset Event</h3>
                  <p className="admin-card-desc">Delete all participants, submissions, and drafts. Irreversible!</p>
                  <button onClick={handleResetEvent} className="admin-btn danger">Reset All Data</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
