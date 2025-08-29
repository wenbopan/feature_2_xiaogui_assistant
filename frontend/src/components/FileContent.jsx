import { useState, useRef, useEffect } from 'react'
import './FileContent.css'

function FileContent({ fileData }) {
  const { file_download_url, content_type, original_filename, final_filename, file_size } = fileData
  
  // Zoom and pan state
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const imageRef = useRef(null)
  const containerRef = useRef(null)

  // Zoom functions
  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev * 1.25, 5)) // Max 5x zoom
  }

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev / 1.25, 0.25)) // Min 0.25x zoom
  }

  const handleZoomReset = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  const handleWheel = (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      const delta = e.deltaY > 0 ? 0.9 : 1.1
      setZoom(prev => Math.max(0.25, Math.min(5, prev * delta)))
    }
  }

  // Pan functions
  const handleMouseDown = (e) => {
    if (zoom > 1) {
      setIsDragging(true)
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
    }
  }

  const handleMouseMove = (e) => {
    if (isDragging && zoom > 1) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  // Reset zoom when content type changes
  useEffect(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [content_type])

  const renderContent = () => {
    // Debug info
    console.log('FileContent renderContent:', {
      file_download_url,
      content_type,
      original_filename,
      final_filename,
      file_size
    });

    if (!file_download_url) {
      return (
        <div className="no-content">
          <p>No file content available</p>
          <p>File: {original_filename}</p>
          <p>Size: {(file_size / 1024 / 1024).toFixed(2)} MB</p>
          <p>Content Type: {content_type}</p>
        </div>
      )
    }

    // Handle images
    if (content_type && (content_type.includes('image') || content_type.match(/\.(jpg|jpeg|png|gif|bmp|webp)$/i))) {
      return (
        <div className="image-container">
          {/* Zoom controls */}
          <div className="zoom-controls">
            <button onClick={handleZoomOut} className="zoom-btn" title="Zoom Out (Ctrl + Scroll Down)">
              <span>−</span>
            </button>
            <span className="zoom-level">{Math.round(zoom * 100)}%</span>
            <button onClick={handleZoomIn} className="zoom-btn" title="Zoom In (Ctrl + Scroll Up)">
              <span>+</span>
            </button>
            <button onClick={handleZoomReset} className="zoom-reset-btn" title="Reset Zoom (Ctrl + 0)">
              <span>⟲</span>
            </button>
          </div>
          
          {/* Image with zoom and pan */}
          <div 
            className="image-wrapper"
            ref={containerRef}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
          >
            <img 
              ref={imageRef}
              src={file_download_url} 
              alt={original_filename}
              className="document-image"
              style={{
                transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
                transformOrigin: 'center center'
              }}
              onError={(e) => {
                console.error('Image failed to load:', e);
                e.target.style.display = 'none';
                e.target.nextSibling.style.display = 'block';
              }}
            />
          </div>
          
          <div className="image-fallback" style={{ display: 'none' }}>
            <p>Image failed to load</p>
            <a href={file_download_url} target="_blank" rel="noopener noreferrer">
              Open Image in New Tab
            </a>
          </div>
        </div>
      )
    }

    // Handle PDFs
    if (content_type && (content_type.includes('pdf') || content_type.includes('PDF'))) {
      return (
        <div className="pdf-container">
          <div className="pdf-viewer-container">
            {/* Simple iframe for PDF viewing - should work now with inline URLs */}
            <iframe
              src={file_download_url}
              title={original_filename}
              className="pdf-viewer"
              style={{ border: 'none', minHeight: '600px' }}
              onLoad={() => console.log('PDF iframe loaded successfully')}
              onError={(e) => console.error('PDF iframe failed to load:', e)}
            />
          </div>
          
          <div className="pdf-controls">
            <a 
              href={file_download_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="pdf-download-btn"
            >
              Open in New Tab
            </a>
          </div>
        </div>
      )
    }

    // Handle other file types
    return (
      <div className="other-file">
        <h3>File Information</h3>
        <p><strong>Original Name:</strong> {original_filename}</p>
        <p><strong>Final Name:</strong> {final_filename || 'N/A'}</p>
        <p><strong>Type:</strong> {content_type}</p>
        <p><strong>Size:</strong> {(file_size / 1024 / 1024).toFixed(2)} MB</p>
        <p><strong>Download:</strong> <a href={file_download_url} target="_blank" rel="noopener noreferrer">Open File</a></p>
        <div className="debug-info">
          <p><strong>Debug:</strong> Content type "{content_type}" not recognized for preview</p>
          <p>Use the download link above to view the file</p>
        </div>
      </div>
    )
  }

  const isPdf = content_type && (content_type.includes('pdf') || content_type.includes('PDF'));
  
  return (
    <div className={`file-content ${isPdf ? 'pdf-content' : ''}`}>
      <div className="file-header">
        <h3>Document Content</h3>
        <div className="file-info">
          <span className="filename">{final_filename || original_filename}</span>
          <span className="file-type">{content_type}</span>
        </div>
      </div>
      
      <div className={`content-display ${isPdf ? 'pdf-content' : ''}`}>
        {renderContent()}
      </div>
    </div>
  )
}

export default FileContent
