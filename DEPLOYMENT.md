# Ads Dashboard - Deployment Guide

## Overview
This guide covers deploying the ads-dashboard to production.

## System Requirements
- Python 3.8+
- Streamlit
- Git
- Network access to Ad platform APIs (Google, Meta, Snap)

## Deployment Methods

### Method 1: Automatic GitHub Actions (Recommended)
The deployment is fully automated using GitHub Actions.

**Trigger deployment:**
1. Go to https://github.com/yousefzaiter/ads-dashboard/actions
2. Select "Deploy to server" workflow
3. Click "Run workflow"
4. Confirm deployment

**What it does:**
- Pulls latest code from main branch
- Installs dependencies
- Restarts Streamlit service
- Clears cache
- Verifies application is running

### Method 2: Manual Deployment

#### Prerequisites
- SSH access to production server
- Sudo privileges (for restarting services)
- Git configured

#### Steps

1. **SSH into the server:**
```bash
ssh user@ads-dashboard-server.com
```

2. **Navigate to project directory:**
```bash
cd /opt/ads-dashboard
```

3. **Pull latest code:**
```bash
git fetch origin main
git reset --hard origin/main
```

4. **Install dependencies:**
```bash
python3 -m pip install -r requirements.txt
```

5. **Update environment variables:**
```bash
# Edit .env with new tokens
nano .env

# Required updates:
# - SNAP_ACCESS_TOKEN (refresh if expired)
# - META_ACCESS_TOKEN (refresh if expiring)
# - Any other tokens that were updated
```

6. **Restart Streamlit:**
```bash
# Kill existing process
pkill -f "streamlit run dashboard.py"
sleep 2

# Clear cache
rm -rf ~/.streamlit/cache*

# Start new process
nohup streamlit run dashboard.py --logger.level=info &
```

7. **Verify deployment:**
```bash
ps aux | grep streamlit
curl http://localhost:8501  # Should return HTML
```

### Method 3: Using Provided Scripts

#### Sync Environment Variables
Transfer the .env file from development to production:

```bash
cd /Users/yousefabuzaiter/mcp-google-ads
./sync_env.sh ads-server.example.com root /opt/ads-dashboard
```

#### Run Full Deployment
On the production server:

```bash
cd /opt/ads-dashboard
./deploy.sh
```

## Environment Variables

The application requires the following environment variables in `.env`:

### Google Ads
- `GOOGLE_ADS_DEVELOPER_TOKEN` - Developer token from Google Ads
- `GOOGLE_ADS_CLIENT_ID` - OAuth client ID
- `GOOGLE_ADS_CLIENT_SECRET` - OAuth client secret
- `GOOGLE_ADS_REFRESH_TOKEN` - OAuth refresh token
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` - MCC account ID (optional)

### Meta (Facebook)
- `META_APP_ID` - App ID from Meta
- `META_APP_SECRET` - App secret from Meta
- `META_ACCESS_TOKEN` - User access token (expires in 60 days)

### Snapchat
- `SNAP_CLIENT_ID` - OAuth client ID
- `SNAP_CLIENT_SECRET` - OAuth client secret
- `SNAP_ACCESS_TOKEN` - OAuth access token (expires, auto-refreshes)
- `SNAP_REFRESH_TOKEN` - OAuth refresh token (used for auto-refresh)

### TikTok (Optional)
- `TIKTOK_APP_ID` - App ID (currently pending)
- `TIKTOK_APP_SECRET` - App secret (currently pending)
- `TIKTOK_ACCESS_TOKEN` - Access token (currently pending)
- `TIKTOK_ADVERTISER_ID` - Advertiser ID (currently pending)

## Token Management

### Snap Token Auto-Refresh
The application automatically refreshes expired Snap tokens using the refresh token flow.

**When:** Automatically when an API call returns 401 Unauthorized
**How:** Exchanges SNAP_REFRESH_TOKEN for new SNAP_ACCESS_TOKEN
**File:** snap_ads_server.py - refresh_snap_token() function

### Meta Token Manual Refresh
Meta tokens expire in 60 days. When expiring:

1. Get new token from: https://developers.facebook.com/tools/explorer/
2. Update `META_ACCESS_TOKEN` in .env on production
3. Restart Streamlit application

### Google Token
Uses refresh token for automatic renewal. Generally stable unless revoked.

## Monitoring

### Check Application Status
```bash
ps aux | grep streamlit
```

### View Logs
```bash
# Streamlit logs
tail -f /var/log/ads-dashboard/streamlit.log

# Deployment logs
tail -f /var/log/ads-dashboard/deploy.log
```

### Verify API Connectivity
The dashboard includes built-in health checks:
- Dashboard page will show token status
- Project pages will display "Token expired" errors if needed
- Admin panel shows API connectivity status

## Troubleshooting

### Streamlit Won't Start
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Check installation
python3 -m pip list | grep streamlit

# Check port 8501 is available
lsof -i :8501
```

### API Errors
- **Meta: 401 Unauthorized** → Token expired, refresh manually
- **Snap: 401 Unauthorized** → Auto-refresh should trigger, check logs
- **Google: 401 Unauthorized** → OAuth issue, check refresh token

### Cache Issues
Clear Streamlit cache:
```bash
rm -rf ~/.streamlit/cache*
pkill -f streamlit
# Restart application
```

## Deployment Status

### Current Version
- **Commit**: b487d29 (Add Snap error logging)
- **Branch**: main
- **Status**: Ready for production

### Verified Components
- ✅ Snap integration (all 3 projects working)
- ✅ Meta integration (tested with current token)
- ✅ Google Ads integration (dashboard working)
- ✅ Token auto-refresh (Snap)
- ✅ Error logging and monitoring

### Known Issues
- ⚠️ TikTok integration pending (credentials not configured)

## Post-Deployment Checklist

After deploying, verify:

- [ ] Dashboard loads without errors
- [ ] Snap accounts display (3+ accounts visible)
- [ ] Meta campaigns show data
- [ ] Google Ads data visible
- [ ] Project detail pages work
- [ ] No 401/401 token errors
- [ ] Logs show normal operation

## Emergency Rollback

If deployment causes issues:

```bash
cd /opt/ads-dashboard
git log --oneline | head -5  # See recent commits
git reset --hard <commit-hash>  # Rollback to previous commit
./deploy.sh  # Redeploy
```

## Support

For issues:
1. Check logs: `/var/log/ads-dashboard/`
2. Verify credentials in `.env`
3. Test API endpoints manually
4. Check GitHub Actions workflow logs

