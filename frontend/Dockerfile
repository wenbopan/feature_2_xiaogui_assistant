# Frontend Dockerfile for Hello Siling Classify and Extract
# Multi-stage build: Build stage
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev dependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Accept build arguments for environment variables
ARG VITE_BACKEND_HOST=localhost
ARG VITE_BACKEND_PORT=8001
ARG VITE_BACKEND_PROTOCOL=http

# Set environment variables for build
ENV VITE_BACKEND_HOST=$VITE_BACKEND_HOST
ENV VITE_BACKEND_PORT=$VITE_BACKEND_PORT
ENV VITE_BACKEND_PROTOCOL=$VITE_BACKEND_PROTOCOL

# Build the application
RUN npm run build

# Production stage: Serve with nginx
FROM nginx:alpine

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
