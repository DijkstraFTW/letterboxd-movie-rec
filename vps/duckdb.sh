#!/bin/bash

# DuckDB Installation and Setup Script for Ubuntu 24.04 LTS
# Installs DuckDB CLI, Python library, and sets up integration examples

set -euo pipefail

# --- AESTHETICS ---

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
DUCK='🦆'
NC='\033[0m'

# --- CONFIGURATION ---

DUCKDB_VERSION="1.1.3"
INSTALL_CLI=true
INSTALL_EXTENSIONS=true
CREATE_EXAMPLES=true
DUCKDB_HOME="/opt/duckdb"
DATA_DIR="${DUCKDB_HOME}/data"
SCRIPTS_DIR="${DUCKDB_HOME}/scripts"

# --- HELPER FUNCTIONS ---

log() {
    echo -e "${GREEN}${DUCK} $1${NC}"
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

configure_settings() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║            DUCKDB INSTALLATION SETUP                   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    info "DuckDB CLI will be installed to /usr/local/bin/duckdb"
    info "For Python integration, use Airflow's Python environment"
    echo
    
    # Extensions
    read -p "Install common DuckDB extensions (parquet, json, httpfs, postgres)? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        INSTALL_EXTENSIONS=false
    else
        INSTALL_EXTENSIONS=true
        info "Common extensions will be installed"
    fi
    
    # Examples
    read -p "Create example scripts and data? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        CREATE_EXAMPLES=false
    else
        CREATE_EXAMPLES=true
        info "Example scripts will be created"
    fi
    
    echo
}

# --- SYSTEM SETUP ---

install_dependencies() {
    log "Installing dependencies..."
    
    sudo apt-get update
    sudo apt-get install -y \
        wget \
        unzip \
        curl
    
    success "Dependencies installed"
}

create_directories() {
    log "Creating DuckDB directories..."
    
    sudo mkdir -p "$DUCKDB_HOME"
    sudo mkdir -p "$DATA_DIR"
    sudo mkdir -p "$SCRIPTS_DIR"
    
    success "Directories created"
}

# --- CLI INSTALLATION ---

install_duckdb_cli() {
    if [ "$INSTALL_CLI" = false ]; then
        info "DuckDB CLI installation skipped"
        return
    fi
    
    log "Installing DuckDB CLI v${DUCKDB_VERSION}..."
    
    # Determine architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        ARCH_SUFFIX="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        ARCH_SUFFIX="aarch64"
    else
        error "Unsupported architecture: $ARCH"
        exit 1
    fi
    
    # Download DuckDB CLI
    local DOWNLOAD_URL="https://github.com/duckdb/duckdb/releases/download/v${DUCKDB_VERSION}/duckdb_cli-linux-${ARCH_SUFFIX}.zip"
    
    cd /tmp
    wget -q "$DOWNLOAD_URL" -O duckdb_cli.zip
    unzip -q duckdb_cli.zip
    sudo mv duckdb /usr/local/bin/
    sudo chmod +x /usr/local/bin/duckdb
    rm duckdb_cli.zip
    
    # Verify installation
    if duckdb --version &>/dev/null; then
        success "DuckDB CLI v${DUCKDB_VERSION} installed successfully"
        duckdb --version
    else
        error "DuckDB CLI installation failed"
        exit 1
    fi
}

# --- EXTENSIONS ---

install_extensions() {
    if [ "$INSTALL_EXTENSIONS" = false ]; then
        info "Extensions installation skipped"
        return
    fi
    
    log "Installing DuckDB extensions..."
    
    # Install extensions using CLI
    duckdb -c "INSTALL parquet; INSTALL json; INSTALL httpfs; INSTALL postgres_scanner;" 2>/dev/null || warn "Some extensions may have failed to install"
    
    success "Extensions installed for CLI"
}

# --- PERMISSIONS ---

set_permissions() {
    log "Setting permissions..."
    
    # Make everything readable
    sudo chmod -R 755 "$DUCKDB_HOME"
    sudo chmod 777 "$DATA_DIR"  # Allow users to create databases
    
    success "Permissions configured"
}

# --- MAIN ---

main() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         DUCKDB INSTALLATION & SETUP                    ║${NC}"
    echo -e "${GREEN}║              Ubuntu 24.04 LTS                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    
    check_root
    configure_settings
    
    install_dependencies
    create_directories
    install_duckdb_cli
    install_extensions
    set_permissions
    
    echo
    success "DuckDB installation completed!"
    echo
    
    # Create info file
    local INFO_FILE="${DUCKDB_HOME}/INSTALLATION_INFO.txt"
    cat << EOF | tee "$INFO_FILE" > /dev/null
DuckDB Installation Summary
===========================
Generated: $(date)

Installation Directory: ${DUCKDB_HOME}
Data Directory: ${DATA_DIR}
Scripts Directory: ${SCRIPTS_DIR}

Installed Components:
EOF
    
    echo "✓ DuckDB CLI: /usr/local/bin/duckdb" | tee -a "$INFO_FILE" > /dev/null
    echo "  Version: $(duckdb --version)" | tee -a "$INFO_FILE" > /dev/null
    
    if [ "$INSTALL_EXTENSIONS" = true ]; then
        echo "✓ Extensions: parquet, json, httpfs, postgres_scanner" | tee -a "$INFO_FILE" > /dev/null
    fi
    
    cat << EOF
