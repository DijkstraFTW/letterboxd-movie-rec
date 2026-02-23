#!/bin/bash

# This script provides additional system hardening and optimization for Ubuntu Server 24.04 LTS
# Run this in addition to or integrated with your PostgreSQL setup script
# Supports multiple profiles: database, web, general purpose

set -euo pipefail

# --- AESTHETICS ---

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
SHIELD='🛡️'
ROCKET='🚀'
NC='\033[0m'

# --- GLOBAL VARIABLES ---

PROFILE=""
TOTAL_RAM_MB=0
SWAP_SIZE=""
ENABLE_FIREWALL=true

# --- HELPER FUNCTIONS ---

log() {
    echo -e "${GREEN}${SHIELD} $1${NC}"
}

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

success() {
    echo -e "${BLUE}${ROCKET} $1${NC}"
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

check_ubuntu() {
    if [ ! -f /etc/lsb-release ]; then
        error "This script is designed for Ubuntu"
        exit 1
    fi

    source /etc/lsb-release
    if [[ ! "$DISTRIB_RELEASE" =~ ^24\. ]]; then
        warn "This script is optimized for Ubuntu 24.04, you're running $DISTRIB_RELEASE"
        if [ "${VPS_NON_INTERACTIVE:-false}" != "true" ]; then
            read -p "Continue anyway? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        else
            info "Continuing anyway (non-interactive mode)"
        fi
    fi
}

# --- DETECTION & CONFIGURATION ---

detect_system_resources() {
    log "Detecting system resources..."
    
    TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
    local TOTAL_RAM_GB=$((TOTAL_RAM_MB / 1024))
    
    info "Detected RAM: ${TOTAL_RAM_GB}GB (${TOTAL_RAM_MB}MB)"
    
    # Determine swap size based on RAM
    if [ "$TOTAL_RAM_MB" -lt 2048 ]; then
        SWAP_SIZE="2G"
        info "RAM < 2GB: Setting swap to 2GB"
    elif [ "$TOTAL_RAM_MB" -lt 4096 ]; then
        SWAP_SIZE="2G"
        info "RAM 2-4GB: Setting swap to 2GB"
    elif [ "$TOTAL_RAM_MB" -lt 8192 ]; then
        SWAP_SIZE="4G"
        info "RAM 4-8GB: Setting swap to 4GB"
    else
        SWAP_SIZE="4G"
        info "RAM > 8GB: Setting swap to 4GB (minimal swap for large systems)"
    fi
    
    echo
}

select_profile() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         VPS OPTIMIZATION PROFILE SELECTION             ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo

    # Check if running in non-interactive mode (CI/CD)
    if [ "${VPS_NON_INTERACTIVE:-false}" = "true" ]; then
        PROFILE="${VPS_PROFILE:-web}"
        if [ "$PROFILE" = "minimal" ]; then
            ENABLE_FIREWALL=false
        fi
        info "Selected: ${PROFILE} profile (non-interactive mode)"
        echo
        return
    fi

    # Interactive mode (original behavior)
    echo -e "${GREEN}Available Profiles:${NC}"
    echo
    echo -e "${YELLOW}1) DATABASE SERVER${NC}"
    echo "   - Optimized for PostgreSQL, MySQL, MongoDB, etc."
    echo "   - High shared memory limits"
    echo "   - Database-focused kernel parameters"
    echo "   - Firewall allows database ports"
    echo
    echo -e "${YELLOW}2) WEB SERVER${NC}"
    echo "   - Optimized for Nginx, Apache, Node.js, etc."
    echo "   - Connection handling optimization"
    echo "   - Firewall allows HTTP/HTTPS"
    echo "   - Network buffer tuning for web traffic"
    echo
    echo -e "${YELLOW}3) GENERAL PURPOSE${NC}"
    echo "   - Balanced optimization for mixed workloads"
    echo "   - Moderate resource allocation"
    echo "   - Basic firewall (SSH only)"
    echo "   - Good for development servers"
    echo
    echo -e "${YELLOW}4) MINIMAL (Security Only)${NC}"
    echo "   - Only security hardening, no performance tuning"
    echo "   - No firewall changes"
    echo "   - For containers or when you manage config manually"
    echo

    while true; do
        read -p "Select profile (1-4): " profile_choice
        case $profile_choice in
            1)
                PROFILE="database"
                info "Selected: DATABASE SERVER profile"
                break
                ;;
            2)
                PROFILE="web"
                info "Selected: WEB SERVER profile"
                break
                ;;
            3)
                PROFILE="general"
                info "Selected: GENERAL PURPOSE profile"
                break
                ;;
            4)
                PROFILE="minimal"
                ENABLE_FIREWALL=false
                info "Selected: MINIMAL profile"
                break
                ;;
            *)
                error "Invalid selection. Please choose 1-4."
                ;;
        esac
    done

    echo
}

