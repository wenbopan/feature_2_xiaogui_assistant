import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import './App.css'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './components/LoginPage'
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
      <AuthProvider>
        <Router>
          <Routes>
            {/* Login page - accessible without authentication */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* Protected routes */}
            <Route path="/" element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/files/view-content" element={
              <ProtectedRoute>
                <DocumentViewer />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/upload" element={
              <ProtectedRoute>
                <UploadPage />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/processing" element={
              <ProtectedRoute>
                <ProcessingPage />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/dashboard/:taskId" element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/instructions" element={
              <ProtectedRoute>
                <InstructionsPage />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/single-file-e2e-test" element={
              <ProtectedRoute>
                <SingleFileE2ETest />
              </ProtectedRoute>
            } />
            
            <Route path="/legal-doc/tasks" element={
              <ProtectedRoute>
                <DocumentViewer />
              </ProtectedRoute>
            } />
            
            {/* Catch all other routes and redirect to home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Router>
      </AuthProvider>
    </div>
  )
}

export default App
