#!/bin/bash

# Nginx + React Deployment Script for Ubuntu 24.04 LTS
# Installs Nginx, configures SSL, serves React apps, and sets up reverse proxy

set -euo pipefail

# --- AESTHETICS ---

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- CONFIGURATION ---

DOMAIN_NAME=""
USE_DOMAIN=false
ENABLE_SSL=false
EMAIL=""
REACT_BUILD_PATH=""
NGINX_USER="www-data"
WEB_ROOT="/var/www/html"
SITES_AVAILABLE="/etc/nginx/sites-available"
SITES_ENABLED="/etc/nginx/sites-enabled"

# --- HELPER FUNCTIONS ---

log() {
    echo -e "${GREEN}🌐 $1${NC}"
}

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

success() {
    echo -e "${BLUE}✅ $1${NC}"
}

info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# --- VALIDATION ---

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        error "Please run as root or with sudo"
        exit 1
    fi
}

check_airflow() {
    if systemctl list-unit-files | grep -q airflow-webserver; then
        return 0
    else
        return 1
    fi
}

# --- CONFIGURATION PROMPTS ---

configure_settings() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         NGINX + REACT DEPLOYMENT SETUP                 ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo

    # Check if running in non-interactive mode (CI/CD)
    if [ "${NGINX_NON_INTERACTIVE:-false}" = "true" ]; then
        info "Running in non-interactive mode"

        # Domain configuration from env vars
        if [ -n "${DOMAIN_NAME}" ]; then
            USE_DOMAIN=true
            info "Domain: ${DOMAIN_NAME}"
        else
            USE_DOMAIN=false
            SERVER_IP=$(hostname -I | awk '{print $1}')
            DOMAIN_NAME="${DOMAIN_NAME:-$SERVER_IP}"
            info "Will configure for IP access: http://${DOMAIN_NAME}"
        fi

        # SSL configuration from env vars
        ENABLE_SSL="${ENABLE_SSL:-false}"
        EMAIL="${EMAIL:-admin@localhost}"

        # React build location
        REACT_BUILD_PATH="${REACT_BUILD_PATH:-}"

        # Airflow - explicitly kept private
        if check_airflow; then
            info "Airflow detected - will remain on localhost only (secure)"
            info "Access via SSH tunnel: ssh -L 8080:localhost:8080 root@${DOMAIN_NAME}"
        fi

        info "Configuration completed (non-interactive)"
        echo
        return
    fi

    # Interactive mode (original behavior)
    # Domain name
    echo -e "${YELLOW}Domain Configuration:${NC}"
    echo "You can use:"
    echo "  1) A domain name (e.g., example.com) - Required for SSL"
    echo "  2) Just the IP address (e.g., 192.168.1.100) - No SSL"
    echo
    read -p "Do you have a domain name pointing to this server? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        USE_DOMAIN=true
        while true; do
            read -p "Enter your domain name (e.g., example.com or app.example.com): " domain_input
            if [ ! -z "$domain_input" ]; then
                DOMAIN_NAME="$domain_input"
                info "Domain: ${DOMAIN_NAME}"
                break
            else
                warn "Domain name cannot be empty"
            fi
        done

        # SSL configuration
        echo
        echo -e "${YELLOW}SSL/HTTPS Configuration:${NC}"
        read -p "Set up free SSL certificate with Let's Encrypt? (Y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            ENABLE_SSL=true
            read -p "Enter your email for SSL certificate notifications: " email_input
            EMAIL="$email_input"
            info "SSL will be configured with Let's Encrypt"
        fi
    else
        USE_DOMAIN=false
        # Get server IP
        SERVER_IP=$(hostname -I | awk '{print $1}')
        DOMAIN_NAME="$SERVER_IP"
        info "Will configure for IP access: http://${SERVER_IP}"
        warn "SSL requires a domain name. Access will be HTTP only."
    fi

    echo

    # React build location
    echo -e "${YELLOW}React Application:${NC}"
    echo "You can either:"
    echo "  1) Provide a path to existing React build folder"
    echo "  2) Skip for now and deploy later"
    echo
    read -p "Do you have a React build folder ready? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        while true; do
            read -p "Enter full path to React build folder (e.g., /home/user/myapp/build): " build_path
            if [ -d "$build_path" ]; then
                REACT_BUILD_PATH="$build_path"
                info "React build: ${REACT_BUILD_PATH}"
                break
            elif [ ! -z "$build_path" ]; then
                warn "Directory not found: $build_path"
                read -p "Continue anyway? (y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    REACT_BUILD_PATH="$build_path"
                    break
                fi
            else
                info "Skipping React deployment for now"
                break
            fi
        done
    else
        info "React app can be deployed later"
    fi

    echo

    # Airflow - explicitly kept private
    if check_airflow; then
        info "Airflow detected - will remain on localhost only (secure)"
        info "Access via SSH tunnel: ssh -L 8080:localhost:8080 root@${DOMAIN_NAME}"
    fi

    echo
}

