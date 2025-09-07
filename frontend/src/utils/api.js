// API utility functions with authentication support

/**
 * Get authentication headers from localStorage
 */
export const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token')
  const tokenType = localStorage.getItem('token_type')
  
  if (token && tokenType) {
    return {
      'Authorization': `${tokenType} ${token}`
    }
  }
  return {}
}

/**
 * Make authenticated fetch request
 */
export const authenticatedFetch = async (url, options = {}) => {
  const authHeaders = getAuthHeaders()
  
  const config = {
    ...options,
    headers: {
      ...authHeaders,
      ...options.headers
    }
  }
  
  const response = await fetch(url, config)
  
  // If unauthorized, redirect to login
  if (response.status === 401) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('token_type')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  
  return response
}

/**
 * Make authenticated POST request with JSON body
 */
export const authenticatedPost = async (url, data, options = {}) => {
  return authenticatedFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    body: JSON.stringify(data),
    ...options
  })
}

/**
 * Make authenticated POST request with FormData
 */
export const authenticatedPostForm = async (url, formData, options = {}) => {
  return authenticatedFetch(url, {
    method: 'POST',
    body: formData,
    ...options
  })
}

/**
 * Make authenticated GET request
 */
export const authenticatedGet = async (url, options = {}) => {
  return authenticatedFetch(url, {
    method: 'GET',
    ...options
  })
}

/**
 * Check if user is authenticated
 */
export const isAuthenticated = () => {
  const token = localStorage.getItem('access_token')
  const tokenType = localStorage.getItem('token_type')
  return !!(token && tokenType)
}

/**
 * Logout user by clearing tokens
 */
export const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('token_type')
  window.location.href = '/login'
}
