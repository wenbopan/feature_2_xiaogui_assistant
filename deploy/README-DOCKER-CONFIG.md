# Docker Configuration Guide

## Environment Configuration

The Docker setup uses environment variables to configure the frontend to connect to the correct backend URL.

### Configuration Files

1. **`docker.env`** - Contains all environment variables for Docker Compose
2. **`docker-compose.aliyun.yml`** - Docker Compose configuration that uses the environment file

### Frontend Backend Configuration

The frontend automatically connects to the backend using these environment variables:

```bash
# Frontend Configuration (in docker.env)
VITE_BACKEND_HOST=backend          # Backend service name in Docker network
VITE_BACKEND_PORT=8001             # Backend port inside Docker
VITE_BACKEND_PROTOCOL=http         # Protocol (http/https)
```

### How It Works

1. **Build Time**: Environment variables are passed as build arguments to the frontend Docker build
2. **Runtime**: The frontend is built with the correct backend URL baked in
3. **Docker Network**: Frontend connects to backend using the service name `backend:8001`

### Environment Examples

#### Local Development (Docker)
```bash
# docker.env
VITE_BACKEND_HOST=backend
VITE_BACKEND_PORT=8001
VITE_BACKEND_PROTOCOL=http
```

**Note**: The Dockerfile defaults are set for Docker environment (port 8001), while local development uses port 8000.

#### Production (External Backend)
```bash
# docker.env
VITE_BACKEND_HOST=your-backend-domain.com
VITE_BACKEND_PORT=443
VITE_BACKEND_PROTOCOL=https
```

#### Custom Backend Port
```bash
# docker.env
VITE_BACKEND_HOST=backend
VITE_BACKEND_PORT=8002
VITE_BACKEND_PROTOCOL=http
```

### Usage

1. **Update Configuration**: Edit `docker.env` with your desired backend settings
2. **Build and Run**: 
   ```bash
   cd deploy
   docker-compose -f docker-compose.aliyun.yml up --build
   ```
3. **Access**: Frontend will be available at `http://localhost:3000`

### Backend Service Discovery

In Docker Compose, services can communicate using:
- **Service Name**: `backend` (defined in docker-compose.yml)
- **Internal Port**: `8001` (backend container port)
- **Full URL**: `http://backend:8001`

The frontend will automatically use this configuration to make API calls to the backend.

### Troubleshooting

If the frontend can't connect to the backend:

1. **Check Environment Variables**: Verify `docker.env` has correct values
2. **Rebuild Frontend**: Run `docker-compose up --build frontend`
3. **Check Backend Health**: Visit `http://localhost:8001/health`
4. **Check Docker Network**: Ensure both services are in the same network

### Development vs Production

- **Development**: Uses `localhost:8000` (no Docker)
- **Docker**: Uses `backend:8001` (Docker network)
- **Production**: Uses external domain (e.g., `api.yourcompany.com:443`)
