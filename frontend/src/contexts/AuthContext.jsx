import React, { createContext, useContext, useState, useEffect } from 'react'
import { API_ENDPOINTS } from '../config/api'

const AuthContext = createContext()

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // 检查本地存储的token
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token')
      const tokenType = localStorage.getItem('token_type')
      
      if (token && tokenType) {
        try {
          // 验证token是否有效
          const response = await fetch(API_ENDPOINTS.ME, {
            headers: {
              'Authorization': `${tokenType} ${token}`
            }
          })
          
          if (response.ok) {
            const userData = await response.json()
            setUser(userData)
            setIsAuthenticated(true)
          } else {
            // Token无效，清除本地存储
            localStorage.removeItem('access_token')
            localStorage.removeItem('token_type')
          }
        } catch (error) {
          console.error('Auth check failed:', error)
          localStorage.removeItem('access_token')
          localStorage.removeItem('token_type')
        }
      }
      
      setLoading(false)
    }

    checkAuth()
  }, [])

  const login = (tokenData) => {
    localStorage.setItem('access_token', tokenData.access_token)
    localStorage.setItem('token_type', tokenData.token_type)
    setIsAuthenticated(true)
    // 可以在这里获取用户信息
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('token_type')
    setUser(null)
    setIsAuthenticated(false)
  }

  const getAuthHeaders = () => {
    const token = localStorage.getItem('access_token')
    const tokenType = localStorage.getItem('token_type')
    
    if (token && tokenType) {
      return {
        'Authorization': `${tokenType} ${token}`
      }
    }
    return {}
  }

  const value = {
    isAuthenticated,
    user,
    loading,
    login,
    logout,
    getAuthHeaders
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthContext
