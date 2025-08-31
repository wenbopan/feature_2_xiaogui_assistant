import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import './ProcessingPage.css'

function ProcessingPage() {
  const [taskId, setTaskId] = useState('')
  const [processingOptions, setProcessingOptions] = useState({
    extractFields: false,
    rename: false
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleTaskIdChange = (e) => {
    const value = e.target.value
    // Only allow numbers
    if (value === '' || /^\d+$/.test(value)) {
      setTaskId(value)
    }
  }

  const handleOptionChange = (option) => {
    setProcessingOptions(prev => ({
      ...prev,
      [option]: !prev[option]
    }))
  }

  const handleSubmit = async () => {
    if (!taskId.trim()) {
      alert('Please enter a Task ID')
      return
    }

    if (!processingOptions.extractFields && !processingOptions.rename) {
      alert('Please select at least one processing option')
      return
    }

    setIsSubmitting(true)

    try {
      const taskIdNum = parseInt(taskId)
      const results = []

      // Start field extraction if selected
      if (processingOptions.extractFields) {
        try {
          const extractResponse = await fetch(`http://localhost:8000/api/v1/tasks/${taskIdNum}/extract-fields`, {
            method: 'POST'
          })
          
          if (extractResponse.ok) {
            const extractResult = await extractResponse.json()
            results.push(`✅ Field extraction started: ${extractResult.total_jobs} jobs created`)
          } else {
            const error = await extractResponse.text()
            results.push(`❌ Field extraction failed: ${error}`)
          }
        } catch (error) {
          results.push(`❌ Field extraction error: ${error.message}`)
        }
      }

      // Start content processing (classification + renaming) if selected
      if (processingOptions.rename) {
        try {
          const processResponse = await fetch(`http://localhost:8000/api/v1/${taskIdNum}/file-classification`, {
            method: 'POST'
          })
          
          if (processResponse.ok) {
            const processResult = await processResponse.json()
            results.push(`✅ Content processing started: ${processResult.total_jobs || 0} jobs created`)
          } else {
            const error = await processResponse.text()
            results.push(`❌ Content processing failed: ${error}`)
          }
        } catch (error) {
          results.push(`❌ Content processing error: ${error.message}`)
        }
      }

      // Show results and redirect
      if (results.length > 0) {
        alert(results.join('\n\n'))
      }
      
      // Redirect to dashboard with task ID
      navigate(`/legal-doc/dashboard/${taskId}`)
    } catch (error) {
      console.error('Failed to start processing:', error)
      alert('Failed to start processing. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const isSubmitDisabled = !taskId.trim() || 
    (!processingOptions.extractFields && !processingOptions.rename) ||
    isSubmitting

  return (
    <div className="processing-page">
      <div className="processing-form">
        <div className="form-header">
          <div className="header-content">
            <h3>📋 File Processing</h3>
            <Link to="/legal-doc/files/view-content" className="back-link">
              ← Back to Documents
            </Link>
          </div>
        </div>
        
        <div className="task-input-section">
          <div className="input-group">
            <label htmlFor="taskId">Task ID</label>
            <input
              type="text"
              id="taskId"
              value={taskId}
              onChange={handleTaskIdChange}
              placeholder="Enter task ID (e.g., 1, 2, 3...)"
              required
            />
            <p className="helper-text">
              (Enter a valid task ID to process files)
            </p>
          </div>
        </div>
        
        <div className="processing-options-section">
          <h4>Select Processing Types:</h4>
          
          <div className="option-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={processingOptions.extractFields}
                onChange={() => handleOptionChange('extractFields')}
              />
              <span className="checkmark"></span>
              <div className="option-content">
                <span className="option-title">Extract Fields</span>
                <span className="option-description">
                  Process files for field extraction
                </span>
              </div>
            </label>
          </div>
          
          <div className="option-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={processingOptions.rename}
                onChange={() => handleOptionChange('rename')}
              />
              <span className="checkmark"></span>
              <div className="option-content">
                <span className="option-title">Rename</span>
                <span className="option-description">
                  Process files for renaming/classification
                </span>
              </div>
            </label>
          </div>
          
          <button
            onClick={handleSubmit}
            disabled={isSubmitDisabled}
            className="submit-btn"
          >
            {isSubmitting ? 'Starting Processing...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ProcessingPage
