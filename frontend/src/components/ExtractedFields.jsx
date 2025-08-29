import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism'
import './ExtractedFields.css'

function ExtractedFields({ fileData }) {
  const { 
    extracted_fields, 
    extraction_status, 
    extraction_error,
    original_filename,
    final_filename 
  } = fileData

  // Smart truncation function for long file paths
  const truncatePath = (path, maxLength = 50) => {
    if (!path || path.length <= maxLength) return path;
    
    // For very long paths, show start + ... + end
    if (path.length > maxLength * 1.5) {
      const startLength = Math.floor(maxLength * 0.4);
      const endLength = Math.floor(maxLength * 0.3);
      return `${path.substring(0, startLength)}...${path.substring(path.length - endLength)}`;
    }
    
    // For moderately long paths, just truncate with ellipsis
    return `${path.substring(0, maxLength)}...`;
  }

  const renderStatus = () => {
    switch (extraction_status) {
      case 'completed':
        return <span className="status completed">✅ Completed</span>
      case 'pending':
        return <span className="status pending">⏳ Pending</span>
      case 'failed':
        return <span className="status failed">❌ Failed</span>
      default:
        return <span className="status unknown">❓ Unknown</span>
    }
  }

  const renderFields = () => {
    if (!extracted_fields || Object.keys(extracted_fields).length === 0) {
      return (
        <div className="no-fields">
          <p>No extracted fields available</p>
          {extraction_status === 'pending' && (
            <p className="pending-message">Field extraction is still in progress...</p>
          )}
        </div>
      )
    }

    return (
      <div className="fields-display">
        <SyntaxHighlighter
          language="json"
          style={tomorrow}
          customStyle={{
            margin: 0,
            borderRadius: '8px',
            fontSize: '14px',
            maxHeight: 'none'
          }}
        >
          {JSON.stringify(extracted_fields, null, 2)}
        </SyntaxHighlighter>
      </div>
    )
  }

  return (
    <div className="extracted-fields">
      <div className="fields-header">
        <h3>Extracted Fields</h3>
        <div className="status-info">
          {renderStatus()}
        </div>
      </div>
      
      {extraction_error && (
        <div className="error-display">
          <h4>Extraction Error:</h4>
          <p className="error-message">{extraction_error}</p>
        </div>
      )}
      
      <div className="fields-content">
        {renderFields()}
      </div>
      
      <div className="file-metadata">
        <h4>File Details</h4>
        <div className="file-path-item">
          <strong>Original:</strong> 
          <span className="file-path" title={original_filename}>
            {truncatePath(original_filename)}
          </span>
        </div>
        <div className="file-path-item">
          <strong>Final:</strong> 
          <span className="file-path" title={final_filename || 'N/A'}>
            {truncatePath(final_filename) || 'N/A'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default ExtractedFields
