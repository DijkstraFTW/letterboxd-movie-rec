# Quick Security Setup Guide

## 🚀 5-Minute Security Setup

### Step 1: Generate API Key
```bash
cd middleware
python -c "import secrets; print('MIDDLEWARE_API_KEY=' + secrets.token_urlsafe(32))"
```

Copy the output to your `.env` file.

### Step 2: Configure Environment Variables
```bash
# Create .env file from example
cp .env.example .env

# Edit with your actual values
nano .env
```

**Minimum required variables:**
```bash
# Required
MIDDLEWARE_API_KEY=your-generated-key-from-step-1

# Development (default values work)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
ALLOWED_HOSTS=localhost,127.0.0.1

# Production (update these!)
# ALLOWED_ORIGINS=https://yourdomain.com
# ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
```

### Step 3: Update Your Frontend

**React/Vite Example:**
```javascript
// In your .env.local
VITE_API_URL=http://localhost:8000
VITE_API_KEY=your-generated-key-from-step-1

// In your API client
const apiClient = {
  async post(endpoint, data) {
    const response = await fetch(`${import.meta.env.VITE_API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': import.meta.env.VITE_API_KEY,
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      if (response.status === 429) {
        throw new Error('Too many requests. Please try again later.');
      }
      if (response.status === 401) {
        throw new Error('Authentication failed.');
      }
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }
};

// Usage
try {
  const result = await apiClient.post('/recommend/trigger', {
    letterboxd_username: 'johndoe',
    data_opt_in: false
  });
  console.log(result);
} catch (error) {
  console.error('API Error:', error.message);
}
```

### Step 4: Test the Setup
```bash
# Start the middleware
python middleware.py

# Test without API key (should fail with 401)
curl -X GET http://localhost:8000/health

# Test with API key (should succeed)
curl -X POST http://localhost:8000/recommend/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"letterboxd_username": "test", "data_opt_in": false}'
```

### Step 5: Monitor Logs
```bash
# Watch middleware logs
tail -f logs/middleware.log

# Watch security logs
tail -f logs/security.log

# Check for blocked IPs
grep "BLOCKED IP" logs/security.log
```

## 🔐 Security Features Enabled

✅ **API Key Authentication** - All endpoints protected
✅ **Rate Limiting** - 5 requests/min per endpoint, 100/hour globally
✅ **IP Blocking** - Auto-block after 5 failed auth attempts
✅ **CORS Protection** - Only allow specified origins
✅ **Request Size Limits** - Max 1MB per request
✅ **Security Headers** - XSS, clickjacking, MIME-sniffing protection
✅ **Input Validation** - Pydantic models validate all inputs
✅ **Audit Logging** - All security events logged

## 📊 Monitoring & Management

### Check Blocked IPs
```bash
curl -X GET http://localhost:8000/admin/security/blocked-ips \
  -H "X-API-Key: your-api-key"
```

### Unblock an IP
```bash
curl -X POST http://localhost:8000/admin/security/unblock-ip \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"ip_address": "192.168.1.100"}'
```

### View Security Stats
```bash
curl -X GET http://localhost:8000/admin/security/stats \
  -H "X-API-Key: your-api-key"
```

## 🚨 Common Issues

### Issue: "Invalid API key" error
**Solution:**
- Verify `MIDDLEWARE_API_KEY` is set in `.env`
- Check the API key is passed in `X-API-Key` header (not `Authorization`)
- Ensure no extra spaces in the key

### Issue: "CORS error" in browser
**Solution:**
- Add your frontend URL to `ALLOWED_ORIGINS` in `.env`
- Example: `ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173`
- Restart the middleware after changing `.env`

### Issue: "429 Too Many Requests"
**Solution:**
- This is rate limiting working correctly
- Wait 1 minute before retrying
- If testing, you can temporarily increase limits in `middleware.py`

### Issue: "IP address temporarily blocked"
**Solution:**
```bash
# Unblock yourself
curl -X POST http://localhost:8000/admin/security/unblock-ip \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"ip_address": "127.0.0.1"}'
```

## 🌐 Production Deployment

### Using Nginx (Recommended)

1. **Install Nginx & Certbot**
```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

2. **Configure Nginx**
```nginx
# /etc/nginx/sites-available/letterboxd-api
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Security headers (in addition to FastAPI's)
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;

        # Rate limiting (additional layer)
        limit_req zone=api burst=10 nodelay;
    }
}

# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
```

3. **Enable HTTPS**
```bash
sudo ln -s /etc/nginx/sites-available/letterboxd-api /etc/nginx/sites-enabled/
sudo certbot --nginx -d api.yourdomain.com
sudo systemctl reload nginx
```

4. **Update Environment Variables**
```bash
ALLOWED_ORIGINS=https://yourdomain.com
ALLOWED_HOSTS=api.yourdomain.com
```

### Using Systemd Service

```ini
# /etc/systemd/system/letterboxd-middleware.service
[Unit]
Description=Letterboxd Middleware API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/letterboxd-movie-rec/middleware
Environment="PATH=/path/to/venv/bin"
EnvironmentFile=/path/to/.env
ExecStart=/path/to/venv/bin/uvicorn middleware:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable letterboxd-middleware
sudo systemctl start letterboxd-middleware
sudo systemctl status letterboxd-middleware
```

## 🎯 Best Practices Summary

1. **Never commit `.env` files** - Add to `.gitignore`
2. **Use HTTPS in production** - Always encrypt API keys in transit
3. **Rotate API keys regularly** - Every 90 days recommended
4. **Monitor logs daily** - Check for suspicious activity
5. **Keep dependencies updated** - Run `pip install -U` regularly
6. **Use environment variables** - Never hardcode secrets
7. **Implement a backend proxy** - Don't expose API keys in frontend
8. **Set up monitoring alerts** - Get notified of security events
9. **Regular backups** - Backup MongoDB and Redis data
10. **Document your setup** - Keep this guide updated with your changes

## 📞 Need Help?

- Security best practices: See [SECURITY.md](./SECURITY.md)
- API documentation: See FastAPI auto-docs at `/docs`
- Logs location: `logs/middleware.log` and `logs/security.log`

---

**Security is not a one-time setup!** Review and update these configurations regularly.
