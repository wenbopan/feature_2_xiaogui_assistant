import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { API_ENDPOINTS, getBackendInfo } from '../config/api'
import './UploadPage.css'

function UploadPage() {
  const [formData, setFormData] = useState({
    organize_date: '',
    project_name: ''
  })
  
  const fileInputRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)



  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value ?? ''
    }))
  }

  const handleFileSelect = (e) => {
    console.log('File input change event fired!')
    console.log('Event target:', e.target)
    console.log('Files:', e.target.files)
    
    const file = e.target.files[0]
    if (file) {
      console.log('Selected file:', file.name, file.size, file.type)
      setSelectedFile(file)
    } else {
      console.log('No file selected')
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
    }
  }

  const handleUpload = () => {
    if (!selectedFile || !formData.project_name || !formData.organize_date) {
      console.error('Missing required fields')
      return
    }

    console.log('Starting upload, setting states...')
    setIsUploading(true)
    setUploadProgress(0)
    console.log('States set - isUploading:', true, 'progress:', 0)

    // Create FormData for file upload
    const uploadData = new FormData()
    uploadData.append('organize_date', formData.organize_date)
    uploadData.append('project_name', formData.project_name)
    uploadData.append('files', selectedFile)

    // Use XMLHttpRequest for progress tracking
    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (event) => {
      console.log('Progress event:', event.loaded, '/', event.total)
      if (event.lengthComputable) {
        const progress = Math.round((event.loaded / event.total) * 100)
        console.log('Setting progress to:', progress)
        setUploadProgress(progress)
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const result = JSON.parse(xhr.responseText)
          console.log('Upload successful:', result)
          
          // Clear form after successful upload
          handleClear()
          
          // Show success message to user
          alert(`Upload successful! Task ID: ${result.task_id}`)
        } catch (error) {
          console.error('Failed to parse response:', error)
          alert('Upload successful but response parsing failed')
        }
      } else {
        console.error('Upload failed:', xhr.status, xhr.statusText)
        alert(`Upload failed: ${xhr.status} ${xhr.statusText}`)
      }
      setIsUploading(false)
      setUploadProgress(0)
    })

    xhr.addEventListener('error', () => {
      console.error('Upload error:', xhr.statusText)
      alert(`Upload error: ${xhr.statusText}`)
      setIsUploading(false)
      setUploadProgress(0)
    })

    xhr.addEventListener('abort', () => {
      console.log('Upload aborted')
      setIsUploading(false)
      setUploadProgress(0)
    })

    // Start the upload
    xhr.open('POST', API_ENDPOINTS.TASK_UPLOAD)
    xhr.send(uploadData)
  }

  const handleClear = () => {
    setFormData({
      organize_date: '',
      project_name: ''
    })
    setSelectedFile(null)
    setIsDragOver(false)
    
    // Reset the file input element to allow re-uploading
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="upload-page">
      <div className="upload-form">
        <div className="form-header">
          <div className="header-content">
            <h3>Legal Document Upload</h3>
            <Link to="/legal-doc/files/view-content" className="back-link">
              ← Back to Documents
            </Link>
          </div>
        </div>
        
        <div className="form-fields">
          <div className="input-group">
            <label htmlFor="organize_date">Organize Date</label>
            <input
              type="date"
              id="organize_date"
              name="organize_date"
              value={formData.organize_date ?? ''}
              onChange={handleInputChange}
              required
              min="1900-01-01"
              max="2100-12-31"

            />
          </div>
          
          <div className="input-group">
            <label htmlFor="project_name">Project Name</label>
            <input
              type="text"
              id="project_name"
              name="project_name"
              value={formData.project_name ?? ''}
              onChange={handleInputChange}
              placeholder="Enter project name"
              required

            />
          </div>
        </div>
        
        <div className="file-upload-area">
          <div 
            className={`drag-drop-zone ${isDragOver ? 'drag-over' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="upload-icon">📁</div>
            <p className="upload-text">
              {selectedFile ? selectedFile.name : 'Click to browse files or drag files here'}
            </p>
            <p className="upload-hint">
              {selectedFile ? `Selected: ${selectedFile.name} (${(selectedFile.size / 1024 / 1024).toFixed(2)} MB)` : 'Supports ZIP files containing documents'}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              id="fileInput"
              accept=".zip"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            <label 
              htmlFor="fileInput" 
              className="browse-btn"
              onClick={() => console.log('Browse button clicked')}
            >
              Browse Files
            </label>
          </div>
          
          {/* Upload Buttons - Moved here for visibility */}
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button 
              onClick={handleClear} 
              style={{ 
                padding: '12px 24px', 
                borderRadius: '8px', 
                border: 'none', 
                background: '#ff6b6b', 
                color: 'white', 
                fontWeight: 'bold', 
                cursor: 'pointer',
                fontSize: '16px'
              }}
            >
              Reset Form
            </button>
            <button 
              onClick={handleUpload} 
              disabled={!selectedFile || !formData.project_name || !formData.organize_date}
              style={{ 
                padding: '12px 24px', 
                borderRadius: '8px', 
                border: 'none', 
                background: (!selectedFile || !formData.project_name || !formData.organize_date) ? '#cccccc' : '#4ade80', 
                color: 'white', 
                fontWeight: 'bold', 
                cursor: (!selectedFile || !formData.project_name || !formData.organize_date) ? 'not-allowed' : 'pointer',
                fontSize: '16px'
              }}
            >
              Upload
            </button>
          </div>
        </div>
        
        {/* Progress Bar */}
        {isUploading && (
          <div className="upload-progress">
            <div className="progress-header">
              <span>Uploading {selectedFile?.name}...</span>
              <span className="progress-percentage">{uploadProgress}%</span>
            </div>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
          </div>
        )}
        
        {/* Debug Info */}
        <div style={{ padding: '10px', fontSize: '12px', color: '#666' }}>
          Debug: isUploading={isUploading.toString()}, progress={uploadProgress}%, selectedFile={selectedFile ? selectedFile.name : 'null'}
        </div>
        
        {/* Upload Controls */}
        <div className="upload-controls" style={{ display: 'flex', padding: '24px', gap: '16px', justifyContent: 'flex-end', background: '#f5f5f5', borderTop: '2px solid #e0e0e0' }}>
          <button onClick={handleClear} className="clear-btn" style={{ padding: '12px 24px', borderRadius: '8px', border: 'none', background: 'linear-gradient(135deg, #ff6b6b 0%, #ffd93d 100%)', color: 'white', fontWeight: '600', cursor: 'pointer' }}>
            Reset Form
          </button>
          <button 
            onClick={handleUpload} 
            className="upload-btn"
            style={{ padding: '12px 24px', borderRadius: '8px', border: 'none', background: isUploading || !selectedFile || !(formData.project_name ?? '').trim() || !(formData.organize_date ?? '').trim() ? '#999' : 'linear-gradient(135deg, #4ade80 0%, #3b82f6 100%)', color: 'white', fontWeight: '600', cursor: isUploading || !selectedFile || !(formData.project_name ?? '').trim() || !(formData.organize_date ?? '').trim() ? 'not-allowed' : 'pointer' }}
            disabled={isUploading || !selectedFile || !(formData.project_name ?? '').trim() || !(formData.organize_date ?? '').trim()}
          >
            {isUploading ? `Uploading... ${uploadProgress}%` : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default UploadPage