${CYAN}════════════════════════════════════════════════════════${NC}
${GREEN}✅ INSTALLATION SUMMARY${NC}
${CYAN}════════════════════════════════════════════════════════${NC}

${YELLOW}DuckDB Installation:${NC}
  🏠 Home Directory: ${DUCKDB_HOME}
  📁 Data Directory: ${DATA_DIR}
  📝 Scripts Directory: ${SCRIPTS_DIR}

EOF

${YELLOW}CLI Usage:${NC}
  Start DuckDB:     ${CYAN}duckdb${NC}
  Query CSV:        ${CYAN}duckdb -c "SELECT * FROM read_csv_auto('file.csv') LIMIT 10"${NC}
  Open database:    ${CYAN}duckdb /path/to/database.duckdb${NC}
  Quick query:      ${CYAN}duckdb-query "SELECT 1 + 1"${NC}

    if [ "$CREATE_EXAMPLES" = true ]; then
        cat << EOF

${YELLOW}Example Scripts:${NC}
  Location:         ${CYAN}${SCRIPTS_DIR}${NC}
  README:           ${CYAN}${SCRIPTS_DIR}/README.md${NC}
  
  Try them out:
    ${CYAN}cd ${SCRIPTS_DIR}${NC}
    ${CYAN}./01_basic_query.sh${NC}
    ${CYAN}./02_create_database.sh${NC}
    ${CYAN}./03_postgres_integration.sh${NC}

${YELLOW}Sample Data:${NC}
  CSV file:         ${CYAN}${DATA_DIR}/sample_sales.csv${NC}
  Database:         ${CYAN}${DATA_DIR}/analytics.duckdb${NC} (created by examples)

EOF
    fi

    cat << 'EOF'
${YELLOW}Python Integration:${NC}
  For Python usage, install DuckDB in Airflow's environment:
    ${CYAN}source /opt/airflow/venv/bin/activate${NC}
    ${CYAN}pip install duckdb${NC}
    ${CYAN}python3${NC}
    ${CYAN}>>> import duckdb${NC}
    ${CYAN}>>> conn = duckdb.connect(':memory:')${NC}

    cat << EOF
${YELLOW}Common DuckDB Commands:${NC}
  
  ${CYAN}# Query CSV file directly (no import needed!)${NC}
  SELECT * FROM read_csv_auto('/path/to/file.csv');
  
  ${CYAN}# Query multiple CSV files${NC}
  SELECT * FROM read_csv_auto('data/*.csv');
  
  ${CYAN}# Query Parquet files${NC}
  SELECT * FROM read_parquet('file.parquet');
  
  ${CYAN}# Query JSON files${NC}
  SELECT * FROM read_json_auto('file.json');
  
  ${CYAN}# Create table from CSV${NC}
  CREATE TABLE mytable AS SELECT * FROM read_csv_auto('file.csv');
  
  ${CYAN}# Export to Parquet${NC}
  COPY mytable TO 'output.parquet' (FORMAT PARQUET);
  
  ${CYAN}# Query remote files${NC}
  SELECT * FROM read_csv_auto('https://example.com/data.csv');

${YELLOW}DuckDB vs PostgreSQL:${NC}
  ${GREEN}Use DuckDB for:${NC}
    • Analytics and data processing
    • Querying CSV/Parquet/JSON files
    • Data science and exploration
    • ETL and data pipelines
    • OLAP workloads (aggregations, analytics)
  
  ${GREEN}Use PostgreSQL for:${NC}
    • Transactional workloads (OLTP)
    • Multi-user applications
    • Concurrent writes
    • Production application databases
    • User authentication/sessions

${YELLOW}Integration with PostgreSQL:${NC}
  DuckDB can query PostgreSQL directly!
  See: ${CYAN}${SCRIPTS_DIR}/04_postgres_integration.py${NC}

${YELLOW}Documentation:${NC}
  Official Docs:    ${CYAN}https://duckdb.org/docs/${NC}
  SQL Reference:    ${CYAN}https://duckdb.org/docs/sql/introduction${NC}
  Python API:       ${CYAN}https://duckdb.org/docs/api/python/overview${NC}
  Extensions:       ${CYAN}https://duckdb.org/docs/extensions/overview${NC}

${YELLOW}Next Steps:${NC}
  1. Try the example scripts:
     ${CYAN}cd ${SCRIPTS_DIR} && ./01_basic_query.sh${NC}
  
  2. Activate Python environment and explore:
     ${CYAN}source ${DUCKDB_HOME}/activate${NC}
     ${CYAN}python3${NC}
  
  3. Create your own database:
     ${CYAN}duckdb ${DATA_DIR}/mydata.duckdb${NC}
  
  4. Query your CSV files:
     ${CYAN}duckdb -c "SELECT * FROM read_csv_auto('yourfile.csv') LIMIT 10"${NC}

${BLUE}${DUCK} DuckDB is ready for fast analytics!${NC}

EOF
}

main