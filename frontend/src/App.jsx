import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import './App.css'
import HomePage from './components/HomePage'
import DocumentViewer from './components/DocumentViewer'
import UploadPage from './components/UploadPage'
import ProcessingPage from './components/ProcessingPage'
import Dashboard from './components/Dashboard'
import InstructionsPage from './components/InstructionsPage'
import SingleFileE2ETest from './components/SingleFileE2ETest'

function App() {
  return (
    <div className="App">
      <Router>
        <Routes>
          {/* Home page */}
          <Route path="/" element={<HomePage />} />
          
          {/* Main document viewer route */}
          <Route path="/legal-doc/files/view-content" element={<DocumentViewer />} />
          
          {/* Upload route */}
          <Route path="/legal-doc/upload" element={<UploadPage />} />
          
          {/* Processing route */}
          <Route path="/legal-doc/processing" element={<ProcessingPage />} />
          
          {/* Dashboard route with task ID parameter */}
          <Route path="/legal-doc/dashboard/:taskId" element={<Dashboard />} />
          
          {/* Instructions management route */}
          <Route path="/legal-doc/instructions" element={<InstructionsPage />} />
          
          {/* Single file E2E test route */}
          <Route path="/legal-doc/single-file-e2e-test" element={<SingleFileE2ETest />} />
          
          {/* Future routes for expansion */}
          <Route path="/legal-doc/tasks" element={<DocumentViewer />} />
          
          {/* Catch all other routes and redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </div>
  )
}

export default App
