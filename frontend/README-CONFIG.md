# Frontend Configuration

## Backend URL Configuration

The frontend can be configured to connect to different backend instances using environment variables.

### Environment Variables

Create a `.env.local` file in the frontend directory with the following variables:

```bash
# For local development (default)
VITE_BACKEND_HOST=localhost
VITE_BACKEND_PORT=8001
VITE_BACKEND_PROTOCOL=http

# For server testing
VITE_BACKEND_HOST=47.98.154.221
VITE_BACKEND_PORT=8001
VITE_BACKEND_PROTOCOL=http
```

### Configuration Options

- `VITE_BACKEND_HOST`: Backend server hostname or IP address (default: localhost)
- `VITE_BACKEND_PORT`: Backend server port (default: 8000)
- `VITE_BACKEND_PROTOCOL`: Protocol to use (default: http)

### Usage Examples

#### Local Development
```bash
# .env.local
VITE_BACKEND_HOST=localhost
VITE_BACKEND_PORT=8000
VITE_BACKEND_PROTOCOL=http
```

#### Server Testing
```bash
# .env.local
VITE_BACKEND_HOST=47.98.154.221
VITE_BACKEND_PORT=8001
VITE_BACKEND_PROTOCOL=http
```

#### Production
```bash
# .env.local
VITE_BACKEND_HOST=your-production-domain.com
VITE_BACKEND_PORT=443
VITE_BACKEND_PROTOCOL=https
```

### How It Works

The configuration is managed in `src/config/api.js` and automatically builds the correct API endpoints based on the environment variables. All components use the centralized configuration instead of hardcoded URLs.

### Switching Between Environments

1. Update the `.env.local` file with the desired backend configuration
2. Restart the development server: `npm run dev`
3. The frontend will automatically connect to the new backend URL

### Default Behavior

If no environment variables are set, the frontend defaults to:
- Host: localhost
- Port: 8000
- Protocol: http
