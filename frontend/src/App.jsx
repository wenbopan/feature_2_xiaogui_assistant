import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import './App.css'
import DocumentViewer from './components/DocumentViewer'
import UploadPage from './components/UploadPage'
import ProcessingPage from './components/ProcessingPage'
import Dashboard from './components/Dashboard'

function App() {
  return (
    <div className="App">
      <Router>
        <Routes>
          {/* Main document viewer route */}
          <Route path="/legal-doc/files/view-content" element={<DocumentViewer />} />
          
          {/* Upload route */}
          <Route path="/legal-doc/upload" element={<UploadPage />} />
          
          {/* Processing route */}
          <Route path="/legal-doc/processing" element={<ProcessingPage />} />
          
          {/* Dashboard route with task ID parameter */}
          <Route path="/legal-doc/dashboard/:taskId" element={<Dashboard />} />
          
          {/* Future routes for expansion */}
          <Route path="/legal-doc/tasks" element={<DocumentViewer />} />
          
          {/* Redirect root to main route */}
          <Route path="/" element={<Navigate to="/legal-doc/files/view-content" replace />} />
          
          {/* Catch all other routes and redirect to main */}
          <Route path="*" element={<Navigate to="/legal-doc/files/view-content" replace />} />
        </Routes>
      </Router>
    </div>
  )
}

export default App
