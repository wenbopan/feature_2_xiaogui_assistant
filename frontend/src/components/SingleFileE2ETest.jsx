import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import './SingleFileE2ETest.css'

function SingleFileE2ETest() {
  const [callbackData, setCallbackData] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef(null)

  // Processing states
  const [processingStep, setProcessingStep] = useState('')
  const [currentFileId, setCurrentFileId] = useState('')
  const [customFileId, setCustomFileId] = useState('')
  const [lastResultCount, setLastResultCount] = useState(0)

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file) {
      setSelectedFile(file)
      setCallbackData([])
      setError(null)
      setSuccess(null)
      setCurrentFileId('')
      setCustomFileId('')
      setLastResultCount(0)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const file = e.dataTransfer.files[0]
    if (file) {
      setSelectedFile(file)
      setCallbackData([])
      setError(null)
      setSuccess(null)
      setCurrentFileId('')
      setCustomFileId('')
      setLastResultCount(0)
    }
  }

  const handleClear = () => {
    setSelectedFile(null)
    setCallbackData([])
    setError(null)
    setSuccess(null)
    setProcessingStep('')
    setCurrentFileId('')
    setCustomFileId('')
    setLastResultCount(0)
    
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const generateFileId = () => {
    if (customFileId.trim()) {
      return customFileId.trim()
    }
    return `test_file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  const getFileExtension = (filename) => {
    const parts = filename.split('.')
    if (parts.length < 2) return null
    return parts[parts.length - 1].toLowerCase()
  }

  const isSupportedFileType = (filename) => {
    const extension = getFileExtension(filename)
    const supportedTypes = ['pdf', 'jpg', 'jpeg', 'png']
    return extension && supportedTypes.includes(extension)
  }

  const checkCallbackResult = async (fileId) => {
    try {
      const response = await fetch(`http://localhost:8001/api/v1/callbacks/results/${fileId}`)
      if (response.ok) {
        const result = await response.json()
        const currentCount = result.results ? result.results.length : 0
        
        // Only update if we have new results
        if (currentCount > lastResultCount) {
          setLastResultCount(currentCount)
          
          // Convert all results to display format
          const newCallbackData = result.results.map(callbackResult => ({
            id: `${callbackResult.type}_${callbackResult.timestamp}`,
            type: callbackResult.type,
            timestamp: callbackResult.timestamp,
            data: callbackResult.data
          }))
          
          setCallbackData(newCallbackData)
          
          // Show the latest result
          const latestResult = result.results[result.results.length - 1]
          setProcessingStep(`${latestResult.type} completed!`)
          setSuccess(`${latestResult.type} completed successfully!`)
          return true
        }
      }
      return false
    } catch (error) {
      console.error('Error checking callback result:', error)
      return false
    }
  }

  const pollForCallback = (fileId, maxAttempts = 30) => {
    let attempts = 0
    
    const poll = async () => {
      attempts++
      const found = await checkCallbackResult(fileId)
      
      // If we found results, we can stop polling for this specific operation
      // But we might want to continue polling for additional results
      // For now, let's stop after finding results to avoid timeout messages
      if (found) {
        return // Stop polling when we find results
      }
      
      // Only stop if we've reached max attempts
      if (attempts >= maxAttempts) {
        setError('Timeout waiting for callback result')
        return
      }
      
      // Wait 2 seconds before next check
      setTimeout(poll, 2000)
    }
    
    // Start polling
    poll()
  }

  const handleClassifyE2E = async () => {
    if (!selectedFile) {
      setError('Please select a file first')
      return
    }

    if (!isSupportedFileType(selectedFile.name)) {
      setError(`Unsupported file type. Supported types: PDF, JPG, JPEG, PNG. Your file: ${selectedFile.name}`)
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      setSuccess(null)
      // Don't clear callbackData - keep existing results
      
      // Use existing file ID if available, otherwise generate new one
      const fileId = currentFileId || generateFileId()
      setCurrentFileId(fileId)
      
      // Reset result count to current count so we can detect new results
      const currentCount = callbackData.length
      setLastResultCount(currentCount)
      
      setProcessingStep('Step 1: Sending file for classification...')

      // Step 1: Send for classification
      const classifyFormData = new FormData()
      classifyFormData.append('file_content', selectedFile)
      classifyFormData.append('file_type', getFileExtension(selectedFile.name))
      classifyFormData.append('file_id', fileId)
      classifyFormData.append('callback_url', 'http://localhost:8001/api/v1/callbacks/classify-file')

      const classifyResponse = await fetch('http://localhost:8001/api/v1/files/classify', {
        method: 'POST',
        body: classifyFormData
      })

      if (!classifyResponse.ok) {
        throw new Error(`Classification failed: ${classifyResponse.status}`)
      }

      const classifyData = await classifyResponse.json()
      
      setProcessingStep('Step 2: Waiting for classification callback...')
      setSuccess('File sent for classification! Waiting for callback...')
      
      // Start polling for callback result (non-blocking)
      pollForCallback(fileId)
      
    } catch (err) {
      console.error('Classification error:', err)
      setError(`Classification failed: ${err.message}`)
      setProcessingStep('')
    } finally {
      setIsLoading(false)
    }
  }

  const handleExtractE2E = async () => {
    if (!selectedFile) {
      setError('Please select a file first')
      return
    }

    if (!isSupportedFileType(selectedFile.name)) {
      setError(`Unsupported file type. Supported types: PDF, JPG, JPEG, PNG. Your file: ${selectedFile.name}`)
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      setSuccess(null)
      // Don't clear callbackData - keep existing results
      
      // Use existing file ID if available, otherwise generate new one
      const fileId = currentFileId || generateFileId()
      setCurrentFileId(fileId)
      
      // Reset result count to current count so we can detect new results
      const currentCount = callbackData.length
      setLastResultCount(currentCount)
      
      setProcessingStep('Step 1: Sending file for field extraction...')

      // Step 1: Send for extraction
      const extractFormData = new FormData()
      extractFormData.append('file_content', selectedFile)
      extractFormData.append('file_type', getFileExtension(selectedFile.name))
      extractFormData.append('file_id', fileId)
      extractFormData.append('callback_url', 'http://localhost:8001/api/v1/callbacks/extract-file')

      const extractResponse = await fetch('http://localhost:8001/api/v1/files/extract-fields', {
        method: 'POST',
        body: extractFormData
      })

      if (!extractResponse.ok) {
        throw new Error(`Extraction failed: ${extractResponse.status}`)
      }

      const extractData = await extractResponse.json()
      
      setProcessingStep('Step 2: Waiting for extraction callback...')
      setSuccess('File sent for extraction! Waiting for callback...')
      
      // Start polling for callback result (non-blocking)
      pollForCallback(fileId)
      
    } catch (err) {
      console.error('Extraction error:', err)
      setError(`Field extraction failed: ${err.message}`)
      setProcessingStep('')
    } finally {
      setIsLoading(false)
    }
  }



  const formatTimestamp = (timestamp) => {
    // Convert Unix timestamp (seconds) to milliseconds for JavaScript Date
    return new Date(timestamp * 1000).toLocaleString()
  }

  const getCallbackTypeLabel = (type) => {
    return type === 'classification' ? '🏷️ Classification' : '📊 Extraction'
  }

  const getCallbackTypeColor = (type) => {
    return type === 'classification' ? '#3b82f6' : '#10b981'
  }

  return (
    <div className="callback-test-page">
      <div className="callback-test-container">
        {/* Header */}
        <div className="test-header">
          <div className="header-content">
            <h2>🔄 E2E Single File Test</h2>
            <Link to="/legal-doc/single-file-test" className="back-link">
              ← Back to Single File Test
            </Link>
          </div>
          <div className="test-description">
            <p>Test complete end-to-end single file processing with real callbacks</p>
          </div>
        </div>

        {/* File Upload Area */}
        <div className="file-upload-section">
          <div 
            className={`drag-drop-zone ${isDragOver ? 'drag-over' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="upload-icon">📄</div>
            <p className="upload-text">
              {selectedFile ? selectedFile.name : 'Click to browse files or drag files here'}
            </p>
            <p className="supported-types">
              Supported types: PDF, JPG, JPEG, PNG
            </p>
            <p className="upload-hint">
              {selectedFile ? 
                `Selected: ${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB)` : 
                'Maximum file size: 10MB'
              }
            </p>
            <input
              ref={fileInputRef}
              type="file"
              id="fileInput"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <label 
              htmlFor="fileInput" 
              className="browse-btn"
            >
              Browse Files
            </label>
          </div>
        </div>

        {/* File ID Input */}
        <div className="file-id-section">
          <div className="file-id-container">
            <label htmlFor="fileIdInput" className="file-id-label">
              File ID (Optional):
            </label>
            <div className="file-id-input-group">
              <input
                type="text"
                id="fileIdInput"
                value={customFileId}
                onChange={(e) => setCustomFileId(e.target.value)}
                placeholder="Enter custom file ID or leave empty for auto-generation"
                className="file-id-input"
              />
              <button
                type="button"
                onClick={() => setCustomFileId(generateFileId())}
                className="generate-id-btn"
                disabled={isLoading}
              >
                Generate ID
              </button>
            </div>
            {currentFileId && (
              <div className="current-file-id">
                <span className="current-id-label">Current File ID:</span>
                <span className="current-id-value">{currentFileId}</span>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="action-buttons">
          <button 
            onClick={handleClassifyE2E}
            disabled={!selectedFile || isLoading}
            className="action-btn classify-btn"
          >
            🏷️ Classify E2E
          </button>
          <button 
            onClick={handleExtractE2E}
            disabled={!selectedFile || isLoading}
            className="action-btn extract-btn"
          >
            📊 Extract E2E
          </button>
          <button 
            onClick={handleClear}
            disabled={isLoading}
            className="action-btn clear-btn"
          >
            🗑️ Clear
          </button>
        </div>

        {/* Processing Status */}
        {isLoading && (
          <div className="processing-status">
            <div className="processing-spinner"></div>
            <p>{processingStep}</p>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="error-message">
            <span className="error-icon">❌</span>
            {error}
          </div>
        )}

        {/* Success Message */}
        {success && (
          <div className="success-message">
            <span className="success-icon">✅</span>
            {success}
          </div>
        )}

        {/* Callback Data Display */}
        <div className="callback-data-section">
          <div className="section-header">
            <h3>📋 E2E Callback Results</h3>
            <div className="file-info">
              {currentFileId && <span>File ID: {currentFileId}</span>}
            </div>
          </div>
          
          {callbackData.length === 0 ? (
            <div className="no-data">
              <p>No E2E processing results yet. Upload a file and run classification or extraction to see real callback data!</p>
            </div>
          ) : (
            <div className="callback-list">
              {callbackData.map((callback) => (
                <div key={callback.id} className="callback-item">
                  <div className="callback-header">
                    <span 
                      className="callback-type"
                      style={{ backgroundColor: getCallbackTypeColor(callback.type) }}
                    >
                      {getCallbackTypeLabel(callback.type)}
                    </span>
                    <span className="callback-timestamp">
                      {formatTimestamp(callback.timestamp)}
                    </span>
                  </div>
                  <div className="callback-content">
                    <pre>{JSON.stringify(callback.data, null, 2)}</pre>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="test-footer">
          <div className="status-info">
            <span className="status-indicator">✅ Connected</span>
            <span>Backend: localhost:8001</span>
            <span>E2E Tests: {callbackData.length}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SingleFileE2ETest