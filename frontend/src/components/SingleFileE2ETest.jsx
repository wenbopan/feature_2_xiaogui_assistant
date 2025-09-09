import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { API_ENDPOINTS, getBackendInfo } from '../config/api'
import { authenticatedFetch, authenticatedPostForm } from '../utils/api'
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
  const [ossUrl, setOssUrl] = useState('')
  const [useOssUrl, setUseOssUrl] = useState(false)

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
      setOssUrl('')
      setUseOssUrl(false)
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
      setOssUrl('')
      setUseOssUrl(false)
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
    setOssUrl('')
    setUseOssUrl(false)
    
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
      const response = await authenticatedFetch(API_ENDPOINTS.CALLBACK_RESULTS(fileId))
      if (response.ok) {
        const result = await response.json()
        const currentCount = result.results ? result.results.length : 0
        
        // Only update if we have new results
        if (currentCount > lastResultCount) {
          setLastResultCount(currentCount)
          
          // Convert all results to display format
          const newCallbackData = result.results.map(callbackResult => {
            let processedData = callbackResult.data
            
            // If file_content is a stringified JSON, parse it for better display
            if (processedData.file_content && typeof processedData.file_content === 'string') {
              try {
                processedData = {
                  ...processedData,
                  file_content: JSON.parse(processedData.file_content)
                }
              } catch (e) {
                // If parsing fails, keep the original string
                console.warn('Failed to parse file_content JSON:', e)
              }
            }
            
            return {
              id: `${callbackResult.type}_${callbackResult.timestamp}`,
              type: callbackResult.type,
              timestamp: callbackResult.timestamp,
              data: processedData
            }
          })
          
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
      
      // Create custom callback structure for classification
      const updateFileCallback = {
        url: API_ENDPOINTS.CALLBACK_CLASSIFY,
        body: {
          file_id: fileId,
          file_category: "${file_category}",
          is_recognized: "${is_recognized}",
          timestamp: new Date().toISOString(),
          test_type: "classification_e2e"
        }
      }
      classifyFormData.append('update_file_callback', JSON.stringify(updateFileCallback))

      const classifyResponse = await authenticatedPostForm(API_ENDPOINTS.CLASSIFY, classifyFormData)

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
      
      // Create custom callback structure for extraction
      const extractFileCallback = {
        url: API_ENDPOINTS.CALLBACK_EXTRACT,
        body: {
          file_id: fileId,
          file_content: "${file_content}",
          is_extracted: "${is_extracted}",
          timestamp: new Date().toISOString(),
          test_type: "extraction_e2e"
        }
      }
      extractFormData.append('extract_file_callback', JSON.stringify(extractFileCallback))

      const extractResponse = await authenticatedPostForm(API_ENDPOINTS.EXTRACT_FIELDS, extractFormData)

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

  const handleClassifyWithOssUrl = async () => {
    if (!ossUrl.trim()) {
      setError('Please enter an OSS URL')
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      setSuccess(null)
      
      const fileId = currentFileId || generateFileId()
      setCurrentFileId(fileId)
      
      const currentCount = callbackData.length
      setLastResultCount(currentCount)
      
      setProcessingStep('Step 1: Sending OSS URL for classification...')

      // Step 1: Send OSS URL for classification
      const classifyFormData = new FormData()
      classifyFormData.append('oss_url', ossUrl.trim())
      classifyFormData.append('file_type', 'pdf') // Assume PDF for OSS URL test
      classifyFormData.append('file_id', fileId)
      
      // Create custom callback structure for classification
      const updateFileCallback = {
        url: API_ENDPOINTS.CALLBACK_CLASSIFY,
        body: {
          file_id: fileId,
          oss_url: ossUrl.trim(),
          file_category: "${file_category}",
          is_recognized: "${is_recognized}",
          timestamp: new Date().toISOString(),
          test_type: "classification_oss_e2e"
        }
      }
      classifyFormData.append('update_file_callback', JSON.stringify(updateFileCallback))

      const classifyResponse = await authenticatedPostForm(API_ENDPOINTS.CLASSIFY, classifyFormData)

      if (!classifyResponse.ok) {
        throw new Error(`Classification failed: ${classifyResponse.status}`)
      }

      const classifyData = await classifyResponse.json()
      
      setProcessingStep('Step 2: Waiting for classification callback...')
      setSuccess('OSS URL sent for classification! Waiting for callback...')
      
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

  const handleExtractWithOssUrl = async () => {
    if (!ossUrl.trim()) {
      setError('Please enter an OSS URL')
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      setSuccess(null)
      
      const fileId = currentFileId || generateFileId()
      setCurrentFileId(fileId)
      
      const currentCount = callbackData.length
      setLastResultCount(currentCount)
      
      setProcessingStep('Step 1: Sending OSS URL for field extraction...')

      // Step 1: Send OSS URL for extraction
      const extractFormData = new FormData()
      extractFormData.append('oss_url', ossUrl.trim())
      extractFormData.append('file_type', 'pdf') // Assume PDF for OSS URL test
      extractFormData.append('file_id', fileId)
      
      // Create custom callback structure for extraction
      const extractFileCallback = {
        url: API_ENDPOINTS.CALLBACK_EXTRACT,
        body: {
          file_id: fileId,
          oss_url: ossUrl.trim(),
          file_content: "${file_content}",
          is_extracted: "${is_extracted}",
          timestamp: new Date().toISOString(),
          test_type: "extraction_oss_e2e"
        }
      }
      extractFormData.append('extract_file_callback', JSON.stringify(extractFileCallback))

      const extractResponse = await authenticatedPostForm(API_ENDPOINTS.EXTRACT_FIELDS, extractFormData)

      if (!extractResponse.ok) {
        throw new Error(`Extraction failed: ${extractResponse.status}`)
      }

      const extractData = await extractResponse.json()
      
      setProcessingStep('Step 2: Waiting for extraction callback...')
      setSuccess('OSS URL sent for extraction! Waiting for callback...')
      
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

  const renderCallbackData = (data) => {
    return <pre className="json-display">{JSON.stringify(data, null, 2)}</pre>
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

        {/* OSS URL Input */}
        <div className="oss-url-section">
          <div className="oss-url-container">
            <div className="oss-url-header">
              <label htmlFor="ossUrlInput" className="oss-url-label">
                OSS URL (Alternative to file upload):
              </label>
              <div className="oss-url-toggle">
                <input
                  type="checkbox"
                  id="useOssUrl"
                  checked={useOssUrl}
                  onChange={(e) => setUseOssUrl(e.target.checked)}
                />
                <label htmlFor="useOssUrl">Use OSS URL instead of file upload</label>
              </div>
            </div>
            {useOssUrl && (
              <div className="oss-url-input-group">
                <input
                  type="url"
                  id="ossUrlInput"
                  value={ossUrl}
                  onChange={(e) => setOssUrl(e.target.value)}
                  placeholder="https://example.com/path/to/file.pdf"
                  className="oss-url-input"
                />
                <button
                  type="button"
                  onClick={() => setOssUrl('')}
                  className="clear-oss-url-btn"
                  disabled={isLoading}
                >
                  Clear
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="action-buttons">
          <div className="file-upload-buttons">
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
          
          {useOssUrl && (
            <div className="oss-url-buttons">
              <button 
                onClick={handleClassifyWithOssUrl}
                disabled={!ossUrl.trim() || isLoading}
                className="action-btn classify-oss-btn"
              >
                🌐 Classify OSS E2E
              </button>
              <button 
                onClick={handleExtractWithOssUrl}
                disabled={!ossUrl.trim() || isLoading}
                className="action-btn extract-oss-btn"
              >
                🌐 Extract OSS E2E
              </button>
            </div>
          )}
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
                    {renderCallbackData(callback.data)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="test-footer">
          <div className="status-info">
            <span className="status-text">Connected</span>
            <span>Backend: {getBackendInfo().host}:{getBackendInfo().port}</span>
            <span>E2E Tests: {callbackData.length}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SingleFileE2ETest