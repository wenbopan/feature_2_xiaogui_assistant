import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import './Dashboard.css'

function Dashboard() {
  const { taskId } = useParams()
  const [taskInfo, setTaskInfo] = useState(null)
  const [processingStatus, setProcessingStatus] = useState({
    extractFields: { status: 'pending', progress: 0, details: null },
    rename: { status: 'pending', progress: 0, details: null }
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastFetchTime, setLastFetchTime] = useState(null)

  useEffect(() => {
    fetchTaskInfo()
    // Set up polling for status updates
    const interval = setInterval(fetchTaskStatus, 2000)
    
    return () => clearInterval(interval)
  }, [taskId])

  const fetchTaskInfo = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/tasks/${taskId}`)
      if (response.ok) {
        const data = await response.json()
        setTaskInfo(data)
      } else {
        setError('Task not found')
      }
    } catch (err) {
      setError('Failed to fetch task information')
    } finally {
      setIsLoading(false)
    }
  }

  const fetchTaskStatus = async () => {
    try {
      // Fetch extraction progress
      const extractResponse = await fetch(`http://localhost:8000/api/v1/tasks/${taskId}/extraction-progress`)
      let extractData = null
      if (extractResponse.ok) {
        extractData = await extractResponse.json()
        console.log('Extraction progress data:', extractData)
      } else {
        console.error('Failed to fetch extraction progress:', extractResponse.status, extractResponse.statusText)
      }

      // Fetch processing progress (renaming/classification)
              const processResponse = await fetch(`http://localhost:8000/api/v1/${taskId}/file-classification-progress`)
      let processData = null
      if (processResponse.ok) {
        processData = await processResponse.json()
        console.log('Processing progress data:', processData)
      } else {
        console.error('Failed to fetch processing progress:', processResponse.status, processResponse.statusText)
      }

      // Update processing status based on real API data
      setProcessingStatus({
        extractFields: {
          status: extractData ? (extractData.completed_files === extractData.total_files ? 'completed' : 'processing') : 'pending',
          progress: extractData && extractData.total_files > 0 ? 
            Math.round((extractData.completed_files / extractData.total_files) * 100) : 0,
          details: extractData
        },
        rename: {
          status: processData ? (processData.completed_files === processData.total_files ? 'completed' : 'processing') : 'pending',
          progress: processData && processData.total_files > 0 ? 
            Math.round((processData.completed_files / processData.total_files) * 100) : 0,
          details: processData
        }
      })
      
      setLastFetchTime(new Date())
    } catch (err) {
      console.error('Failed to fetch status:', err)
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#10b981'
      case 'processing': return '#3b82f6'
      case 'failed': return '#ef4444'
      default: return '#6b7280'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return '✅'
      case 'processing': return '🔄'
      case 'failed': return '❌'
      default: return '⏳'
    }
  }

  if (isLoading) {
    return (
      <div className="dashboard-page">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading task information...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard-page">
        <div className="error-container">
          <h2>❌ Error</h2>
          <p>{error}</p>
          <Link to="/legal-doc/files/view-content" className="back-btn">
            Back to Documents
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-container">
        <div className="dashboard-header">
          <div className="header-content">
            <h2>📊 Task Dashboard</h2>
            <Link to="/legal-doc/files/view-content" className="back-link">
              ← Back to Documents
            </Link>
          </div>
        </div>

        {taskInfo && (
          <div className="task-info-section">
            <h3>Task Information</h3>
            <div className="task-details">
              <div className="detail-item">
                <span className="label">Task ID:</span>
                <span className="value">{taskInfo.id}</span>
              </div>
              <div className="detail-item">
                <span className="label">Project Name:</span>
                <span className="value">{taskInfo.project_name}</span>
              </div>
              <div className="detail-item">
                <span className="label">Organize Date:</span>
                <span className="value">{taskInfo.organize_date}</span>
              </div>
              <div className="detail-item">
                <span className="label">Status:</span>
                <span className="value status-badge" style={{ backgroundColor: getStatusColor(taskInfo.status) }}>
                  {taskInfo.status}
                </span>
              </div>
            </div>
          </div>
        )}

        <div className="processing-status-section">
          <h3>Processing Status</h3>
          
          <div className="status-cards">
            <div className="status-card">
              <div className="status-header">
                <span className="status-icon">
                  {getStatusIcon(processingStatus.extractFields.status)}
                </span>
                <h4>Extract Fields</h4>
              </div>
              
              <div className="progress-container">
                <div className="progress-bar">
                  <div 
                    className="progress-fill"
                    style={{ width: `${processingStatus.extractFields.progress}%` }}
                  ></div>
                </div>
                <span className="progress-text">
                  {Math.round(processingStatus.extractFields.progress)}%
                </span>
              </div>
              
              <div className="status-text">
                Status: {processingStatus.extractFields.status}
              </div>
              
              {processingStatus.extractFields.details && (
                <div className="status-details">
                  <div className="detail-row">
                    <span>Total: {processingStatus.extractFields.details.total_files}</span>
                    <span>Completed: {processingStatus.extractFields.details.completed_files}</span>
                  </div>
                  <div className="detail-row">
                    <span>Failed: {processingStatus.extractFields.details.failed_files}</span>
                    <span>Pending: {processingStatus.extractFields.details.pending_files}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="status-card">
              <div className="status-header">
                <span className="status-icon">
                  {getStatusIcon(processingStatus.rename.status)}
                </span>
                <h4>Content Processing</h4>
              </div>
              
              <div className="progress-container">
                <div className="progress-bar">
                  <div 
                    className="progress-fill"
                    style={{ width: `${processingStatus.rename.progress}%` }}
                  ></div>
                </div>
                <span className="progress-text">
                  {Math.round(processingStatus.rename.progress)}%
                </span>
              </div>
              
              <div className="status-text">
                Status: {processingStatus.rename.status}
              </div>
              
              {processingStatus.rename.details ? (
                <div className="status-details">
                  <div className="detail-row">
                    <span>Total: {processingStatus.rename.details.total_files}</span>
                    <span>Completed: {processingStatus.rename.details.completed_files}</span>
                  </div>
                  <div className="detail-row">
                    <span>Failed: {processingStatus.rename.details.failed_files}</span>
                    <span>Pending: {processingStatus.rename.details.pending_files}</span>
                  </div>
                </div>
              ) : (
                <div className="status-details">
                  <div className="detail-row">
                    <span className="error-text">⚠️ Progress data unavailable</span>
                  </div>
                  <div className="detail-row">
                    <span>Check backend logs for details</span>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <div className="processing-details">
            <p className="detail-text">
              <strong>Note:</strong> Content processing includes document classification and file renaming.
            </p>
          </div>
        </div>

        <div className="debug-section">
          <h4>Debug Information</h4>
          <div className="debug-info">
            <p><strong>Last Fetch:</strong> {lastFetchTime ? lastFetchTime.toLocaleTimeString() : 'Never'}</p>
            <p><strong>Extraction Endpoint:</strong> 
              {processingStatus.extractFields.details ? '✅ Working' : '❌ Failed'}
            </p>
            <p><strong>Processing Endpoint:</strong> 
              {processingStatus.rename.details ? '✅ Working' : '❌ Failed'}
            </p>
            <button onClick={fetchTaskStatus} className="refresh-btn">
              🔄 Refresh Status
            </button>
          </div>
        </div>

        <div className="actions-section">
          <Link to="/legal-doc/processing" className="new-task-btn">
            Process Another Task
          </Link>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
