#!/bin/bash
# Complete sync: .env + clients.json to production server
# Syncs everything needed for a complete deployment

set -e

SERVER_HOST="${1:-}"
SERVER_USER="${2:-}"
SERVER_PATH="${3:-/opt/ads-dashboard}"

if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ]; then
    echo "🚀 Ads Dashboard - Complete Data Sync"
    echo "====================================="
    echo ""
    echo "Usage: ./sync_all.sh <host> <user> [path]"
    echo ""
    echo "Examples:"
    echo "  ./sync_all.sh ads.example.com ubuntu"
    echo "  ./sync_all.sh 192.168.1.100 root /opt/ads-dashboard"
    echo ""
    echo "This will sync:"
    echo "  ✓ clients.json (3 projects)"
    echo "  ✓ .env (all credentials)"
    exit 1
fi

echo "🚀 Ads Dashboard - Complete Data Sync"
echo "====================================="
echo ""
echo "Target: $SERVER_USER@$SERVER_HOST"
echo "Path: $SERVER_PATH"
echo ""

# Check files exist
if [ ! -f "clients.json" ]; then
    echo "❌ Error: clients.json not found!"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ Error: .env not found!"
    exit 1
fi

echo "📋 Files to sync:"
echo "  1. clients.json ($(wc -c < clients.json) bytes)"
echo "  2. .env ($(wc -c < .env) bytes)"
echo ""

# Create backups on server
echo "📦 Creating backups on server..."
ssh -q "$SERVER_USER@$SERVER_HOST" "mkdir -p $SERVER_PATH/backups" || true
BACKUP_TIME=$(date +%s)
ssh -q "$SERVER_USER@$SERVER_HOST" "[ -f $SERVER_PATH/clients.json ] && cp -f $SERVER_PATH/clients.json $SERVER_PATH/backups/clients.json.$BACKUP_TIME" || true
ssh -q "$SERVER_USER@$SERVER_HOST" "[ -f $SERVER_PATH/.env ] && cp -f $SERVER_PATH/.env $SERVER_PATH/backups/.env.$BACKUP_TIME" || true

# Sync files
echo "📤 Uploading files..."
scp -q clients.json "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/clients.json"
echo "   ✓ clients.json uploaded"

scp -q .env "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/.env"
echo "   ✓ .env uploaded"

# Verify uploads
echo ""
echo "✅ Verifying..."

# Check clients.json
PROJECTS=$(ssh -q "$SERVER_USER@$SERVER_HOST" "python3 -c \"import json; data = json.load(open('$SERVER_PATH/clients.json')); print(len(data.get('projects', [])))\" 2>/dev/null" || echo "0")
echo "   Projects: $PROJECTS"

# Check .env
TOKEN_CHECK=$(ssh -q "$SERVER_USER@$SERVER_HOST" "grep -c '^[A-Z_]*TOKEN=' $SERVER_PATH/.env 2>/dev/null" || echo "0")
echo "   Credentials: $TOKEN_CHECK tokens found"

echo ""
echo "📊 Summary:"
ssh -q "$SERVER_USER@$SERVER_HOST" "python3 << 'PYTHON_EOF'
import json, os

clients_file = '$SERVER_PATH/clients.json'
env_file = '$SERVER_PATH/.env'

# Check clients.json
if os.path.exists(clients_file):
    with open(clients_file) as f:
        data = json.load(f)
        projects = data.get('projects', [])
        print(f'   Projects: {len(projects)} configured')
        for p in projects:
            plats = [k for k, v in p.get('platforms', {}).items() if any(str(x).strip() for x in v.values())]
            print(f'     - {p.get(\"name\")}: {len(plats)} platforms')

# Check .env
if os.path.exists(env_file):
    with open(env_file) as f:
        env_vars = [l for l in f.readlines() if l.startswith(('SNAP_', 'META_', 'GOOGLE_', 'TIKTOK_'))]
        print(f'   Environment: {len(env_vars)} variables')
        
        # Check token status
        tokens = {}
        for line in env_vars:
            if '_TOKEN=' in line:
                key = line.split('=')[0]
                tokens[key] = '✓'
        for key in tokens:
            print(f'     ✓ {key}')

print('')
print('   Backups created: backups/clients.json.$BACKUP_TIME, backups/.env.$BACKUP_TIME')
PYTHON_EOF
"

echo ""
echo "✅ Sync completed successfully!"
echo ""
echo "🔄 Next steps:"
echo "  1. SSH into server: ssh $SERVER_USER@$SERVER_HOST"
echo "  2. Restart Streamlit:"
echo "     cd $SERVER_PATH"
echo "     pkill -f 'streamlit run dashboard.py'"
echo "     sleep 2"
echo "     rm -rf ~/.streamlit/cache*"
echo "     nohup streamlit run dashboard.py --logger.level=info &"
echo "  3. Verify: ps aux | grep streamlit"
echo ""
echo "📋 Or use automated deployment:"
echo "  ssh $SERVER_USER@$SERVER_HOST 'cd $SERVER_PATH && ./deploy.sh'"

