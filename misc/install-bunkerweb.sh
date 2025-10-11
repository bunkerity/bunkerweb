#!/bin/bash

# BunkerWeb Easy Install Script
# Automatically installs BunkerWeb on supported Linux distributions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
# Hardcoded default version (immutable reference)
DEFAULT_BUNKERWEB_VERSION="1.6.5"
# Mutable effective version (can be overridden by --version)
BUNKERWEB_VERSION="$DEFAULT_BUNKERWEB_VERSION"
NGINX_VERSION=""
ENABLE_WIZARD=""
FORCE_INSTALL="no"
INTERACTIVE_MODE="yes"
CROWDSEC_INSTALL="no"
CROWDSEC_APPSEC_INSTALL="no"
INSTALL_TYPE=""
BUNKERWEB_INSTANCES_INPUT=""
UPGRADE_SCENARIO="no"
BACKUP_DIRECTORY=""
AUTO_BACKUP="yes"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to run command with error checking
run_cmd() {
    echo -e "${BLUE}[CMD]${NC} $*"
    if ! "$@"; then
        print_error "Command failed: $*"
        exit 1
    fi
}

# Function to check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        print_error "This script must be run as root. Please use sudo or run as root."
        exit 1
    fi
}

# Function to detect operating system
detect_os() {
    DISTRO_ID=""
    DISTRO_VERSION=""
    DISTRO_CODENAME=""

    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
        DISTRO_VERSION="$VERSION_ID"
        DISTRO_CODENAME="$VERSION_CODENAME"
    elif [ -f /etc/redhat-release ]; then
        DISTRO_ID="redhat"
        DISTRO_VERSION=$(grep -oE '[0-9]+\.[0-9]+' /etc/redhat-release | head -1)
    elif command -v lsb_release >/dev/null 2>&1; then
        DISTRO_ID=$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]')
        DISTRO_VERSION=$(lsb_release -rs 2>/dev/null)
        DISTRO_CODENAME=$(lsb_release -cs 2>/dev/null)
    else
        print_error "Unable to detect operating system"
        exit 1
    fi

    print_status "Detected OS: $DISTRO_ID $DISTRO_VERSION"
}

