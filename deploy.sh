#!/bin/bash
# Deployment script for ads-dashboard
# This runs on the production server

set -e

PROJECT_DIR="/opt/ads-dashboard"
APP_SCRIPT="dashboard.py"
LOG_FILE="/var/log/ads-dashboard/deploy.log"

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Starting deployment..."
log "=========================================="

# Navigate to project directory
cd "$PROJECT_DIR" || { log "ERROR: Cannot cd to $PROJECT_DIR"; exit 1; }

# Check if .env exists
if [ ! -f ".env" ]; then
    log "⚠️  WARNING: .env file not found. Using defaults."
fi

# Pull latest changes from GitHub
log "📥 Pulling latest code from GitHub..."
git fetch origin main
git reset --hard origin/main

# Install/update dependencies
log "📦 Installing dependencies..."
python3 -m pip install -q -r requirements.txt 2>&1 | tee -a "$LOG_FILE"

# Stop existing Streamlit process
log "🛑 Stopping existing Streamlit process..."
pkill -f "streamlit run $APP_SCRIPT" || true
sleep 2

# Clear Streamlit cache
log "🗑️  Clearing Streamlit cache..."
rm -rf ~/.streamlit/cache* || true

# Start new Streamlit process
log "🚀 Starting Streamlit application..."
nohup streamlit run "$APP_SCRIPT" --logger.level=info > /var/log/ads-dashboard/streamlit.log 2>&1 &
STREAMLIT_PID=$!
log "   PID: $STREAMLIT_PID"

# Wait for Streamlit to start
sleep 3

# Verify Streamlit is running
if ps -p $STREAMLIT_PID > /dev/null; then
    log "✅ Streamlit started successfully"
else
    log "❌ ERROR: Streamlit failed to start"
    log "Check logs: /var/log/ads-dashboard/streamlit.log"
    exit 1
fi

log "=========================================="
log "✅ Deployment completed successfully!"
log "=========================================="