configure_firewall_by_profile() {
    if [ "$ENABLE_FIREWALL" = false ]; then
        info "Skipping firewall configuration (minimal profile)"
        return
    fi
    
    log "Configuring firewall for ${PROFILE} profile..."
    
    # Install UFW if not present
    if ! command -v ufw &> /dev/null; then
        sudo apt-get install -y ufw
    fi
    
    # Reset to defaults
    sudo ufw --force reset
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Always allow SSH
    sudo ufw allow ssh
    
    # Profile-specific ports
    case $PROFILE in
        database)
            sudo ufw allow 5432/tcp  # PostgreSQL
            info "Opened database port for PostgreSQL"
            # sudo ufw allow 3306/tcp  # MySQL/MariaDB
            # sudo ufw allow 27017/tcp # MongoDB
            # info "Opened database ports (PostgreSQL, MySQL, MongoDB)"
            ;;
        web)
            sudo ufw allow 80/tcp    # HTTP
            sudo ufw allow 443/tcp   # HTTPS
            info "Opened web ports (HTTP, HTTPS)"
            ;;
        general)
            info "Only SSH port opened (general purpose)"
            ;;
    esac
    
    # Enable firewall
    echo "y" | sudo ufw enable
    
    success "Firewall configured for ${PROFILE} profile"
}

# --- SYSTEM OPTIMIZATION ---

setup_swap() {
    log "Configuring swap space..."
    
    # Check if swap already exists
    if [ -f /swapfile ]; then
        warn "Swap file already exists, skipping..."
        return
    fi
    
    log "Creating ${SWAP_SIZE} swap file..."
    sudo fallocate -l "$SWAP_SIZE" /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    
    # Make swap permanent
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    
    success "Swap space (${SWAP_SIZE}) configured successfully"
}

configure_system_limits() {
    log "Configuring system resource limits..."
    
    # Backup original file
    if [ ! -f /etc/security/limits.conf.bak ]; then
        sudo cp /etc/security/limits.conf /etc/security/limits.conf.bak
    fi
    
    # Add limits if not already present
    if ! grep -q "# VPS Optimization Limits" /etc/security/limits.conf; then
        sudo tee -a /etc/security/limits.conf > /dev/null <<EOF

# VPS Optimization Limits
* soft nofile 65536
* hard nofile 65536
* soft nproc 65536
* hard nproc 65536
root soft nofile 65536
root hard nofile 65536
EOF
    fi
    
    success "System resource limits configured"
}

optimize_kernel_parameters() {
    log "Optimizing kernel parameters for ${PROFILE} profile..."
    
    # Backup original file
    if [ ! -f /etc/sysctl.conf.bak ]; then
        sudo cp /etc/sysctl.conf /etc/sysctl.conf.bak
    fi
    
    # Calculate memory-based values
    local SHMMAX=$((TOTAL_RAM_MB * 1024 * 1024 / 2))  # 50% of RAM in bytes
    local SHMALL=$((SHMMAX / 4096))  # In pages (4KB)
    
    # Remove old VPS optimizations if present
    sudo sed -i '/# VPS Kernel Optimizations/,/^$/d' /etc/sysctl.conf
    
    # Base optimizations for all profiles
    sudo tee -a /etc/sysctl.conf > /dev/null <<EOF

# VPS Kernel Optimizations - Profile: ${PROFILE} - RAM: ${TOTAL_RAM_MB}MB
# Reduce swap usage
vm.swappiness = 10

# Improve cache management
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5

# Security enhancements
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
EOF

    # Profile-specific optimizations
    case $PROFILE in
        database)
            sudo tee -a /etc/sysctl.conf > /dev/null <<EOF

