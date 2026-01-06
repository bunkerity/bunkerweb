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
DEFAULT_BUNKERWEB_VERSION="1.6.7~rc1"
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
MANAGER_IP_INPUT=""
DNS_RESOLVERS_INPUT=""
API_LISTEN_HTTPS_INPUT=""
UPGRADE_SCENARIO="no"
BACKUP_DIRECTORY=""
AUTO_BACKUP="yes"
SYSTEM_ARCH=""

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

# Function to detect system architecture and warn for unsupported combinations
detect_architecture() {
    SYSTEM_ARCH=$(uname -m 2>/dev/null || echo "unknown")
    NORMALIZED_ARCH="$SYSTEM_ARCH"
    case "$SYSTEM_ARCH" in
        x86_64|amd64)
            NORMALIZED_ARCH="amd64"
            ;;
        aarch64|arm64)
            NORMALIZED_ARCH="arm64"
            ;;
        armv7l|armhf)
            NORMALIZED_ARCH="armhf"
            ;;
        unknown)
            print_warning "Unable to detect system architecture."
            ;;
        *)
            print_warning "Architecture $SYSTEM_ARCH has not been validated with the easy install script."
            if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                read -p "Continue anyway? (y/N): " -r
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    exit 1
                fi
            fi
            ;;
    esac
    export NORMALIZED_ARCH
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
            echo "  6) API Only: Installs only the API service component."
            echo
            while true; do
                echo -e "${YELLOW}Select installation type (1-6) [1]:${NC} "
                read -p "" -r
                REPLY=${REPLY:-1}
                case $REPLY in
                    1) INSTALL_TYPE="full"; break ;;
                    2) INSTALL_TYPE="manager"; break ;;
                    3) INSTALL_TYPE="worker"; break ;;
                    4) INSTALL_TYPE="scheduler"; break ;;
                    5) INSTALL_TYPE="ui"; break ;;
                    6) INSTALL_TYPE="api"; break ;;
                    *) echo "Invalid option. Please choose a number between 1 and 6." ;;
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
                echo "Leave empty to add workers later."
                echo
                echo -e "${YELLOW}Enter BunkerWeb instances (or press Enter to skip):${NC} "
                read -p "" -r BUNKERWEB_INSTANCES_INPUT
                if [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
                    print_warning "No instances configured. You can add workers later."
                    print_status "See: https://docs.bunkerweb.io/latest/advanced/#3-manage-workers"
                fi
            fi
        fi

        if [ "$INSTALL_TYPE" = "manager" ] && [ -z "$MANAGER_IP_INPUT" ]; then
            local detected_ip=""
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🌐 Manager API Binding${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The manager listens on 0.0.0.0 but only whitelists explicit local IPs for API access."
            echo "We'll detect the best local IPv4 to whitelist, or you can provide one manually."
            echo
            detected_ip=$(get_primary_ipv4)
            if [ -n "$detected_ip" ]; then
                while true; do
                    echo -e "${YELLOW}Whitelist detected IP $detected_ip for API access? (Y/n):${NC}"
                    read -p "" -r
                    case $REPLY in
                        [Yy]*|"")
                            MANAGER_IP_INPUT="$detected_ip"
                            break
                            ;;
                        [Nn]*)
                            echo
                            echo -e "${BLUE}----------------------------------------${NC}"
                            echo -e "${BLUE}✍️  Manual Manager IP Entry${NC}"
                            echo -e "${BLUE}----------------------------------------${NC}"
                            echo "Enter the IPv4 address you want to whitelist for manager API access."
                            prompt_for_local_ipv4 MANAGER_IP_INPUT
                            break
                            ;;
                        *)
                            echo "Please answer yes (y) or no (n)."
                            ;;
                    esac
                done
            else
                print_warning "Unable to detect a local IPv4 automatically."
                echo -e "${BLUE}----------------------------------------${NC}"
                echo -e "${BLUE}✍️  Manual Manager IP Entry${NC}"
                echo -e "${BLUE}----------------------------------------${NC}"
                echo "Enter the IPv4 address you want to whitelist for manager API access."
                prompt_for_local_ipv4 MANAGER_IP_INPUT
            fi
        fi

        if [ "$INSTALL_TYPE" = "worker" ] && [ -z "$MANAGER_IP_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🛡️  Manager API Access${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "Provide the IP address (or space-separated list) of the manager/scheduler that will control this worker."
            echo "The worker API listens on 0.0.0.0, and these IPs will be whitelisted automatically."
            echo
            while true; do
                echo -e "${YELLOW}Enter manager IP address(es):${NC} "
                read -p "" -r MANAGER_IP_INPUT
                if [ -n "$MANAGER_IP_INPUT" ]; then
                    break
                else
                    print_warning "This field cannot be empty for Worker installations."
                fi
            done
        fi

        # Ask about custom DNS resolvers for full, manager, or worker installations
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "worker" ]] && [ -z "$DNS_RESOLVERS_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🔍 DNS Resolvers Configuration${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "BunkerWeb needs DNS resolvers for domain resolution."
            echo "Default: 9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4 (Quad9 and Google DNS)"
            echo
            while true; do
                echo -e "${YELLOW}Use custom DNS resolvers? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*)
                        echo -e "${YELLOW}Enter space-separated DNS resolver IPs:${NC} "
                        read -p "" -r DNS_RESOLVERS_INPUT
                        if [ -n "$DNS_RESOLVERS_INPUT" ]; then
                            break
                        else
                            print_warning "DNS resolvers cannot be empty. Please enter at least one resolver."
                        fi
                        ;;
                    [Nn]*|"")
                        DNS_RESOLVERS_INPUT="9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about internal API HTTPS communication for full, manager, or worker installations
        if [[ "$INSTALL_TYPE" = "full" || "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "worker" ]] && [ -z "$API_LISTEN_HTTPS_INPUT" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🔒 Internal API HTTPS Communication${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The scheduler/manager can communicate with BunkerWeb/worker instances via HTTPS"
            echo "for internal API communication (not the public API service)."
            echo "Default: HTTP only (no HTTPS)"
            echo
            while true; do
                echo -e "${YELLOW}Enable HTTPS for internal API communication? (y/N):${NC} "
                read -p "" -r
                case $REPLY in
                    [Yy]*)
                        API_LISTEN_HTTPS_INPUT="yes"
                        break
                        ;;
                    [Nn]*|"")
                        API_LISTEN_HTTPS_INPUT="no"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about setup wizard
        if [ "$INSTALL_TYPE" = "manager" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🧙 Setup Wizard Not Available${NC}"
            echo -e "${BLUE}========================================${NC}"
            if [ "$ENABLE_WIZARD" = "yes" ]; then
                print_warning "Setup wizard cannot be enabled for manager mode; it will be disabled."
            fi
            echo "Manager installations are not compatible with the setup wizard."
            echo "The UI can still be started normally without the wizard."
            ENABLE_WIZARD="no"
        elif [ -z "$ENABLE_WIZARD" ]; then
            if [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "scheduler" ] || [ "$INSTALL_TYPE" = "api" ]; then
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

        if [ "$INSTALL_TYPE" = "manager" ] && [ -z "$SERVICE_UI" ]; then
            echo
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}🖥  Manager Web UI${NC}"
            echo -e "${BLUE}========================================${NC}"
            echo "The setup wizard is disabled, but you can still start the Web UI service."
            echo "Do you want the Web UI to run after installation?"
            while true; do
                echo -e "${YELLOW}Start the Web UI service? (Y/n):${NC} "
                read -p "" -r
                case $REPLY in
                    [Nn]*)
                        export SERVICE_UI="no"
                        break
                        ;;
                    [Yy]*|"")
                        export SERVICE_UI="yes"
                        break
                        ;;
                    *)
                        echo "Please answer yes (y) or no (n)."
                        ;;
                esac
            done
        fi

        # Ask about CrowdSec installation
        if [[ "$INSTALL_TYPE" != "worker" && "$INSTALL_TYPE" != "scheduler" && "$INSTALL_TYPE" != "ui" && "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "api" ]]; then
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
            # CrowdSec not applicable for manager, worker, scheduler-only, ui-only, or api-only installations
            CROWDSEC_INSTALL="no"
        fi

        # Ask about API service enablement (not applicable for worker, scheduler-only, ui-only, or api-only)
        if [[ "$INSTALL_TYPE" != "worker" && "$INSTALL_TYPE" != "scheduler" && "$INSTALL_TYPE" != "ui" && "$INSTALL_TYPE" != "api" ]] && [ -z "$SERVICE_API" ]; then
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
        elif [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "api" ]]; then
            # API service not applicable for these installation types
            SERVICE_API=no
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
            "api") echo "  📦 Installation type: API Only" ;;
        esac
        if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
            echo "  🔗 BunkerWeb instances: $BUNKERWEB_INSTANCES_INPUT"
        fi
        if [ -n "$MANAGER_IP_INPUT" ]; then
            echo "  📡 Manager API whitelist: $MANAGER_IP_INPUT"
        fi
        if [ -n "$DNS_RESOLVERS_INPUT" ]; then
            echo "  🔍 DNS resolvers: $DNS_RESOLVERS_INPUT"
        fi
        if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
            echo "  🔒 Internal API HTTPS: Enabled"
        fi
        if [ "$INSTALL_TYPE" = "manager" ]; then
            echo "  🖥 Web UI service: $([ "${SERVICE_UI:-yes}" = "no" ] && echo "Disabled" || echo "Enabled")"
            echo "  🧙 Setup wizard: Disabled (not supported in manager mode)"
        else
            echo "  🧙 Setup wizard: $([ "$ENABLE_WIZARD" = "yes" ] && echo "Enabled" || echo "Disabled")"
        fi
        if [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" ]]; then
            echo "  🔌 API service: Not available for this mode"
        elif [ "${SERVICE_API:-no}" = "yes" ]; then
            echo "  🔌 API service: Enabled"
        else
            echo "  🔌 API service: Disabled"
        fi
        echo "  🖥 Operating system: $DISTRO_ID $DISTRO_VERSION"
        echo "  ⚙️ Architecture: ${SYSTEM_ARCH:-unknown}"
        echo "  🟢 NGINX version: $NGINX_VERSION"
        if [ "$INSTALL_TYPE" = "manager" ] || [ "$INSTALL_TYPE" = "worker" ] || [ "$INSTALL_TYPE" = "api" ]; then
            echo "  🦙 CrowdSec: Not available for this mode"
        else
            if [ "$CROWDSEC_INSTALL" = "yes" ]; then
                if [ "$CROWDSEC_APPSEC_INSTALL" = "yes" ]; then
                    echo "  🦙 CrowdSec: Will be installed (with AppSec Component)"
                else
                    echo "  🦙 CrowdSec: Will be installed (without AppSec Component)"
                fi
            else
                echo "  🦙 CrowdSec: Not installed"
            fi
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
            if [[ "$DISTRO_VERSION" != "41" && "$DISTRO_VERSION" != "42" && "$DISTRO_VERSION" != "43" ]]; then
                print_warning "Only Fedora 41, 42 and 43 are officially supported"
                if [ "$FORCE_INSTALL" != "yes" ] && [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
            # Note: Fedora 42 and 43 have removed NGINX 1.28.0 from their mirrors,
            # so NGINX 1.28.1 is required for these versions. Fedora 41 still has 1.28.0.
            if [ "$DISTRO_VERSION" != "41" ]; then
                NGINX_VERSION="1.28.1"
            else
                NGINX_VERSION="1.28.0"
            fi
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
            print_error "Supported distributions: Debian 12/13, Ubuntu 22.04/24.04, Fedora 41/42/43, RHEL 8/9/10"
            exit 1
            ;;
    esac
}

# Function to check for port conflicts
check_ports() {
    if [[ "$INSTALL_TYPE" == "full" || "$INSTALL_TYPE" == "worker" || -z "$INSTALL_TYPE" ]]; then
        if command -v ss >/dev/null 2>&1; then
            if ss -tulpn | grep -E ":(80|443)\s" >/dev/null 2>&1; then
                print_warning "Port 80 or 443 appears to be in use."
                print_warning "Common conflict: Apache/httpd running."
                print_warning "Please stop conflicting services before proceeding."
                if [ "$INTERACTIVE_MODE" = "yes" ]; then
                    read -p "Continue anyway? (y/N): " -r
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        exit 1
                    fi
                fi
            fi
        fi
    fi
}

# Check if provided IPv4 belongs to a private (LAN) range
is_private_ipv4() {
    local ip="$1"
    local o1 o2 _o3 _o4

    if [[ ! $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        return 1
    fi

    IFS='.' read -r o1 o2 _o3 _o4 <<< "$ip"

    if [ "$o1" -eq 10 ]; then
        return 0
    elif [ "$o1" -eq 172 ] && [ "$o2" -ge 16 ] && [ "$o2" -le 31 ]; then
        return 0
    elif [ "$o1" -eq 192 ] && [ "$o2" -eq 168 ]; then
        return 0
    fi

    return 1
}

# Extract the first IPv4 address from a whitespace-separated list
extract_first_ipv4() {
    local input="$1"
    local token

    for token in $input; do
        if [[ $token =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
            echo "$token"
            return 0
        fi
    done

    echo ""
    return 1
}

# Prompt interactively for a local IPv4 address
prompt_for_local_ipv4() {
    local -n __target_var="$1"
    local answer=""
    local ip=""

    while true; do
        echo -e "${YELLOW}Enter the local IPv4 address to use:${NC} "
        read -p "" -r answer
        ip=$(extract_first_ipv4 "$answer")
        if [ -n "$ip" ]; then
            __target_var="$ip"
            return 0
        fi
        print_warning "Invalid IPv4 address. Please try again."
    done
}

# Function to determine the primary IPv4 address of the current host using only
# locally available routing/interface information (no external queries)
get_primary_ipv4() {
    local primary_ip=""
    local route_output=""
    local host_output=""
    local addr_output=""
    local prev=""
    local token=""
    local line=""
    local candidate=""

    if command -v ip >/dev/null 2>&1; then
        route_output=$(ip -4 route show default 2>/dev/null || true)
        if [ -z "$route_output" ]; then
            route_output=$(ip route show default 2>/dev/null || true)
        fi
        if [ -n "$route_output" ]; then
            for token in $route_output; do
                if [ "$prev" = "src" ]; then
                    candidate="$token"
                    if is_private_ipv4 "$candidate"; then
                        primary_ip="$candidate"
                        break
                    fi
                fi
                prev="$token"
            done
        fi
    fi

    if [ -z "$primary_ip" ] && command -v hostname >/dev/null 2>&1; then
        host_output=$(hostname -I 2>/dev/null || true)
        if [ -n "$host_output" ]; then
            for token in $host_output; do
                if [[ $token =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && is_private_ipv4 "$token"; then
                    primary_ip="$token"
                    break
                fi
            done
        fi
    fi

    if [ -z "$primary_ip" ] && command -v ip >/dev/null 2>&1; then
        addr_output=$(ip -4 addr show scope global 2>/dev/null || true)
        if [ -n "$addr_output" ]; then
            while IFS= read -r line; do
                case "$line" in
                    *inet\ *)
                        line=${line#*inet }
                        candidate=${line%%/*}
                        if [[ $candidate =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && is_private_ipv4 "$candidate"; then
                            primary_ip="$candidate"
                            break
                        fi
                        ;;
                esac
            done <<< "$addr_output"
        fi
    fi

    echo "$primary_ip"
}

# Ensure manager installations expose the API and only whitelist the local host IP
configure_manager_api_defaults() {
    local config_file="/etc/bunkerweb/variables.env"
    local whitelist_ip
    local provided_ip

    provided_ip=$(extract_first_ipv4 "$MANAGER_IP_INPUT")

    if [ -n "$provided_ip" ]; then
        whitelist_ip="$provided_ip"
    else
        whitelist_ip=$(get_primary_ipv4)
    fi

    if [ -z "$whitelist_ip" ]; then
        if [ "$INTERACTIVE_MODE" = "yes" ]; then
            print_warning "Unable to detect a local network IP automatically."
            prompt_for_local_ipv4 whitelist_ip
            MANAGER_IP_INPUT="$whitelist_ip"
        else
            print_error "Unable to detect a local network IP. Provide it with --manager-ip <IP>."
            exit 1
        fi
    fi

    whitelist_ip="127.0.0.0/8 $whitelist_ip"
    whitelist_ip=$(printf '%s\n' "$whitelist_ip" | xargs)

    if [ -z "$provided_ip" ]; then
        MANAGER_IP_INPUT="$whitelist_ip"
    fi

    print_status "Applying manager API defaults (listen on 0.0.0.0, whitelist local IP $whitelist_ip)"

    if [ ! -d /etc/bunkerweb ]; then
        mkdir -p /etc/bunkerweb
    fi

    {
        echo "SERVER_NAME="
        if [ -n "$BUNKERWEB_INSTANCES_INPUT" ]; then
            echo "BUNKERWEB_INSTANCES=$BUNKERWEB_INSTANCES_INPUT"
        else
            echo "BUNKERWEB_INSTANCES="
        fi
        # Use custom DNS resolvers if provided, otherwise use defaults
        if [ -n "$DNS_RESOLVERS_INPUT" ]; then
            echo "DNS_RESOLVERS=$DNS_RESOLVERS_INPUT"
        else
            echo "DNS_RESOLVERS=9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4" # Quad9, Google
        fi
        echo "HTTP_PORT=80"
        echo "HTTPS_PORT=443"
        echo "API_LISTEN_IP=0.0.0.0"
        echo "API_WHITELIST_IP=$whitelist_ip"
        if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
            echo "API_LISTEN_HTTPS=yes"
        fi
        echo "API_TOKEN="
        # Enable multisite mode when UI service is used
        if [ "${SERVICE_UI:-yes}" != "no" ]; then
            echo "MULTISITE=yes"
        fi
    } > "$config_file"
    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true

    print_status "Enabling and starting BunkerWeb Scheduler with configured settings..."
    run_cmd systemctl enable --now bunkerweb-scheduler
    sleep 2
    systemctl status bunkerweb-scheduler --no-pager -l || print_warning "BunkerWeb Scheduler may not be running"
}

# Ensure worker installations whitelist the selected manager/scheduler IPs
configure_worker_api_whitelist() {
    local config_file="/etc/bunkerweb/variables.env"
    local whitelist_value

    if [ -z "$MANAGER_IP_INPUT" ]; then
        print_warning "Manager IP not provided; please whitelist it manually in $config_file."
        return
    fi

    whitelist_value="127.0.0.0/8 $MANAGER_IP_INPUT"
    whitelist_value=$(printf '%s\n' "$whitelist_value" | xargs)

    print_status "Applying worker API whitelist: $whitelist_value"

    if [ ! -d /etc/bunkerweb ]; then
        mkdir -p /etc/bunkerweb
    fi

    if [ ! -f "$config_file" ]; then
        touch "$config_file"
    fi

    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true

    if grep -q "^API_LISTEN_IP=" "$config_file"; then
        sed -i 's|^API_LISTEN_IP=.*|API_LISTEN_IP=0.0.0.0|' "$config_file"
    else
        echo "API_LISTEN_IP=0.0.0.0" >> "$config_file"
    fi

    if grep -q "^API_WHITELIST_IP=" "$config_file"; then
        sed -i "s|^API_WHITELIST_IP=.*|API_WHITELIST_IP=$whitelist_value|" "$config_file"
    else
        echo "API_WHITELIST_IP=$whitelist_value" >> "$config_file"
    fi

    # Configure custom DNS resolvers if provided
    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        print_status "Configuring custom DNS resolvers: $DNS_RESOLVERS_INPUT"
        if grep -q "^DNS_RESOLVERS=" "$config_file"; then
            sed -i "s|^DNS_RESOLVERS=.*|DNS_RESOLVERS=$DNS_RESOLVERS_INPUT|" "$config_file"
        else
            echo "DNS_RESOLVERS=$DNS_RESOLVERS_INPUT" >> "$config_file"
        fi
    fi

    # Configure internal API HTTPS if enabled
    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        print_status "Configuring internal API HTTPS communication"
        if grep -q "^API_LISTEN_HTTPS=" "$config_file"; then
            sed -i "s|^API_LISTEN_HTTPS=.*|API_LISTEN_HTTPS=yes|" "$config_file"
        else
            echo "API_LISTEN_HTTPS=yes" >> "$config_file"
        fi
    fi

    print_status "Enabling and starting BunkerWeb with configured settings..."
    run_cmd systemctl enable --now bunkerweb
    sleep 2
    systemctl status bunkerweb --no-pager -l || print_warning "BunkerWeb may not be running"
}

# Configure full installation settings (DNS resolvers, API HTTPS, multisite)
configure_full_config() {
    local config_file="/etc/bunkerweb/variables.env"
    local needs_reload=false

    if [ ! -d /etc/bunkerweb ]; then
        mkdir -p /etc/bunkerweb
    fi

    if [ ! -f "$config_file" ]; then
        touch "$config_file"
    fi

    chown root:nginx "$config_file" 2>/dev/null || true
    chmod 660 "$config_file" 2>/dev/null || true

    # Configure custom DNS resolvers if provided
    if [ -n "$DNS_RESOLVERS_INPUT" ]; then
        print_status "Configuring custom DNS resolvers: $DNS_RESOLVERS_INPUT"
        if grep -q "^DNS_RESOLVERS=" "$config_file"; then
            sed -i "s|^DNS_RESOLVERS=.*|DNS_RESOLVERS=$DNS_RESOLVERS_INPUT|" "$config_file"
        else
            echo "DNS_RESOLVERS=$DNS_RESOLVERS_INPUT" >> "$config_file"
        fi
        needs_reload=true
    fi

    # Configure internal API HTTPS if enabled
    if [ -n "$API_LISTEN_HTTPS_INPUT" ] && [ "$API_LISTEN_HTTPS_INPUT" = "yes" ]; then
        print_status "Configuring internal API HTTPS communication"
        if grep -q "^API_LISTEN_HTTPS=" "$config_file"; then
            sed -i "s|^API_LISTEN_HTTPS=.*|API_LISTEN_HTTPS=yes|" "$config_file"
        else
            echo "API_LISTEN_HTTPS=yes" >> "$config_file"
        fi
        needs_reload=true
    fi

    # Enable multisite mode when UI service is used
    if [ "$ENABLE_WIZARD" = "yes" ] || [ "${SERVICE_UI:-no}" = "yes" ]; then
        if grep -q "^MULTISITE=" "$config_file"; then
            sed -i "s|^MULTISITE=.*|MULTISITE=yes|" "$config_file"
        else
            echo "MULTISITE=yes" >> "$config_file"
        fi
        needs_reload=true
    fi

    # Start bunkerweb and the scheduler if any changes were made
    if [ "$needs_reload" = true ]; then
        print_status "Enabling and starting services with configured settings..."
        run_cmd systemctl enable --now bunkerweb
        run_cmd systemctl enable --now bunkerweb-scheduler
    fi
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
    run_cmd apt install -y --allow-downgrades "bunkerweb=$BUNKERWEB_VERSION"

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

    run_cmd dnf makecache
    run_cmd dnf install -y "bunkerweb-$BUNKERWEB_VERSION"

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
                    run_cmd apt install -y "$dep"
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
  type: bunkerweb
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
    cscli collections install bunkerity/bunkerweb
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

    # Display next steps based on installation type and wizard status
    case "$INSTALL_TYPE" in
        "manager")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/scheduler.env"
            echo "     Set DATABASE_URI (e.g., sqlite:///var/lib/bunkerweb/db.sqlite3)"
            echo "  2. Verify BUNKERWEB_INSTANCES is set to: $BUNKERWEB_INSTANCES_INPUT"
            if [ "${SERVICE_UI:-yes}" != "no" ]; then
                echo "  3. Access the Web UI at: http://your-server-ip:7000"
                echo "  4. Use the UI to manage your BunkerWeb workers"
            else
                echo "  3. Start the Web UI: systemctl start bunkerweb-ui"
                echo "  4. Access the UI at: http://your-server-ip:7000"
            fi
            echo
            echo "📝 Manager mode information:"
            echo "  • The scheduler orchestrates configuration across all workers"
            echo "  • Workers must have their API accessible on port 5000 (default)"
            echo "  • Ensure workers whitelist this manager's IP: $MANAGER_IP_INPUT"
            echo "  • Use multisite mode: MULTISITE=yes for multiple services"
            ;;
        "worker")
            echo "Next steps:"
            echo "  1. Verify this worker's API is accessible from the manager"
            echo "     Default API port: 5000 (configured via API_HTTP_PORT)"
            echo "  2. Ensure firewall allows connections from: $MANAGER_IP_INPUT"
            echo "  3. Configuration will be pushed automatically from the manager"
            echo
            echo "📝 Worker mode information:"
            echo "  • This instance is managed remotely by the scheduler"
            echo "  • API_WHITELIST_IP is configured to allow: $MANAGER_IP_INPUT"
            echo "  • API listens on: 0.0.0.0:5000 (whitelisting enforces access control)"
            echo "  • Local config changes in /etc/bunkerweb/variables.env may be overwritten"
            echo "  • Check logs: journalctl -u bunkerweb -f"
            ;;
        "scheduler")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/scheduler.env"
            echo "     Set DATABASE_URI for shared configuration storage"
            echo "  2. Verify BUNKERWEB_INSTANCES is set to: $BUNKERWEB_INSTANCES_INPUT"
            echo "  3. Restart scheduler: systemctl restart bunkerweb-scheduler"
            echo "  4. Use 'bwcli' commands to manage the cluster"
            echo
            echo "📝 Scheduler-only mode information:"
            echo "  • Workers communicate via their API (port 5000 by default)"
            echo "  • Install the Web UI separately for graphical management"
            echo "  • All instances must share the same database backend"
            ;;
        "ui")
            echo "Next steps:"
            echo "  1. Configure database connection in /etc/bunkerweb/ui.env"
            echo "     Set DATABASE_URI to the same database as your scheduler"
            echo "  2. Restart the UI: systemctl restart bunkerweb-ui"
            echo "  3. Access the Web UI at: http://your-server-ip:7000"
            echo
            echo "📝 UI-only mode information:"
            echo "  • The UI must connect to the same database as the scheduler"
            echo "  • Requires an existing scheduler instance managing workers"
            echo "  • Default UI port: 7000"
            ;;
        "api")
            echo "Next steps:"
            echo "  1. Configure API settings in /etc/bunkerweb/api.env"
            echo "     Set API_LISTEN_IP and API_HTTP_PORT as needed"
            echo "  2. Configure database connection: DATABASE_URI"
            echo "  3. Restart the API: systemctl restart bunkerweb-api"
            echo "  4. The API will be available at: http://your-server-ip:8000"
            echo
            echo "📝 API-only mode information:"
            echo "  • The API service provides programmatic access to BunkerWeb"
            echo "  • Must connect to the same database as scheduler/UI"
            echo "  • Default API port: 8000 (FastAPI service, not internal API)"
            echo "  • Configure API_KEY for authentication if needed"
            ;;
        "full"|*)
            if [ "$ENABLE_WIZARD" = "yes" ]; then
                echo "Next steps:"
                echo "  1. Access the setup wizard at: https://your-server-ip/setup"
                echo "  2. Follow the configuration wizard to complete setup"
                echo
                echo "📝 Setup wizard information:"
                echo "  • The wizard guides you through initial configuration"
                echo "  • Configure your first protected service"
                echo "  • Set up SSL/TLS certificates automatically"
                echo "  • Access the management UI after completion"
            else
                echo "Next steps:"
                echo "  1. Edit /etc/bunkerweb/variables.env to configure BunkerWeb"
                echo "  2. Add your server settings and protected services"
                echo "  3. Restart services: systemctl restart bunkerweb bunkerweb-scheduler"
                echo
                echo "📝 Manual configuration:"
                echo "  • Default database: SQLite (upgrade to MariaDB/PostgreSQL for production)"
                echo "  • Use 'bwcli' for command-line management"
                echo "  • Check logs: journalctl -u bunkerweb -f"
                echo "  • Access Web UI (if enabled): http://your-server-ip:7000"
            fi
            ;;
    esac
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
    echo "  --api-only               API service only installation"
    echo
    echo "Security integrations:"
    echo "  --crowdsec               Install and configure CrowdSec"
    echo "  --no-crowdsec            Skip CrowdSec installation"
    echo "  --crowdsec-appsec        Install CrowdSec with AppSec component"
    echo
    echo "Advanced options:"
    echo "  --instances \"IP1 IP2\"    Space-separated list of BunkerWeb instances"
    echo "                           (optional for --manager and --scheduler-only)"
    echo "  --manager-ip IPs         Manager/Scheduler IPs to whitelist (required for --worker in non-interactive mode, overrides auto-detect for --manager)"
    echo "  --dns-resolvers \"IP1 IP2\"  Custom DNS resolver IPs (for --full, --manager, --worker)"
    echo "  --api-https              Enable HTTPS for internal API communication (default: HTTP only)"
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
    echo "  $0 --worker --manager-ip 10.20.30.40"
    echo "                           # Worker installation with manager IP"
    echo "  $0 --dns-resolvers \"1.1.1.1 1.0.0.1\""
    echo "                           # Use Cloudflare DNS resolvers"
    echo "  $0 --manager --instances \"192.168.1.10 192.168.1.11\" --api-https"
    echo "                           # Manager with workers over HTTPS"
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
        --api-only)
            INSTALL_TYPE="api"
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
        --manager-ip)
            MANAGER_IP_INPUT="$2"
            shift 2
            ;;
        --dns-resolvers)
            DNS_RESOLVERS_INPUT="$2"
            shift 2
            ;;
        --api-https)
            API_LISTEN_HTTPS_INPUT="yes"
            shift
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
            if [ -n "$MANAGER_IP_INPUT" ]; then
                echo "Manager IP: $MANAGER_IP_INPUT"
            fi
            if [ -n "$DNS_RESOLVERS_INPUT" ]; then
                echo "DNS resolvers: $DNS_RESOLVERS_INPUT"
            fi
            if [ -n "$API_LISTEN_HTTPS_INPUT" ]; then
                echo "API HTTPS: $API_LISTEN_HTTPS_INPUT"
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

# Force wizard off for manager installations
if [ "$INSTALL_TYPE" = "manager" ]; then
    if [ "$ENABLE_WIZARD" = "yes" ]; then
        print_warning "Setup wizard cannot run in manager mode; disabling it."
    fi
    ENABLE_WIZARD="no"
fi

# Validate instances option usage
if [ -n "$BUNKERWEB_INSTANCES_INPUT" ] && [[ "$INSTALL_TYPE" != "manager" && "$INSTALL_TYPE" != "scheduler" ]]; then
    print_error "The --instances option can only be used with --manager or --scheduler-only installation types"
    exit 1
fi

# Inform about missing instances for manager/scheduler in non-interactive mode
if [ "$INTERACTIVE_MODE" = "no" ] && [[ "$INSTALL_TYPE" = "manager" || "$INSTALL_TYPE" = "scheduler" ]] && [ -z "$BUNKERWEB_INSTANCES_INPUT" ]; then
    print_warning "No BunkerWeb instances configured. You can add workers later."
    print_status "See: https://docs.bunkerweb.io/latest/integrations/#linux"
fi

if [ "$INTERACTIVE_MODE" = "no" ] && [ "$INSTALL_TYPE" = "worker" ] && [ -z "$MANAGER_IP_INPUT" ]; then
    print_error "The --manager-ip option is required when using --worker in non-interactive mode"
    print_error "Example: --worker --manager-ip 10.20.30.40"
    exit 1
fi

# Validate CrowdSec options usage
if [[ "$CROWDSEC_INSTALL" = "yes" || "$CROWDSEC_APPSEC_INSTALL" = "yes" ]] && [[ "$INSTALL_TYPE" = "worker" || "$INSTALL_TYPE" = "scheduler" || "$INSTALL_TYPE" = "ui" || "$INSTALL_TYPE" = "api" ]]; then
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
            run_cmd apt install -y --allow-downgrades "bunkerweb=$BUNKERWEB_VERSION"
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
    detect_architecture
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

    # Check for port conflicts after knowing the install type
    check_ports

    # Set environment variables based on installation type
    case "$INSTALL_TYPE" in
        "manager")
            export MANAGER_MODE=yes
            export ENABLE_WIZARD=no
            ;;
        "worker")
            export WORKER_MODE=yes
            export ENABLE_WIZARD=no
            ;;
        "scheduler")
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=yes
            export SERVICE_UI=no
            ;;
        "ui")
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            export SERVICE_UI=yes
            ;;
        "api")
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
            export SERVICE_UI=no
            export SERVICE_API=yes
            ;;
        "full"|"")
            ;;
    esac

    # Pass UI_WIZARD to postinstall script
    if [ "$ENABLE_WIZARD" = "no" ]; then
        export UI_WIZARD=no
    fi

    print_status "Installing BunkerWeb $BUNKERWEB_VERSION"
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
    # Set environment variables to prevent postinstall from starting services we'll configure
    if [ "$INSTALL_TYPE" = "manager" ]; then
        export SERVICE_SCHEDULER=no
    elif [ "$INSTALL_TYPE" = "worker" ]; then
        export SERVICE_BUNKERWEB=no
    elif [ "$INSTALL_TYPE" = "full" ] || [ -z "$INSTALL_TYPE" ]; then
        # Only prevent start if we have configuration to apply
        if [ -n "$DNS_RESOLVERS_INPUT" ] || [ -n "$API_LISTEN_HTTPS_INPUT" ]; then
            export SERVICE_BUNKERWEB=no
            export SERVICE_SCHEDULER=no
        fi
    fi

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

    if [ "$INSTALL_TYPE" = "manager" ]; then
        configure_manager_api_defaults
    elif [ "$INSTALL_TYPE" = "worker" ]; then
        configure_worker_api_whitelist
    elif [ "$INSTALL_TYPE" = "full" ] || [ -z "$INSTALL_TYPE" ]; then
        configure_full_config
    fi

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