# Function to ask user preferences
ask_user_preferences() {
    if [ "$INTERACTIVE_MODE" = "yes" ]; then
        echo
        print_step "Configuration Options"
        echo

        # Ask about installation type
        if [ -z "$INSTALL_TYPE" ]; then
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}📦 Installation Type${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "Choose the type of installation based on your needs:"
            echo "  1) Full Stack (default): All-in-one installation (BunkerWeb, Scheduler, UI)."
            echo "  2) Manager: Installs Scheduler and UI to manage remote BunkerWeb workers."
            echo "  3) Worker: Installs only the BunkerWeb instance, to be managed remotely."
            echo "  4) Scheduler Only: Installs only the Scheduler component."
            echo "  5) Web UI Only: Installs only the Web UI component."
            echo
            while true; do
                echo -e "${YELLOW}Select installation type (1-5) [1]:${NC} "
                read -p "" -r
                REPLY=${REPLY:-1}
                case $REPLY in
                    1) INSTALL_TYPE="full"; break ;;
                    2) INSTALL_TYPE="manager"; break ;;
                    3) INSTALL_TYPE="worker"; break ;;
                    4) INSTALL_TYPE="scheduler"; break ;;
                    5) INSTALL_TYPE="ui"; break ;;
                    *) echo "Invalid option. Please choose a number between 1 and 5." ;;
                esac
            done
        fi

        if [[ "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "scheduler" ]]; then
            if [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🔗 BunkerWeb Instances Configuration${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "Please provide the list of BunkerWeb instances (workers) to manage."
                echo "Format: a space-separated list of IP addresses or hostnames."
                echo "Example: 192.168.1.10 192.168.1.11"
                echo
                while true; do
                    echo -e "${YELLOW}Enter BunkerWeb instances:${NC} "
                    read -p "" -r BUNKERWEB_INSTANCES_INPUT
                    if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
                        break
                    else
                        print_warning "This field cannot be empty for Manager/Scheduler installations."
                    fi
                done
            fi
        fi

        # Ask about setup wizard
        if [ -z "$ENABLE_WIZARD" ]; then
            if [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "scheduler" ]; then
                ENABLE_WIZARD="no"
            else
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🧙 BunkerWeb Setup Wizard${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "The BunkerWeb setup wizard provides a web-based interface to:"
                echo "  • Complete initial configuration easily"
                echo "  • Set up your first protected service"
                echo "  • Configure SSL/TLS certificates"
                echo "  • Access the management interface"
                echo
                while true; do
                    echo -e "${YELLOW}Would you like to enable the setup wizard? (Y/n):${NC} "
                    read -p "" -r
                    case $REPLY in
                        [Yy]*|"")
                            ENABLE_WIZARD="yes"
                            break
                            ;;
                        [Nn]*)
                            ENABLE_WIZARD="no"
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            fi
        fi

        # Ask about CrowdSec installation
        if [ "$INSTALL_TYPE" != "worker" ] && [ "$INSTALL_TYPE" != "scheduler" ] && [ "$INSTALL_TYPE" != "ui" ]; then
            if [ -z "$CROWDSEC_INSTALL" ] || [ "$CROWDSEC_INSTALL" = "no" ]; then
                echo
                echo -e "${BLUE}========================================${NC}"
                echo -e "${BLUE}🦙 CrowdSec Intrusion Prevention${NC}"
                echo -e "${BLUE}========================================${NC}"
                echo "CrowdSec is a community-powered, open-source intrusion prevention engine that analyzes logs in real time to detect, block and share intelligence on malicious IPs."
                echo "It seamlessly integrates with BunkerWeb for automated threat remediation."
                echo
                while true; do
                    echo -e "${YELLOW}Would you like to automatically install and configure CrowdSec? (Y/n):${NC} "
                    read -p "" -r
                    case $REPLY in
                        [Yy]*|"")
                            CROWDSEC_INSTALL="yes"
                            break
                            ;;
                        [Nn]*)
                            CROWDSEC_INSTALL="no"
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            fi
        else
            # CrowdSec not applicable for worker, scheduler-only, or ui-only installations
            CROWDSEC_INSTALL="no"
        fi

        # Ask about API service enablement
        if [ -z "$SERVICE_API" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🧩 BunkerWeb API Service${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The BunkerWeb API provides a programmatic interface (FastAPI) to manage instances,"
            echo "perform actions (reload/stop), and integrate with external systems."
            echo "It is optional and disabled by default on Linux installations."
            echo
            while true; do
                echo -e "${YELLOW}Enable the API service? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*) SERVICE_API=yes; break ;;
                    ""|[Nn]*) SERVICE_API=no; break ;;
                    *) echo "Please answer yes (y) or no (n)." ;;
                esac
            done
        fi

        # Ask about AppSec installation if CrowdSec is chosen
        if [ "$CROWDSEC_INSTALL" = "yes" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🛡️ CrowdSec Application Security (AppSec)${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "CrowdSec Application Security Component (AppSec) adds advanced application security, turning CrowdSec into a full WAF."
            echo "It's optional, installs alongside CrowdSec, and integrates seamlessly with the engine."
            echo
            while true; do
                echo -e "${YELLOW}Would you like to install and configure the CrowdSec AppSec Component? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*|"")
                        CROWDSEC_APPSEC_INSTALL="yes"
                        break
                        ;;
                    [Nn]*)
                        CROWDSEC_APPSEC_INSTALL="no"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        echo
        print_status "Configuration summary:"
        echo "  🛡 BunkerWeb version: $BUNKERWEB_VERSION"
        case "$INSTALL_TYPE" in
            "full"|"") echo "  📦 Installation type: Full Stack" ;;
            "manager") echo "  📦 Installation type: Manager" ;;
            "worker") echo "  📦 Installation type: Worker" ;;
            "scheduler") echo "  📦 Installation type: Scheduler Only" ;;
            "ui") echo "  📦 Installation type: Web UI Only" ;;
        esac
        if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
            echo "  🔗 BunkerWeb instances: $BUNKERWEB_INSTANCES_INPUT"
        fi
        echo "  🧙 Setup wizard: $([ "$ENABLE_WIZARD" = "yes" ] && echo "Enabled" || echo "Disabled")"
        echo "  🖥 Operating system: $DISTRO_ID $DISTRO_VERSION"
        echo "  🟢 NGINX version: $NGINX_VERSION"
        if [ "$CROWDSEC_INSTALL" = "yes" ]; then
            if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
                echo "  🦙 CrowdSec: Will be installed (with AppSec Component)"
            else
                echo "  🦙 CrowdSec: Will be installed (without AppSec Component)"
            fi
        else
            echo "  🦙 CrowdSec: Not installed"
        fi
        echo
    fi
}

# Function to show RHEL database warning
show_rhel_database_warning() {
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]]; then
        echo
        print_warning "Important information for RHEL-based systems:"
        echo
        echo "If you plan to use an external database (recommended for production),"
        echo "you'll need to install the appropriate database client:"
        echo
        echo "  For MariaDB: dnf install mariadb"
        echo "  For MySQL:   dnf install mysql"
        echo "  For PostgreSQL: dnf install postgresql"
        echo
        echo "This is required for the BunkerWeb Scheduler to connect to your database."
        echo
        read -p "Press Enter to continue..." -r
    fi
}
check_supported_os() {
    case "$DISTRO_ID" in
        "debian")
            if [[ "$DISTRO_VERSION" != "12" && "$DISTRO_VERSION" != "13" ]]; then
                print_warning "Only Debian 12 (Bookworm) and 13 (Trixie) are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.28.0-1~$DISTRO_CODENAME"
            ;;
        "ubuntu")
            if [[ "$DISTRO_VERSION" != "22.04" && "$DISTRO_VERSION" != "24.04" ]]; then
                print_warning "Only Ubuntu 22.04 (Jammy) and 24.04 (Noble) are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.28.0-1~$DISTRO_CODENAME"
            ;;
        "fedora")
            if [[ "$DISTRO_VERSION" != "41" && "$DISTRO_VERSION" != "42" ]]; then
                print_warning "Only Fedora 41 and 42 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.28.0"
            ;;
        "rhel"|"rocky"|"almalinux")
            major_version=$(echo "$DISTRO_VERSION" | cut -d. -f1)
            if [[ "$major_version" != "8" && "$major_version" != "9" && "$major_version" != "10" ]]; then
                print_warning "Only RHEL 8, 9, and 10 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            NGINX_VERSION="1.28.0"
            ;;
        *)
            print_error "Unsupported operating system: $DISTRO_ID"
            print_error "Supported distributions: Debian 12/13, Ubuntu 22.04/24.04, Fedora 41/42, RHEL 8/9/10"
            exit 1
            ;;
    esac
}

