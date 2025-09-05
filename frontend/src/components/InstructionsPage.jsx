import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { API_ENDPOINTS, getBackendInfo } from '../config/api'
import './InstructionsPage.css'

function InstructionsPage() {
  const [instructions, setInstructions] = useState({
    '发票': '',
    '租赁协议': '',
    '变更/解除协议': '',
    '账单': '',
    '银行回单': ''
  })
  
  const [originalInstructions, setOriginalInstructions] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [configInfo, setConfigInfo] = useState({
    version: '',
    last_updated: '',
    config_path: ''
  })

  useEffect(() => {
    loadInstructions()
  }, [])

  const loadInstructions = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      const response = await fetch(API_ENDPOINTS.INSTRUCTIONS)
      if (!response.ok) {
        throw new Error(`Failed to load instructions: ${response.status}`)
      }
      
      const data = await response.json()
      
      if (data.success && data.memory_instructions) {
        // Use memory_instructions directly (these are the current active instructions)
        const loadedInstructions = {
          '发票': data.memory_instructions['发票'] || '',
          '租赁协议': data.memory_instructions['租赁协议'] || '',
          '变更/解除协议': data.memory_instructions['变更/解除协议'] || '',
          '账单': data.memory_instructions['账单'] || '',
          '银行回单': data.memory_instructions['银行回单'] || ''
        }
        
        setInstructions(loadedInstructions)
        setOriginalInstructions({ ...loadedInstructions })
        setConfigInfo({
          version: data.config?.version || 'Unknown',
          last_updated: data.last_modified || 'Unknown',
          config_path: data.config_path || 'Unknown'
        })
      } else {
        throw new Error('Invalid response format')
      }
    } catch (err) {
      console.error('Failed to load instructions:', err)
      setError(`Failed to load instructions: ${err.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInstructionChange = (category, value) => {
    setInstructions(prev => ({
      ...prev,
      [category]: value
    }))
  }

  const handleSubmit = async () => {
    try {
      setIsSubmitting(true)
      setError(null)
      setSuccess(null)
      
      const response = await fetch(API_ENDPOINTS.INSTRUCTIONS_HOT_SWAP, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(instructions)
      })
      
      if (!response.ok) {
        throw new Error(`Failed to hot-swap instructions: ${response.status}`)
      }
      
      const data = await response.json()
      
      if (data.success) {
        setSuccess('Instructions hot-swapped successfully!')
        // Update the original instructions to reflect the new state
        setOriginalInstructions({ ...instructions })
        setConfigInfo(prev => ({
          ...prev,
          last_updated: data.last_modified || new Date().toISOString()
        }))
      } else {
        throw new Error('Failed to hot-swap instructions')
      }
    } catch (err) {
      console.error('Failed to hot-swap instructions:', err)
      setError(`Failed to hot-swap instructions: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    setInstructions({ ...originalInstructions })
    setError(null)
    setSuccess(null)
  }

  const handleResetToOriginal = async () => {
    try {
      setIsSubmitting(true)
      setError(null)
      setSuccess(null)
      
      const response = await fetch(API_ENDPOINTS.INSTRUCTIONS_RESET, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (!response.ok) {
        throw new Error(`Failed to reset instructions: ${response.status}`)
      }
      
      const data = await response.json()
      
      if (data.success) {
        // Reload the instructions from the server
        await loadInstructions()
        setSuccess('Instructions reset to original successfully!')
      } else {
        throw new Error('Failed to reset instructions')
      }
    } catch (err) {
      console.error('Failed to reset instructions:', err)
      setError(`Failed to reset instructions: ${err.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const hasChanges = () => {
    return Object.keys(instructions).some(key => 
      instructions[key] !== originalInstructions[key]
    )
  }

  const categories = [
    { key: '发票', name: 'Invoice', chinese: '发票', icon: '📄' },
    { key: '租赁协议', name: 'Lease', chinese: '租赁协议', icon: '📄' },
    { key: '变更/解除协议', name: 'Amendment', chinese: '变更/解除协议', icon: '📄' },
    { key: '账单', name: 'Bill', chinese: '账单', icon: '📄' },
    { key: '银行回单', name: 'Bank Receipt', chinese: '银行回单', icon: '📄' }
  ]

  if (isLoading) {
    return (
      <div className="instructions-page">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading instructions...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="instructions-page">
      <div className="instructions-container">
        {/* Header */}
        <div className="instructions-header">
          <div className="header-content">
            <h2>📋 Instructions Management</h2>
            <Link to="/legal-doc/files/view-content" className="back-link">
              ← Back to Documents
            </Link>
          </div>
          <div className="config-info">
            <span>Version: {configInfo.version}</span>
            <span>Last Updated: {new Date(configInfo.last_updated).toLocaleString()}</span>
            <span>Categories: {Object.keys(instructions).length}</span>
          </div>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className="message error-message">
            <span className="message-icon">❌</span>
            {error}
          </div>
        )}
        
        {success && (
          <div className="message success-message">
            <span className="message-icon">✅</span>
            {success}
          </div>
        )}

        {/* Instructions Editor */}
        <div className="instructions-editor">
          {categories.map(category => (
            <div key={category.key} className="instruction-section">
              <div className="section-header">
                <span className="section-icon">{category.icon}</span>
                <h3>{category.name} ({category.chinese})</h3>
              </div>
              <div className="instruction-textarea-container">
                <textarea
                  className="instruction-textarea"
                  value={instructions[category.key]}
                  onChange={(e) => handleInstructionChange(category.key, e.target.value)}
                  placeholder={`Enter instructions for ${category.name}...`}
                  rows={8}
                />
                <div className="character-count">
                  {instructions[category.key].length} characters
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="action-buttons">
          <button 
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="submit-btn"
          >
            {isSubmitting ? '🔄 Hot-Swapping...' : '🔄 Hot-Swap'}
          </button>
          <button 
            onClick={handleReset}
            disabled={isSubmitting}
            className="reset-btn"
          >
            ↩️ Discard
          </button>
          <button 
            onClick={handleResetToOriginal}
            disabled={isSubmitting}
            className="reset-original-btn"
          >
            🔄 Reset
          </button>
        </div>

        {/* Footer */}
        <div className="instructions-footer">
          <div className="status-info">
            <span className="status-indicator">✅ Connected</span>
            <span>Last Sync: {new Date().toLocaleString()}</span>
            <span>Backend: {getBackendInfo().host}:{getBackendInfo().port}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default InstructionsPage
