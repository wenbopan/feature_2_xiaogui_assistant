import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './SearchPanel.css'

function SearchPanel({ onSearch, onClear, loading }) {
  const navigate = useNavigate()
  const [taskId, setTaskId] = useState('')
  const [relativePath, setRelativePath] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (taskId && relativePath) {
      onSearch(taskId, relativePath)
    }
  }

  const handleClear = () => {
    setTaskId('')
    setRelativePath('')
    onClear()
  }

  return (
    <div className="search-panel">
      <form onSubmit={handleSubmit}>
        <div className="search-inputs">
          <div className="input-group">
            <label htmlFor="taskId">Task ID:</label>
            <input
              type="number"
              id="taskId"
              value={taskId}
              onChange={(e) => setTaskId(e.target.value)}
              placeholder="Enter task ID"
              required
            />
          </div>
          
          <div className="input-group">
            <label htmlFor="relativePath">Relative Path:</label>
            <input
              type="text"
              id="relativePath"
              value={relativePath}
              onChange={(e) => setRelativePath(e.target.value)}
              placeholder="Enter relative path (e.g., 发票/易酷科技/文件名.jpg)"
              required
            />
          </div>
        </div>
        
        <div className="search-buttons">
          <button 
            type="submit" 
            disabled={loading || !taskId || !relativePath}
            className="search-btn"
          >
            {loading ? 'Searching...' : '🔍 Search'}
          </button>
          
          <button 
            type="button" 
            onClick={handleClear}
            className="clear-btn"
          >
            🗑️ Clear
          </button>
          
          <Link to="/legal-doc/upload" className="upload-link">
            📤 Upload Documents
          </Link>
          
          <Link to="/legal-doc/processing" className="processing-link">
            ⚙️ Process Files
          </Link>
          
          <button 
            type="button" 
            onClick={() => {
              if (taskId) {
                navigate(`/legal-doc/dashboard/${taskId}`)
              } else {
                alert('Please enter a Task ID first to view the dashboard.')
              }
            }}
            className="dashboard-link"
          >
            📊 Dashboard
          </button>
        </div>
      </form>
    </div>
  )
}

export default SearchPanel
