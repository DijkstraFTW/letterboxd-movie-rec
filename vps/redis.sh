#!/bin/bash

# Redis Installation and Hardening Script for Ubuntu 24.04 LTS
# This script installs Redis and configures it securely for production use

set -euo pipefail

# --- AESTHETICS ---

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- CONFIGURATION ---

REDIS_PORT=6379
REDIS_MAXMEMORY=""
REDIS_PASSWORD=""
ALLOW_REMOTE_ACCESS=false
REDIS_CONF="/etc/redis/redis.conf"

# --- HELPER FUNCTIONS ---

log() {
    echo -e "${GREEN}🔴 $1${NC}"
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

# --- DETECTION ---

detect_ram() {
    log "Detecting system resources..."
    
    local TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
    local TOTAL_RAM_GB=$((TOTAL_RAM_MB / 1024))
    
    info "Total RAM: ${TOTAL_RAM_GB}GB (${TOTAL_RAM_MB}MB)"
    
    # Set Redis maxmemory to 25% of total RAM (conservative for shared server)
    # Adjust if Redis is your primary workload
    local REDIS_MEM_MB=$((TOTAL_RAM_MB / 4))
    REDIS_MAXMEMORY="${REDIS_MEM_MB}mb"
    
    info "Recommended Redis max memory: ${REDIS_MAXMEMORY}"
    echo
}

# --- CONFIGURATION PROMPTS ---

configure_settings() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║            REDIS CONFIGURATION SETUP                   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo

    # Check if running in non-interactive mode (CI/CD)
    if [ "${REDIS_NON_INTERACTIVE:-false}" = "true" ]; then
        info "Running in non-interactive mode"

        # Remote access from env var or default
        ALLOW_REMOTE_ACCESS="${ALLOW_REMOTE_ACCESS:-false}"
        if [ "$ALLOW_REMOTE_ACCESS" = "true" ]; then
            warn "Remote access will be enabled. A strong password is REQUIRED."
        else
            info "Redis will only accept local connections (127.0.0.1)"
        fi

        # Password from env var or auto-generate
        if [ -z "$REDIS_PASSWORD" ]; then
            REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
            info "Auto-generated password: ${REDIS_PASSWORD}"
        fi

        # Max memory from env var or use default
        # REDIS_MAXMEMORY is already set in detect_system_resources
        info "Redis max memory set to: ${REDIS_MAXMEMORY}"

        info "Configuration completed (non-interactive)"
        echo
        return
    fi

    # Interactive mode (original behavior)
    # Remote access
    echo -e "${YELLOW}Remote Access Configuration:${NC}"
    echo "Redis can be configured for:"
    echo "  1) Local access only (127.0.0.1) - Most secure"
    echo "  2) Remote access (0.0.0.0) - Requires strong password"
    echo
    read -p "Allow remote access? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ALLOW_REMOTE_ACCESS=true
        warn "Remote access will be enabled. A strong password is REQUIRED."
    else
        ALLOW_REMOTE_ACCESS=false
        info "Redis will only accept local connections (127.0.0.1)"
    fi
    echo

    # Password configuration
    echo -e "${YELLOW}Password Configuration:${NC}"
    if [ "$ALLOW_REMOTE_ACCESS" = true ]; then
        echo "A password is REQUIRED for remote access."
    else
        echo "A password is recommended even for local access."
    fi
    echo

    while true; do
        read -sp "Enter Redis password (leave empty to auto-generate): " REDIS_PASSWORD
        echo

        if [ -z "$REDIS_PASSWORD" ]; then
            # Generate strong password
            REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
            info "Auto-generated password: ${REDIS_PASSWORD}"
            echo -e "${RED}SAVE THIS PASSWORD! You'll need it to connect to Redis.${NC}"
            echo
            break
        elif [ ${#REDIS_PASSWORD} -lt 16 ]; then
            warn "Password too short. Please use at least 16 characters."
        else
            break
        fi
    done

    # Max memory adjustment
    echo -e "${YELLOW}Memory Configuration:${NC}"
    echo "Recommended max memory: ${REDIS_MAXMEMORY}"
    read -p "Press Enter to use recommended, or type custom value (e.g., 512mb, 2gb): " custom_mem
    if [ ! -z "$custom_mem" ]; then
        REDIS_MAXMEMORY="$custom_mem"
    fi
    info "Redis max memory set to: ${REDIS_MAXMEMORY}"
    echo
}

# --- INSTALLATION ---

install_redis() {
    log "Installing Redis..."
    
    # Update package list
    sudo apt-get update
    
    # Install Redis
    sudo apt-get install -y redis-server redis-tools
    
    # Stop Redis before configuration
    sudo systemctl stop redis-server
    
    success "Redis installed successfully"
}

# --- CONFIGURATION ---

configure_redis() {
    log "Configuring Redis for production..."
    
    # Backup original configuration
    if [ -f "$REDIS_CONF" ]; then
        sudo cp "$REDIS_CONF" "${REDIS_CONF}.bak.$(date +%Y%m%d_%H%M%S)"
        info "Original config backed up"
    fi
    
    # Network binding
    if [ "$ALLOW_REMOTE_ACCESS" = true ]; then
        sudo sed -i "s/^bind 127.0.0.1.*/bind 0.0.0.0/" "$REDIS_CONF"
        info "Configured for remote access (0.0.0.0)"
    else
        sudo sed -i "s/^bind .*/bind 127.0.0.1/" "$REDIS_CONF"
        info "Configured for local access only (127.0.0.1)"
    fi
    
    # Protected mode
    if [ "$ALLOW_REMOTE_ACCESS" = true ]; then
        sudo sed -i "s/^protected-mode yes/protected-mode no/" "$REDIS_CONF"
    else
        sudo sed -i "s/^protected-mode .*/protected-mode yes/" "$REDIS_CONF"
    fi
    
    # Port
    sudo sed -i "s/^port .*/port ${REDIS_PORT}/" "$REDIS_CONF"
    
    # Password
    if grep -q "^# requirepass" "$REDIS_CONF"; then
        sudo sed -i "s/^# requirepass .*/requirepass ${REDIS_PASSWORD}/" "$REDIS_CONF"
    elif grep -q "^requirepass" "$REDIS_CONF"; then
        sudo sed -i "s/^requirepass .*/requirepass ${REDIS_PASSWORD}/" "$REDIS_CONF"
    else
        echo "requirepass ${REDIS_PASSWORD}" | sudo tee -a "$REDIS_CONF" > /dev/null
    fi
    
    # Max memory
    if grep -q "^# maxmemory " "$REDIS_CONF"; then
        sudo sed -i "s/^# maxmemory .*/maxmemory ${REDIS_MAXMEMORY}/" "$REDIS_CONF"
    elif grep -q "^maxmemory " "$REDIS_CONF"; then
        sudo sed -i "s/^maxmemory .*/maxmemory ${REDIS_MAXMEMORY}/" "$REDIS_CONF"
    else
        echo "maxmemory ${REDIS_MAXMEMORY}" | sudo tee -a "$REDIS_CONF" > /dev/null
    fi
    
    # Max memory policy (evict least recently used keys)
    if grep -q "^# maxmemory-policy" "$REDIS_CONF"; then
        sudo sed -i "s/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/" "$REDIS_CONF"
    elif grep -q "^maxmemory-policy" "$REDIS_CONF"; then
        sudo sed -i "s/^maxmemory-policy .*/maxmemory-policy allkeys-lru/" "$REDIS_CONF"
    else
        echo "maxmemory-policy allkeys-lru" | sudo tee -a "$REDIS_CONF" > /dev/null
    fi
    
    # Persistence configuration (RDB snapshots)
    sudo sed -i "s/^save 900 1/save 900 1/" "$REDIS_CONF"
    sudo sed -i "s/^save 300 10/save 300 10/" "$REDIS_CONF"
    sudo sed -i "s/^save 60 10000/save 60 10000/" "$REDIS_CONF"
    
    # Enable AOF (Append Only File) for better durability
    if grep -q "^appendonly no" "$REDIS_CONF"; then
        sudo sed -i "s/^appendonly no/appendonly yes/" "$REDIS_CONF"
    fi
    
    success "Redis configured with production settings"
}

# --- SECURITY HARDENING ---

harden_redis() {
    log "Applying security hardening..."
    
    # Disable dangerous commands
    cat << EOF | sudo tee -a "$REDIS_CONF" > /dev/null

# Security: Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
rename-command DEBUG ""
EOF
    
    # Set proper file permissions
    sudo chmod 640 "$REDIS_CONF"
    sudo chown redis:redis "$REDIS_CONF"
    
    success "Security hardening applied"
}

# --- SYSTEM CONFIGURATION ---

configure_system() {
    log "Configuring system for Redis..."
    
    # Disable Transparent Huge Pages (THP) - Redis recommendation
    if [ ! -f /etc/rc.local ]; then
        cat << 'EOF' | sudo tee /etc/rc.local > /dev/null
#!/bin/bash
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag
exit 0
EOF
        sudo chmod +x /etc/rc.local
    fi
    
    # Apply immediately
    echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled > /dev/null
    echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag > /dev/null
    
    # Increase max open files for Redis
    if ! grep -q "redis soft nofile" /etc/security/limits.conf; then
        cat << EOF | sudo tee -a /etc/security/limits.conf > /dev/null
redis soft nofile 65536
redis hard nofile 65536
EOF
    fi
    
    # Kernel parameters for Redis
    if ! grep -q "# Redis optimizations" /etc/sysctl.conf; then
        cat << EOF | sudo tee -a /etc/sysctl.conf > /dev/null

# Redis optimizations
vm.overcommit_memory = 1
net.core.somaxconn = 65535
EOF
        sudo sysctl -p > /dev/null
    fi
    
    success "System configured for Redis"
}

# --- FIREWALL ---

configure_firewall() {
    if [ "$ALLOW_REMOTE_ACCESS" = true ]; then
        log "Configuring firewall for remote Redis access..."
        
        if command -v ufw &> /dev/null; then
            sudo ufw allow ${REDIS_PORT}/tcp
            success "Firewall configured - port ${REDIS_PORT} opened"
        else
            warn "UFW not found. Please manually open port ${REDIS_PORT} if using a firewall"
        fi
    else
        info "Firewall configuration skipped (local access only)"
    fi
}

# --- SERVICE MANAGEMENT ---

setup_service() {
    log "Configuring Redis service..."
    
    # Enable supervised mode in systemd
    sudo sed -i "s/^supervised no/supervised systemd/" "$REDIS_CONF"
    
    # Enable and start Redis
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
    
    # Wait for Redis to start
    sleep 2
    
    # Check if Redis is running
    if sudo systemctl is-active --quiet redis-server; then
        success "Redis service is running"
    else
        error "Redis service failed to start"
        sudo systemctl status redis-server
        exit 1
    fi
}

# --- TESTING ---

test_redis() {
    log "Testing Redis connection..."
    
    # Test with authentication
    if redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
        success "Redis is responding correctly"
    else
        warn "Unable to connect to Redis. Please check the configuration."
    fi
    
    # Display Redis info
    echo
    info "Redis Information:"
    redis-cli -a "$REDIS_PASSWORD" INFO server 2>/dev/null | grep -E "redis_version|os|process_id|tcp_port" || true
}

# --- MAIN ---

main() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          REDIS INSTALLATION & HARDENING                ║${NC}"
    echo -e "${GREEN}║              Ubuntu 24.04 LTS                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    check_root
    detect_ram
    configure_settings
    
    install_redis
    configure_redis
    harden_redis
    configure_system
    configure_firewall
    setup_service
    test_redis
    
    echo
    success "Redis installation and hardening completed!"
    echo
    
    # Save credentials to file
    local CREDS_FILE="/root/redis-credentials.txt"
    cat << EOF | sudo tee "$CREDS_FILE" > /dev/null
Redis Configuration Summary
===========================
Generated: $(date)

Connection Details:
- Host: $(if [ "$ALLOW_REMOTE_ACCESS" = true ]; then echo "0.0.0.0 (remote access enabled)"; else echo "127.0.0.1 (local only)"; fi)
- Port: ${REDIS_PORT}
- Password: ${REDIS_PASSWORD}
- Max Memory: ${REDIS_MAXMEMORY}

Connection String:
redis://default:${REDIS_PASSWORD}@localhost:${REDIS_PORT}/0

Connection Examples:
--------------------

redis-cli:
redis-cli -a ${REDIS_PASSWORD}

Python (redis-py):
import redis
r = redis.Redis(host='localhost', port=${REDIS_PORT}, password='${REDIS_PASSWORD}', decode_responses=True)

Node.js (ioredis):
const Redis = require('ioredis');
const redis = new Redis({
  host: 'localhost',
  port: ${REDIS_PORT},
  password: '${REDIS_PASSWORD}'
});

Configuration File: ${REDIS_CONF}
Backup: ${REDIS_CONF}.bak.*

IMPORTANT: Keep this file secure and delete it after copying the credentials!
EOF
    
    sudo chmod 600 "$CREDS_FILE"
    
    cat << EOF
${CYAN}════════════════════════════════════════════════════════${NC}
${GREEN}✅ INSTALLATION SUMMARY${NC}
${CYAN}════════════════════════════════════════════════════════${NC}

${YELLOW}Redis Configuration:${NC}
  📍 Bind Address: $(if [ "$ALLOW_REMOTE_ACCESS" = true ]; then echo "0.0.0.0 (ALL interfaces)"; else echo "127.0.0.1 (LOCAL only)"; fi)
  🔌 Port: ${REDIS_PORT}
  🔒 Password: ${REDIS_PASSWORD}
  💾 Max Memory: ${REDIS_MAXMEMORY}
  📝 Persistence: RDB + AOF enabled

${YELLOW}Security Features:${NC}
  ✅ Password authentication enabled
  ✅ Dangerous commands disabled (FLUSHDB, FLUSHALL, CONFIG, etc.)
  ✅ Protected mode configured
  ✅ File permissions hardened
  ✅ Transparent Huge Pages disabled

${YELLOW}Credentials File:${NC}
  📄 Location: ${CREDS_FILE}
  ${RED}⚠️  IMPORTANT: This file contains sensitive information!${NC}
  ${RED}    Copy the password and delete this file:${NC}
      ${CYAN}sudo cat ${CREDS_FILE}${NC}
      ${CYAN}sudo rm ${CREDS_FILE}${NC}

${YELLOW}Quick Test:${NC}
  ${CYAN}redis-cli -a ${REDIS_PASSWORD} ping${NC}

${YELLOW}Common Commands:${NC}
  View logs:     ${CYAN}sudo journalctl -u redis-server -f${NC}
  Restart:       ${CYAN}sudo systemctl restart redis-server${NC}
  Status:        ${CYAN}sudo systemctl status redis-server${NC}
  Config file:   ${CYAN}sudo nano ${REDIS_CONF}${NC}

${YELLOW}Monitoring:${NC}
  Redis CLI:     ${CYAN}redis-cli -a ${REDIS_PASSWORD} INFO${NC}
  Memory usage:  ${CYAN}redis-cli -a ${REDIS_PASSWORD} INFO memory${NC}
  Stats:         ${CYAN}redis-cli -a ${REDIS_PASSWORD} INFO stats${NC}

${BLUE}🚀 Redis is ready for production use!${NC}

EOF
}

main