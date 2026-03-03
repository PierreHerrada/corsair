# =============================================================================
# Corsair — Multi-stage Docker Build
# =============================================================================
# Stage 1: Build React frontend
# Stage 2: Install Python dependencies
# Stage 3: Final image with nginx + supervisord + uvicorn
# =============================================================================

# --- Stage 1: Frontend Build ---
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python Dependencies ---
FROM python:3.12-slim AS python-deps
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 3: Final Image ---
FROM python:3.12-slim

# Install nginx, supervisord, and Node.js (for Claude Code CLI)
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor curl git && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user for running Claude CLI
# (--dangerously-skip-permissions rejects root execution)
RUN useradd -m -s /bin/bash corsair

# Copy Python dependencies
COPY --from=python-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html

# Copy infrastructure configs
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY infra/supervisord.conf /etc/supervisor/conf.d/corsair.conf

# Copy entrypoint script
COPY infra/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Remove default nginx config
RUN rm -f /etc/nginx/sites-enabled/default

# Create workspaces directory and give corsair user access
RUN mkdir -p /home/corsair/workspaces && \
    chown -R corsair:corsair /app/backend /home/corsair

EXPOSE 80 8000

ENTRYPOINT ["/app/entrypoint.sh"]
