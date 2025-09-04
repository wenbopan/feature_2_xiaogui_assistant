import { Link } from 'react-router-dom'
import './HomePage.css'

function HomePage() {
  return (
    <div className="home-page">
      <div className="home-container">
        <header className="home-header">
          <h1>Hello Siling 文档处理系统</h1>
          <p>智能文档分类与字段提取平台</p>
        </header>

        <div className="features-grid">
          <div className="feature-card">
            <h3>📄 文档查看器</h3>
            <p>查看已处理的文档和提取结果</p>
            <Link to="/legal-doc/files/view-content" className="feature-link">
              进入文档查看器
            </Link>
          </div>

          <div className="feature-card">
            <h3>📤 文件上传</h3>
            <p>批量上传文档进行处理</p>
            <Link to="/legal-doc/upload" className="feature-link">
              上传文件
            </Link>
          </div>

          <div className="feature-card">
            <h3>⚙️ 处理状态</h3>
            <p>查看文档处理进度和状态</p>
            <Link to="/legal-doc/processing" className="feature-link">
              查看处理状态
            </Link>
          </div>

          <div className="feature-card">
            <h3>📊 仪表板</h3>
            <p>查看任务详情和统计信息</p>
            <Link to="/legal-doc/dashboard" className="feature-link">
              打开仪表板
            </Link>
          </div>

          <div className="feature-card">
            <h3>📝 指令管理</h3>
            <p>管理分类和提取指令</p>
            <Link to="/legal-doc/instructions" className="feature-link">
              管理指令
            </Link>
          </div>

          <div className="feature-card highlight">
            <h3>🧪 单文件 E2E 测试</h3>
            <p>测试文档分类和字段提取的完整流程</p>
            <Link to="/legal-doc/single-file-e2e-test" className="feature-link">
              开始测试
            </Link>
          </div>
        </div>

        <div className="api-section">
          <h2>API 接口</h2>
          <div className="api-grid">
            <div className="api-card">
              <h4>文档分类 API</h4>
              <code>POST /api/v1/files/classify</code>
              <p>对上传的文档进行智能分类</p>
            </div>
            <div className="api-card">
              <h4>字段提取 API</h4>
              <code>POST /api/v1/files/extract-fields</code>
              <p>从文档中提取特定字段信息</p>
            </div>
            <div className="api-card">
              <h4>健康检查 API</h4>
              <code>GET /health</code>
              <p>检查服务运行状态</p>
            </div>
            <div className="api-card">
              <h4>回调结果 API</h4>
              <code>GET /api/v1/callbacks/results/{fileId}</code>
              <p>获取异步处理结果</p>
            </div>
          </div>
        </div>

        <div className="status-section">
          <h2>系统状态</h2>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-indicator online"></span>
              <span>前端服务: 运行中</span>
            </div>
            <div className="status-item">
              <span className="status-indicator online"></span>
              <span>后端服务: 运行中</span>
            </div>
            <div className="status-item">
              <span className="status-indicator online"></span>
              <span>数据库: 连接正常</span>
            </div>
            <div className="status-item">
              <span className="status-indicator online"></span>
              <span>对象存储: 连接正常</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default HomePage
