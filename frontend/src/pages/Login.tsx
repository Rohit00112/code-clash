import { useState, useEffect } from 'react'
import { api } from '../services/api'
import './Login.css'

interface LoginProps {
  onLogin: (user: any) => void
}

const CODE_SNIPPETS = [
  'def sieve(n):',
  '  primes = []',
  'for i in range(2, n):',
  '  if all(i % p for p in primes):',
  '    primes.append(i)',
  'return primes',
  'function bfs(graph, start) {',
  '  let queue = [start];',
  '  let visited = new Set();',
  '  while (queue.length) {',
  '    let node = queue.shift();',
  '    visited.add(node);',
  '  }',
  '}',
  'int dp[N][N];',
  'for(int i=0;i<n;i++)',
  '  dp[i][0] = 1;',
  'sort(arr.begin(), arr.end());',
  'while(lo <= hi) {',
  '  int mid = (lo+hi)/2;',
  '}',
  'if __name__ == "__main__":',
  '    solve()',
  'O(n log n)',
  'HashMap<String, List<Integer>>',
  'return Math.max(left, right)+1;',
  'stack.push(node.left)',
  'memo[key] = result',
  'adj[u].push_back(v);',
  'int ans = INT_MAX;',
  'res = max(res, curr)',
]

export default function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [typedLine, setTypedLine] = useState('')
  const [snippetIndex, setSnippetIndex] = useState(0)

  // Typing animation for code snippets
  useEffect(() => {
    const snippet = CODE_SNIPPETS[snippetIndex]
    let charIndex = 0
    setTypedLine('')

    const typeInterval = setInterval(() => {
      if (charIndex <= snippet.length) {
        setTypedLine(snippet.slice(0, charIndex))
        charIndex++
      } else {
        clearInterval(typeInterval)
        setTimeout(() => {
          setSnippetIndex((prev) => (prev + 1) % CODE_SNIPPETS.length)
        }, 1500)
      }
    }, 60)

    return () => clearInterval(typeInterval)
  }, [snippetIndex])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await api.post('/auth/login', { username, password })
      const { access_token, user } = response.data
      localStorage.setItem('token', access_token)
      onLogin(user)
    } catch (err: any) {
      const data = err.response?.data
      let msg = 'Login failed'
      if (data?.error) msg = data.error
      else if (data?.details && Array.isArray(data.details)) {
        msg = data.details.map((d: any) => d.message || d.msg).join('. ')
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-content">
        {/* Left side - Branding */}
        <div className="login-hero">
          <div className="hero-badge">ALGORITHM BATTLE</div>
          <h1 className="hero-title">
            <span className="title-accent">&lt;</span>
            Creative
            <span className="title-accent">&gt;</span>
            <br />
            <span className="title-clash">Clash</span>
            <span className="title-year">2026</span>
          </h1>
          <p className="hero-tagline">Where Code Meets Competition</p>

          <div className="hero-terminal">
            <div className="terminal-header">
              <span className="terminal-dot red"></span>
              <span className="terminal-dot yellow"></span>
              <span className="terminal-dot green"></span>
              <span className="terminal-title">battle.py</span>
            </div>
            <div className="terminal-body">
              <span className="terminal-prompt">$</span>
              <span className="terminal-typed">{typedLine}</span>
              <span className="terminal-cursor">|</span>
            </div>
          </div>

          <div className="hero-stats">
            <div className="stat-item">
              <span className="stat-icon">&#9889;</span>
              <div>
                <div className="stat-value">6</div>
                <div className="stat-label">Languages</div>
              </div>
            </div>
            <div className="stat-item">
              <span className="stat-icon">&#9881;</span>
              <div>
                <div className="stat-value">N</div>
                <div className="stat-label">Challenges</div>
              </div>
            </div>
            <div className="stat-item">
              <span className="stat-icon">&#9201;</span>
              <div>
                <div className="stat-value">Real</div>
                <div className="stat-label">Time Judge</div>
              </div>
            </div>
          </div>

          <div className="hero-event">
            <span className="event-icon">&#128205;</span> Innovation Lab, Itahari International College
            <br />
            <span className="event-icon">&#128197;</span> 24th - 27th February 2026
          </div>
        </div>

        {/* Right side - Login Form */}
        <div className="login-box">
          <div className="login-box-header">
            <div className="header-line"></div>
            <span className="header-text">// AUTHENTICATE</span>
            <div className="header-line"></div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>
                <span className="label-symbol">&#9654;</span> username
              </label>
              <div className="input-wrapper">
                <span className="input-prefix">@</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="enter_username"
                  required
                  autoFocus
                  autoComplete="off"
                />
              </div>
            </div>

            <div className="form-group">
              <label>
                <span className="label-symbol">&#9654;</span> password
              </label>
              <div className="input-wrapper">
                <span className="input-prefix">*</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            {error && (
              <div className="error">
                <span className="error-icon">&#9888;</span> {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="login-btn">
              {loading ? (
                <span className="loading-text">
                  <span className="spinner"></span>
                  Authenticating...
                </span>
              ) : (
                <>
                  <span>Initialize Battle</span>
                  <span className="btn-arrow">&#10148;</span>
                </>
              )}
            </button>
          </form>

          <div className="login-footer">
            <span className="footer-line">// powered by</span>
            <span className="footer-brand">Innovation Lab, Itahari International College</span>
          </div>
        </div>
      </div>
    </div>
  )
}