# Function to install NGINX on Debian/Ubuntu
install_nginx_debian() {
    print_step "Installing NGINX on Debian/Ubuntu"

    # Install prerequisites
    run_cmd apt update
    run_cmd apt install -y curl gnupg2 ca-certificates lsb-release

    if [ "$DISTRO_ID" = "debian" ]; then
        run_cmd apt install -y debian-archive-keyring
    elif [ "$DISTRO_ID" = "ubuntu" ]; then
        run_cmd apt install -y ubuntu-keyring
    fi

    # Add NGINX repository
    curl -fsSL https://nginx.org/keys/nginx_signing.key | gpg --dearmor | tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/$DISTRO_ID $DISTRO_CODENAME nginx" | tee /etc/apt/sources.list.d/nginx.list

    # Update and install NGINX
    run_cmd apt update
    run_cmd apt install -y "nginx=$NGINX_VERSION"

    # Hold NGINX package to prevent upgrades
    run_cmd apt-mark hold nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

# Function to install NGINX on Fedora
install_nginx_fedora() {
    print_step "Installing NGINX on Fedora"

    # Install versionlock plugin
    run_cmd dnf install -y 'dnf-command(versionlock)'

    # Enable testing repository if needed
    if ! dnf info "nginx-$NGINX_VERSION" >/dev/null 2>&1; then
        print_status "Enabling updates-testing repository"
        if [ "$DISTRO_VERSION" = "40" ]; then
            run_cmd dnf config-manager --set-enabled updates-testing
        else
            run_cmd dnf config-manager setopt updates-testing.enabled=1
        fi
    fi

    # Install NGINX
    run_cmd dnf install -y "nginx-$NGINX_VERSION"

    # Lock NGINX version
    run_cmd dnf versionlock add nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

# Function to install NGINX on RHEL
install_nginx_rhel() {
    print_step "Installing NGINX on RHEL"

    # Install versionlock plugin
    run_cmd dnf install -y 'dnf-command(versionlock)'

    # Create NGINX repository file
    cat > /etc/yum.repos.d/nginx.repo << EOF
[nginx-stable]
name=nginx stable repo
baseurl=http://nginx.org/packages/centos/\$releasever/\$basearch/
gpgcheck=1
enabled=1
gpgkey=https://nginx.org/keys/nginx_signing.key
module_hotfixes=true

[nginx-mainline]
name=nginx mainline repo
baseurl=http://nginx.org/packages/mainline/centos/\$releasever/\$basearch/
gpgcheck=1
enabled=0
gpgkey=https://nginx.org/keys/nginx_signing.key
module_hotfixes=true
EOF

    # Install NGINX
    run_cmd dnf install -y "nginx-$NGINX_VERSION"

    # Lock NGINX version
    run_cmd dnf versionlock add nginx

    print_status "NGINX $NGINX_VERSION installed successfully"
}

# Function to install BunkerWeb on Debian/Ubuntu
install_bunkerweb_debian() {
    print_step "Installing BunkerWeb on Debian/Ubuntu"

    # Handle testing/dev version
    if [[ "$BUNKERWEB_VERSION" =~ (testing|dev) ]]; then
        print_status "Adding force-bad-version directive for testing/dev version"
        echo "force-bad-version" >> /etc/dpkg/dpkg.cfg
    fi

    # Set environment variables
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # Download and add BunkerWeb repository
    run_cmd curl -fsSL https://repo.bunkerweb.io/install/script.deb.sh -o /tmp/bunkerweb-repo.sh
    run_cmd bash /tmp/bunkerweb-repo.sh
    run_cmd rm -f /tmp/bunkerweb-repo.sh

    run_cmd apt update
    run_cmd apt install -y "bunkerweb=$BUNKERWEB_VERSION"

    # Hold BunkerWeb package to prevent upgrades
    run_cmd apt-mark hold bunkerweb

    print_status "BunkerWeb $BUNKERWEB_VERSION installed successfully"
}

# Function to install BunkerWeb on Fedora/RHEL
install_bunkerweb_rpm() {
    print_step "Installing BunkerWeb on $DISTRO_ID"

    # Set environment variables
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    # Add BunkerWeb repository and install
    run_cmd curl -fsSL https://repo.bunkerweb.io/install/script.rpm.sh -o /tmp/bunkerweb-repo.sh
    run_cmd bash /tmp/bunkerweb-repo.sh
    run_cmd rm -f /tmp/bunkerweb-repo.sh

    if [ "$DISTRO_ID" = "fedora" ]; then
        run_cmd dnf makecache
        run_cmd dnf install -y "bunkerweb-$BUNKERWEB_VERSION"
    else
        dnf check-update || true  # Don't fail if no updates available
        run_cmd dnf install -y "bunkerweb-$BUNKERWEB_VERSION"
    fi

    # Lock BunkerWeb version
    run_cmd dnf versionlock add bunkerweb

    print_status "BunkerWeb $BUNKERWEB_VERSION installed successfully"
}

# Function to install CrowdSec
install_crowdsec() {
    echo
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}CrowdSec Security Engine Installation${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    print_step "Installing CrowdSec security engine"

    # Ensure required dependencies
    for dep in curl gnupg2 ca-certificates; do
        if ! command -v $dep >/dev/null 2>&1; then
            print_status "Installing missing dependency: $dep"
            case "$DISTRO_ID" in
                "debian"|"ubuntu")
                    run_cmd apt update
                    run_cmd apt install -y $dep
                    ;;
                "fedora"|"rhel"|"rocky"|"almalinux")
                    run_cmd dnf install -y $dep
                    ;;
                *)
                    print_warning "Automatic install not supported on $DISTRO_ID"
                    ;;
            esac
        fi
    done

    echo -e "${YELLOW}--- Step 1: Add CrowdSec repository and install engine ---${NC}"
    print_step "Adding CrowdSec repository and installing engine"
    run_cmd curl -s https://install.crowdsec.net | sh
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            run_cmd apt install -y crowdsec
            ;;
        "fedora"|"rhel"|"rocky"|"almalinux")
            run_cmd dnf install -y crowdsec
            ;;
        *)
            print_error "Unsupported distribution: $DISTRO_ID"
            return
            ;;
    esac
    print_status "CrowdSec engine installed"

    echo -e "${YELLOW}--- Step 2: Configure log acquisition for BunkerWeb ---${NC}"
    print_step "Configuring CrowdSec to parse BunkerWeb logs"
    ACQ_FILE="/etc/crowdsec/acquis.yaml"
    ACQ_CONTENT="filenames:
  - /var/log/bunkerweb/access.log
  - /var/log/bunkerweb/error.log
  - /var/log/bunkerweb/modsec_audit.log