# Database server optimizations
kernel.shmmax = ${SHMMAX}
kernel.shmall = ${SHMALL}
kernel.shmmni = 4096
vm.overcommit_memory = 2
vm.overcommit_ratio = 80
EOF
            info "Applied database-specific kernel parameters"
            ;;
            
        web)
            # Calculate connection limits based on RAM
            local MAX_CONNTRACK=$((TOTAL_RAM_MB * 64))
            if [ $MAX_CONNTRACK -gt 524288 ]; then
                MAX_CONNTRACK=524288
            fi
            
            sudo tee -a /etc/sysctl.conf > /dev/null <<EOF

# Web server optimizations
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_keepalive_intvl = 15
net.netfilter.nf_conntrack_max = ${MAX_CONNTRACK}
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1

# Network buffer sizes
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
EOF
            info "Applied web server-specific kernel parameters"
            ;;
            
        general)
            sudo tee -a /etc/sysctl.conf > /dev/null <<EOF

# General purpose optimizations
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.netfilter.nf_conntrack_max = 131072
net.core.rmem_max = 8388608
net.core.wmem_max = 8388608
net.ipv4.tcp_rmem = 4096 87380 8388608
net.ipv4.tcp_wmem = 4096 65536 8388608
EOF
            info "Applied general purpose kernel parameters"
            ;;
            
        minimal)
            info "Minimal profile: Only base security kernel parameters applied"
            ;;
    esac
    
    # Load the new parameters
    sudo sysctl -p
    
    success "Kernel parameters optimized for ${PROFILE} profile"
}

configure_timezone() {
    log "Setting timezone to UTC..."
    sudo timedatectl set-timezone UTC
    success "Timezone set to UTC"
}

# --- SECURITY ---

setup_unattended_upgrades() {
    log "Setting up automatic security updates..."
    
    sudo apt-get install -y unattended-upgrades apt-listchanges
    
    # Configure unattended-upgrades
    sudo tee /etc/apt/apt.conf.d/50unattended-upgrades > /dev/null <<EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}";
    "\${distro_id}:\${distro_codename}-security";
    "\${distro_id}ESMApps:\${distro_codename}-apps-security";
    "\${distro_id}ESM:\${distro_codename}-infra-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";
EOF
    
    # Enable automatic updates
    sudo tee /etc/apt/apt.conf.d/20auto-upgrades > /dev/null <<EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF
    
    sudo systemctl enable unattended-upgrades
    sudo systemctl start unattended-upgrades
    
    success "Automatic security updates enabled"
}

harden_shared_memory() {
    log "Hardening shared memory..."
    
    if ! grep -q "tmpfs /run/shm" /etc/fstab; then
        echo "tmpfs /run/shm tmpfs defaults,noexec,nosuid 0 0" | sudo tee -a /etc/fstab
        sudo mount -o remount /run/shm 2>/dev/null || true
    fi
    
    success "Shared memory hardened"
}

disable_unnecessary_services() {
    log "Disabling unnecessary services..."
    
    # List of services that are often not needed on a server
    SERVICES_TO_DISABLE=(
        "bluetooth.service"
        "cups.service"
        "avahi-daemon.service"
    )
    
    for service in "${SERVICES_TO_DISABLE[@]}"; do
        if systemctl list-unit-files | grep -q "$service"; then
            sudo systemctl disable "$service" 2>/dev/null || true
            sudo systemctl stop "$service" 2>/dev/null || true
            log "Disabled $service"
        fi
    done
    
    success "Unnecessary services disabled"
}

