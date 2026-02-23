#!/bin/bash

# Apache Airflow Installation Script for Ubuntu 24.04 LTS
# Installs Airflow with PostgreSQL backend and production-ready configuration

set -euo pipefail

# --- AESTHETICS ---

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- CONFIGURATION ---

AIRFLOW_HOME="/opt/airflow"
AIRFLOW_USER="airflow"
AIRFLOW_VERSION="2.10.4"
PYTHON_VERSION="3.11"
AIRFLOW_PORT=8080
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="airflow"
POSTGRES_USER="airflow"
POSTGRES_PASSWORD=""
AIRFLOW_ADMIN_USER="admin"
AIRFLOW_ADMIN_PASSWORD=""
AIRFLOW_ADMIN_EMAIL="admin@localhost"
FERNET_KEY=""
EXECUTOR="LocalExecutor"  # LocalExecutor or CeleryExecutor
INSTALL_REDIS=false
REDIS_HOST="localhost"
REDIS_PORT="6379"

# --- HELPER FUNCTIONS ---

log() {
    echo -e "${GREEN}✈️  $1${NC}"
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

check_postgres() {
    if ! command -v psql &> /dev/null; then
        error "PostgreSQL is not installed. Please install PostgreSQL first."
        echo "Run: sudo apt install postgresql postgresql-contrib"
        exit 1
    fi
    
    if ! sudo systemctl is-active --quiet postgresql; then
        error "PostgreSQL is not running. Please start PostgreSQL first."
        echo "Run: sudo systemctl start postgresql"
        exit 1
    fi
    
    success "PostgreSQL detected and running"
}

# --- CONFIGURATION PROMPTS ---

configure_settings() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         APACHE AIRFLOW CONFIGURATION SETUP             ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo

    # Check if running in non-interactive mode (CI/CD)
    if [ "${AIRFLOW_NON_INTERACTIVE:-false}" = "true" ]; then
        info "Running in non-interactive mode"

        # Executor selection from env var or default
        if [ "${AIRFLOW_EXECUTOR:-LocalExecutor}" = "CeleryExecutor" ]; then
            EXECUTOR="CeleryExecutor"
            INSTALL_REDIS=true
            info "CeleryExecutor selected - Redis support will be configured"
        else
            EXECUTOR="LocalExecutor"
            info "LocalExecutor selected"
        fi

        # PostgreSQL configuration from env vars with defaults
        POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
        POSTGRES_PORT="${POSTGRES_PORT:-5432}"
        POSTGRES_DB="${POSTGRES_DB:-airflow}"
        POSTGRES_USER="${POSTGRES_USER:-airflow}"
        POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)}"

        # Admin user configuration from env vars with defaults
        AIRFLOW_ADMIN_USER="${AIRFLOW_ADMIN_USER:-admin}"
        AIRFLOW_ADMIN_EMAIL="${AIRFLOW_ADMIN_EMAIL:-admin@localhost}"
        AIRFLOW_ADMIN_PASSWORD="${AIRFLOW_ADMIN_PASSWORD:-$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)}"

        # Web server port
        AIRFLOW_PORT="${AIRFLOW_PORT:-8080}"

        # Generate Fernet key or use provided one
        if [ -z "${FERNET_KEY}" ]; then
            FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
        fi

        info "Configuration completed (non-interactive)"
        echo
        return
    fi

    # Interactive mode (original behavior)
    # Executor selection
    echo -e "${YELLOW}Executor Selection:${NC}"
    echo "  1) LocalExecutor - Single machine, simpler (recommended for most)"
    echo "  2) CeleryExecutor - Distributed, requires Redis/RabbitMQ"
    echo
    read -p "Select executor (1-2) [1]: " executor_choice
    executor_choice=${executor_choice:-1}

    if [ "$executor_choice" = "2" ]; then
        EXECUTOR="CeleryExecutor"
        INSTALL_REDIS=true
        info "CeleryExecutor selected - Redis support will be configured"
    else
        EXECUTOR="LocalExecutor"
        info "LocalExecutor selected"
    fi
    echo

    # PostgreSQL configuration
    echo -e "${YELLOW}PostgreSQL Database Configuration:${NC}"
    read -p "PostgreSQL host [localhost]: " pg_host
    POSTGRES_HOST=${pg_host:-localhost}

    read -p "PostgreSQL port [5432]: " pg_port
    POSTGRES_PORT=${pg_port:-5432}

    read -p "Database name [airflow]: " pg_db
    POSTGRES_DB=${pg_db:-airflow}

    read -p "Database user [airflow]: " pg_user
    POSTGRES_USER=${pg_user:-airflow}

    while true; do
        read -sp "Database password (leave empty to auto-generate): " pg_pass
        echo
        if [ -z "$pg_pass" ]; then
            POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
            info "Auto-generated database password: ${POSTGRES_PASSWORD}"
            break
        elif [ ${#pg_pass} -lt 12 ]; then
            warn "Password too short. Please use at least 12 characters."
        else
            POSTGRES_PASSWORD="$pg_pass"
            break
        fi
    done
    echo

    # Admin user configuration
    echo -e "${YELLOW}Airflow Admin User Configuration:${NC}"
    read -p "Admin username [admin]: " admin_user
    AIRFLOW_ADMIN_USER=${admin_user:-admin}

    read -p "Admin email [admin@localhost]: " admin_email
    AIRFLOW_ADMIN_EMAIL=${admin_email:-admin@localhost}

    while true; do
        read -sp "Admin password (leave empty to auto-generate): " admin_pass
        echo
        if [ -z "$admin_pass" ]; then
            AIRFLOW_ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
            info "Auto-generated admin password: ${AIRFLOW_ADMIN_PASSWORD}"
            break
        elif [ ${#admin_pass} -lt 12 ]; then
            warn "Password too short. Please use at least 12 characters."
        else
            AIRFLOW_ADMIN_PASSWORD="$admin_pass"
            break
        fi
    done
    echo

    # Web server port
    read -p "Airflow webserver port [8080]: " af_port
    AIRFLOW_PORT=${af_port:-8080}

    # Generate Fernet key
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    info "Configuration completed"
    echo
}

# --- SYSTEM SETUP ---

install_dependencies() {
    log "Installing system dependencies..."
    
    sudo apt-get update
    sudo apt-get install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        libpq-dev \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-setuptools \
        curl \
        git \
        sqlite3
    
    success "System dependencies installed"
}

create_airflow_user() {
    log "Creating Airflow system user..."
    
    if ! id "$AIRFLOW_USER" &>/dev/null; then
        sudo useradd -r -m -s /bin/bash "$AIRFLOW_USER"
        success "User '$AIRFLOW_USER' created"
    else
        info "User '$AIRFLOW_USER' already exists"
    fi
}

setup_directories() {
    log "Setting up Airflow directories..."
    
    sudo mkdir -p "$AIRFLOW_HOME"
    sudo mkdir -p "$AIRFLOW_HOME/dags"
    sudo mkdir -p "$AIRFLOW_HOME/logs"
    sudo mkdir -p "$AIRFLOW_HOME/plugins"
    sudo mkdir -p "$AIRFLOW_HOME/config"
    
    sudo chown -R "$AIRFLOW_USER:$AIRFLOW_USER" "$AIRFLOW_HOME"
    
    success "Airflow directories created"
}

# --- DATABASE SETUP ---

setup_postgres_database() {
    log "Setting up PostgreSQL database for Airflow..."
    
    # Create database user
    sudo -u postgres psql -c "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD';" 2>/dev/null || \
        warn "User $POSTGRES_USER may already exist"
    
    # Create database
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;" 2>/dev/null || \
        warn "Database $POSTGRES_DB may already exist"
    
    # Grant privileges
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;"
    
    success "PostgreSQL database configured"
}

# --- AIRFLOW INSTALLATION ---

install_airflow() {
    log "Installing Apache Airflow ${AIRFLOW_VERSION}..."
    
    # Set up Python virtual environment
    sudo -u "$AIRFLOW_USER" python3 -m venv "$AIRFLOW_HOME/venv"
    
    # Construct constraints URL
    local PYTHON_VERSION_SHORT=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
    local CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION_SHORT}.txt"
    
    # Install Airflow with PostgreSQL support
    sudo -u "$AIRFLOW_USER" bash -c "
        source $AIRFLOW_HOME/venv/bin/activate
        export AIRFLOW_HOME=$AIRFLOW_HOME
        pip install --upgrade pip
        pip install 'apache-airflow[postgres,celery,redis]==${AIRFLOW_VERSION}' --constraint '${CONSTRAINT_URL}'
    "
    
    success "Apache Airflow installed"
}

# --- AIRFLOW CONFIGURATION ---

configure_airflow() {
    log "Configuring Airflow..."
    
    # Set environment variable
    export AIRFLOW_HOME="$AIRFLOW_HOME"
    
    # Initialize Airflow database (creates airflow.cfg)
    sudo -u "$AIRFLOW_USER" bash -c "
        source $AIRFLOW_HOME/venv/bin/activate
        export AIRFLOW_HOME=$AIRFLOW_HOME
        airflow db init
    "
    
    # Configure airflow.cfg
    local AIRFLOW_CFG="$AIRFLOW_HOME/airflow.cfg"
    
    # Database connection
    local SQL_ALCHEMY_CONN="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
    sudo -u "$AIRFLOW_USER" sed -i "s|^sql_alchemy_conn = .*|sql_alchemy_conn = ${SQL_ALCHEMY_CONN}|" "$AIRFLOW_CFG"
    
    # Executor
    sudo -u "$AIRFLOW_USER" sed -i "s/^executor = .*/executor = ${EXECUTOR}/" "$AIRFLOW_CFG"
    
    # Fernet key
    sudo -u "$AIRFLOW_USER" sed -i "s|^fernet_key = .*|fernet_key = ${FERNET_KEY}|" "$AIRFLOW_CFG"
    
    # Web server configuration
    sudo -u "$AIRFLOW_USER" sed -i "s/^web_server_port = .*/web_server_port = ${AIRFLOW_PORT}/" "$AIRFLOW_CFG"
    sudo -u "$AIRFLOW_USER" sed -i "s/^expose_config = .*/expose_config = False/" "$AIRFLOW_CFG"
    
    # Security
    sudo -u "$AIRFLOW_USER" sed -i "s/^load_examples = .*/load_examples = False/" "$AIRFLOW_CFG"
    sudo -u "$AIRFLOW_USER" sed -i "s/^donot_pickle = .*/donot_pickle = True/" "$AIRFLOW_CFG"
    
    # DAG configuration
    sudo -u "$AIRFLOW_USER" sed -i "s|^dags_folder = .*|dags_folder = ${AIRFLOW_HOME}/dags|" "$AIRFLOW_CFG"
    
    # Logging
    sudo -u "$AIRFLOW_USER" sed -i "s|^base_log_folder = .*|base_log_folder = ${AIRFLOW_HOME}/logs|" "$AIRFLOW_CFG"
    
    # If CeleryExecutor, configure broker
    if [ "$EXECUTOR" = "CeleryExecutor" ]; then
        local BROKER_URL="redis://${REDIS_HOST}:${REDIS_PORT}/0"
        local RESULT_BACKEND="db+postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
        
        sudo -u "$AIRFLOW_USER" sed -i "s|^broker_url = .*|broker_url = ${BROKER_URL}|" "$AIRFLOW_CFG"
        sudo -u "$AIRFLOW_USER" sed -i "s|^result_backend = .*|result_backend = ${RESULT_BACKEND}|" "$AIRFLOW_CFG"
    fi
    
    # Upgrade database
    sudo -u "$AIRFLOW_USER" bash -c "
        source $AIRFLOW_HOME/venv/bin/activate
        export AIRFLOW_HOME=$AIRFLOW_HOME
        airflow db upgrade
    "
    
    success "Airflow configured"
}

# --- USER SETUP ---

create_admin_user() {
    log "Creating Airflow admin user..."
    
    sudo -u "$AIRFLOW_USER" bash -c "
        source $AIRFLOW_HOME/venv/bin/activate
        export AIRFLOW_HOME=$AIRFLOW_HOME
        airflow users create \
            --username ${AIRFLOW_ADMIN_USER} \
            --firstname Admin \
            --lastname User \
            --role Admin \
            --email ${AIRFLOW_ADMIN_EMAIL} \
            --password ${AIRFLOW_ADMIN_PASSWORD}
    " 2>/dev/null || warn "Admin user may already exist"
    
    success "Admin user created"
}

# --- SYSTEMD SERVICES ---

create_systemd_services() {
    log "Creating systemd services..."
    
    # Webserver service
    cat << EOF | sudo tee /etc/systemd/system/airflow-webserver.service > /dev/null
[Unit]
Description=Airflow webserver daemon
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Environment="AIRFLOW_HOME=${AIRFLOW_HOME}"
User=${AIRFLOW_USER}
Group=${AIRFLOW_USER}
Type=simple
ExecStart=${AIRFLOW_HOME}/venv/bin/airflow webserver --port ${AIRFLOW_PORT}
Restart=on-failure
RestartSec=5s
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    
    # Scheduler service
    cat << EOF | sudo tee /etc/systemd/system/airflow-scheduler.service > /dev/null
[Unit]
Description=Airflow scheduler daemon
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Environment="AIRFLOW_HOME=${AIRFLOW_HOME}"
User=${AIRFLOW_USER}
Group=${AIRFLOW_USER}
Type=simple
ExecStart=${AIRFLOW_HOME}/venv/bin/airflow scheduler
Restart=on-failure
RestartSec=5s
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    
    # If CeleryExecutor, create worker service
    if [ "$EXECUTOR" = "CeleryExecutor" ]; then
        cat << EOF | sudo tee /etc/systemd/system/airflow-worker.service > /dev/null
[Unit]
Description=Airflow celery worker daemon
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Environment="AIRFLOW_HOME=${AIRFLOW_HOME}"
User=${AIRFLOW_USER}
Group=${AIRFLOW_USER}
Type=simple
ExecStart=${AIRFLOW_HOME}/venv/bin/airflow celery worker
Restart=on-failure
RestartSec=5s
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    success "Systemd services created"
}

# --- SERVICE MANAGEMENT ---

start_services() {
    log "Starting Airflow services..."
    
    sudo systemctl enable airflow-webserver
    sudo systemctl enable airflow-scheduler
    sudo systemctl start airflow-webserver
    sudo systemctl start airflow-scheduler
    
    if [ "$EXECUTOR" = "CeleryExecutor" ]; then
        sudo systemctl enable airflow-worker
        sudo systemctl start airflow-worker
    fi
    
    sleep 5
    
    # Check status
    if sudo systemctl is-active --quiet airflow-webserver && \
       sudo systemctl is-active --quiet airflow-scheduler; then
        success "Airflow services started successfully"
    else
        warn "Some services may have failed to start. Check status with:"
        echo "  sudo systemctl status airflow-webserver"
        echo "  sudo systemctl status airflow-scheduler"
    fi
}

# --- FIREWALL ---

configure_firewall() {
    log "Configuring firewall..."
    
    if command -v ufw &> /dev/null; then
        sudo ufw allow ${AIRFLOW_PORT}/tcp
        success "Firewall configured - port ${AIRFLOW_PORT} opened"
    else
        warn "UFW not found. Please manually open port ${AIRFLOW_PORT}"
    fi
}

# --- SAMPLE DAG ---

create_sample_dag() {
    log "Creating sample DAG..."
    
    cat << 'EOF' | sudo -u "$AIRFLOW_USER" tee "$AIRFLOW_HOME/dags/sample_dag.py" > /dev/null
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'sample_hello_world',
    default_args=default_args,
    description='A simple hello world DAG',
    schedule_interval=None,  # Manual trigger only
    catchup=False,
)

def print_hello():
    return 'Hello from Airflow!'

hello_task = PythonOperator(
    task_id='hello_task',
    python_callable=print_hello,
    dag=dag,
)

bash_task = BashOperator(
    task_id='bash_task',
    bash_command='echo "This is a bash command"',
    dag=dag,
)

hello_task >> bash_task
EOF
    
    success "Sample DAG created at ${AIRFLOW_HOME}/dags/sample_dag.py"
}

# --- MAIN ---

main() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      APACHE AIRFLOW INSTALLATION & SETUP               ║${NC}"
    echo -e "${GREEN}║              Ubuntu 24.04 LTS                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    check_root
    check_postgres
    configure_settings
    
    install_dependencies
    create_airflow_user
    setup_directories
    setup_postgres_database
    install_airflow
    configure_airflow
    create_admin_user
    create_systemd_services
    start_services
    configure_firewall
    create_sample_dag
    
    echo
    success "Apache Airflow installation completed!"
    echo
    
    # Save credentials
    local CREDS_FILE="/root/airflow-credentials.txt"
    cat << EOF | sudo tee "$CREDS_FILE" > /dev/null
Apache Airflow Configuration
=============================
Generated: $(date)

Airflow Home: ${AIRFLOW_HOME}
Airflow Version: ${AIRFLOW_VERSION}
Executor: ${EXECUTOR}

Web UI:
- URL: http://$(hostname -I | awk '{print $1}'):${AIRFLOW_PORT}
- Username: ${AIRFLOW_ADMIN_USER}
- Password: ${AIRFLOW_ADMIN_PASSWORD}

PostgreSQL Database:
- Host: ${POSTGRES_HOST}
- Port: ${POSTGRES_PORT}
- Database: ${POSTGRES_DB}
- User: ${POSTGRES_USER}
- Password: ${POSTGRES_PASSWORD}

Fernet Key: ${FERNET_KEY}

Connection String:
postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

Configuration File: ${AIRFLOW_HOME}/airflow.cfg
DAGs Directory: ${AIRFLOW_HOME}/dags
Logs Directory: ${AIRFLOW_HOME}/logs

IMPORTANT: Keep this file secure and delete it after copying the credentials!
EOF
    
    sudo chmod 600 "$CREDS_FILE"
    
    cat << EOF
${CYAN}════════════════════════════════════════════════════════${NC}
${GREEN}✅ INSTALLATION SUMMARY${NC}
${CYAN}════════════════════════════════════════════════════════${NC}

${YELLOW}Airflow Configuration:${NC}
  🏠 Home Directory: ${AIRFLOW_HOME}
  ⚙️  Executor: ${EXECUTOR}
  🌐 Web UI Port: ${AIRFLOW_PORT}
  📁 DAGs Folder: ${AIRFLOW_HOME}/dags

${YELLOW}Access Information:${NC}
  🌍 URL: ${CYAN}http://$(hostname -I | awk '{print $1}'):${AIRFLOW_PORT}${NC}
  👤 Username: ${AIRFLOW_ADMIN_USER}
  🔑 Password: ${AIRFLOW_ADMIN_PASSWORD}

${YELLOW}Database:${NC}
  🐘 PostgreSQL Database: ${POSTGRES_DB}
  👤 DB User: ${POSTGRES_USER}
  🔑 DB Password: ${POSTGRES_PASSWORD}

${YELLOW}Credentials File:${NC}
  📄 Location: ${CREDS_FILE}
  ${RED}⚠️  IMPORTANT: This file contains sensitive information!${NC}
  ${RED}    Copy the credentials and delete this file:${NC}
      ${CYAN}sudo cat ${CREDS_FILE}${NC}
      ${CYAN}sudo rm ${CREDS_FILE}${NC}

${YELLOW}Service Management:${NC}
  Status:        ${CYAN}sudo systemctl status airflow-webserver${NC}
  Status:        ${CYAN}sudo systemctl status airflow-scheduler${NC}
EOF

    if [ "$EXECUTOR" = "CeleryExecutor" ]; then
        echo "  Status:        ${CYAN}sudo systemctl status airflow-worker${NC}"
    fi

    cat << EOF
  Restart:       ${CYAN}sudo systemctl restart airflow-webserver${NC}
  Restart:       ${CYAN}sudo systemctl restart airflow-scheduler${NC}
  Logs:          ${CYAN}sudo journalctl -u airflow-webserver -f${NC}
  Logs:          ${CYAN}sudo journalctl -u airflow-scheduler -f${NC}

${YELLOW}Airflow CLI (as airflow user):${NC}
  ${CYAN}sudo -u airflow bash${NC}
  ${CYAN}source ${AIRFLOW_HOME}/venv/bin/activate${NC}
  ${CYAN}export AIRFLOW_HOME=${AIRFLOW_HOME}${NC}
  ${CYAN}airflow dags list${NC}
  ${CYAN}airflow dags trigger sample_hello_world${NC}

${YELLOW}DAG Development:${NC}
  1. Create DAGs in: ${AIRFLOW_HOME}/dags/
  2. Airflow will automatically detect new DAGs
  3. Check DAG syntax: ${CYAN}airflow dags list-import-errors${NC}
  4. Sample DAG created: sample_hello_world

${YELLOW}Next Steps:${NC}
  1. Access the web UI and log in with the credentials above
  2. Explore the sample DAG (sample_hello_world)
  3. Create your own DAGs in ${AIRFLOW_HOME}/dags/
  4. Configure connections and variables in the web UI
  5. Set up email notifications if needed
  6. Review and tune airflow.cfg for your needs

${YELLOW}Useful Commands:${NC}
  List DAGs:         ${CYAN}airflow dags list${NC}
  Trigger DAG:       ${CYAN}airflow dags trigger <dag_id>${NC}
  List tasks:        ${CYAN}airflow tasks list <dag_id>${NC}
  Test task:         ${CYAN}airflow tasks test <dag_id> <task_id> <date>${NC}

${BLUE}✈️  Apache Airflow is ready for orchestration!${NC}

EOF
}

main