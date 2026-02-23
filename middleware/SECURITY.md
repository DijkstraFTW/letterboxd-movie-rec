# API Security Guide

## 🔒 Security Measures Implemented

### 1. **API Key Authentication**
- All endpoints (except `/health`) require a valid API key in the `X-API-Key` header
- API key must be set via `MIDDLEWARE_API_KEY` environment variable
- Generate a strong key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

**Frontend Usage:**
```javascript
const response = await fetch('https://api.yourdomain.com/recommend/trigger', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key-here'
  },
  body: JSON.stringify({ letterboxd_username: 'user', data_opt_in: false })
});
```

### 2. **Rate Limiting**
- **Global limit**: 100 requests per hour per IP address
- **Per-endpoint limit**: 5 requests per minute per IP address
- Helps prevent abuse and DoS attacks

**Rate Limit Headers in Response:**
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 4
X-RateLimit-Reset: 1234567890
```

### 3. **CORS (Cross-Origin Resource Sharing)**
- Restricted to specific frontend domains only
- Configure via `ALLOWED_ORIGINS` environment variable
- Only allows `GET` and `POST` methods
- Only allows `Content-Type` and `X-API-Key` headers

### 4. **Request Size Limits**
- Maximum request body size: 1MB (configurable)
- Prevents large payload attacks
- Returns 413 error if exceeded

### 5. **Trusted Host Protection**
- Validates the `Host` header
- Prevents Host Header Injection attacks
- Configure via `ALLOWED_HOSTS` environment variable

### 6. **Security Headers**
All responses include:
- `X-Content-Type-Options: nosniff` - Prevents MIME-sniffing
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-XSS-Protection: 1; mode=block` - XSS protection
- `Strict-Transport-Security` - Forces HTTPS
- `Content-Security-Policy` - Restricts resource loading

### 7. **Input Validation**
- All inputs validated using Pydantic models
- Type checking and field validation
- Prevents injection attacks

## 🚀 Deployment Checklist

### Environment Setup

1. **Generate Strong API Key**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Configure Environment Variables**
   ```bash
   # Copy example file
   cp .env.example .env

   # Edit with your values
   nano .env
   ```

3. **Set Production Origins**
   ```bash
   ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
   ```

### HTTPS/TLS Setup

**CRITICAL**: Always use HTTPS in production to encrypt API keys in transit.

**Option 1: Reverse Proxy (Recommended)**
```nginx
# nginx configuration
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Option 2: Uvicorn with SSL**
```python
uvicorn.run(
    "middleware.middleware:app",
    host="0.0.0.0",
    port=8443,
    ssl_keyfile="/path/to/key.pem",
    ssl_certfile="/path/to/cert.pem",
)
```

### Additional Security Recommendations

#### 1. **API Key Rotation**
- Rotate API keys periodically (every 90 days)
- Support multiple API keys for zero-downtime rotation
- Log all key usage for auditing

#### 2. **IP Whitelisting** (Optional)
Add to your middleware if you have a fixed set of IPs:

```python
ALLOWED_IPS = os.getenv("ALLOWED_IPS", "").split(",")

@app.middleware("http")
async def ip_whitelist(request: Request, call_next):
    if ALLOWED_IPS and request.client.host not in ALLOWED_IPS:
        logger.warning(f"Blocked request from unauthorized IP: {request.client.host}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "IP not allowed"}
        )
    return await call_next(request)
```

#### 3. **Monitoring & Alerting**
- Monitor failed authentication attempts
- Set up alerts for rate limit violations
- Track unusual traffic patterns

**Example: Log Analysis**
```bash
# Monitor failed auth attempts
grep "Invalid API key" logs/middleware.log | wc -l

