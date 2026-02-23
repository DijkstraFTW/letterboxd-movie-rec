#!/bin/bash

# System Monitoring and Alerting Script
# Monitors RAM, Disk, SSL certificates, and sends email alerts

set -euo pipefail

# --- AESTHETICS ---

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- CONFIGURATION ---

ALERT_EMAIL=""
SMTP_HOST=""
SMTP_PORT="587"
SMTP_USER=""
SMTP_PASSWORD=""
RAM_THRESHOLD=80
DISK_THRESHOLD=80
SSL_CHECK_DAYS=30
ENABLE_EMAIL_ALERTS=false

# --- HELPER FUNCTIONS ---

log() {
    echo -e "${GREEN}📊 $1${NC}"
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

# --- CONFIGURATION ---

configure_alerts() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         SYSTEM MONITORING CONFIGURATION                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo

    # Check if running in non-interactive mode (CI/CD)
    if [ "${MONITORING_NON_INTERACTIVE:-false}" = "true" ]; then
        info "Running in non-interactive mode"

        # Email alerts from env var or default
        ENABLE_EMAIL_ALERTS="${ENABLE_EMAIL_ALERTS:-false}"

        if [ "$ENABLE_EMAIL_ALERTS" = "true" ]; then
            ALERT_EMAIL="${ALERT_EMAIL:-admin@localhost}"
            SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
            SMTP_PORT="${SMTP_PORT:-587}"
            SMTP_USER="${SMTP_USER:-}"
            SMTP_PASSWORD="${SMTP_PASSWORD:-}"
            info "Email alerts will be sent to: ${ALERT_EMAIL}"
        else
            info "Email alerts disabled. Logs will be written to /var/log/system-monitoring.log"
        fi

        # Thresholds from env vars or defaults
        RAM_THRESHOLD="${RAM_THRESHOLD:-80}"
        DISK_THRESHOLD="${DISK_THRESHOLD:-80}"
        SSL_CHECK_DAYS="${SSL_CHECK_DAYS:-30}"

        info "Thresholds set: RAM ${RAM_THRESHOLD}%, Disk ${DISK_THRESHOLD}%, SSL ${SSL_CHECK_DAYS} days"
        info "Configuration completed (non-interactive)"
        echo
        return
    fi

    # Interactive mode (original behavior)
    # Email alerts
    echo -e "${YELLOW}Email Alert Configuration:${NC}"
    echo "Do you want to receive email alerts?"
    echo "  Note: Requires SMTP server (Gmail, SendGrid, etc.)"
    echo
    read -p "Enable email alerts? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ENABLE_EMAIL_ALERTS=true

        read -p "Enter your email address: " email
        ALERT_EMAIL="$email"

        echo
        echo "SMTP Configuration (for sending emails):"
        echo "  Example for Gmail:"
        echo "    Host: smtp.gmail.com"
        echo "    Port: 587"
        echo "    Use App Password (not your regular password)"
        echo

        read -p "SMTP Host (e.g., smtp.gmail.com): " smtp_host
        SMTP_HOST="$smtp_host"

        read -p "SMTP Port [587]: " smtp_port
        SMTP_PORT=${smtp_port:-587}

        read -p "SMTP Username (usually your email): " smtp_user
        SMTP_USER="$smtp_user"

        read -sp "SMTP Password (or App Password): " smtp_pass
        SMTP_PASSWORD="$smtp_pass"
        echo

        info "Email alerts will be sent to: ${ALERT_EMAIL}"
    else
        ENABLE_EMAIL_ALERTS=false
        info "Email alerts disabled. Logs will be written to /var/log/system-monitoring.log"
    fi

    echo

    # Thresholds
    echo -e "${YELLOW}Alert Thresholds:${NC}"
    read -p "RAM alert threshold (%) [80]: " ram_thresh
    RAM_THRESHOLD=${ram_thresh:-80}

    read -p "Disk alert threshold (%) [80]: " disk_thresh
    DISK_THRESHOLD=${disk_thresh:-80}

    read -p "SSL certificate warning days [30]: " ssl_days
    SSL_CHECK_DAYS=${ssl_days:-30}

    info "Thresholds set: RAM ${RAM_THRESHOLD}%, Disk ${DISK_THRESHOLD}%, SSL ${SSL_CHECK_DAYS} days"
    echo
}

# --- INSTALLATION ---

