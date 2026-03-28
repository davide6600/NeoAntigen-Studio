# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY services/frontend/package*.json ./
RUN npm ci
COPY services/frontend/ ./
RUN npm run build

# Production stage
FROM nginx:alpine
# Copy built assets to NGINX
COPY --from=builder /app/dist /usr/share/nginx/html

# Add a basic NGINX server configuration to support React Router (SPA routing)
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://api:8000/; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
    location /metrics { \
        proxy_pass http://api:8000/metrics; \
        proxy_set_header Host $host; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
