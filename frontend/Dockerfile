# Frontend Dockerfile for Hello Siling Classify and Extract
# Multi-stage build: Build stage
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Configure npm to use Chinese mirror for faster installation
RUN npm config set registry https://registry.npmmirror.com/

# Install all dependencies (including dev dependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Accept build arguments for environment variables
ARG VITE_BACKEND_HOST=47.98.154.221
ARG VITE_BACKEND_PORT=8001
ARG VITE_BACKEND_PROTOCOL=http

# Set environment variables for build
ENV VITE_BACKEND_HOST=$VITE_BACKEND_HOST
ENV VITE_BACKEND_PORT=$VITE_BACKEND_PORT
ENV VITE_BACKEND_PROTOCOL=$VITE_BACKEND_PROTOCOL

# Build the application
RUN npm run build

# Production stage: Serve with Vite Preview
FROM node:20-alpine

# Install curl for health checks
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories && apk add --no-cache curl

# Set working directory
WORKDIR /app

# Copy built files from build stage
COPY --from=build /app/dist ./dist
COPY --from=build /app/package*.json ./

# Install only production dependencies
RUN npm ci --only=production

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

# Start Vite preview server
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "3000"]
