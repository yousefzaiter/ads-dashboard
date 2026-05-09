#!/bin/bash
# Sync .env to production server
# This script uses SSH to safely copy the .env file

set -e

SERVER_HOST="${1:-}"
SERVER_USER="${2:-}"
SERVER_PATH="${3:-/opt/ads-dashboard}"

if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ]; then
    echo "Usage: ./sync_env.sh <host> <user> [path]"
    echo "Example: ./sync_env.sh ads.example.com root /opt/ads-dashboard"
    exit 1
fi

echo "📤 Syncing .env to $SERVER_USER@$SERVER_HOST:$SERVER_PATH/"
echo "⚠️  Make sure your SSH key is configured"
echo ""

if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    exit 1
fi

# Create backup on server
echo "Creating backup..."
ssh -q "$SERVER_USER@$SERVER_HOST" "cp -f $SERVER_PATH/.env $SERVER_PATH/.env.backup.$(date +%s)"

# Copy .env file
echo "Uploading .env..."
scp -q .env "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/.env"

# Verify
echo "Verifying..."
ssh -q "$SERVER_USER@$SERVER_HOST" "grep '^SNAP_ACCESS_TOKEN=' $SERVER_PATH/.env | cut -c1-30"

echo ""
echo "✅ .env synced successfully!"
echo "📝 Note: You may need to restart the Streamlit service on the server"
echo "   Command: ssh $SERVER_USER@$SERVER_HOST 'systemctl restart streamlit'"