labels:
  type: nginx
"
    if [ -f "$ACQ_FILE" ]; then
        cp "$ACQ_FILE" "${ACQ_FILE}.bak"
        echo "$ACQ_CONTENT" >> "$ACQ_FILE"
        print_status "Appended BunkerWeb acquisition config to: $ACQ_FILE"
    else
        echo "$ACQ_CONTENT" > "$ACQ_FILE"
        print_status "Created acquisition file: $ACQ_FILE"
    fi

    echo -e "${YELLOW}--- Step 3: Update hub and install core collections/parsers ---${NC}"
    print_step "Updating hub and installing detection collections/parsers"
    cscli hub update
    cscli collections install crowdsecurity/nginx
    cscli parsers install crowdsecurity/geoip-enrich

    # AppSec installation if chosen
    if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
        echo -e "${YELLOW}--- Step 4: Install and configure CrowdSec AppSec Component ---${NC}"
        print_step "Installing and configuring CrowdSec AppSec Component"
        APPSEC_ACQ_FILE="/etc/crowdsec/acquis.d/appsec.yaml"
        APPSEC_ACQ_CONTENT="appsec_config: crowdsecurity/appsec-default
labels:
  type: appsec
listen_addr: 127.0.0.1:7422
source: appsec
"
        mkdir -p /etc/crowdsec/acquis.d
        echo "$APPSEC_ACQ_CONTENT" > "$APPSEC_ACQ_FILE"
        print_status "Created AppSec acquisition file: $APPSEC_ACQ_FILE"
        cscli collections install crowdsecurity/appsec-virtual-patching
        cscli collections install crowdsecurity/appsec-generic-rules
        print_status "Installed AppSec collections"
    fi

    echo -e "${YELLOW}--- Step 5: Register BunkerWeb bouncer(s) and retrieve API key ---${NC}"
    print_step "Registering BunkerWeb bouncer with CrowdSec"
    BOUNCER_KEY=$(cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6 --output raw)
    if [ -z "$BOUNCER_KEY" ]; then
        print_warning "Failed to retrieve API key; please register manually: cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6"
    else
        print_status "Bouncer Successfully registered"
    fi

    CROWDSEC_ENV_TMP="/var/tmp/crowdsec.env"
    {
        echo "USE_CROWDSEC=yes"
        echo "CROWDSEC_API=http://127.0.0.1:8080"
        if [ -n "$BOUNCER_KEY" ]; then
            echo "CROWDSEC_API_KEY=$BOUNCER_KEY"
        fi
        if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
            echo "CROWDSEC_APPSEC_URL=http://127.0.0.1:7422"
        fi
    } > "$CROWDSEC_ENV_TMP"

    echo
    echo -e "${GREEN}CrowdSec installed successfully${NC}"
    echo "See BunkerWeb docs for more: https://docs.bunkerweb.io/latest/features/#crowdsec"
    echo -e "${BLUE}========================================${NC}"
}

