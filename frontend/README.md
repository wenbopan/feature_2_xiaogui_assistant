# Legal Docs MVP Frontend

React + Vite frontend for the Legal Docs MVP application.

## Quick Start

### Prerequisites
- Node.js (v16 or higher)
- npm
- Backend server running on port 8001

### Development

1. **Start the frontend development server:**
   ```bash
   ./startup.sh --dev
   ```

2. **Start in production mode:**
   ```bash
   ./startup.sh --prod
   ```

### Manual Setup

If you prefer to run commands manually:

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Create environment file:**
   ```bash
   cp env.template .env
   # Edit .env if needed
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

## Configuration

The frontend uses environment variables for configuration. Copy `env.template` to `.env` and modify as needed:

- `VITE_BACKEND_HOST` - Backend host (default: localhost)
- `VITE_BACKEND_PORT` - Backend port (default: 8001)
- `VITE_BACKEND_PROTOCOL` - Backend protocol (default: http)

## Service URLs

- **Frontend:** http://localhost:5173
- **Backend:** http://localhost:8001
- **API Docs:** http://localhost:8001/docs

## Development Features

- Hot reload for instant updates
- Backend connection checking
- Environment configuration validation
- Production build support