# Monitor rate limit hits
grep "429" logs/middleware.log | tail -20
```

#### 4. **DDoS Protection**
For production, use:
- **Cloudflare** - Free tier includes DDoS protection
- **AWS WAF** - Web Application Firewall
- **Nginx rate limiting** - Additional layer before your app

#### 5. **Database Security**
```python
# MongoDB connection with authentication
MONGO_URI = "mongodb://user:pass@localhost:27017/?authSource=admin&tls=true"
```

## 🧪 Testing Security

### Test API Key Authentication
```bash
# Should fail (401)
curl -X POST https://api.yourdomain.com/recommend/trigger

# Should succeed (200)
curl -X POST https://api.yourdomain.com/recommend/trigger \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"letterboxd_username": "test", "data_opt_in": false}'
```

### Test Rate Limiting
```bash
# Trigger rate limit (run multiple times quickly)
for i in {1..10}; do
  curl -X GET https://api.yourdomain.com/recommend/popular \
    -H "X-API-Key: your-api-key"
done
```

### Test CORS
```bash
# Should be blocked if origin not in ALLOWED_ORIGINS
curl -X OPTIONS https://api.yourdomain.com/recommend/popular \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: POST"
```

## 📊 Monitoring Endpoints

### Health Check (No Auth Required)
```bash
curl https://api.yourdomain.com/health
```

## 🔐 Frontend Integration Best Practices

### 1. **Never Expose API Keys in Frontend Code**
❌ **Bad:**
```javascript
// Don't hardcode API keys in frontend!
const API_KEY = "abc123-secret-key";
```

✅ **Good:**
```javascript
// Use environment variables
const API_KEY = import.meta.env.VITE_API_KEY;

// Or use a backend proxy
const response = await fetch('/api/recommend', {
  method: 'POST',
  body: JSON.stringify(data)
});
```

### 2. **Recommended Architecture**

```
[Frontend] → [Your Backend/Proxy] → [Middleware API]
             (stores API key)        (FastAPI)
```

Create a simple backend proxy:
```python
# backend_proxy.py
from fastapi import FastAPI, Request
import httpx

app = FastAPI()
MIDDLEWARE_URL = "https://api.yourdomain.com"
API_KEY = os.getenv("MIDDLEWARE_API_KEY")

@app.post("/api/recommend")
async def proxy_recommend(request: Request):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MIDDLEWARE_URL}/recommend/trigger",
            json=data,
            headers={"X-API-Key": API_KEY}
        )
        return response.json()
```

### 3. **Use HTTPS Everywhere**
```javascript
// Always use HTTPS in production
const API_URL = process.env.NODE_ENV === 'production'
  ? 'https://api.yourdomain.com'
  : 'http://localhost:8000';
```

## 🚨 Incident Response

### If API Key is Compromised:

1. **Immediately rotate the key**
   ```bash
   # Generate new key
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # Update environment variable
   export MIDDLEWARE_API_KEY="new-key-here"

   # Restart service
   systemctl restart letterboxd-middleware
   ```

2. **Check logs for unauthorized access**
   ```bash
   grep "Invalid API key" logs/middleware.log
   ```

3. **Update all clients with new key**

4. **Consider implementing key revocation list**

## 📝 Compliance & Legal

- **GDPR**: If storing EU user data, ensure compliance
- **Rate Limiting**: Protects your infrastructure costs
- **Logging**: Keep audit logs for security incidents
- **Data Retention**: Define policies for user data

## 🔍 Security Audit Checklist

- [ ] HTTPS enabled in production
- [ ] API keys are strong and random (32+ characters)
- [ ] API keys stored in environment variables, not code
- [ ] CORS configured with specific origins only
- [ ] Rate limiting enabled and tested
- [ ] Request size limits configured
- [ ] Security headers present in responses
- [ ] Failed auth attempts are logged
- [ ] MongoDB has authentication enabled
- [ ] Redis has password protection
- [ ] Firewall configured to block unauthorized IPs
- [ ] Regular security updates applied
- [ ] Monitoring and alerting configured
- [ ] Backup and disaster recovery plan in place

## 📚 Additional Resources

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [Mozilla Web Security Guidelines](https://infosec.mozilla.org/guidelines/web_security)