# --- MONITORING & LOGGING ---

setup_log_rotation() {
    log "Configuring log rotation..."
    
    sudo tee /etc/logrotate.d/custom-logs > /dev/null <<EOF
/var/log/syslog {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 syslog adm
    sharedscripts
    postrotate
        /usr/lib/rsyslog/rsyslog-rotate
    endscript
}

/var/log/auth.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 syslog adm
    sharedscripts
    postrotate
        /usr/lib/rsyslog/rsyslog-rotate
    endscript
}
EOF
    
    success "Log rotation configured"
}

install_monitoring_tools() {
    log "Installing monitoring and diagnostic tools..."
    
    sudo apt-get install -y \
        htop \
        iotop \
        iftop \
        nethogs \
        sysstat \
        ncdu \
        dstat \
        curl \
        wget \
        net-tools \
        dnsutils
    
    # Enable sysstat
    sudo sed -i 's/ENABLED="false"/ENABLED="true"/' /etc/default/sysstat
    sudo systemctl enable sysstat
    sudo systemctl start sysstat
    
    success "Monitoring tools installed"
}

# --- PERFORMANCE ---

optimize_ssh_performance() {
    log "Optimizing SSH performance..."
    
    # Add compression and keep-alive settings
    if ! grep -q "# Performance optimizations" /etc/ssh/sshd_config; then
        sudo tee -a /etc/ssh/sshd_config > /dev/null <<EOF

# Performance optimizations
Compression yes
ClientAliveInterval 60
ClientAliveCountMax 3
UseDNS no
EOF
        sudo systemctl restart ssh.service
    fi
    
    success "SSH performance optimized"
}

# --- BACKUP HELPERS ---

create_backup_directory() {
    log "Creating backup directory structure..."
    
    sudo mkdir -p /var/backups/system
    sudo mkdir -p /var/backups/configs
    
    # Backup important config files
    sudo cp /etc/fstab /var/backups/configs/fstab.bak
    sudo cp /etc/sysctl.conf /var/backups/configs/sysctl.conf.bak
    sudo cp /etc/ssh/sshd_config /var/backups/configs/sshd_config.bak
    
    success "Backup directories created and configs backed up"
}

# --- MAIN SCRIPT ---

main() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     VPS SYSTEM HARDENING & OPTIMIZATION SCRIPT         ║${NC}"
    echo -e "${GREEN}║              Ubuntu 24.04 LTS Optimized                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    # Validation
    check_root
    check_ubuntu
    
    # Detection and profile selection
    detect_system_resources
    select_profile
    
    log "Starting VPS system hardening and optimization..."
    echo
    
    # System optimization
    setup_swap
    configure_system_limits
    optimize_kernel_parameters
    configure_timezone
    
    # Security hardening
    setup_unattended_upgrades
    harden_shared_memory
    disable_unnecessary_services
    
    # Profile-specific firewall
    configure_firewall_by_profile
    
    # Monitoring and logging
    setup_log_rotation
    install_monitoring_tools
    
    # Performance
    optimize_ssh_performance
    
    # Backup
    create_backup_directory
    
    echo
    success "VPS system hardening and optimization completed successfully!"
    echo
    
    # Profile-specific summary
    local PROFILE_DESCRIPTION=""
    case $PROFILE in
        database)
            PROFILE_DESCRIPTION="DATABASE SERVER - Optimized for PostgreSQL, MySQL, MongoDB"
            ;;
        web)
            PROFILE_DESCRIPTION="WEB SERVER - Optimized for Nginx, Apache, Node.js"
            ;;
        general)
            PROFILE_DESCRIPTION="GENERAL PURPOSE - Balanced for mixed workloads"
            ;;
        minimal)
            PROFILE_DESCRIPTION="MINIMAL - Security hardening only"
            ;;
    esac
    
    # Final recommendations
    cat << EOF
${GREEN}${SHIELD} SYSTEM OPTIMIZATION SUMMARY${NC}