# --- INSTALLATION ---

install_nginx() {
    log "Installing Nginx..."
    
    sudo apt-get update
    sudo apt-get install -y nginx
    
    # Stop Nginx for configuration
    sudo systemctl stop nginx
    
    success "Nginx installed"
}

install_certbot() {
    if [ "$ENABLE_SSL" = false ]; then
        info "SSL disabled, skipping Certbot installation"
        return
    fi
    
    log "Installing Certbot for Let's Encrypt..."
    
    sudo apt-get install -y certbot python3-certbot-nginx
    
    success "Certbot installed"
}

# --- NGINX CONFIGURATION ---

create_nginx_config() {
    log "Creating Nginx configuration..."
    
    local CONFIG_FILE="${SITES_AVAILABLE}/default"
    
    # Backup original config
    if [ -f "$CONFIG_FILE" ]; then
        sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Create new configuration
    if [ "$ENABLE_SSL" = true ]; then
        create_ssl_config
    else
        create_http_config
    fi
    
    success "Nginx configuration created"
}

create_http_config() {
    local CONFIG_FILE="${SITES_AVAILABLE}/default"
    
    cat << EOF | sudo tee "$CONFIG_FILE" > /dev/null
# Nginx Configuration for ${DOMAIN_NAME}
# Generated by nginx.sh on $(date)

# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=api:10m rate=5r/s;
limit_conn_zone \$binary_remote_addr zone=addr:10m;

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name ${DOMAIN_NAME};
    
    root ${WEB_ROOT};
    index index.html index.htm;
    
    # Rate limiting
    limit_req zone=general burst=20 nodelay;
    limit_conn addr 10;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript application/json;
    
    # React app - handle client-side routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # API endpoints with stricter rate limiting
    location /api/ {
        limit_req zone=api burst=10 nodelay;

        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for long-running recommendations
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:8000/health;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
}

create_ssl_config() {
    local CONFIG_FILE="${SITES_AVAILABLE}/default"
    
    # Initial HTTP config (certbot will modify this)
    cat << EOF | sudo tee "$CONFIG_FILE" > /dev/null
# Nginx Configuration for ${DOMAIN_NAME}
# Generated by nginx.sh on $(date)
# SSL will be configured by Certbot

# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=api:10m rate=5r/s;
limit_conn_zone \$binary_remote_addr zone=addr:10m;

server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name ${DOMAIN_NAME};
    
    root ${WEB_ROOT};
    index index.html index.htm;
    
    # Rate limiting
    limit_req zone=general burst=20 nodelay;
    limit_conn addr 10;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/javascript application/json;
    
    # React app - handle client-side routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # API endpoints with stricter rate limiting
    location /api/ {
        limit_req zone=api burst=10 nodelay;

        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for long-running recommendations
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:8000/health;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF
}

# --- REACT DEPLOYMENT ---

deploy_react_app() {
    if [ -z "$REACT_BUILD_PATH" ]; then
        info "No React build path provided, creating placeholder"
        create_placeholder_index
        return
    fi
    
    if [ ! -d "$REACT_BUILD_PATH" ]; then
        warn "React build directory not found: ${REACT_BUILD_PATH}"
        create_placeholder_index
        return
    fi
    
    log "Deploying React application..."
    
    # Clear existing files (except hidden files)
    sudo rm -rf ${WEB_ROOT}/*
    
    # Copy React build
    sudo cp -r ${REACT_BUILD_PATH}/* ${WEB_ROOT}/
    
    # Set permissions
    sudo chown -R ${NGINX_USER}:${NGINX_USER} ${WEB_ROOT}
    sudo find ${WEB_ROOT} -type d -exec chmod 755 {} \;
    sudo find ${WEB_ROOT} -type f -exec chmod 644 {} \;
    
    success "React application deployed to ${WEB_ROOT}"
}

create_placeholder_index() {
    log "Creating placeholder index.html..."
    
    cat << 'EOF' | sudo tee ${WEB_ROOT}/index.html > /dev/null
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            max-width: 600px;
        }
        h1 { font-size: 3rem; margin-bottom: 1rem; }
        p { font-size: 1.2rem; opacity: 0.9; margin-bottom: 2rem; }
        .status { background: rgba(255, 255, 255, 0.2); padding: 1rem; border-radius: 10px; }
        .status-item { margin: 0.5rem 0; }
        .check { color: #4ade80; }
        code { background: rgba(0, 0, 0, 0.3); padding: 0.2rem 0.5rem; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Server Ready!</h1>
        <p>Your Nginx server is configured and running</p>
        <div class="status">
            <div class="status-item"><span class="check">✓</span> Nginx installed</div>
            <div class="status-item"><span class="check">✓</span> Configuration loaded</div>
            <div class="status-item"><span class="check">✓</span> Server running</div>
        </div>
        <p style="margin-top: 2rem; font-size: 1rem;">
            Deploy your React app by copying the build folder to:<br>
            <code>/var/www/html</code>
        </p>
    </div>
</body>
</html>
EOF
    
    sudo chown ${NGINX_USER}:${NGINX_USER} ${WEB_ROOT}/index.html
    info "Placeholder page created"
}

# --- SSL SETUP ---

setup_ssl() {
    if [ "$ENABLE_SSL" = false ]; then
        info "SSL setup skipped"
        return
    fi
    
    log "Setting up SSL with Let's Encrypt..."
    
    # Ensure Nginx is running for certbot verification
    sudo systemctl start nginx
    
    # Run certbot
    sudo certbot --nginx \
        -d "$DOMAIN_NAME" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive \
        --redirect
    
    if [ $? -eq 0 ]; then
        success "SSL certificate installed successfully"
        info "Auto-renewal is configured via systemd timer"
    else
        warn "SSL setup failed. You can try again later with:"
        echo "  sudo certbot --nginx -d $DOMAIN_NAME"
    fi
}

# --- FIREWALL ---

configure_firewall() {
    log "Configuring firewall..."
    
    if command -v ufw &> /dev/null; then
        sudo ufw allow 'Nginx Full'  # Allows both 80 and 443
        sudo ufw status | grep -q "Status: active" && success "Firewall configured" || info "Firewall rules added (not active)"
    else
        warn "UFW not found. Please manually open ports 80 and 443"
    fi
}

# --- SERVICE MANAGEMENT ---

configure_service() {
    log "Configuring Nginx service..."
    
    # Test configuration
    sudo nginx -t
    
    if [ $? -ne 0 ]; then
        error "Nginx configuration test failed!"
        exit 1
    fi
    
    # Enable and start
    sudo systemctl enable nginx
    sudo systemctl restart nginx
    
    # Wait and check
    sleep 2
    
    if sudo systemctl is-active --quiet nginx; then
        success "Nginx service is running"
    else
        error "Nginx failed to start"
        sudo systemctl status nginx
        exit 1
    fi
}

# --- POST-INSTALL INFO ---

create_deployment_guide() {
    local GUIDE_FILE="/root/react-deployment-guide.txt"
    
    cat << EOF | sudo tee "$GUIDE_FILE" > /dev/null
React + Nginx Deployment Guide
===============================
Generated: $(date)

Server Configuration:
- Domain/IP: ${DOMAIN_NAME}
- SSL: $(if [ "$ENABLE_SSL" = true ]; then echo "Enabled (HTTPS)"; else echo "Disabled (HTTP only)"; fi)
- Web Root: ${WEB_ROOT}
- Nginx Config: ${SITES_AVAILABLE}/default

Access URLs:
$(if [ "$ENABLE_SSL" = true ]; then echo "- Website: https://${DOMAIN_NAME}"; else echo "- Website: http://${DOMAIN_NAME}"; fi)

Airflow Access (Secure - localhost only):
-----------------------------------------
Airflow is NOT exposed to the internet for security.

To access Airflow remotely, use SSH tunnel:
  ssh -L 8080:localhost:8080 root@${DOMAIN_NAME}
  
Then visit on your local machine:
  http://localhost:8080

Or SSH into server and access locally:
  ssh root@${DOMAIN_NAME}
  curl http://localhost:8080

Deploying Your React App:
-------------------------

1. Build your React app locally:
   cd /path/to/your/react/app
   npm run build

2. Copy build folder to server:
   scp -r build/* root@${DOMAIN_NAME}:/var/www/html/

   OR use rsync:
   rsync -avz --delete build/ root@${DOMAIN_NAME}:/var/www/html/

3. Set correct permissions:
   sudo chown -R www-data:www-data /var/www/html
   sudo find /var/www/html -type d -exec chmod 755 {} \;
   sudo find /var/www/html -type f -exec chmod 644 {} \;

Quick Deployment Script:
------------------------
#!/bin/bash
# Save this as deploy.sh in your React project

npm run build
rsync -avz --delete build/ root@${DOMAIN_NAME}:/var/www/html/
ssh root@${DOMAIN_NAME} "chown -R www-data:www-data /var/www/html"
echo "Deployment complete!"

Nginx Management:
-----------------
Test config:      sudo nginx -t
Reload:           sudo systemctl reload nginx
Restart:          sudo systemctl restart nginx
Status:           sudo systemctl status nginx
View logs:        sudo tail -f /var/log/nginx/access.log
View errors:      sudo tail -f /var/log/nginx/error.log

SSL Certificate:
----------------
$(if [ "$ENABLE_SSL" = true ]; then
cat << SSLEOF
Renew manually:   sudo certbot renew
Auto-renewal:     Configured via systemd timer
Check renewal:    sudo certbot renew --dry-run
Certificate info: sudo certbot certificates
SSLEOF
else
    echo "SSL not configured. To add SSL later:"
    echo "1. Point your domain to this server"
    echo "2. Run: sudo certbot --nginx -d yourdomain.com"
fi)

Configuration Files:
-------------------
Nginx config:     /etc/nginx/sites-available/default
Nginx main:       /etc/nginx/nginx.conf
Web root:         /var/www/html
Logs directory:   /var/log/nginx

Troubleshooting:
----------------
- If site doesn't load, check: sudo systemctl status nginx
- For errors, check: sudo tail -f /var/log/nginx/error.log
- Test config: sudo nginx -t
- For React routing issues, ensure try_files is set correctly
- Clear browser cache if changes don't appear

Environment Variables in React:
-------------------------------
For API endpoints, create .env files:

.env.production:
REACT_APP_API_URL=$(if [ "$ENABLE_SSL" = true ]; then echo "https://${DOMAIN_NAME}/api"; else echo "http://${DOMAIN_NAME}/api"; fi)

Then access in your code:
const API_URL = process.env.REACT_APP_API_URL;

Note: Airflow is not exposed publicly for security.
If you need to access Airflow API from React, use SSH tunnel or VPN.
EOF
    
    sudo chmod 600 "$GUIDE_FILE"
    info "Deployment guide created: ${GUIDE_FILE}"
}

# --- MAIN ---

main() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         NGINX + REACT DEPLOYMENT SCRIPT                ║${NC}"
    echo -e "${GREEN}║              Ubuntu 24.04 LTS                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    check_root
    configure_settings
    
    install_nginx
    install_certbot
    create_nginx_config
    deploy_react_app
    configure_firewall
    configure_service
    
    # SSL must be done after nginx is running
    if [ "$ENABLE_SSL" = true ]; then
        setup_ssl
    fi
    
    create_deployment_guide
    
    echo
    success "Nginx + React deployment completed!"
    echo
    
    cat << EOF
${CYAN}════════════════════════════════════════════════════════${NC}
${GREEN}✅ DEPLOYMENT SUMMARY${NC}
${CYAN}════════════════════════════════════════════════════════${NC}

${YELLOW}Your Website:${NC}
$(if [ "$ENABLE_SSL" = true ]; then
    echo "  🌍 URL: ${CYAN}https://${DOMAIN_NAME}${NC}"
    echo "  🔒 SSL: ${GREEN}Enabled (Let's Encrypt)${NC}"
else
    echo "  🌍 URL: ${CYAN}http://${DOMAIN_NAME}${NC}"
    echo "  🔒 SSL: ${RED}Not configured (HTTP only)${NC}"
fi)
  📁 Web Root: ${CYAN}${WEB_ROOT}${NC}

${YELLOW}Secure Services (localhost only):${NC}
  🔒 PostgreSQL: localhost:5432
  🔒 Redis: localhost:6379
  🔒 Airflow: localhost:8080
  
  ${CYAN}Access Airflow via SSH tunnel:${NC}
  ssh -L 8080:localhost:8080 root@${DOMAIN_NAME}
  Then visit: http://localhost:8080

${YELLOW}Deployment Guide:${NC}
  📄 Location: ${CYAN}/root/react-deployment-guide.txt${NC}
  View: ${CYAN}cat /root/react-deployment-guide.txt${NC}

${YELLOW}Quick Deploy Your React App:${NC}
  ${CYAN}# On your local machine:${NC}
  cd /path/to/your/react/app
  npm run build
  scp -r build/* root@${DOMAIN_NAME}:/var/www/html/

${YELLOW}Nginx Management:${NC}
  Test config: ${CYAN}sudo nginx -t${NC}
  Reload:      ${CYAN}sudo systemctl reload nginx${NC}
  Status:      ${CYAN}sudo systemctl status nginx${NC}
  Logs:        ${CYAN}sudo tail -f /var/log/nginx/access.log${NC}

EOF

    if [ "$ENABLE_SSL" = true ]; then
        cat << EOF
${YELLOW}SSL Certificate:${NC}
  📧 Renewal notifications: ${EMAIL}
  🔄 Auto-renewal: ${GREEN}Enabled${NC}
  Check status: ${CYAN}sudo certbot certificates${NC}

EOF
    fi

    cat << EOF
${YELLOW}Next Steps:${NC}
  1. Visit your site: $(if [ "$ENABLE_SSL" = true ]; then echo "https://${DOMAIN_NAME}"; else echo "http://${DOMAIN_NAME}"; fi)
  2. Deploy your React app using the guide above
  3. Configure your React app's API endpoints
  4. Set up CI/CD for automatic deployments (optional)

${BLUE}🌐 Your web server is ready!${NC}

EOF
}

main