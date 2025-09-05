import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { API_ENDPOINTS, getBackendInfo } from '../config/api'
import SearchPanel from './SearchPanel'
import FileContent from './FileContent'
import ExtractedFields from './ExtractedFields'
import './DocumentViewer.css'

function DocumentViewer() {
  const [fileData, setFileData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  // Initialize from URL parameters on component mount
  useEffect(() => {
    const taskId = searchParams.get('taskId')
    const relativePath = searchParams.get('relativePath')
    
    if (taskId && relativePath) {
      handleSearch(taskId, relativePath, false) // Don't update URL since we're reading from it
    }
  }, [])

  const handleSearch = async (taskId, relativePath, updateURL = true) => {
    setLoading(true)
    setError(null)
    
    // Update URL with search parameters
    if (updateURL) {
      setSearchParams({ taskId, relativePath })
    }
    
    const requestBody = {
      task_id: parseInt(taskId),
      relative_path: relativePath
    }
    
    console.log('Sending request to:', API_ENDPOINTS.VIEW_CONTENT)
    console.log('Request body:', requestBody)
    
    try {
      const response = await fetch(API_ENDPOINTS.VIEW_CONTENT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      })

      console.log('Response status:', response.status)
      console.log('Response headers:', response.headers)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Error response body:', errorText)
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      console.log('Success response data:', data)
      setFileData(data)
    } catch (err) {
      console.error('Fetch error:', err)
      setError(err.message)
      setFileData(null)
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setFileData(null)
    setError(null)
    setSearchParams({}) // Clear URL parameters
  }



  return (
    <div className="document-viewer">
      <SearchPanel onSearch={handleSearch} onClear={handleClear} loading={loading} />
      
      {error && (
        <div className="error-message">
          Error: {error}
        </div>
      )}
      
      {fileData && (
        <div className="main-content">
          <FileContent fileData={fileData} />
          <ExtractedFields fileData={fileData} />
        </div>
      )}
    </div>
  )
}

export default DocumentViewer