install_dependencies() {
    log "Installing monitoring dependencies..."
    
    sudo apt-get update
    sudo apt-get install -y \
        bc \
        mailutils \
        ssmtp \
        curl
    
    success "Dependencies installed"
}

# --- EMAIL CONFIGURATION ---

configure_email() {
    if [ "$ENABLE_EMAIL_ALERTS" = false ]; then
        info "Email configuration skipped"
        return
    fi
    
    log "Configuring email sending..."
    
    # Configure ssmtp
    cat << EOF | sudo tee /etc/ssmtp/ssmtp.conf > /dev/null
# SSMTP Configuration for Monitoring Alerts
root=${ALERT_EMAIL}
mailhub=${SMTP_HOST}:${SMTP_PORT}
hostname=$(hostname)
AuthUser=${SMTP_USER}
AuthPass=${SMTP_PASSWORD}
UseSTARTTLS=YES
UseTLS=YES
FromLineOverride=YES
EOF
    
    sudo chmod 640 /etc/ssmtp/ssmtp.conf
    
    success "Email configuration complete"
}

# --- MONITORING SCRIPTS ---

create_monitoring_script() {
    log "Creating monitoring script..."
    
    cat << 'MONITOR_EOF' > /usr/local/bin/system-monitor.sh
#!/bin/bash

# System Monitoring Script
# Checks RAM, Disk, SSL, and sends alerts

LOG_FILE="/var/log/system-monitoring.log"
ALERT_SENT_FILE="/var/lib/system-monitor/alerts-sent"

# Load configuration
if [ -f /etc/system-monitor.conf ]; then
    source /etc/system-monitor.conf
else
    echo "Configuration file not found!" | tee -a "$LOG_FILE"
    exit 1
fi

# Create state directory
mkdir -p /var/lib/system-monitor

# Initialize alert tracking file
touch "$ALERT_SENT_FILE"

# --- HELPER FUNCTIONS ---

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local subject="$1"
    local message="$2"
    local alert_type="$3"
    
    log_message "ALERT: $subject"
    
    # Check if alert was recently sent (within last hour)
    if grep -q "$alert_type:$(date +%Y%m%d%H)" "$ALERT_SENT_FILE" 2>/dev/null; then
        log_message "Alert already sent this hour, skipping duplicate"
        return
    fi
    
    if [ "$ENABLE_EMAIL_ALERTS" = "true" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL" 2>/dev/null
        if [ $? -eq 0 ]; then
            log_message "Email alert sent to $ALERT_EMAIL"
            echo "$alert_type:$(date +%Y%m%d%H)" >> "$ALERT_SENT_FILE"
        else
            log_message "Failed to send email alert"
        fi
    fi
}

# --- CHECKS ---

check_ram() {
    local ram_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    local ram_used=$(free -h | grep Mem | awk '{print $3}')
    local ram_total=$(free -h | grep Mem | awk '{print $2}')
    
    log_message "RAM Usage: ${ram_usage}% (${ram_used}/${ram_total})"
    
    if [ "$ram_usage" -ge "$RAM_THRESHOLD" ]; then
        local message="WARNING: High RAM usage detected!

Server: $(hostname)
RAM Usage: ${ram_usage}%
Used: ${ram_used} / ${ram_total}
Threshold: ${RAM_THRESHOLD}%

Time: $(date)

Top 5 processes by memory:
$(ps aux --sort=-%mem | head -6)

Action recommended: Check running processes and consider upgrading RAM or optimizing applications."
        
        send_alert "⚠️ High RAM Usage Alert - ${ram_usage}%" "$message" "ram"
    fi
}

check_disk() {
    df -h | grep -vE '^Filesystem|tmpfs|cdrom|loop' | awk '{print $5 " " $6}' | while read output; do
        usage=$(echo $output | awk '{print $1}' | sed 's/%//')
        partition=$(echo $output | awk '{print $2}')
        
        log_message "Disk Usage: ${partition} ${usage}%"
        
        if [ "$usage" -ge "$DISK_THRESHOLD" ]; then
            local disk_info=$(df -h "$partition")
            local message="WARNING: High disk usage detected!

Server: $(hostname)
Partition: ${partition}
Usage: ${usage}%
Threshold: ${DISK_THRESHOLD}%

Disk Info:
${disk_info}

Largest directories in ${partition}:
$(du -h ${partition} 2>/dev/null | sort -rh | head -10)

Action recommended: Clean up old logs, backups, or expand disk space."
            
            send_alert "⚠️ High Disk Usage Alert - ${partition} ${usage}%" "$message" "disk_${partition}"
        fi
    done
}

check_ssl() {
    if [ ! -d /etc/letsencrypt/live ]; then
        log_message "No SSL certificates found"
        return
    fi
    
    for cert_dir in /etc/letsencrypt/live/*/; do
        if [ -f "${cert_dir}cert.pem" ]; then
            local domain=$(basename "$cert_dir")
            local expiry_date=$(openssl x509 -enddate -noout -in "${cert_dir}cert.pem" | cut -d= -f2)
            local expiry_epoch=$(date -d "$expiry_date" +%s)
            local now_epoch=$(date +%s)
            local days_left=$(( ($expiry_epoch - $now_epoch) / 86400 ))
            
            log_message "SSL Certificate: ${domain} - ${days_left} days until expiry"
            
            if [ "$days_left" -le "$SSL_CHECK_DAYS" ]; then
                local message="WARNING: SSL certificate expiring soon!

Server: $(hostname)
Domain: ${domain}
Days remaining: ${days_left}
Expiry date: ${expiry_date}

Action required: Renew SSL certificate
Command: sudo certbot renew

If auto-renewal is failing, check:
1. Port 80 is open
2. DNS points to this server
3. Certbot timer is running: systemctl status certbot.timer"
                
                send_alert "⚠️ SSL Certificate Expiring - ${domain} (${days_left} days)" "$message" "ssl_${domain}"
            fi
        fi
    done
}

check_services() {
    local services=("nginx" "postgresql" "redis-server" "airflow-webserver" "airflow-scheduler")
    
    for service in "${services[@]}"; do
        if systemctl list-unit-files | grep -q "^${service}.service"; then
            if systemctl is-active --quiet "$service"; then
                log_message "Service OK: $service"
            else
                local message="WARNING: Service down!

Server: $(hostname)
Service: ${service}
Status: STOPPED

Action required: Restart the service
Command: sudo systemctl start ${service}

Check logs: sudo journalctl -u ${service} -n 50"
                
                send_alert "⚠️ Service Down - ${service}" "$message" "service_${service}"
            fi
        fi
    done
}

# --- MAIN CHECKS ---

log_message "=== Starting system monitoring checks ==="

check_ram
check_disk
check_ssl
check_services

log_message "=== Monitoring checks complete ==="

# Clean up old alert records (older than 24 hours)
find /var/lib/system-monitor -name "alerts-sent" -mtime +1 -delete 2>/dev/null || true

exit 0
MONITOR_EOF
    
    sudo chmod +x /usr/local/bin/system-monitor.sh
    
    success "Monitoring script created"
}

create_config_file() {
    log "Creating configuration file..."
    
    cat << EOF | sudo tee /etc/system-monitor.conf > /dev/null
# System Monitoring Configuration
# Generated on $(date)

ENABLE_EMAIL_ALERTS=${ENABLE_EMAIL_ALERTS}
ALERT_EMAIL="${ALERT_EMAIL}"
RAM_THRESHOLD=${RAM_THRESHOLD}
DISK_THRESHOLD=${DISK_THRESHOLD}
SSL_CHECK_DAYS=${SSL_CHECK_DAYS}
EOF
    
    sudo chmod 600 /etc/system-monitor.conf
    
    success "Configuration file created"
}

# --- CRON SETUP ---

setup_cron() {
    log "Setting up automated monitoring..."
    
    # Run every 15 minutes
    (sudo crontab -l 2>/dev/null | grep -v "system-monitor.sh"; echo "*/15 * * * * /usr/local/bin/system-monitor.sh") | sudo crontab -
    
    success "Monitoring scheduled every 15 minutes"
}

# --- TEST MONITORING ---

test_monitoring() {
    log "Testing monitoring script..."
    
    /usr/local/bin/system-monitor.sh
    
    echo
    info "Check the log file for results:"
    echo "  tail -20 /var/log/system-monitoring.log"
    
    if [ "$ENABLE_EMAIL_ALERTS" = true ]; then
        echo
        warn "If no alerts were triggered, you won't receive a test email"
        info "To test email manually, run:"
        echo "  echo 'Test alert' | mail -s 'Test Alert' $ALERT_EMAIL"
    fi
}

# --- SSL RENEWAL REMINDER ---

setup_ssl_check() {
    log "Setting up SSL renewal check..."
    
    # Ensure certbot timer is enabled
    if systemctl list-unit-files | grep -q certbot.timer; then
        sudo systemctl enable certbot.timer
        sudo systemctl start certbot.timer
        success "Certbot auto-renewal timer enabled"
    else
        info "Certbot not installed or timer not found"
    fi
    
    # Create SSL renewal test script
    cat << 'EOF' > /usr/local/bin/test-ssl-renewal.sh
#!/bin/bash
echo "Testing SSL certificate renewal..."
sudo certbot renew --dry-run
if [ $? -eq 0 ]; then
    echo "✅ SSL renewal test passed"
else
    echo "❌ SSL renewal test failed - check configuration"
fi
EOF
    
    sudo chmod +x /usr/local/bin/test-ssl-renewal.sh
    
    info "Test SSL renewal anytime with: sudo test-ssl-renewal.sh"
}

# --- MAIN ---

main() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         SYSTEM MONITORING & ALERTING SETUP             ║${NC}"
    echo -e "${GREEN}║              Ubuntu 24.04 LTS                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    check_root
    configure_alerts
    
    install_dependencies
    configure_email
    create_config_file
    create_monitoring_script
    setup_cron
    setup_ssl_check
    test_monitoring
    
    echo
    success "Monitoring and alerting setup complete!"
    echo
    
    cat << EOF
${CYAN}════════════════════════════════════════════════════════${NC}
${GREEN}✅ MONITORING SUMMARY${NC}
${CYAN}════════════════════════════════════════════════════════${NC}

${YELLOW}What's Being Monitored:${NC}
  📊 RAM Usage: Alert at ${RAM_THRESHOLD}%
  💾 Disk Usage: Alert at ${DISK_THRESHOLD}%
  🔒 SSL Certificates: Alert at ${SSL_CHECK_DAYS} days before expiry
  🔧 Services: nginx, postgresql, redis, airflow

${YELLOW}Monitoring Schedule:${NC}
  ⏰ Every 15 minutes (via cron)
  📝 Logs: /var/log/system-monitoring.log

$(if [ "$ENABLE_EMAIL_ALERTS" = true ]; then
cat << ALERT_EOF
${YELLOW}Email Alerts:${NC}
  📧 Enabled
  ✉️  Send to: ${ALERT_EMAIL}
  🔄 Cooldown: 1 hour between duplicate alerts
ALERT_EOF
else
    echo "${YELLOW}Email Alerts:${NC}"
    echo "  ❌ Disabled"
    echo "  Alerts logged to /var/log/system-monitoring.log"
fi)

${YELLOW}Useful Commands:${NC}
  View logs:           ${CYAN}tail -f /var/log/system-monitoring.log${NC}
  Run check now:       ${CYAN}sudo /usr/local/bin/system-monitor.sh${NC}
  Test SSL renewal:    ${CYAN}sudo test-ssl-renewal.sh${NC}
  Check cron:          ${CYAN}sudo crontab -l${NC}
  Edit thresholds:     ${CYAN}sudo nano /etc/system-monitor.conf${NC}

${YELLOW}SSL Auto-Renewal:${NC}
  Status:              ${CYAN}sudo systemctl status certbot.timer${NC}
  Test renewal:        ${CYAN}sudo certbot renew --dry-run${NC}
  View certificates:   ${CYAN}sudo certbot certificates${NC}

${YELLOW}Manual Alert Test:${NC}
  ${CYAN}echo "Test message" | mail -s "Test Alert" ${ALERT_EMAIL}${NC}

${YELLOW}Current System Status:${NC}
EOF
    
    # Show current stats
    local ram_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}')
    
    echo "  RAM: ${ram_usage}% used"
    echo "  Disk (/): ${disk_usage} used"
    
    if [ -d /etc/letsencrypt/live ]; then
        for cert_dir in /etc/letsencrypt/live/*/; do
            if [ -f "${cert_dir}cert.pem" ]; then
                local domain=$(basename "$cert_dir")
                local expiry_date=$(openssl x509 -enddate -noout -in "${cert_dir}cert.pem" | cut -d= -f2)
                local expiry_epoch=$(date -d "$expiry_date" +%s)
                local now_epoch=$(date +%s)
                local days_left=$(( ($expiry_epoch - $now_epoch) / 86400 ))
                echo "  SSL (${domain}): ${days_left} days until expiry"
            fi
        done
    fi
    
    echo
    echo -e "${BLUE}📊 Monitoring is now active!${NC}"
    echo
}

main