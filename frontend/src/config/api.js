// API Configuration
const API_CONFIG = {
  // Default backend port for local development
  BACKEND_PORT: import.meta.env.VITE_BACKEND_PORT || '8000',
  // Backend host
  BACKEND_HOST: import.meta.env.VITE_BACKEND_HOST || 'localhost',
  // Protocol
  PROTOCOL: import.meta.env.VITE_BACKEND_PROTOCOL || 'http',
}

// Build the base URL
const BASE_URL = `${API_CONFIG.PROTOCOL}://${API_CONFIG.BACKEND_HOST}:${API_CONFIG.BACKEND_PORT}`

// API endpoints
export const API_ENDPOINTS = {
  // Health check
  HEALTH: `${BASE_URL}/health`,
  
  // File operations
  CLASSIFY: `${BASE_URL}/api/v1/files/classify`,
  EXTRACT_FIELDS: `${BASE_URL}/api/v1/files/extract-fields`,
  VIEW_CONTENT: `${BASE_URL}/api/v1/files/view-content`,
  
  // Task operations
  TASK_DETAILS: (taskId) => `${BASE_URL}/api/v1/tasks/${taskId}`,
  TASK_UPLOAD: `${BASE_URL}/api/v1/tasks/upload`,
  TASK_EXTRACT_FIELDS: (taskId) => `${BASE_URL}/api/v1/tasks/${taskId}/extract-fields`,
  TASK_EXTRACTION_PROGRESS: (taskId) => `${BASE_URL}/api/v1/tasks/${taskId}/extraction-progress`,
  TASK_CLASSIFICATION: (taskId) => `${BASE_URL}/api/v1/${taskId}/file-classification`,
  TASK_CLASSIFICATION_PROGRESS: (taskId) => `${BASE_URL}/api/v1/${taskId}/file-classification-progress`,
  
  // Callback endpoints
  CALLBACK_RESULTS: (fileId) => `${BASE_URL}/api/v1/callbacks/results/${fileId}`,
  CALLBACK_CLASSIFY: `${BASE_URL}/api/v1/callbacks/classify-file`,
  CALLBACK_EXTRACT: `${BASE_URL}/api/v1/callbacks/extract-file`,
  
  // Instructions management
  INSTRUCTIONS: `${BASE_URL}/api/v1/config/instructions`,
  INSTRUCTIONS_HOT_SWAP: `${BASE_URL}/api/v1/config/instructions/hot-swap`,
  INSTRUCTIONS_RESET: `${BASE_URL}/api/v1/config/instructions/reset`,
  INSTRUCTIONS_CATEGORY: (category) => `${BASE_URL}/api/v1/config/instructions/category/${category}`,
}

// Export configuration for debugging
export const CONFIG = {
  ...API_CONFIG,
  BASE_URL,
}

// Helper function to get backend status info
export const getBackendInfo = () => ({
  host: API_CONFIG.BACKEND_HOST,
  port: API_CONFIG.BACKEND_PORT,
  protocol: API_CONFIG.PROTOCOL,
  fullUrl: BASE_URL,
})
