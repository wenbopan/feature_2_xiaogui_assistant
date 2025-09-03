import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import './SingleFileTest.css'

function SingleFileTest() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [processingStep, setProcessingStep] = useState('')
  const fileInputRef = useRef(null)

  const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file) {
      setSelectedFile(file)
      setResults(null)
      setError(null)
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
      setResults(null)
      setError(null)
    }
  }

  const handleClear = () => {
    setSelectedFile(null)
    setResults(null)
    setError(null)
    setProcessingStep('')
    
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleClassify = async () => {
    if (!selectedFile) {
      setError('Please select a file first')
      return
    }

    try {
      setIsProcessing(true)
      setError(null)
      setResults(null)
      setProcessingStep('Classifying file...')

      const formData = new FormData()
      formData.append('file_content', selectedFile)
      formData.append('file_type', selectedFile.name.split('.').pop() || 'unknown')

      const response = await fetch('http://localhost:8000/api/v1/files/classify', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`Classification failed: ${response.status}`)
      }

      const data = await response.json()
      
      setResults(prev => ({
        ...prev,
        classification: {
          status: 'completed',
          result: data
        }
      }))
      
      setProcessingStep('Classification completed!')
    } catch (err) {
      console.error('Classification error:', err)
      setError(`Classification failed: ${err.message}`)
      setProcessingStep('')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleExtract = async () => {
    if (!selectedFile) {
      setError('Please select a file first')
      return
    }

    try {
      setIsProcessing(true)
      setError(null)
      setProcessingStep('Extracting fields...')

      const formData = new FormData()
      formData.append('file_content', selectedFile)
      formData.append('file_type', selectedFile.name.split('.').pop() || 'unknown')

      const response = await fetch('http://localhost:8000/api/v1/files/extract-fields', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`Extraction failed: ${response.status}`)
      }

      const data = await response.json()
      
      setResults(prev => ({
        ...prev,
        extraction: {
          status: 'completed',
          result: data
        }
      }))
      
      setProcessingStep('Field extraction completed!')
    } catch (err) {
      console.error('Extraction error:', err)
      setError(`Field extraction failed: ${err.message}`)
      setProcessingStep('')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleProcessBoth = async () => {
    if (!selectedFile) {
      setError('Please select a file first')
      return
    }

    try {
      setIsProcessing(true)
      setError(null)
      setResults(null)
      setProcessingStep('Processing file (classification + extraction)...')

      // First, classify the file
      setProcessingStep('Step 1: Classifying file...')
      const classifyFormData = new FormData()
      classifyFormData.append('file_content', selectedFile)
      classifyFormData.append('file_type', selectedFile.name.split('.').pop() || 'unknown')

      const classifyResponse = await fetch('http://localhost:8000/api/v1/files/classify', {
        method: 'POST',
        body: classifyFormData
      })

      if (!classifyResponse.ok) {
        throw new Error(`Classification failed: ${classifyResponse.status}`)
      }

      const classifyData = await classifyResponse.json()
      
      setResults(prev => ({
        ...prev,
        classification: {
          status: 'completed',
          result: classifyData
        }
      }))

      // Then, extract fields
      setProcessingStep('Step 2: Extracting fields...')
      const extractFormData = new FormData()
      extractFormData.append('file_content', selectedFile)
      extractFormData.append('file_type', selectedFile.name.split('.').pop() || 'unknown')

      const extractResponse = await fetch('http://localhost:8000/api/v1/files/extract-fields', {
        method: 'POST',
        body: extractFormData
      })

      if (!extractResponse.ok) {
        throw new Error(`Extraction failed: ${extractResponse.status}`)
      }

      const extractData = await extractResponse.json()
      
      setResults(prev => ({
        ...prev,
        extraction: {
          status: 'completed',
          result: extractData
        }
      }))
      
      setProcessingStep('Both classification and extraction completed!')
    } catch (err) {
      console.error('Processing error:', err)
      setError(`Processing failed: ${err.message}`)
      setProcessingStep('')
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="single-file-test-page">
      <div className="single-file-test-container">
        {/* Header */}
        <div className="test-header">
          <div className="header-content">
            <h2>🧪 Single File Test</h2>
            <div className="header-links">
              <Link to="/legal-doc/files/view-content" className="back-link">
                ← Back to Documents
              </Link>
              <Link to="/legal-doc/e2e-test" className="callback-link">
                🔄 E2E Test →
              </Link>
            </div>
          </div>
          <div className="test-description">
            <p>Test file classification and field extraction on individual files</p>
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
            <p className="upload-hint">
              {selectedFile ? 
                `Selected: ${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB)` : 
                'Supports PDF, DOC, DOCX, and other document formats'
              }
            </p>
            <input
              ref={fileInputRef}
              type="file"
              id="fileInput"
              accept=".pdf,.doc,.docx,.txt,.jpg,.jpeg,.png"
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

        {/* Action Buttons */}
        <div className="action-buttons">
          <button 
            onClick={handleClassify}
            disabled={!selectedFile || isProcessing}
            className="action-btn classify-btn"
          >
            🏷️ Classify Only
          </button>
          <button 
            onClick={handleExtract}
            disabled={!selectedFile || isProcessing}
            className="action-btn extract-btn"
          >
            📊 Extract Fields Only
          </button>
          <button 
            onClick={handleProcessBoth}
            disabled={!selectedFile || isProcessing}
            className="action-btn process-both-btn"
          >
            🔄 Process Both
          </button>
          <button 
            onClick={handleClear}
            disabled={isProcessing}
            className="action-btn clear-btn"
          >
            🗑️ Clear
          </button>
        </div>

        {/* Processing Status */}
        {isProcessing && (
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

        {/* Results */}
        {results && (
          <div className="results-section">
            <h3>📋 Results</h3>
            
            {/* Classification Results */}
            {results.classification && (
              <div className="result-card classification-result">
                <h4>🏷️ Classification Result</h4>
                <div className="result-content">
                  <pre>{JSON.stringify(results.classification.result, null, 2)}</pre>
                </div>
              </div>
            )}

            {/* Extraction Results */}
            {results.extraction && (
              <div className="result-card extraction-result">
                <h4>📊 Field Extraction Result</h4>
                <div className="result-content">
                  <pre>{JSON.stringify(results.extraction.result, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="test-footer">
          <div className="status-info">
            <span className="status-indicator">✅ Connected</span>
            <span>Backend: localhost:8000</span>
            <span>Last Test: {new Date().toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SingleFileTest