# Function to show final information
show_final_info() {
    echo
    echo "========================================="
    echo -e "${GREEN}BunkerWeb Installation Complete!${NC}"
    echo "========================================="
    echo
    echo "Services status:"
    systemctl status bunkerweb --no-pager -l || true
    systemctl status bunkerweb-scheduler --no-pager -l || true
    # Show API service status if present on this system
    if systemctl list-units --type=service --all | grep -q '^bunkerweb-api.service'; then
        systemctl status bunkerweb-api --no-pager -l || true
    fi

    if [ "$ENABLE_WIZARD" = "yes" ]; then
        systemctl status bunkerweb-ui --no-pager -l || true
    fi

    echo
    echo "Configuration:"
    echo "  - Main config: /etc/bunkerweb/variables.env"

    if [ "$ENABLE_WIZARD" = "yes" ]; then
        echo "  - UI config: /etc/bunkerweb/ui.env"
    fi

    echo "  - Scheduler config: /etc/bunkerweb/scheduler.env"
    if [ "${SERVICE_API:-no}" = "yes" ] || systemctl list-units --type=service --all | grep -q '^bunkerweb-api.service'; then
        echo "  - API config: /etc/bunkerweb/api.env"
    fi
    echo "  - Logs: /var/log/bunkerweb/"
    echo

    if [ "$ENABLE_WIZARD" = "yes" ]; then
        echo "Next steps:"
        echo "  1. Access the setup wizard at: https://your-server-ip/setup"
        echo "  2. Follow the configuration wizard to complete setup"
        echo
        echo "📝 Setup wizard information:"
        echo "  • The wizard will guide you through the initial configuration"
        echo "  • You can configure your first protected service"
        echo "  • SSL/TLS certificates can be set up automatically"
        echo "  • Access the management interface after completion"
    else
        echo "Next steps:"
        echo "  1. Edit /etc/bunkerweb/variables.env to configure BunkerWeb"
        echo "  2. Add your server settings and protected services"
        echo "  3. Restart services: systemctl restart bunkerweb-scheduler"
        echo
        echo "📝 Manual configuration:"
        echo "  • See documentation for configuration examples"
        echo "  • Use 'bwcli' command for advanced management"
    fi
    echo

    # Show RHEL database information if applicable
    if [[ "$DISTRO_ID" =~ ^(rhel|centos|fedora|rocky|almalinux|redhat)$ ]]; then
        echo "💾 Database clients for external databases:"
        echo "  • MariaDB: dnf install mariadb"
        echo "  • MySQL: dnf install mysql"
        echo "  • PostgreSQL: dnf install postgresql"
        echo
    fi

    echo "📚 Resources:"
    echo "  • Documentation: https://docs.bunkerweb.io"
    echo "  • Community support: https://discord.bunkerity.com"
    echo "  • Commercial support: https://panel.bunkerweb.io/store/support"
    echo "========================================="
}

