import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { API_ENDPOINTS } from '../config/api'
import './LoginPage.css'

const LoginPage = ({ onLogin }) => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

  // 获取重定向路径，默认为首页
  const redirectPath = location.state?.from?.pathname || '/'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)

      const response = await fetch(API_ENDPOINTS.LOGIN, {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const data = await response.json()
        // 保存token到localStorage
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('token_type', data.token_type)
        
        // 调用父组件的登录回调
        if (onLogin) {
          onLogin(data)
        }
        
        // 重定向到原来要访问的页面
        navigate(redirectPath, { replace: true })
      } else {
        const errorData = await response.json()
        setError(errorData.detail || '登录失败')
      }
    } catch (err) {
      setError('网络错误，请稍后重试')
      console.error('Login error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <div className="login-form-wrapper">
        <div className="login-header">
          <h1>小桂助手</h1>
          <p>请登录以继续使用</p>
        </div>
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={loading}
              placeholder="请输入用户名"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              placeholder="请输入密码"
            />
          </div>
          
          {error && <div className="error-message">{error}</div>}
          
          <button 
            type="submit" 
            className="login-button"
            disabled={loading}
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
        
        <div className="login-footer">
          <p>默认账号: admin</p>
          <p>默认密码: secret</p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
