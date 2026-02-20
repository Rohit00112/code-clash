import { useState, useRef, useEffect } from 'react'
import Editor from '@monaco-editor/react'
import './VSCodeIDE.css'

interface VSCodeIDEProps {
  code: string
  onChange: (value: string) => void
  language: string
  onLanguageChange?: (lang: string) => void
  onTestRun: () => void
  onSubmit: () => void
  loading: boolean
  output: string
  onTerminalCommand?: (cmd: string) => Promise<string>
  functionName?: string
}

const LANG_LABELS: Record<string, string> = {
  python: 'Python',
  java: 'Java',
  c: 'C',
  cpp: 'C++',
  javascript: 'JavaScript',
  csharp: 'C#'
}

const LANG_ICONS: Record<string, string> = {
  python: 'py',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  javascript: 'js',
  csharp: 'cs'
}

const PYTHON_IMPORTS: Record<string, { module: string; alias?: string; item?: string }> = {
  'np': { module: 'numpy', alias: 'np' },
  'numpy': { module: 'numpy' },
  'pd': { module: 'pandas', alias: 'pd' },
  'pandas': { module: 'pandas' },
  'defaultdict': { module: 'collections', item: 'defaultdict' },
  'Counter': { module: 'collections', item: 'Counter' },
  'deque': { module: 'collections', item: 'deque' },
  'heapq': { module: 'heapq' },
  'bisect': { module: 'bisect' },
  'math': { module: 'math' },
  'sqrt': { module: 'math', item: 'sqrt' },
  'ceil': { module: 'math', item: 'ceil' },
  'floor': { module: 'math', item: 'floor' },
  'gcd': { module: 'math', item: 'gcd' },
  're': { module: 're' },
  'sys': { module: 'sys' },
  'itertools': { module: 'itertools' },
  'permutations': { module: 'itertools', item: 'permutations' },
  'combinations': { module: 'itertools', item: 'combinations' },
}

