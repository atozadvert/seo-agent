# SEO Guardian - Railway Deployment Guide

Complete guide to deploy SEO Guardian on Railway with automated monitoring.

## 🚀 Quick Deploy to Railway

### Prerequisites
- GitHub account
- Railway account (sign up at https://railway.app)
- Google Search Console access
- Gmail account for email reports

### Step 1: Prepare Your Repository

1. **Push to GitHub** (if not already done):
```bash
git init
git add .
git commit -m "Initial SEO Guardian deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/seo-guardian.git
git push -u origin main
```

2. **Verify .gitignore** - Make sure sensitive files are excluded:
   - `.env`
   - `token.pickle`
   - `*.json` (OAuth secrets)
   - `*.db` (databases)

### Step 2: Deploy on Railway

1. Go to https://railway.app
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `seo-guardian` repository
4. Railway will auto-detect Python and use the `Procfile`

### Step 3: Configure Environment Variables

In Railway dashboard → **Variables** tab, add these:

#### Required Variables
```bash
# Email Configuration
EMAIL_FROM=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
REPORT_EMAIL=info@atozadvert.com

# Google Search Console (Service Account)
GSC_SERVICE_ACCOUNT_JSON=<base64_encoded_json>
```

#### Optional but Recommended
```bash
# WhatsApp Alerts (Twilio)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
MY_WHATSAPP_NUMBER=whatsapp:+923001234567

# Slack Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx

# Google PageSpeed API
GOOGLE_PAGESPEED_API=your_api_key
```

### Step 4: Google Search Console Setup (Critical!)

Railway runs in the cloud, so production should use a **Service Account**. The scripts now support both methods:

- **Railway/production**: `GSC_SERVICE_ACCOUNT_JSON`
- **Local/manual runs**: `token.pickle` created by `python setup_google_auth.py`

1. **Create Service Account**:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create credentials → Service Account
   - Download JSON key file

2. **Add to Google Search Console**:
   - Open Google Search Console
   - Settings → Users and permissions
   - Add the service account email as **Owner**
 
3. **Encode for Railway**:
```bash
# On Mac/Linux:
base64 -i service_account.json | tr -d '\n'

# On Windows (PowerShell):
[Convert]::ToBase64String([IO.File]::ReadAllBytes("service_account.json"))
```

4. **Add to Railway**:
   - Copy the base64 string
   - In Railway Variables: `GSC_SERVICE_ACCOUNT_JSON = <paste here>`

### Step 5: Custom Domain (Optional)

1. In Railway → **Settings** → **Domains**
2. Click **"Generate Domain"** for free Railway subdomain
3. Or add custom domain: `seo.atozadvert.com`
4. Update your DNS CNAME to point to Railway URL

### Step 6: Verify Deployment

1. Check Railway **Deployments** tab - should show "Success"
2. Click the generated URL to access your dashboard
3. Check **Logs** tab for any errors

## 📅 Automated Scheduling

The `railway.toml` file configures cron jobs:

```toml
# Daily SEO scan at 4 AM UTC (9 AM PKT)
[[cronJobs]]
schedule = "0 4 * * *"
command = "python seo_guardian.py"

# Daily rank tracking at 5 AM UTC (10 AM PKT)
[[cronJobs]]
schedule = "0 5 * * *"
command = "python rank_tracker.py"

# Uptime checks every 30 minutes
[[cronJobs]]
schedule = "*/30 * * * *"
command = "python uptime_monitor.py"

# Monthly report on 1st of each month at 7 AM UTC
[[cronJobs]]
schedule = "0 7 1 * *"
command = "python monthly_report.py"
```

## 🔧 Troubleshooting

### Issue: "No token.pickle" error
**Solution**: On Railway, set `GSC_SERVICE_ACCOUNT_JSON`. For local runs, create `token.pickle` with `python setup_google_auth.py`.

### Issue: Email not sending
**Solution**: 
- Use Gmail App Password, not regular password
- Enable 2FA on Gmail
- Generate App Password: https://myaccount.google.com/apppasswords

### Issue: Database not persisting
**Solution**: Railway provides ephemeral storage. For production:
1. Add Railway PostgreSQL plugin
2. Or use Railway Volumes for SQLite persistence

### Issue: Cron jobs not running
**Solution**: 
- Check Railway logs
- Verify `railway.toml` is in root directory
- Ensure commands are executable

### Issue: GSC service account connects but returns no sites
**Solution**:
- Add the service-account email to Google Search Console as an Owner or Full user
- Confirm the base64 value in `GSC_SERVICE_ACCOUNT_JSON` decodes to valid JSON
- Redeploy after updating Railway variables

## 📊 Monitoring Your Deployment

### View Logs
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# View logs
railway logs
```

### Check Dashboard
- Access your Railway URL
- Dashboard shows all metrics
- Refresh data with button in sidebar

### Email Reports
- Daily reports sent to `info@atozadvert.com`
- Monthly summary on 1st of each month
- Check spam folder if not receiving

## 🔐 Security Best Practices

1. **Never commit secrets**:
   - Use `.env` for local development
   - Use Railway Variables for production
   - Keep `.gitignore` updated

2. **Rotate credentials regularly**:
   - Change Gmail App Password every 90 days
   - Regenerate API keys periodically

3. **Monitor access**:
   - Check Railway activity logs
   - Review Google Search Console permissions
   - Monitor email delivery

## 💰 Cost Estimate

Railway Pricing (as of 2026):
- **Free Tier**: $5 credit/month
- **Hobby Plan**: $5/month (500 hours)
- **Pro Plan**: $20/month (unlimited)

Your usage:
- Streamlit dashboard: ~720 hours/month
- Cron jobs: Minimal usage
- **Recommended**: Hobby Plan ($5/month)

## 🆘 Support

If you encounter issues:

1. Check Railway logs first
2. Review this guide
3. Check GitHub issues
4. Contact: info@atozadvert.com

## 📚 Next Steps

After successful deployment:

1. ✅ Test WhatsApp alerts: `python whatsapp_alerts.py`
2. ✅ Run manual scan: `python seo_guardian.py`
3. ✅ Check dashboard at your Railway URL
4. ✅ Verify email reports are being sent
5. ✅ Add more sites via dashboard form

---

**Deployed successfully?** Star the repo and share with your team! 🎉