# Function to show usage
usage() {
    echo "BunkerWeb Easy Install Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -v, --version VERSION    BunkerWeb version to install (default: ${DEFAULT_BUNKERWEB_VERSION})"
    echo "  -w, --enable-wizard      Enable the setup wizard (default in interactive mode)"
    echo "  -n, --no-wizard          Disable the setup wizard"
    echo "  -y, --yes                Non-interactive mode, use defaults"
    echo "      --api, --enable-api  Enable the API service (disabled by default on Linux)"
    echo "      --no-api             Explicitly disable the API service"
    echo "  -f, --force              Force installation on unsupported OS versions"
    echo "  -q, --quiet              Silent installation (suppress output)"
    echo "  -h, --help               Show this help message"
    echo "      --dry-run            Show what would be installed without doing it"
    echo
    echo "Installation types:"
    echo "  --full                   Full stack installation (default)"
    echo "  --manager                Manager installation (Scheduler + UI)"
    echo "  --worker                 Worker installation (BunkerWeb only)"
    echo "  --scheduler-only         Scheduler only installation"
    echo "  --ui-only                Web UI only installation"
    echo
    echo "Security integrations:"
    echo "  --crowdsec               Install and configure CrowdSec"
    echo "  --no-crowdsec            Skip CrowdSec installation"
    echo "  --crowdsec-appsec        Install CrowdSec with AppSec component"
    echo
    echo "Advanced options:"
    echo "  --instances \"IP1 IP2\"    Space-separated list of BunkerWeb instances"
    echo "                           (required for --manager and --scheduler-only)"
    echo "  --backup-dir PATH        Directory to store automatic backup before upgrade"
    echo "  --no-auto-backup         Skip automatic backup (you MUST have done it manually)"
    echo
    echo "Examples:"
    echo "  $0                       # Interactive installation"
    echo "  $0 --no-wizard           # Install without setup wizard"
    echo "  $0 --version 1.6.0       # Install specific version"
    echo "  $0 --yes                 # Non-interactive with defaults"
    echo "  $0 --force               # Force install on unsupported OS"
    echo "  $0 --manager --instances \"192.168.1.10 192.168.1.11\""
    echo "                           # Manager setup with worker instances"
    echo "  $0 --worker --no-wizard  # Worker-only installation"
    echo "  $0 --crowdsec-appsec     # Full installation with CrowdSec AppSec"
    echo "  $0 --quiet --yes         # Silent non-interactive installation"
    echo "  $0 --dry-run             # Preview installation without executing"
    echo
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            # Fix: actually use provided argument for version
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                print_error "Missing version after $1"
                exit 1
            fi
            BUNKERWEB_VERSION="$2"
            shift 2
            ;;
        -w|--enable-wizard)
            ENABLE_WIZARD="yes"
            shift
            ;;
        -n|--no-wizard)
            ENABLE_WIZARD="no"
            shift
            ;;
        -y|--yes)
            INTERACTIVE_MODE="no"
            ENABLE_WIZARD="yes"  # Default to wizard in non-interactive mode
            shift
            ;;
        -f|--force)
            FORCE_INSTALL="yes"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --full)
            INSTALL_TYPE="full"
            shift
            ;;
        --manager)
            INSTALL_TYPE="manager"
            shift
            ;;
        --worker)
            INSTALL_TYPE="worker"
            shift
            ;;
        --scheduler-only)
            INSTALL_TYPE="scheduler"
            shift
            ;;
        --ui-only)
            INSTALL_TYPE="ui"
            shift
            ;;
        --crowdsec)
            CROWDSEC_INSTALL="yes"
            shift
            ;;
        --no-crowdsec)
            CROWDSEC_INSTALL="no"
            shift
            ;;
        --crowdsec-appsec)
            CROWDSEC_INSTALL="yes"
            CROWDSEC_APPSEC_INSTALL="yes"
            shift
            ;;
        --instances)
            BUNKERWEB_INSTANCES_INPUT="$2"
            shift 2
            ;;
        --api|--enable-api)
            SERVICE_API=yes
            shift
            ;;
        --no-api)
            SERVICE_API=no
            shift
            ;;
        --backup-dir)
            BACKUP_DIRECTORY="$2"; shift 2 ;;
        --no-auto-backup)
            AUTO_BACKUP="no"; shift ;;
        -q|--quiet)
            exec >/dev/null 2>&1
            shift
            ;;
        --dry-run)
            echo "Dry run mode - would install BunkerWeb $BUNKERWEB_VERSION"
            detect_os
            check_supported_os
            echo "Installation type: ${INSTALL_TYPE:-full}"
            echo "Setup wizard: ${ENABLE_WIZARD:-auto}"
            echo "CrowdSec: ${CROWDSEC_INSTALL:-no}"
            if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
                echo "BunkerWeb instances: $BUNKERWEB_INSTANCES_INPUT"
            fi
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate instances option usage
if [ -n "$BUNKERWEB_INSTANCES_INPUT" ] && [[ "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "scheduler" ]]; then
    print_error "The --instances option can only be used with --manager or --scheduler-only installation types"
    exit 1
fi

# Validate required instances for manager/scheduler in non-interactive mode
if [ "$INTERACTIVE_MODE" = "no" ] && [[ "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "scheduler" ]] && [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
    print_error "The --instances option is required when using --manager or --scheduler-only in non-interactive mode"
    print_error "Example: --manager --instances \"192.168.1.10 192.168.1.11\""
    exit 1
fi

# Validate CrowdSec options usage
if [[ "$CROWDSEC_INSTALL" = "yes" || "$CROWDSEC_APPSEC_INSTALL" = "yes" ]] && [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" ]]; then
    print_error "CrowdSec options (--crowdsec, --crowdsec-appsec) can only be used with --full or --manager installation types"
    exit 1
fi

# Detect existing installation and handle reinstall/upgrade
check_existing_installation() {
    if [ -f /usr/share/bunkerweb/VERSION ]; then
        INSTALLED_VERSION=$(cat /usr/share/bunkerweb/VERSION 2>/dev/null || echo "unknown")
        print_status "Detected existing BunkerWeb installation (version ${INSTALLED_VERSION})"
        if [ "$INSTALLED_VERSION" = "$BUNKERWEB_VERSION" ]; then
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                echo
                read -p "BunkerWeb ${INSTALLED_VERSION} already installed. Show status and exit? (Y/n): " -r
                case $REPLY in
                    [Nn]*) print_status "Nothing to do."; exit 0 ;;
                    *) show_final_info; exit 0 ;;
                esac
            else
                print_status "BunkerWeb ${INSTALLED_VERSION} already installed. Nothing to do."; exit 0
            fi
        else
            print_warning "Requested version ${BUNKERWEB_VERSION} differs from installed version ${INSTALLED_VERSION}. Upgrade will be attempted."
            if [ "$INTERACTIVE_MODE" = "yes" ]; then
                read -p "Proceed with upgrade? (Y/n): " -r
                case $REPLY in
                    [Nn]*) print_status "Upgrade cancelled."; exit 0 ;;
                esac
            fi
            UPGRADE_SCENARIO="yes"
        fi
    fi
}

perform_upgrade_backup() {
    [ "$UPGRADE_SCENARIO" != "yes" ] && return 0
    if [ "$AUTO_BACKUP" != "yes" ]; then
        print_warning "Automatic backup disabled. Ensure you already performed a manual backup (see https://docs.bunkerweb.io/latest/upgrading)."
        return 0
    fi
    if ! command -v bwcli >/dev/null 2>&1; then
        print_warning "bwcli not found, cannot run automatic backup. Perform manual backup per documentation."
        return 0
    fi
    if ! systemctl is-active --quiet bunkerweb-scheduler; then
        print_warning "Scheduler service not active; starting temporarily for backup."
        systemctl start bunkerweb-scheduler || print_warning "Failed to start scheduler; backup may fail."
        TEMP_STARTED="yes"
    fi
    if [ -z "$BACKUP_DIRECTORY" ]; then
        BACKUP_DIRECTORY="/var/tmp/bunkerweb-backup-$(date +%Y%m%d-%H%M%S)"
    fi
    mkdir -p "$BACKUP_DIRECTORY" || {
        print_warning "Unable to create backup directory $BACKUP_DIRECTORY. Skipping automatic backup."; return 0; }
    print_step "Creating pre-upgrade backup in $BACKUP_DIRECTORY"
    if BACKUP_DIRECTORY="$BACKUP_DIRECTORY" bwcli plugin backup save; then
        print_status "Backup completed: $BACKUP_DIRECTORY"
    else
        print_warning "Automatic backup failed. Verify manually before continuing."
    fi
    if [ "$TEMP_STARTED" = "yes" ]; then
        systemctl stop bunkerweb-scheduler || print_warning "Failed to stop bunkerweb-scheduler after temporary start."
    fi
}

upgrade_only() {
    # Interactive confirmation about backup (optional, enabled by default)
    if [ "$INTERACTIVE_MODE" = "yes" ]; then
        if [ "$AUTO_BACKUP" = "yes" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}💾 Pre-upgrade Backup${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "A pre-upgrade backup is recommended to preserve configuration and database."
            echo "You can change the destination directory or accept the default."
            DEFAULT_BACKUP_DIR="/var/tmp/bunkerweb-backup-$(date +%Y%m%d-%H%M%S)"
            echo
            echo -e "${YELLOW}Create automatic backup before upgrade? (Y/n):${NC} "
            read -p "" -r
            case $REPLY in
                [Nn]*) AUTO_BACKUP="no" ;;
                *)
                    echo -e "${YELLOW}Backup directory [${DEFAULT_BACKUP_DIR}]:${NC} "
                    read -p "" -r BACKUP_DIRECTORY_INPUT
                    if [ -n "$BACKUP_DIRECTORY_INPUT" ]; then
                        BACKUP_DIRECTORY="$BACKUP_DIRECTORY_INPUT"
                    else
                        BACKUP_DIRECTORY="${BACKUP_DIRECTORY:-$DEFAULT_BACKUP_DIR}"
                    fi
                    ;;
            esac
        else
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}⚠️  Backup Confirmation${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "Automatic backup is disabled. Make sure you already performed a manual backup as described in the documentation."
            echo
            echo -e "${YELLOW}Confirm manual backup was performed? (y/N):${NC} "
            read -p "" -r
            case $REPLY in
                [Yy]*) ;; * ) print_error "Upgrade aborted until backup is confirmed."; exit 1 ;;
            esac
        fi
    fi

    print_status "Upgrade mode: $INSTALLED_VERSION -> $BUNKERWEB_VERSION"
    perform_upgrade_backup
    # Remove holds/version locks
    case "$DISTRO_ID" in
        debian|ubuntu)
            if command -v apt-mark >/dev/null 2>&1; then
                print_status "Removing holds (bunkerweb, nginx)"
                apt-mark unhold bunkerweb nginx >/dev/null 2>&1 || true
            fi
            ;;
        fedora|rhel|rocky|almalinux)
            if command -v dnf >/dev/null 2>&1; then
                print_status "Removing versionlock (bunkerweb, nginx)"
                dnf versionlock delete bunkerweb nginx >/dev/null 2>&1 || true
            fi
            ;;
    esac
    # Stop services (best effort)
    print_step "Stopping services prior to upgrade"
    for svc in bunkerweb-ui bunkerweb-scheduler bunkerweb; do
        if systemctl list-units --type=service --all | grep -q "^${svc}.service"; then
            if systemctl is-active --quiet "$svc"; then
                run_cmd systemctl stop "$svc"
            fi
        fi
    done
    # Install new version only (do NOT reinstall nginx)
    print_step "Upgrading BunkerWeb package"
    case "$DISTRO_ID" in
        debian|ubuntu)
            run_cmd apt update
            run_cmd apt install -y "bunkerweb=$BUNKERWEB_VERSION"
            run_cmd apt-mark hold bunkerweb nginx
            ;;
        fedora|rhel|rocky|almalinux)
            if [ "$DISTRO_ID" = "fedora" ]; then
                run_cmd dnf makecache || true
            else
                dnf check-update || true
            fi
            run_cmd dnf install -y --allowerasing "bunkerweb-$BUNKERWEB_VERSION"
            run_cmd dnf versionlock add bunkerweb nginx
            ;;
    esac
    show_final_info
    exit 0
}