export default function VSCodeIDE({
  code,
  onChange,
  language,
  onTestRun,
  onSubmit,
  loading,
  output,
  onTerminalCommand,
  onLanguageChange
}: VSCodeIDEProps) {
  const [activePanel, setActivePanel] = useState<'output' | 'terminal'>('output')
  const [terminalHistory, setTerminalHistory] = useState<Array<{ type: 'cmd' | 'out' | 'err' | 'sys', text: string }>>([
    { type: 'sys', text: 'Creative Clash Terminal — type "help" for commands' }
  ])
  const [terminalInput, setTerminalInput] = useState('')
  const terminalEndRef = useRef<HTMLDivElement>(null)
  const outputEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [terminalHistory])

  // Auto-scroll output
  useEffect(() => {
    outputEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [output])

  // Keyboard shortcuts: Ctrl+Enter = Run, Ctrl+Shift+Enter = Submit
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'Enter') {
        e.preventDefault()
        if (!loading) onSubmit()
      } else if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault()
        if (!loading) onTestRun()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [loading, onTestRun, onSubmit])

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editor.focus()
    monaco.languages.registerCompletionItemProvider('python', {
      triggerCharacters: ['.', ' ', 'n', 'p', 'c', 'm', 's', 'd', 'h', 'i', 'r'],
      provideCompletionItems: (model: any, position: any) => {
        const word = model.getWordUntilPosition(position)
        const range = { startLineNumber: position.lineNumber, startColumn: word.startColumn, endLineNumber: position.lineNumber, endColumn: word.endColumn }
        const items: any[] = []
        const existingCode = model.getValue()
        for (const [key, val] of Object.entries(PYTHON_IMPORTS)) {
          if (!key.toLowerCase().startsWith(word.word.toLowerCase())) continue
          let importText = ''
          if (val.item) importText = `from ${val.module} import ${val.item}`
          else if (val.alias) importText = `import ${val.module} as ${val.alias}`
          else importText = `import ${val.module}`
          if (existingCode.includes(val.module) || existingCode.includes(importText)) continue
          items.push({
            label: key,
            kind: monaco.languages.CompletionItemKind.Module,
            detail: importText,
            insertText: importText + '\n',
            range,
          })
        }
        return { suggestions: items }
      }
    })
  }

  const runTerminalCommand = async (cmd: string) => {
    const c = cmd.trim().toLowerCase()
    setTerminalHistory(prev => [...prev, { type: 'cmd', text: cmd }])

    if (c === 'clear' || c === 'cls') {
      setTerminalHistory([{ type: 'sys', text: 'Terminal cleared' }])
      return
    }
    if (c === 'help') {
      setTerminalHistory(prev => [...prev,
        { type: 'sys', text: 'Available commands:' },
        { type: 'out', text: '  run          Test your code (Ctrl+Enter)' },
        { type: 'out', text: '  submit       Submit for grading (Ctrl+Shift+Enter)' },
        { type: 'out', text: '  pip install  Install a Python package' },
        { type: 'out', text: '  clear        Clear terminal' },
        { type: 'sys', text: 'Keyboard shortcuts:' },
        { type: 'out', text: '  Ctrl+Enter         Run Code' },
        { type: 'out', text: '  Ctrl+Shift+Enter   Submit Solution' },
      ])
      return
    }
    if (c === 'run') {
      setTerminalHistory(prev => [...prev, { type: 'sys', text: 'Running test...' }])
      onTestRun()
      return
    }
    if (c === 'submit') {
      setTerminalHistory(prev => [...prev, { type: 'sys', text: 'Submitting solution...' }])
      onSubmit()
      return
    }
    if (onTerminalCommand && (c.startsWith('pip ') || c.startsWith('npm ') || c.startsWith('python ') || c.startsWith('node '))) {
      try {
        const result = await onTerminalCommand(cmd)
        setTerminalHistory(prev => [...prev, { type: 'out', text: result || 'Done' }])
      } catch (e: any) {
        setTerminalHistory(prev => [...prev, { type: 'err', text: e?.message || 'Command failed' }])
      }
      return
    }
    setTerminalHistory(prev => [...prev, { type: 'err', text: `Unknown command: ${cmd}. Type "help" for available commands.` }])
  }

  const handleTerminalKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && terminalInput.trim()) {
      runTerminalCommand(terminalInput)
      setTerminalInput('')
    }
  }

  // Parse output for structured display
  const renderOutput = () => {
    if (!output) {
      return <div className="ide-output-empty">Run or submit your code to see results here.</div>
    }

    const lines = output.split('\n')
    return (
      <div className="ide-output-lines">
        {lines.map((line, i) => {
          let cls = 'ide-output-line'
          if (line.includes('PASS') || line.includes('Accepted') || line.includes('successful') || line.includes('Score:')) cls += ' success'
          else if (line.includes('FAIL') || line.includes('Error') || line.includes('error') || line.includes('Wrong') || line.includes('Traceback')) cls += ' error'
          else if (line.includes('Running') || line.includes('Submitting') || line.includes('Test Case') || line.includes('---')) cls += ' info'
          else if (line.startsWith('Output:') || line.startsWith('Expected:') || line.startsWith('Got:')) cls += ' detail'
          return <div key={i} className={cls}>{line || '\u00A0'}</div>
        })}
        <div ref={outputEndRef} />
      </div>
    )
  }

  return (
    <div className="ide">
      {/* Top bar */}
      <div className="ide-topbar">
        <div className="ide-topbar-left">
          <div className="ide-file-tab active">
            <span className="ide-file-icon">{LANG_ICONS[language] || 'txt'}</span>
            <span className="ide-file-name">solution.{LANG_ICONS[language] || 'txt'}</span>
          </div>
        </div>
        <div className="ide-topbar-center">
          {onLanguageChange && (
            <select value={language} onChange={(e) => onLanguageChange(e.target.value)} className="ide-lang-select">
              {Object.entries(LANG_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
          )}
        </div>
        <div className="ide-topbar-right">
          <button onClick={onTestRun} disabled={loading} className="ide-action-btn run">
            {loading ? <><span className="ide-spinner" /> Running...</> : <>Run Code <span className="ide-shortcut">Ctrl+Enter</span></>}
          </button>
          <button onClick={onSubmit} disabled={loading} className="ide-action-btn submit">
            {loading ? <><span className="ide-spinner" /> Submitting...</> : <>Submit <span className="ide-shortcut">Ctrl+Shift+Enter</span></>}
          </button>
        </div>
      </div>

      {/* Editor area */}
      <div className="ide-body">
        <div className="ide-editor-area">
          {loading && (
            <div className="ide-loading-overlay">
              <div className="ide-loading-content">
                <span className="ide-spinner large" />
                <span>Executing...</span>
              </div>
            </div>
          )}
          <Editor
            height="100%"
            language={language === 'cpp' ? 'cpp' : language === 'csharp' ? 'csharp' : language}
            value={code}
            onChange={(v) => onChange(v || '')}
            onMount={handleEditorDidMount}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 14,
              fontFamily: "'Fira Code', 'Cascadia Code', Consolas, monospace",
              fontLigatures: true,
              lineNumbers: 'on',
              renderLineHighlight: 'all',
              bracketPairColorization: { enabled: true },
              guides: { bracketPairs: true, indentation: true },
              automaticLayout: true,
              tabSize: 4,
              insertSpaces: true,
              wordWrap: 'on',
              formatOnPaste: true,
              formatOnType: true,
              suggestOnTriggerCharacters: true,
              quickSuggestions: { other: true, comments: false, strings: true },
              acceptSuggestionOnEnter: 'on',
              tabCompletion: 'on',
              parameterHints: { enabled: true },
              hover: { enabled: true },
              scrollBeyondLastLine: false,
              smoothScrolling: true,
              cursorBlinking: 'smooth',
              cursorSmoothCaretAnimation: 'on',
              padding: { top: 12 },
              scrollbar: {
                verticalScrollbarSize: 8,
                horizontalScrollbarSize: 8,
              }
            }}
          />
        </div>

        {/* Bottom panel */}
        <div className="ide-bottom-panel">
          <div className="ide-panel-tabs">
            <button
              className={`ide-panel-tab ${activePanel === 'output' ? 'active' : ''}`}
              onClick={() => setActivePanel('output')}
            >
              Output
              {output && <span className="ide-panel-dot" />}
            </button>
            <button
              className={`ide-panel-tab ${activePanel === 'terminal' ? 'active' : ''}`}
              onClick={() => setActivePanel('terminal')}
            >
              Terminal
            </button>
          </div>

          {/* Output panel */}
          {activePanel === 'output' && (
            <div className="ide-output-panel">
              {renderOutput()}
            </div>
          )}

          {/* Terminal panel */}
          {activePanel === 'terminal' && (
            <div className="ide-terminal-panel">
              <div className="ide-terminal-scroll">
                {terminalHistory.map((entry, i) => (
                  <div key={i} className={`ide-term-line ${entry.type}`}>
                    {entry.type === 'cmd' && <span className="ide-term-prompt">$</span>}
                    {entry.type === 'sys' && <span className="ide-term-sys-icon">i</span>}
                    <span>{entry.text}</span>
                  </div>
                ))}
                <div ref={terminalEndRef} />
              </div>
              <div className="ide-terminal-input-row">
                <span className="ide-term-input-prompt">$</span>
                <input
                  type="text"
                  value={terminalInput}
                  onChange={(e) => setTerminalInput(e.target.value)}
                  onKeyDown={handleTerminalKey}
                  placeholder="Type a command..."
                  className="ide-terminal-input"
                  spellCheck={false}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
