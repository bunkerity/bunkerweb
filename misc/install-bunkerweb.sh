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
BUNKERWEB_VERSION="1.6.3-rc1"
NGINX_VERSION=""
ENABLE_WIZARD=""
FORCE_INSTALL="no"
INTERACTIVE_MODE="yes"
CROWDSEC_INSTALL="no"
CROWDSEC_APPSEC_INSTALL="no"

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

        # Ask about setup wizard
        if [ -z "$ENABLE_WIZARD" ]; then
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🧙‍♂️ BunkerWeb Setup Wizard${NC}"
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

        # Ask about CrowdSec installation
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
        echo "  🧙‍♂️ Setup wizard: $([ "$ENABLE_WIZARD" = "yes" ] && echo "Enabled" || echo "Disabled")"
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
            if [ "$DISTRO_VERSION" != "12" ]; then
                print_warning "Only Debian 12 (Bookworm) is officially supported"
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
            if [[ "$DISTRO_VERSION" != "40" && "$DISTRO_VERSION" != "41" && "$DISTRO_VERSION" != "42" ]]; then
                print_warning "Only Fedora 40, 41, and 42 are officially supported"
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
            if [[ "$major_version" != "8" && "$major_version" != "9" ]]; then
                print_warning "Only RHEL 8 and 9 are officially supported"
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
            print_error "Supported distributions: Debian 12, Ubuntu 22.04/24.04, Fedora 40/41/42, RHEL 8/9"
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

    echo -e "${YELLOW}--- Step 6: Restart and enable services ---${NC}"
    print_step "Restarting services and enabling at boot"
    run_cmd systemctl restart crowdsec
    sleep 2
    systemctl status crowdsec --no-pager -l || print_warning "CrowdSec may not be running"

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
    echo "  -v, --version VERSION    BunkerWeb version to install (default: $BUNKERWEB_VERSION)"
    echo "  -w, --enable-wizard      Enable the setup wizard (default in interactive mode)"
    echo "  -n, --no-wizard          Disable the setup wizard"
    echo "  -y, --yes                Non-interactive mode, use defaults"
    echo "  -f, --force              Force installation on unsupported OS versions"
    echo "  -h, --help               Show this help message"
    echo
    echo "Examples:"
    echo "  $0                       # Interactive installation"
    echo "  $0 --no-wizard           # Install without setup wizard"
    echo "  $0 --version 1.6.0       # Install specific version"
    echo "  $0 --yes                 # Non-interactive with defaults"
    echo "  $0 --force               # Force install on unsupported OS"
    echo
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            BUNKERWEB_VERSION="1.6.3-rc1"
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
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

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

    # Show RHEL database warning early
    show_rhel_database_warning

    # Ask user preferences in interactive mode
    ask_user_preferences

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

    # Install NGINX based on distribution
    case "$DISTRO_ID" in
        "debian"|"ubuntu")
            install_nginx_debian
            install_bunkerweb_debian
            ;;
        "fedora")
            install_nginx_fedora
            install_bunkerweb_rpm
            ;;
        "rhel"|"rocky"|"almalinux")
            install_nginx_rhel
            install_bunkerweb_rpm
            ;;
    esac

    # Install CrowdSec if chosen
    if [ "$CROWDSEC_INSTALL" = "yes" ]; then
        install_crowdsec
    fi

    # Show final information
    show_final_info
}

# Run main function
main "$@"
