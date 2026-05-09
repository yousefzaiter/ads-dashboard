#!/bin/bash
# Sync clients.json (projects configuration) to production server
# This script safely copies the clients.json file containing project definitions

set -e

SERVER_HOST="${1:-}"
SERVER_USER="${2:-}"
SERVER_PATH="${3:-/opt/ads-dashboard}"

if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ]; then
    echo "Usage: ./sync_clients.sh <host> <user> [path]"
    echo "Example: ./sync_clients.sh ads.example.com root /opt/ads-dashboard"
    exit 1
fi

echo "📤 Syncing clients.json to $SERVER_USER@$SERVER_HOST:$SERVER_PATH/"
echo "⚠️  This contains project configurations - ensure SSH is secure"
echo ""

if [ ! -f "clients.json" ]; then
    echo "❌ Error: clients.json file not found!"
    exit 1
fi

# Create backup on server
echo "Creating backup..."
ssh -q "$SERVER_USER@$SERVER_HOST" "cp -f $SERVER_PATH/clients.json $SERVER_PATH/clients.json.backup.$(date +%s)"

# Copy clients.json file
echo "Uploading clients.json..."
scp -q clients.json "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/clients.json"

# Verify
echo "Verifying..."
ssh -q "$SERVER_USER@$SERVER_HOST" "python3 -c \"import json; data = json.load(open('$SERVER_PATH/clients.json')); print('Projects found:', len(data.get('projects', []))); print('Clients found:', len(data.get('clients', [])))\""

echo ""
echo "✅ clients.json synced successfully!"
echo "📋 Summary:"
ssh -q "$SERVER_USER@$SERVER_HOST" "python3 << 'PYTHON_EOF'
import json
with open('$SERVER_PATH/clients.json') as f:
    data = json.load(f)
    print('   Projects:')
    for p in data.get('projects', []):
        print(f\"     - {p.get('name', 'Unknown')} ({p.get('id')})\")
    print('\\n   Platforms configured:')
    for p in data.get('projects', []):
        plats = [k for k, v in p.get('platforms', {}).items() if any(v.values())]
        print(f\"     - {p.get('name')}: {', '.join(plats) if plats else 'None'}\")
PYTHON_EOF
"

echo ""
echo "⚠️  After syncing, restart Streamlit on the server:"
echo "   ssh $SERVER_USER@$SERVER_HOST 'pkill -f streamlit; sleep 2; nohup streamlit run dashboard.py &'"