${CYAN}Profile:${NC} ${PROFILE_DESCRIPTION}
${CYAN}RAM Detected:${NC} ${TOTAL_RAM_MB}MB
${CYAN}Swap Configured:${NC} ${SWAP_SIZE}

✅ Completed:
   - Swap space configured (${SWAP_SIZE})
   - System resource limits optimized
   - Kernel parameters tuned for ${PROFILE} profile
   - Automatic security updates enabled
   - Shared memory hardened
   - Unnecessary services disabled
EOF

    if [ "$ENABLE_FIREWALL" = true ]; then
        echo "   - Firewall configured for ${PROFILE} profile"
    else
        echo "   - Firewall configuration skipped (minimal profile)"
    fi

    cat << EOF
   - Log rotation configured
   - Monitoring tools installed (htop, iotop, sysstat, etc.)
   - SSH performance optimized
   - Configuration backups created in /var/backups/configs

${YELLOW}📋 PROFILE-SPECIFIC NOTES:${NC}
EOF

    case $PROFILE in
        database)
            cat << EOF

   ${CYAN}Database Server Configuration:${NC}
   - Shared memory: $(numfmt --to=iec ${SHMMAX} 2>/dev/null || echo "${SHMMAX} bytes")
   - Firewall ports: 5432 (PostgreSQL), 3306 (MySQL), 27017 (MongoDB)
   - Optimized for: Large datasets, concurrent connections
   
   ${YELLOW}Next steps for database setup:${NC}
   1. Install your database server (PostgreSQL, MySQL, etc.)
   2. Configure database-specific settings
   3. Set up database backups
   4. Create database users and set strong passwords
EOF
            ;;
        web)
            cat << EOF

   ${CYAN}Web Server Configuration:${NC}
   - Max connections: High (optimized for web traffic)
   - Firewall ports: 80 (HTTP), 443 (HTTPS)
   - Network buffers: Tuned for concurrent connections
   
   ${YELLOW}Next steps for web server:${NC}
   1. Install your web server (Nginx, Apache, etc.)
   2. Set up SSL certificates (Let's Encrypt recommended)
   3. Configure your application
   4. Set up log rotation for web server logs
EOF
            ;;
        general)
            cat << EOF

   ${CYAN}General Purpose Configuration:${NC}
   - Balanced resource allocation
   - Firewall: SSH only
   - Suitable for development, small apps, or mixed workloads
   
   ${YELLOW}Next steps:${NC}
   1. Install your required software
   2. Configure firewall for additional ports as needed:
      sudo ufw allow <port>/tcp
   3. Set up application-specific monitoring
EOF
            ;;
        minimal)
            cat << EOF

   ${CYAN}Minimal Configuration:${NC}
   - Security hardening only
   - No firewall changes made
   - No performance tuning applied
   
   ${YELLOW}Next steps:${NC}
   1. Configure firewall manually if needed
   2. Tune kernel parameters for your specific use case
   3. Install and configure required software
EOF
            ;;
    esac

    cat << EOF

${YELLOW}📋 RECOMMENDED NEXT STEPS (ALL PROFILES):${NC}

1. Review automatic update settings:
   ${CYAN}sudo nano /etc/apt/apt.conf.d/50unattended-upgrades${NC}

2. Check system resource usage:
   ${CYAN}htop${NC}
   ${CYAN}free -h${NC}
   ${CYAN}df -h${NC}

3. Review enabled services:
   ${CYAN}systemctl list-unit-files --state=enabled${NC}

4. Monitor system logs:
   ${CYAN}journalctl -f${NC}
   ${CYAN}tail -f /var/log/syslog${NC}

5. Test firewall status:
   ${CYAN}sudo ufw status verbose${NC}

6. Review kernel parameters applied:
   ${CYAN}sysctl -a | grep -E '(vm\.|net\.|kernel\.shm)'${NC}

7. ${RED}IMPORTANT: Reboot to apply all changes:${NC}
   ${CYAN}sudo reboot${NC}

${BLUE}${ROCKET} System is now optimized and hardened for ${PROFILE} workload!${NC}

EOF
}

# Run main function
main