# Main installation function
main() {
    echo "========================================="
    echo "       BunkerWeb Easy Install Script"
    echo "========================================="
    echo

    # Preliminary checks
    check_root
    detect_os
    check_supported_os
    # New: check if already installed (after OS detection)
    check_existing_installation

    # If upgrade scenario, skip prompts & ancillary installs
    if [ "$UPGRADE_SCENARIO" = "yes" ]; then
        upgrade_only
    fi

    # Show RHEL database warning early
    show_rhel_database_warning

    # Ask user preferences in interactive mode
    ask_user_preferences

    if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
        # Use a temporary file to pass the setting to the postinstall script
        echo "BUNKERWEB_INSTANCES=$BUNKERWEB_INSTANCES_INPUT" > /var/tmp/bunkerweb_instances.env
    fi

    # Persist API enablement for postinstall if chosen
    if [ "${SERVICE_API:-no}" = "yes" ]; then
        touch /var/tmp/bunkerweb_enable_api
    fi

    # Set environment variables based on installation type
    case "$INSTALL_TYPE" in
        "manager")
            print_status "Installation Type: Manager"
            export MANAGER_MODE=yes
            ;;
        "worker")
            print_status "Installation Type: Worker"
            export WORKER_MODE=yes
            ;;
        "scheduler")
            print_status "Installation Type: Scheduler only"
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=yes
            export SERVICE_UI=no
            ;;
        "ui")
            print_status "Installation Type: Web UI only"
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            export SERVICE_UI=yes
            ;;
        "full"|"")
            print_status "Installation Type: Full Stack"
            ;;
    esac

    # Pass UI_WIZARD to postinstall script
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    print_status "Installing BunkerWeb $BUNKERWEB_VERSION"
    print_status "Setup wizard: $([ "$ENABLE_WIZARD" = "yes" ] && echo "Enabled" || echo "Disabled")"
    echo

    # Confirmation prompt in interactive mode
    if [ "$INTERACTIVE_MODE" = "yes" ] && [ "$FORCE_INSTALL" != "yes" ]; then
        read -p "Continue with installation? (Y/n): " -r
        case $REPLY in
            [Nn]*)
                print_status "Installation cancelled"
                exit 0
                ;;
        esac
    fi

    # If upgrading, remove holds/versionlocks so upgrade can proceed
    if [ "$UPGRADE_SCENARIO" = "yes" ]; then
        case "$DISTRO_ID" in
            debian|ubuntu)
                if command -v apt-mark >/dev/null 2>&1; then
                    print_status "Removing holds on bunkerweb & nginx (upgrade scenario)"
                    apt-mark unhold bunkerweb nginx >/dev/null 2>&1 || true
                fi
                ;;
            fedora|rhel|rocky|almalinux)
                if command -v dnf >/dev/null 2>&1; then
                    print_status "Removing versionlock on bunkerweb & nginx (upgrade scenario)"
                    dnf versionlock delete bunkerweb nginx >/dev/null 2>&1 || true
                fi
                ;;
        esac
        # Stop services before upgrading (per upgrading.md procedure)
        print_step "Stopping BunkerWeb services before upgrade"
        for svc in bunkerweb bunkerweb-ui bunkerweb-scheduler; do
            if systemctl list-units --type=service --all | grep -q "^${svc}.service"; then
                if systemctl is-active --quiet "$svc"; then
                    run_cmd systemctl stop "$svc"
                else
                    print_status "Service $svc not active, skipping stop"
                fi
            fi
        done
    fi

    # Install NGINX based on distribution
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            install_nginx_debian
            ;;
        "fedora")
            install_nginx_fedora
            ;;
        "rhel"|"rocky"|"almalinux")
            install_nginx_rhel
            ;;
    esac

    # Install CrowdSec if chosen
    if [ "$CROWDSEC_INSTALL" = "yes" ]; then
        install_crowdsec
    fi

    # Install BunkerWeb based on distribution
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            install_bunkerweb_debian
            ;;
        "fedora")
            install_bunkerweb_rpm
            ;;
        "rhel"|"rocky"|"almalinux")
            install_bunkerweb_rpm
            ;;
    esac

    if [ "$CROWDSEC_INSTALL" = "yes" ]; then
        run_cmd systemctl restart crowdsec
        sleep 2
        systemctl status crowdsec --no-pager -l || print_warning "CrowdSec may not be running"
    fi

    # Show final information
    show_final_info
}

# Run main function
main "$@"
