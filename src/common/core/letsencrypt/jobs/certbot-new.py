#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from base64 import b64decode
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from json import dumps, loads
from os import environ, getenv, sep
from os.path import join
from pathlib import Path
from re import MULTILINE, match, search
from select import select
from shutil import which
from socket import getaddrinfo, gaierror, AF_INET, AF_INET6
from subprocess import DEVNULL, PIPE, STDOUT, Popen, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Dict, Literal, Type, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from pydantic import ValidationError
from requests import get

from letsencrypt import (
    CloudflareProvider,
    DesecProvider,
    DigitalOceanProvider,
    DnsimpleProvider,
    DnsMadeEasyProvider,
    GehirnProvider,
    GoogleProvider,
    InfomaniakProvider,
    IonosProvider,
    LinodeProvider,
    LuaDnsProvider,
    NjallaProvider,
    NSOneProvider,
    OvhProvider,
    Rfc2136Provider,
    Route53Provider,
    SakuraCloudProvider,
    ScalewayProvider,
    WildcardGenerator,
)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("LETS-ENCRYPT.new")
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", "bin", "certbot")
DEPS_PATH = join(sep, "usr", "share", "bunkerweb", "deps", "python")

LOGGER_CERTBOT = setup_logger("LETS-ENCRYPT.new.certbot")
status = 0

PLUGIN_PATH = Path(sep, "usr", "share", "bunkerweb", "core", "letsencrypt")
JOBS_PATH = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH = CACHE_PATH.joinpath("etc")
WORK_DIR = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR = join(sep, "var", "log", "bunkerweb", "letsencrypt")

PSL_URL = "https://publicsuffix.org/list/public_suffix_list.dat"
PSL_STATIC_FILE = "public_suffix_list.dat"

# ZeroSSL Configuration
ZEROSSL_ACME_SERVER = "https://acme.zerossl.com/v2/DV90"
ZEROSSL_STAGING_SERVER = "https://acme.zerossl.com/v2/DV90"  # ZeroSSL doesn't have staging
LETSENCRYPT_ACME_SERVER = "https://acme-v02.api.letsencrypt.org/directory"
LETSENCRYPT_STAGING_SERVER = "https://acme-staging-v02.api.letsencrypt.org/directory"


def load_public_suffix_list(job):
    # Load and cache the public suffix list for domain validation
    job_cache = job.get_cache(PSL_STATIC_FILE, with_info=True, with_data=True)
    if (
        isinstance(job_cache, dict)
        and job_cache.get("last_update")
        and job_cache["last_update"] < (datetime.now().astimezone() - 
                                       timedelta(days=1)).timestamp()
    ):
        return job_cache["data"].decode("utf-8").splitlines()

    try:
        resp = get(PSL_URL, timeout=5)
        resp.raise_for_status()
        content = resp.text
        cached, err = JOB.cache_file(PSL_STATIC_FILE, content.encode("utf-8"))
        if not cached:
            LOGGER.error(f"Error while saving public suffix list to cache : {err}")
        return content.splitlines()
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while downloading public suffix list : {e}")
        if PSL_STATIC_FILE.exists():
            with PSL_STATIC_FILE.open("r", encoding="utf-8") as f:
                return f.read().splitlines()
        return []


def parse_psl(psl_lines):
    # Parse PSL lines into rules and exceptions sets
    rules = set()
    exceptions = set()
    for line in psl_lines:
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("!"):
            exceptions.add(line[1:])
            continue
        rules.add(line)
    return {"rules": rules, "exceptions": exceptions}


def is_domain_blacklisted(domain, psl):
    # Check if domain is forbidden by PSL rules
    domain = domain.lower().strip(".")
    labels = domain.split(".")
    for i in range(len(labels)):
        candidate = ".".join(labels[i:])
        if candidate in psl["exceptions"]:
            return False
        if candidate in psl["rules"]:
            if i == 0:
                return True
            if i == 0 and domain.startswith("*."):
                return True
            if i == 0 or (i == 1 and labels[0] == "*"):
                return True
            if len(labels[i:]) == len(labels):
                return True
        if f"*.{candidate}" in psl["rules"]:
            if len(labels[i:]) == 2:
                return True
    return False


def get_certificate_authority_config(ca_provider, staging=False):
    # Get ACME server configuration for the specified CA provider
    if ca_provider.lower() == "zerossl":
        return {
            "server": ZEROSSL_STAGING_SERVER if staging else ZEROSSL_ACME_SERVER,
            "name": "ZeroSSL"
        }
    else:  # Default to Let's Encrypt
        return {
            "server": LETSENCRYPT_STAGING_SERVER if staging else LETSENCRYPT_ACME_SERVER,
            "name": "Let's Encrypt"
        }


def setup_zerossl_eab_credentials(email, api_key=None):
    # Setup External Account Binding (EAB) credentials for ZeroSSL
    LOGGER.info(f"Setting up ZeroSSL EAB credentials for email: {email}")
    
    if not api_key:
        LOGGER.error("❌ ZeroSSL API key not provided")
        LOGGER.warning("ZeroSSL API key not provided, attempting registration with email")
        return None, None
    
    LOGGER.info("Making request to ZeroSSL API for EAB credentials")
    
    # Try the correct ZeroSSL API endpoint
    try:
        # The correct endpoint for ZeroSSL EAB credentials
        response = get(
            "https://api.zerossl.com/acme/eab-credentials",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )
        LOGGER.info(f"ZeroSSL API response status: {response.status_code}")
        
        if response.status_code == 200:
            response.raise_for_status()
            eab_data = response.json()
            LOGGER.info(f"ZeroSSL API response data: {eab_data}")
            
            # ZeroSSL typically returns eab_kid and eab_hmac_key directly
            if "eab_kid" in eab_data and "eab_hmac_key" in eab_data:
                eab_kid = eab_data.get("eab_kid")
                eab_hmac_key = eab_data.get("eab_hmac_key")
                LOGGER.info(f"✓ Successfully obtained EAB credentials from ZeroSSL")
                LOGGER.info(f"EAB Kid: {eab_kid[:10] if eab_kid else 'None'}...")
                LOGGER.info(f"EAB HMAC Key: {eab_hmac_key[:10] if eab_hmac_key else 'None'}...")
                return eab_kid, eab_hmac_key
            else:
                LOGGER.error(f"❌ Invalid ZeroSSL API response format: {eab_data}")
                return None, None
        else:
            # Try alternative endpoint if first one fails
            LOGGER.warning(f"Primary endpoint failed with {response.status_code}, trying alternative")
            response_text = response.text
            LOGGER.info(f"Primary endpoint response: {response_text}")
            
            # Try alternative endpoint with email parameter
            response = get(
                "https://api.zerossl.com/acme/eab-credentials-email",
                params={"email": email},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30
            )
            LOGGER.info(f"Alternative ZeroSSL API response status: {response.status_code}")
            response.raise_for_status()
            eab_data = response.json()
            
            LOGGER.info(f"Alternative ZeroSSL API response data: {eab_data}")
            
            if eab_data.get("success"):
                eab_kid = eab_data.get("eab_kid")
                eab_hmac_key = eab_data.get("eab_hmac_key")
                LOGGER.info(f"✓ Successfully obtained EAB credentials from ZeroSSL (alternative endpoint)")
                LOGGER.info(f"EAB Kid: {eab_kid[:10] if eab_kid else 'None'}...")
                LOGGER.info(f"EAB HMAC Key: {eab_hmac_key[:10] if eab_hmac_key else 'None'}...")
                return eab_kid, eab_hmac_key
            else:
                LOGGER.error(f"❌ ZeroSSL EAB registration failed: {eab_data}")
                return None, None
            
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"❌ Error setting up ZeroSSL EAB credentials: {e}")
        
        # Additional troubleshooting info
        LOGGER.error("Troubleshooting steps:")
        LOGGER.error("1. Verify your ZeroSSL API key is valid")
        LOGGER.error("2. Check your ZeroSSL account has ACME access enabled")
        LOGGER.error("3. Ensure the API key has the correct permissions")
        LOGGER.error("4. Try regenerating your ZeroSSL API key")
        
        return None, None


def get_caa_records(domain):
    # Get CAA records for a domain using dig command
    
    # Check if dig command is available
    if not which("dig"):
        LOGGER.info("dig command not available for CAA record checking")
        return None
    
    try:
        # Use dig to query CAA records
        LOGGER.info(f"Querying CAA records for domain: {domain}")
        result = run(
            ["dig", "+short", domain, "CAA"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            LOGGER.info(f"Found CAA records for domain {domain}")
            caa_records = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line:
                    # CAA record format: flags tag "value"
                    # Example: 0 issue "letsencrypt.org"
                    parts = line.split(' ', 2)
                    if len(parts) >= 3:
                        flags = parts[0]
                        tag = parts[1]
                        value = parts[2].strip('"')
                        caa_records.append({
                            'flags': flags,
                            'tag': tag,
                            'value': value
                        })
            LOGGER.info(f"Parsed {len(caa_records)} CAA records for domain {domain}")
            return caa_records
        else:
            LOGGER.info(f"No CAA records found for domain {domain} (dig return code: {result.returncode})")
            return []
            
    except BaseException as e:
        LOGGER.info(f"Error querying CAA records for {domain}: {e}")
        return None


def check_caa_authorization(domain, ca_provider, is_wildcard=False):
    # Check if the CA provider is authorized by CAA records
    
    LOGGER.info(f"Checking CAA authorization for domain: {domain}, CA: {ca_provider}, wildcard: {is_wildcard}")
    
    # Map CA providers to their CAA identifiers
    ca_identifiers = {
        "letsencrypt": ["letsencrypt.org"],
        "zerossl": ["sectigo.com", "zerossl.com"]  # ZeroSSL uses Sectigo
    }
    
    allowed_identifiers = ca_identifiers.get(ca_provider.lower(), [])
    if not allowed_identifiers:
        LOGGER.warning(f"Unknown CA provider for CAA check: {ca_provider}")
        return True  # Allow unknown providers (conservative approach)
    
    # Check CAA records for the domain and parent domains
    check_domain = domain.lstrip("*.")
    domain_parts = check_domain.split(".")
    LOGGER.info(f"Will check CAA records for domain chain: {check_domain}")
    
    for i in range(len(domain_parts)):
        current_domain = ".".join(domain_parts[i:])
        LOGGER.info(f"Checking CAA records for: {current_domain}")
        caa_records = get_caa_records(current_domain)
        
        if caa_records is None:
            # dig not available, skip CAA check
            LOGGER.info("CAA record checking skipped (dig command not available)")
            return True
        
        if caa_records:
            LOGGER.info(f"Found CAA records for {current_domain}")
            
            # Check relevant CAA records
            issue_records = []
            issuewild_records = []
            
            for record in caa_records:
                if record['tag'] == 'issue':
                    issue_records.append(record['value'])
                elif record['tag'] == 'issuewild':
                    issuewild_records.append(record['value'])
            
            # Log found records
            if issue_records:
                LOGGER.info(f"CAA issue records: {', '.join(issue_records)}")
            if issuewild_records:
                LOGGER.info(f"CAA issuewild records: {', '.join(issuewild_records)}")
            
            # Check authorization based on certificate type
            if is_wildcard:
                # For wildcard certificates, check issuewild first, then fall back to issue
                check_records = issuewild_records if issuewild_records else issue_records
                record_type = "issuewild" if issuewild_records else "issue"
            else:
                # For regular certificates, check issue records
                check_records = issue_records
                record_type = "issue"
            
            LOGGER.info(f"Using CAA {record_type} records for authorization check")
            
            if not check_records:
                LOGGER.info(f"No relevant CAA {record_type} records found for {current_domain}")
                continue
            
            # Check if any of our CA identifiers are authorized
            authorized = False
            LOGGER.info(f"Checking authorization for CA identifiers: {', '.join(allowed_identifiers)}")
            for identifier in allowed_identifiers:
                for record in check_records:
                    # Handle explicit deny (empty value or semicolon)
                    if record == ";" or record.strip() == "":
                        LOGGER.warning(f"CAA {record_type} record explicitly denies all CAs")
                        return False
                    
                    # Check for CA authorization
                    if identifier in record:
                        authorized = True
                        LOGGER.info(f"✓ CA {ca_provider} ({identifier}) authorized by CAA {record_type} record")
                        break
                if authorized:
                    break
            
            if not authorized:
                LOGGER.error(f"❌ CA {ca_provider} is NOT authorized by CAA {record_type} records")
                LOGGER.error(f"Domain {current_domain} CAA {record_type} allows: {', '.join(check_records)}")
                LOGGER.error(f"But {ca_provider} uses: {', '.join(allowed_identifiers)}")
                return False
            
            # If we found CAA records and we're authorized, we can stop checking parent domains
            LOGGER.info(f"✓ CAA authorization successful for {domain}")
            return True
    
    # No CAA records found in the entire chain
    LOGGER.info(f"No CAA records found for {check_domain} or parent domains - any CA allowed")
    return True


def validate_domains_for_http_challenge(domains_list, ca_provider="letsencrypt", is_wildcard=False):
    # Validate that all domains have valid A/AAAA records and CAA authorization for HTTP challenge
    LOGGER.info(f"Validating {len(domains_list)} domains for HTTP challenge: {', '.join(domains_list)}")
    invalid_domains = []
    caa_blocked_domains = []
    
    # Check if CAA validation should be skipped
    skip_caa_check = getenv("ACME_LETS_ENCRYPT_SKIP_CAA_CHECK", "no") == "yes"
    
    # Get external IPs once for all domain checks
    external_ips = get_external_ip()
    if external_ips:
        if external_ips.get("ipv4"):
            LOGGER.info(f"Server external IPv4 address: {external_ips['ipv4']}")
        if external_ips.get("ipv6"):
            LOGGER.info(f"Server external IPv6 address: {external_ips['ipv6']}")
    else:
        LOGGER.warning("Could not determine server external IP - skipping IP match validation")
    
    for domain in domains_list:
        # Check DNS A/AAAA records with retry mechanism
        if not check_domain_a_record(domain, external_ips):
            invalid_domains.append(domain)
            continue
        
        # Check CAA authorization
        if not skip_caa_check:
            if not check_caa_authorization(domain, ca_provider, is_wildcard):
                caa_blocked_domains.append(domain)
        else:
            LOGGER.info(f"CAA check skipped for {domain} (ACME_LETS_ENCRYPT_SKIP_CAA_CHECK=yes)")
    
    # Report results
    if invalid_domains:
        LOGGER.error(f"The following domains do not have valid A/AAAA records and cannot be used "
                    f"for HTTP challenge: {', '.join(invalid_domains)}")
        LOGGER.error("Please ensure domains resolve to this server before requesting certificates")
        return False
    
    if caa_blocked_domains:
        LOGGER.error(f"The following domains have CAA records that block {ca_provider}: "
                    f"{', '.join(caa_blocked_domains)}")
        LOGGER.error("Please update CAA records to authorize the certificate authority or use a different CA")
        LOGGER.info("You can skip CAA checking by setting ACME_LETS_ENCRYPT_SKIP_CAA_CHECK=yes")
        return False
    
    LOGGER.info(f"All domains have valid DNS records and CAA authorization for HTTP challenge: {', '.join(domains_list)}")
    return True


def get_external_ip():
    # Get the external/public IP addresses of this server (both IPv4 and IPv6)
    LOGGER.info("Getting external IP addresses for server")
    ipv4_services = [
        "https://ipv4.icanhazip.com",
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "https://ipv4.jsonip.com"
    ]
    
    ipv6_services = [
        "https://ipv6.icanhazip.com",
        "https://api6.ipify.org",
        "https://ipv6.jsonip.com"
    ]
    
    external_ips = {"ipv4": None, "ipv6": None}
    
    # Try to get IPv4 address
    LOGGER.info("Attempting to get external IPv4 address")
    for service in ipv4_services:
        try:
            if "jsonip.com" in service:
                # This service returns JSON format
                response = get(service, timeout=5)
                response.raise_for_status()
                data = response.json()
                ip = data.get("ip", "").strip()
            else:
                # These services return plain text IP
                response = get(service, timeout=5)
                response.raise_for_status()
                ip = response.text.strip()
            
            # Basic IPv4 validation
            if ip and "." in ip and len(ip.split(".")) == 4:
                try:
                    # Validate it's a proper IPv4 address
                    getaddrinfo(ip, None, AF_INET)
                    external_ips["ipv4"] = ip
                    LOGGER.info(f"Successfully obtained external IPv4 address: {ip}")
                    break
                except gaierror:
                    continue
        except BaseException as e:
            LOGGER.info(f"Failed to get IPv4 address from {service}: {e}")
            continue
    
    # Try to get IPv6 address
    LOGGER.info("Attempting to get external IPv6 address")
    for service in ipv6_services:
        try:
            if "jsonip.com" in service:
                response = get(service, timeout=5)
                response.raise_for_status()
                data = response.json()
                ip = data.get("ip", "").strip()
            else:
                response = get(service, timeout=5)
                response.raise_for_status()
                ip = response.text.strip()
            
            # Basic IPv6 validation
            if ip and ":" in ip:
                try:
                    # Validate it's a proper IPv6 address
                    getaddrinfo(ip, None, AF_INET6)
                    external_ips["ipv6"] = ip
                    LOGGER.info(f"Successfully obtained external IPv6 address: {ip}")
                    break
                except gaierror:
                    continue
        except BaseException as e:
            LOGGER.info(f"Failed to get IPv6 address from {service}: {e}")
            continue
    
    if not external_ips["ipv4"] and not external_ips["ipv6"]:
        LOGGER.warning("Could not determine external IP address (IPv4 or IPv6) from any service")
        return None
    
    LOGGER.info(f"External IP detection completed - IPv4: {external_ips['ipv4'] or 'not found'}, IPv6: {external_ips['ipv6'] or 'not found'}")
    return external_ips


def check_domain_a_record(domain, external_ips=None):
    # Check if domain has valid A/AAAA records for HTTP challenge
    LOGGER.info(f"Checking DNS A/AAAA records for domain: {domain}")
    try:
        # Remove wildcard prefix if present
        check_domain = domain.lstrip("*.")
        
        # Attempt to resolve the domain to IP addresses
        result = getaddrinfo(check_domain, None)
        if result:
            ipv4_addresses = [addr[4][0] for addr in result if addr[0] == AF_INET]
            ipv6_addresses = [addr[4][0] for addr in result if addr[0] == AF_INET6]
            
            if not ipv4_addresses and not ipv6_addresses:
                LOGGER.warning(f"Domain {check_domain} has no A or AAAA records")
                return False
            
            # Log found addresses
            if ipv4_addresses:
                LOGGER.info(f"Domain {check_domain} IPv4 A records: {', '.join(ipv4_addresses[:3])}")
            if ipv6_addresses:
                LOGGER.info(f"Domain {check_domain} IPv6 AAAA records: {', '.join(ipv6_addresses[:3])}")
            
            # Check if any record matches the external IPs
            if external_ips:
                ipv4_match = False
                ipv6_match = False
                
                # Check IPv4 match
                if external_ips.get("ipv4") and ipv4_addresses:
                    if external_ips["ipv4"] in ipv4_addresses:
                        LOGGER.info(f"✓ Domain {check_domain} IPv4 A record matches server external IP ({external_ips['ipv4']})")
                        ipv4_match = True
                    else:
                        LOGGER.warning(f"⚠ Domain {check_domain} IPv4 A record does not match server external IP")
                        LOGGER.warning(f"  Domain IPv4: {', '.join(ipv4_addresses)}")
                        LOGGER.warning(f"  Server IPv4: {external_ips['ipv4']}")
                
                # Check IPv6 match
                if external_ips.get("ipv6") and ipv6_addresses:
                    if external_ips["ipv6"] in ipv6_addresses:
                        LOGGER.info(f"✓ Domain {check_domain} IPv6 AAAA record matches server external IP ({external_ips['ipv6']})")
                        ipv6_match = True
                    else:
                        LOGGER.warning(f"⚠ Domain {check_domain} IPv6 AAAA record does not match server external IP")
                        LOGGER.warning(f"  Domain IPv6: {', '.join(ipv6_addresses)}")
                        LOGGER.warning(f"  Server IPv6: {external_ips['ipv6']}")
                
                # Determine if we have any matching records
                has_any_match = ipv4_match or ipv6_match
                has_external_ip = external_ips.get("ipv4") or external_ips.get("ipv6")
                
                if has_external_ip and not has_any_match:
                    LOGGER.warning(f"⚠ Domain {check_domain} records do not match any server external IP")
                    LOGGER.warning(f"  HTTP challenge may fail - ensure domain points to this server")
                    
                    # Check if we should treat this as an error
                    strict_ip_check = getenv("LETS_ENCRYPT_HTTP_STRICT_IP_CHECK", "no") == "yes"
                    if strict_ip_check:
                        LOGGER.error(f"Strict IP check enabled - rejecting certificate request for {check_domain}")
                        return False
            
            LOGGER.info(f"✓ Domain {check_domain} DNS validation passed")
            return True
        else:
            LOGGER.info(f"Domain {check_domain} validation failed - no DNS resolution")
            LOGGER.warning(f"Domain {check_domain} does not resolve")
            return False
            
    except gaierror as e:
        LOGGER.info(f"Domain {check_domain} DNS resolution failed (gaierror): {e}")
        LOGGER.warning(f"DNS resolution failed for domain {check_domain}: {e}")
        return False
    except BaseException as e:
        LOGGER.info(format_exc())
        LOGGER.error(f"Error checking DNS records for domain {check_domain}: {e}")
        return False


def validate_domains_for_http_challenge(domains_list):
    # Validate that all domains have valid A/AAAA records for HTTP challenge
    LOGGER.info(f"Validating {len(domains_list)} domains for HTTP challenge: {', '.join(domains_list)}")
    invalid_domains = []
    
    # Get external IPs once for all domain checks
    external_ips = get_external_ip()
    if external_ips:
        if external_ips.get("ipv4"):
            LOGGER.info(f"Server external IPv4 address: {external_ips['ipv4']}")
        if external_ips.get("ipv6"):
            LOGGER.info(f"Server external IPv6 address: {external_ips['ipv6']}")
    else:
        LOGGER.warning("Could not determine server external IP - skipping IP match validation")
    
    for domain in domains_list:
        if not check_domain_a_record(domain, external_ips):
            invalid_domains.append(domain)
    
    if invalid_domains:
        LOGGER.error(f"The following domains do not have valid A/AAAA records and cannot be used "
                    f"for HTTP challenge: {', '.join(invalid_domains)}")
        LOGGER.error("Please ensure domains resolve to this server before requesting certificates")
        return False
    
    LOGGER.info(f"All domains have valid DNS records for HTTP challenge: {', '.join(domains_list)}")
    return True


def certbot_new_with_retry(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: str = None,
    credentials_path: Union[str, Path] = None,
    propagation: str = "default",
    profile: str = "classic",
    staging: bool = False,
    force: bool = False,
    cmd_env: Dict[str, str] = None,
    max_retries: int = 0,
    ca_provider: str = "letsencrypt",
    api_key: str = None,
    server_name: str = None,
) -> int:
    # Execute certbot with retry mechanism
    attempt = 1
    while attempt <= max_retries + 1:
        if attempt > 1:
            LOGGER.warning(f"Certificate generation failed, retrying... "
                          f"(attempt {attempt}/{max_retries + 1})")
            wait_time = min(30 * (2 ** (attempt - 2)), 300)
            LOGGER.info(f"Waiting {wait_time} seconds before retry...")
            sleep(wait_time)

        result = certbot_new(
            challenge_type,
            domains,
            email,
            provider,
            credentials_path,
            propagation,
            profile,
            staging,
            force,
            cmd_env,
            ca_provider,
            api_key,
            server_name,
        )

        if result == 0:
            if attempt > 1:
                LOGGER.info(f"Certificate generation succeeded on attempt {attempt}")
            return result

        if attempt >= max_retries + 1:
            LOGGER.error(f"Certificate generation failed after {max_retries + 1} attempts")
            return result

        attempt += 1

    return result


def certbot_new(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: str = None,
    credentials_path: Union[str, Path] = None,
    propagation: str = "default",
    profile: str = "classic",
    staging: bool = False,
    force: bool = False,
    cmd_env: Dict[str, str] = None,
    ca_provider: str = "letsencrypt",
    api_key: str = None,
    server_name: str = None,
) -> int:
    # Generate new certificate using certbot
    if isinstance(credentials_path, str):
        credentials_path = Path(credentials_path)

    ca_config = get_certificate_authority_config(ca_provider, staging)
    
    command = [
        CERTBOT_BIN,
        "certonly",
        "--config-dir",
        DATA_PATH.as_posix(),
        "--work-dir",
        WORK_DIR,
        "--logs-dir",
        LOGS_DIR,
        "-n",
        "-d",
        domains,
        "--email",
        email,
        "--agree-tos",
        "--expand",
        f"--preferred-profile={profile}",
        "--server",
        ca_config["server"],
    ]

    if not cmd_env:
        cmd_env = {}

    # Handle certificate key type based on DNS provider and CA
    if challenge_type == "dns" and provider in ("infomaniak", "ionos"):
        # Infomaniak and IONOS require RSA certificates with 4096-bit keys
        command.extend(["--rsa-key-size", "4096"])
        LOGGER.info(f"Using RSA-4096 for {provider} provider with {domains}")
    else:
        # Use elliptic curve certificates for all other providers
        if ca_provider.lower() == "zerossl":
            # Use P-384 elliptic curve for ZeroSSL certificates
            command.extend(["--elliptic-curve", "secp384r1"])
            LOGGER.info(f"Using ZeroSSL P-384 curve for {domains}")
        else:
            # Use P-256 elliptic curve for Let's Encrypt certificates
            command.extend(["--elliptic-curve", "secp256r1"])
            LOGGER.info(f"Using Let's Encrypt P-256 curve for {domains}")
    
    # Handle ZeroSSL EAB credentials
    if ca_provider.lower() == "zerossl":
        LOGGER.info(f"ZeroSSL detected as CA provider for {domains}")
        
        # Check for manually provided EAB credentials first
        eab_kid_env = getenv("ACME_ZEROSSL_EAB_KID", "") or getenv(f"{server_name}_ACME_ZEROSSL_EAB_KID", "")
        eab_hmac_env = getenv("ACME_ZEROSSL_EAB_HMAC_KEY", "") or getenv(f"{server_name}_ACME_ZEROSSL_EAB_HMAC_KEY", "")
        
        if eab_kid_env and eab_hmac_env:
            LOGGER.info("✓ Using manually provided ZeroSSL EAB credentials from environment")
            command.extend(["--eab-kid", eab_kid_env, "--eab-hmac-key", eab_hmac_env])
            LOGGER.info(f"✓ Using ZeroSSL EAB credentials for {domains}")
            LOGGER.info(f"EAB Kid: {eab_kid_env[:10]}...")
        elif api_key:
            LOGGER.info(f"ZeroSSL API key provided, setting up EAB credentials")
            eab_kid, eab_hmac = setup_zerossl_eab_credentials(email, api_key)
            if eab_kid and eab_hmac:
                command.extend(["--eab-kid", eab_kid, "--eab-hmac-key", eab_hmac])
                LOGGER.info(f"✓ Using ZeroSSL EAB credentials for {domains}")
                LOGGER.info(f"EAB Kid: {eab_kid[:10]}...")
            else:
                LOGGER.error("❌ Failed to obtain ZeroSSL EAB credentials")
                LOGGER.error("Alternative: Set ACME_ZEROSSL_EAB_KID and ACME_ZEROSSL_EAB_HMAC_KEY environment variables")
                LOGGER.warning("Proceeding without EAB - this will likely fail")
        else:
            LOGGER.error("❌ No ZeroSSL API key provided!")
            LOGGER.error("Set ACME_ZEROSSL_API_KEY environment variable")
            LOGGER.error("Or set ACME_ZEROSSL_EAB_KID and ACME_ZEROSSL_EAB_HMAC_KEY directly")
            LOGGER.warning("Proceeding without EAB - this will likely fail")

    if challenge_type == "dns":
        command.append("--preferred-challenges=dns")

        if propagation != "default":
            if not propagation.isdigit():
                LOGGER.warning(f"Invalid propagation time : {propagation}, "
                              "using provider's default...")
            else:
                command.extend([f"--dns-{provider}-propagation-seconds", propagation])

        if provider == "route53":
            with credentials_path.open("r") as file:
                for line in file:
                    key, value = line.strip().split("=", 1)
                    cmd_env[key] = value
        else:
            command.extend([f"--dns-{provider}-credentials", credentials_path.as_posix()])

        if provider in ("desec", "infomaniak", "ionos", "njalla", "scaleway"):
            command.extend(["--authenticator", f"dns-{provider}"])
        else:
            command.append(f"--dns-{provider}")

    elif challenge_type == "http":
        command.extend(
            [
                "--manual",
                "--preferred-challenges=http",
                "--manual-auth-hook",
                JOBS_PATH.joinpath("certbot-auth.py").as_posix(),
                "--manual-cleanup-hook",
                JOBS_PATH.joinpath("certbot-cleanup.py").as_posix(),
            ]
        )

    if force:
        command.append("--force-renewal")

    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        command.append("-v")

    LOGGER.info(f"Executing certbot command for {domains}")
    # Show command but mask sensitive EAB values for security
    safe_command = []
    mask_next = False
    for item in command:
        if mask_next:
            safe_command.append("***MASKED***")
            mask_next = False
        elif item in ["--eab-kid", "--eab-hmac-key"]:
            safe_command.append(item)
            mask_next = True
        else:
            safe_command.append(item)
    LOGGER.info(f"Command: {' '.join(safe_command)}")
    
    current_date = datetime.now()
    process = Popen(command, stdin=DEVNULL, stderr=PIPE, universal_newlines=True, env=cmd_env)

    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    break

        if datetime.now() - current_date > timedelta(seconds=5):
            challenge_info = (" (this may take a while depending on the provider)" 
                            if challenge_type == "dns" else "")
            LOGGER.info(f"⏳ Still generating {ca_config['name']} certificate(s)"
                       f"{challenge_info}...")
            current_date = datetime.now()

    return process.returncode


IS_MULTISITE = getenv("MULTISITE", "no") == "yes"

try:
    servers = getenv("SERVER_NAME", "www.example.com").lower() or []

    if isinstance(servers, str):
        servers = servers.split(" ")

    if not servers:
        LOGGER.warning("There are no server names, skipping generation...")
        sys_exit(0)

    use_letsencrypt = False
    use_letsencrypt_dns = False

    if not IS_MULTISITE:
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        use_letsencrypt_dns = getenv("LETS_ENCRYPT_CHALLENGE", "http") == "dns"
        domains_server_names = {servers[0]: " ".join(servers).lower()}
    else:
        domains_server_names = {}

        for first_server in servers:
            if first_server and getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") == "yes":
                use_letsencrypt = True

            if first_server and getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", 
                                      "http") == "dns":
                use_letsencrypt_dns = True

            domains_server_names[first_server] = getenv(f"{first_server}_SERVER_NAME", 
                                                       first_server).lower()

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping generation...")
        sys_exit(0)

    provider_classes = {}

    if use_letsencrypt_dns:
        provider_classes: Dict[
            str,
            Union[
                Type[CloudflareProvider],
                Type[DesecProvider],
                Type[DigitalOceanProvider],
                Type[DnsimpleProvider],
                Type[DnsMadeEasyProvider],
                Type[GehirnProvider],
                Type[GoogleProvider],
                Type[InfomaniakProvider],
                Type[IonosProvider],
                Type[LinodeProvider],
                Type[LuaDnsProvider],
                Type[NjallaProvider],
                Type[NSOneProvider],
                Type[OvhProvider],
                Type[Rfc2136Provider],
                Type[Route53Provider],
                Type[SakuraCloudProvider],
                Type[ScalewayProvider],
            ],
        ] = {
            "cloudflare": CloudflareProvider,
            "desec": DesecProvider,
            "digitalocean": DigitalOceanProvider,
            "dnsimple": DnsimpleProvider,
            "dnsmadeeasy": DnsMadeEasyProvider,
            "gehirn": GehirnProvider,
            "google": GoogleProvider,
            "infomaniak": InfomaniakProvider,
            "ionos": IonosProvider,
            "linode": LinodeProvider,
            "luadns": LuaDnsProvider,
            "njalla": NjallaProvider,
            "nsone": NSOneProvider,
            "ovh": OvhProvider,
            "rfc2136": Rfc2136Provider,
            "route53": Route53Provider,
            "sakuracloud": SakuraCloudProvider,
            "scaleway": ScalewayProvider,
        }

    JOB = Job(LOGGER, __file__)

    # Restore data from db cache of certbot-renew job
    JOB.restore_cache(job_name="certbot-renew")

    env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "RELOAD_MIN_TIMEOUT": getenv("RELOAD_MIN_TIMEOUT", "5"),
        "DISABLE_CONFIGURATION_TESTING": getenv("DISABLE_CONFIGURATION_TESTING", 
                                               "no").lower(),
    }
    env["PYTHONPATH"] = env["PYTHONPATH"] + (f":{DEPS_PATH}" 
                                           if DEPS_PATH not in env["PYTHONPATH"] 
                                           else "")
    if getenv("DATABASE_URI"):
        env["DATABASE_URI"] = getenv("DATABASE_URI")

    proc = run(
        [
            CERTBOT_BIN,
            "certificates",
            "--config-dir",
            DATA_PATH.as_posix(),
            "--work-dir",
            WORK_DIR,
            "--logs-dir",
            LOGS_DIR,
        ],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        env=env,
        check=False,
    )
    stdout = proc.stdout

    WILDCARD_GENERATOR = WildcardGenerator()
    credential_paths = set()
    generated_domains = set()
    domains_to_ask = {}
    active_cert_names = set()

    if proc.returncode != 0:
        LOGGER.error(f"Error while checking certificates :\n{proc.stdout}")
    else:
        certificate_blocks = stdout.split("Certificate Name: ")[1:]
        for first_server, domains in domains_server_names.items():
            if (getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") if IS_MULTISITE 
                else getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
                continue

            letsencrypt_challenge = (getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", 
                                          "http") if IS_MULTISITE 
                                   else getenv("LETS_ENCRYPT_CHALLENGE", "http"))
            original_first_server = deepcopy(first_server)

            if (
                letsencrypt_challenge == "dns"
                and (getenv(f"{original_first_server}_USE_LETS_ENCRYPT_WILDCARD", "no") 
                     if IS_MULTISITE 
                     else getenv("USE_LETS_ENCRYPT_WILDCARD", "no")) == "yes"
            ):
                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains((first_server,))
                first_server = wildcards[0].lstrip("*.")
                domains = set(wildcards)
            else:
                domains = set(domains.split(" "))

            # Add the certificate name to our active set regardless if we're generating it or not
            active_cert_names.add(first_server)

            certificate_block = None
            for block in certificate_blocks:
                if block.startswith(f"{first_server}\n"):
                    certificate_block = block
                    break

            if not certificate_block:
                domains_to_ask[first_server] = 1
                LOGGER.warning(f"[{original_first_server}] Certificate block for "
                              f"{first_server} not found, asking new certificate...")
                continue

            # Validating the credentials
            try:
                cert_domains = search(r"Domains: (?P<domains>.*)\n\s*Expiry Date: "
                                    r"(?P<expiry_date>.*)\n", certificate_block, MULTILINE)
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"[{original_first_server}] Error while parsing "
                           f"certificate block: {e}")
                continue

            if not cert_domains:
                LOGGER.error(f"[{original_first_server}] Failed to parse domains "
                           "and expiry date from certificate block.")
                continue

            cert_domains_list = cert_domains.group("domains").strip().split()
            cert_domains_set = set(cert_domains_list)
            desired_domains_set = (set(domains) if isinstance(domains, (list, set)) 
                                 else set(domains.split()))

            if cert_domains_set != desired_domains_set:
                domains_to_ask[first_server] = 2
                LOGGER.warning(
                    f"[{original_first_server}] Domains for {first_server} differ "
                    f"from desired set (existing: {sorted(cert_domains_set)}, "
                    f"desired: {sorted(desired_domains_set)}), asking new certificate..."
                )
                continue

            # Check if CA provider has changed
            ca_provider = (getenv(f"{original_first_server}_ACME_SSL_CA_PROVIDER", 
                                "letsencrypt") if IS_MULTISITE 
                         else getenv("ACME_SSL_CA_PROVIDER", "letsencrypt"))
            
            renewal_file = DATA_PATH.joinpath("renewal", f"{first_server}.conf")
            if renewal_file.is_file():
                current_server = None
                with renewal_file.open("r") as file:
                    for line in file:
                        if line.startswith("server"):
                            current_server = line.strip().split("=", 1)[1].strip()
                            break
                
                expected_config = get_certificate_authority_config(
                    ca_provider, 
                    (getenv(f"{original_first_server}_USE_LETS_ENCRYPT_STAGING", "no") 
                     if IS_MULTISITE 
                     else getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes"
                )
                
                if current_server and current_server != expected_config["server"]:
                    domains_to_ask[first_server] = 2
                    LOGGER.warning(f"[{original_first_server}] CA provider for "
                                 f"{first_server} has changed, asking new certificate...")
                    continue

            use_staging = (
                getenv(f"{original_first_server}_USE_LETS_ENCRYPT_STAGING", "no") 
                if IS_MULTISITE 
                else getenv("USE_LETS_ENCRYPT_STAGING", "no")
            ) == "yes"
            is_test_cert = "TEST_CERT" in cert_domains.group("expiry_date")

            if (is_test_cert and not use_staging) or (not is_test_cert and use_staging):
                domains_to_ask[first_server] = 2
                LOGGER.warning(f"[{original_first_server}] Certificate environment "
                              f"(staging/production) changed for {first_server}, "
                              "asking new certificate...")
                continue

            provider = (getenv(f"{original_first_server}_LETS_ENCRYPT_DNS_PROVIDER", "") 
                       if IS_MULTISITE 
                       else getenv("LETS_ENCRYPT_DNS_PROVIDER", ""))

            if not renewal_file.is_file():
                LOGGER.error(f"[{original_first_server}] Renewal file for "
                           f"{first_server} not found, asking new certificate...")
                domains_to_ask[first_server] = 1
                continue

            current_provider = None
            with renewal_file.open("r") as file:
                for line in file:
                    if line.startswith("authenticator"):
                        key, value = line.strip().split("=", 1)
                        current_provider = value.strip().replace("dns-", "")
                        break

            if letsencrypt_challenge == "dns":
                if provider and current_provider != provider:
                    domains_to_ask[first_server] = 2
                    LOGGER.warning(f"[{original_first_server}] Provider for "
                                 f"{first_server} is not the same as in the "
                                 "certificate, asking new certificate...")
                    continue

                # Check if DNS credentials have changed
                if provider and current_provider == provider:
                    credential_key = (f"{original_first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
                                    if IS_MULTISITE 
                                    else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM")
                    current_credential_items = {}

                    for env_key, env_value in environ.items():
                        if env_value and env_key.startswith(credential_key):
                            if " " not in env_value:
                                current_credential_items["json_data"] = env_value
                                continue
                            key, value = env_value.split(" ", 1)
                            current_credential_items[key.lower()] = (
                                value.removeprefix("= ").replace("\\n", "\n")
                                     .replace("\\t", "\t").replace("\\r", "\r").strip()
                            )

                    if "json_data" in current_credential_items:
                        value = current_credential_items.pop("json_data")
                        if (not current_credential_items and len(value) % 4 == 0 
                            and match(r"^[A-Za-z0-9+/=]+$", value)):
                            with suppress(BaseException):
                                decoded = b64decode(value).decode("utf-8")
                                json_data = loads(decoded)
                                if isinstance(json_data, dict):
                                    current_credential_items = {
                                        k.lower(): str(v).removeprefix("= ")
                                                           .replace("\\n", "\n")
                                                           .replace("\\t", "\t")
                                                           .replace("\\r", "\r").strip()
                                        for k, v in json_data.items()
                                    }

                    if current_credential_items:
                        for key, value in current_credential_items.items():
                            if (provider != "rfc2136" and len(value) % 4 == 0 
                                and match(r"^[A-Za-z0-9+/=]+$", value)):
                                with suppress(BaseException):
                                    decoded = b64decode(value).decode("utf-8")
                                    if decoded != value:
                                        current_credential_items[key] = (
                                            decoded.removeprefix("= ")
                                                   .replace("\\n", "\n")
                                                   .replace("\\t", "\t")
                                                   .replace("\\r", "\r").strip()
                                        )

                        if provider in provider_classes:
                            with suppress(ValidationError, KeyError):
                                current_provider_instance = provider_classes[provider](
                                    **current_credential_items
                                )
                                current_credentials_content = (
                                    current_provider_instance.get_formatted_credentials()
                                )

                                file_type = current_provider_instance.get_file_type()
                                stored_credentials_path = CACHE_PATH.joinpath(
                                    first_server, f"credentials.{file_type}"
                                )

                                if stored_credentials_path.is_file():
                                    stored_credentials_content = (
                                        stored_credentials_path.read_bytes()
                                    )
                                    if stored_credentials_content != current_credentials_content:
                                        domains_to_ask[first_server] = 2
                                        LOGGER.warning(
                                            f"[{original_first_server}] DNS credentials "
                                            f"for {first_server} have changed, "
                                            "asking new certificate..."
                                        )
                                        continue
            elif current_provider != "manual" and letsencrypt_challenge == "http":
                domains_to_ask[first_server] = 2
                LOGGER.warning(f"[{original_first_server}] {first_server} is no longer "
                              "using DNS challenge, asking new certificate...")
                continue

            domains_to_ask[first_server] = 0
            LOGGER.info(f"[{original_first_server}] Certificates already exist for "
                       f"domain(s) {domains}, expiry date: "
                       f"{cert_domains.group('expiry_date')}")

    psl_lines = None
    psl_rules = None

    for first_server, domains in domains_server_names.items():
        if (getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") if IS_MULTISITE 
            else getenv("AUTO_LETS_ENCRYPT", "no")) != "yes":
            LOGGER.info(f"SSL certificate generation is not activated for "
                       f"{first_server}, skipping...")
            continue

        # Getting all the necessary data
        data = {
            "email": (getenv(f"{first_server}_EMAIL_LETS_ENCRYPT", "") if IS_MULTISITE 
                     else getenv("EMAIL_LETS_ENCRYPT", "")) or f"contact@{first_server}",
            "challenge": (getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") 
                         if IS_MULTISITE 
                         else getenv("LETS_ENCRYPT_CHALLENGE", "http")),
            "staging": (getenv(f"{first_server}_USE_LETS_ENCRYPT_STAGING", "no") 
                       if IS_MULTISITE 
                       else getenv("USE_LETS_ENCRYPT_STAGING", "no")) == "yes",
            "use_wildcard": (getenv(f"{first_server}_USE_LETS_ENCRYPT_WILDCARD", "no") 
                           if IS_MULTISITE 
                           else getenv("USE_LETS_ENCRYPT_WILDCARD", "no")) == "yes",
            "provider": (getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER", "") 
                        if IS_MULTISITE 
                        else getenv("LETS_ENCRYPT_DNS_PROVIDER", "")),
            "propagation": (getenv(f"{first_server}_LETS_ENCRYPT_DNS_PROPAGATION", 
                                  "default") if IS_MULTISITE 
                           else getenv("LETS_ENCRYPT_DNS_PROPAGATION", "default")),
            "profile": (getenv(f"{first_server}_LETS_ENCRYPT_PROFILE", "classic") 
                       if IS_MULTISITE 
                       else getenv("LETS_ENCRYPT_PROFILE", "classic")),
            "check_psl": (getenv(f"{first_server}_LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", 
                               "yes") if IS_MULTISITE 
                         else getenv("LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES", "yes")) == "no",
            "max_retries": (getenv(f"{first_server}_LETS_ENCRYPT_MAX_RETRIES", "0") 
                           if IS_MULTISITE 
                           else getenv("LETS_ENCRYPT_MAX_RETRIES", "0")),
            "ca_provider": (getenv(f"{first_server}_ACME_SSL_CA_PROVIDER", "letsencrypt") 
                           if IS_MULTISITE 
                           else getenv("ACME_SSL_CA_PROVIDER", "letsencrypt")),
            "api_key": (getenv(f"{first_server}_ACME_ZEROSSL_API_KEY", "") if IS_MULTISITE 
                       else getenv("ACME_ZEROSSL_API_KEY", "")),
            "credential_items": {},
        }
        
        LOGGER.info(f"Service {first_server} configuration:")
        LOGGER.info(f"  CA Provider: {data['ca_provider']}")
        LOGGER.info(f"  API Key provided: {'Yes' if data['api_key'] else 'No'}")
        LOGGER.info(f"  Challenge type: {data['challenge']}")
        LOGGER.info(f"  Staging: {data['staging']}")
        LOGGER.info(f"  Wildcard: {data['use_wildcard']}")

        # Override profile if custom profile is set
        custom_profile = (getenv(f"{first_server}_LETS_ENCRYPT_CUSTOM_PROFILE", "") 
                         if IS_MULTISITE 
                         else getenv("LETS_ENCRYPT_CUSTOM_PROFILE", "")).strip()
        if custom_profile:
            data["profile"] = custom_profile

        if data["challenge"] == "http" and data["use_wildcard"]:
            LOGGER.warning(f"Wildcard is not supported with HTTP challenge, "
                          f"disabling wildcard for service {first_server}...")
            data["use_wildcard"] = False

        if (not data["use_wildcard"] and not domains_to_ask.get(first_server)) or (
            data["use_wildcard"] and not domains_to_ask.get(
                WILDCARD_GENERATOR.extract_wildcards_from_domains((first_server,))[0]
                                  .lstrip("*.")
            )
        ):
            continue

        if not data["max_retries"].isdigit():
            LOGGER.warning(f"Invalid max retries value for service {first_server} : "
                          f"{data['max_retries']}, using default value of 0...")
            data["max_retries"] = 0
        else:
            data["max_retries"] = int(data["max_retries"])

        # Getting the DNS provider data if necessary
        if data["challenge"] == "dns":
            credential_key = (f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
                            if IS_MULTISITE 
                            else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM")
            credential_items = {}

            # Collect all credential items
            for env_key, env_value in environ.items():
                if env_value and env_key.startswith(credential_key):
                    if " " not in env_value:
                        credential_items["json_data"] = env_value
                        continue
                    key, value = env_value.split(" ", 1)
                    credential_items[key.lower()] = (value.removeprefix("= ")
                                                          .replace("\\n", "\n")
                                                          .replace("\\t", "\t")
                                                          .replace("\\r", "\r").strip())

            if "json_data" in credential_items:
                value = credential_items.pop("json_data")
                # Handle the case of a single credential that might be base64-encoded JSON
                if (not credential_items and len(value) % 4 == 0 
                    and match(r"^[A-Za-z0-9+/=]+$", value)):
                    try:
                        decoded = b64decode(value).decode("utf-8")
                        json_data = loads(decoded)
                        if isinstance(json_data, dict):
                            data["credential_items"] = {
                                k.lower(): str(v).removeprefix("= ")
                                                  .replace("\\n", "\n")
                                                  .replace("\\t", "\t")
                                                  .replace("\\r", "\r").strip()
                                for k, v in json_data.items()
                            }
                    except BaseException as e:
                        LOGGER.debug(format_exc())
                        LOGGER.error(f"Error while decoding JSON data for service "
                                   f"{first_server} : {value} : \n{e}")

            if not data["credential_items"]:
                # Process regular credentials
                data["credential_items"] = {}
                for key, value in credential_items.items():
                    # Check for base64 encoding
                    if (data["provider"] != "rfc2136" and len(value) % 4 == 0 
                        and match(r"^[A-Za-z0-9+/=]+$", value)):
                        try:
                            decoded = b64decode(value).decode("utf-8")
                            if decoded != value:
                                value = (decoded.removeprefix("= ")
                                               .replace("\\n", "\n")
                                               .replace("\\t", "\t")
                                               .replace("\\r", "\r").strip())
                        except BaseException as e:
                            LOGGER.debug(format_exc())
                            LOGGER.debug(f"Error while decoding credential item {key} "
                                       f"for service {first_server} : {value} : \n{e}")
                    data["credential_items"][key] = value

        LOGGER.debug(f"Data for service {first_server} : {dumps(data)}")

        # Validate CA provider and API key requirements
        LOGGER.info(f"Service {first_server} - CA Provider: {data['ca_provider']}, "
                   f"API Key provided: {'Yes' if data['api_key'] else 'No'}")
        
        if data["ca_provider"].lower() == "zerossl":
            if not data["api_key"]:
                LOGGER.warning(f"ZeroSSL API key not provided for service {first_server}, "
                              "falling back to Let's Encrypt...")
                data["ca_provider"] = "letsencrypt"
            else:
                LOGGER.info(f"✓ ZeroSSL configuration valid for service {first_server}")

        # Checking if the DNS data is valid
        if data["challenge"] == "dns":
            if not data["provider"]:
                LOGGER.warning(
                    f"No provider found for service {first_server} "
                    f"(available providers : {', '.join(provider_classes.keys())}), "
                    "skipping certificate(s) generation..."
                )
                continue
            elif data["provider"] not in provider_classes:
                LOGGER.warning(
                    f"Provider {data['provider']} not found for service {first_server} "
                    f"(available providers : {', '.join(provider_classes.keys())}), "
                    "skipping certificate(s) generation..."
                )
                continue
            elif not data["credential_items"]:
                LOGGER.warning(
                    f"No valid credentials items found for service {first_server} "
                    "(you should have at least one), skipping certificate(s) generation..."
                )
                continue

            try:
                provider = provider_classes[data["provider"]](**data["credential_items"])
            except ValidationError as ve:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while validating credentials for service "
                           f"{first_server} :\n{ve}")
                continue

            content = provider.get_formatted_credentials()
        else:
            content = b"http_challenge"

        is_blacklisted = False

        # Adding the domains to Wildcard Generator if necessary
        file_type = (provider.get_file_type() if data["challenge"] == "dns" else "txt")
        file_path = (first_server, f"credentials.{file_type}")
        
        if data["use_wildcard"]:
            # Use the improved method for generating consistent group names
            group = WILDCARD_GENERATOR.create_group_name(
                domain=first_server,
                provider=data["provider"] if data["challenge"] == "dns" else "http",
                challenge_type=data["challenge"],
                staging=data["staging"],
                content_hash=bytes_hash(content, algorithm="sha1"),
                profile=data["profile"],
            )

            LOGGER.info(
                f"Service {first_server} is using wildcard, "
                + ("the propagation time will be the provider's default and " 
                   if data["challenge"] == "dns" else "")
                + "the email will be the same as the first domain that created the group..."
            )

            if data["check_psl"]:
                if psl_lines is None:
                    psl_lines = load_public_suffix_list(JOB)
                if psl_rules is None:
                    psl_rules = parse_psl(psl_lines)

                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains(
                    domains.split(" ")
                )

                LOGGER.info(f"Wildcard domains for {first_server} : {wildcards}")

                for d in wildcards:
                    if is_domain_blacklisted(d, psl_rules):
                        LOGGER.error(f"Wildcard domain {d} is blacklisted by Public "
                                   f"Suffix List, refusing certificate request for "
                                   f"{first_server}.")
                        is_blacklisted = True
                        break

            if not is_blacklisted:
                WILDCARD_GENERATOR.extend(group, domains.split(" "), data["email"], 
                                        data["staging"])
                file_path = (f"{group}.{file_type}",)
                LOGGER.info(f"[{first_server}] Wildcard group {group}")
        elif data["check_psl"]:
            if psl_lines is None:
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                psl_rules = parse_psl(psl_lines)

            for d in domains.split():
                if is_domain_blacklisted(d, psl_rules):
                    LOGGER.error(f"Domain {d} is blacklisted by Public Suffix List, "
                               f"refusing certificate request for {first_server}.")
                    is_blacklisted = True
                    break

        if is_blacklisted:
            continue

        # Generating the credentials file
        credentials_path = CACHE_PATH.joinpath(*file_path)

        if data["challenge"] == "dns":
            if not credentials_path.is_file():
                cached, err = JOB.cache_file(
                    credentials_path.name, content, job_name="certbot-renew", 
                    service_id=first_server if not data["use_wildcard"] else ""
                )
                if not cached:
                    LOGGER.error(f"Error while saving service {first_server}'s "
                               f"credentials file in cache : {err}")
                    continue
                LOGGER.info(f"Successfully saved service {first_server}'s "
                           "credentials file in cache")
            elif data["use_wildcard"]:
                LOGGER.info(f"Service {first_server}'s wildcard credentials file "
                           "has already been generated")
            else:
                old_content = credentials_path.read_bytes()
                if old_content != content:
                    LOGGER.warning(f"Service {first_server}'s credentials file is "
                                 "outdated, updating it...")
                    cached, err = JOB.cache_file(credentials_path.name, content, 
                                               job_name="certbot-renew", 
                                               service_id=first_server)
                    if not cached:
                        LOGGER.error(f"Error while updating service {first_server}'s "
                                   f"credentials file in cache : {err}")
                        continue
                    LOGGER.info(f"Successfully updated service {first_server}'s "
                               "credentials file in cache")
                else:
                    LOGGER.info(f"Service {first_server}'s credentials file is up to date")

            credential_paths.add(credentials_path)
            credentials_path.chmod(0o600)  # Setting the permissions to 600 (this is important to avoid warnings from certbot)

        if data["use_wildcard"]:
            continue

        domains = domains.replace(" ", ",")
        ca_name = get_certificate_authority_config(data["ca_provider"])["name"]
        LOGGER.info(
            f"Asking {ca_name} certificates for domain(s) : {domains} "
            f"(email = {data['email']}){' using staging' if data['staging'] else ''} "
            f"with {data['challenge']} challenge, using {data['profile']!r} profile..."
        )

        if (
            certbot_new_with_retry(
                data["challenge"],
                domains,
                data["email"],
                data["provider"],
                credentials_path,
                data["propagation"],
                data["profile"],
                data["staging"],
                domains_to_ask[first_server] == 2,
                cmd_env=env,
                max_retries=data["max_retries"],
                ca_provider=data["ca_provider"],
                api_key=data["api_key"],
                server_name=first_server,
            )
            != 0
        ):
            status = 2
            LOGGER.error(f"Certificate generation failed for domain(s) {domains} ...")
        else:
            status = 1 if status == 0 else status
            LOGGER.info(f"Certificate generation succeeded for domain(s) : {domains}")

        generated_domains.update(domains.split(","))

    # Generating the wildcards if necessary
    wildcards = WILDCARD_GENERATOR.get_wildcards()
    if wildcards:
        for group, data in wildcards.items():
            if not data:
                continue
            
            # Generating the certificate from the generated credentials
            group_parts = group.split("_")
            provider = group_parts[0]
            profile = group_parts[2]
            base_domain = group_parts[3]

            email = data.pop("email")
            credentials_file = CACHE_PATH.joinpath(
                f"{group}.{provider_classes[provider].get_file_type() if provider in provider_classes else 'txt'}"
            )

            # Get CA provider for this group
            original_server = None
            for server in domains_server_names.keys():
                if base_domain in server or server in base_domain:
                    original_server = server
                    break
            
            ca_provider = "letsencrypt"  # default
            api_key = None
            if original_server:
                ca_provider = (getenv(f"{original_server}_ACME_SSL_CA_PROVIDER", "letsencrypt") 
                             if IS_MULTISITE 
                             else getenv("ACME_SSL_CA_PROVIDER", "letsencrypt"))
                api_key = (getenv(f"{original_server}_ACME_ZEROSSL_API_KEY", "") 
                          if IS_MULTISITE 
                          else getenv("ACME_ZEROSSL_API_KEY", ""))

            # Process different environment types (staging/prod)
            for key, domains in data.items():
                if not domains:
                    continue

                staging = key == "staging"
                ca_name = get_certificate_authority_config(ca_provider)["name"]
                LOGGER.info(
                    f"Asking {ca_name} wildcard certificates for domain(s): {domains} "
                    f"(email = {email}){' using staging ' if staging else ''} "
                    f"with {'dns' if provider in provider_classes else 'http'} challenge, "
                    f"using {profile!r} profile..."
                )

                domains_split = domains.split(",")

                # Add wildcard certificate names to active set
                for domain in domains_split:
                    # Extract the base domain from the wildcard domain
                    base_domain = WILDCARD_GENERATOR.get_base_domain(domain)
                    active_cert_names.add(base_domain)

                if (
                    certbot_new_with_retry(
                        "dns",
                        domains,
                        email,
                        provider,
                        credentials_file,
                        "default",
                        profile,
                        staging,
                        domains_to_ask.get(base_domain, 0) == 2,
                        cmd_env=env,
                        ca_provider=ca_provider,
                        api_key=api_key,
                        server_name=original_server,
                    )
                    != 0
                ):
                    status = 2
                    LOGGER.error(f"Certificate generation failed for domain(s) {domains} ...")
                else:
                    status = 1 if status == 0 else status
                    LOGGER.info(f"Certificate generation succeeded for domain(s): {domains}")

                generated_domains.update(domains_split)
    else:
        LOGGER.info("No wildcard domains found, skipping wildcard certificate(s) generation...")

    if CACHE_PATH.is_dir():
        # Clearing all missing credentials files
        for ext in ("*.ini", "*.env", "*.json"):
            for file in list(CACHE_PATH.rglob(ext)):
                if "etc" in file.parts or not file.is_file():
                    continue
                # If the file is not in the wildcard groups, remove it
                if file not in credential_paths:
                    LOGGER.info(f"Removing old credentials file {file}")
                    JOB.del_cache(file.name, job_name="certbot-renew", 
                                service_id=file.parent.name if file.parent.name != "letsencrypt" else "")

    # Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info("Clear old certificates is activated, removing old / no longer "
                   "used certificates...")

        # Get list of all certificates
        proc = run(
            [
                CERTBOT_BIN,
                "certificates",
                "--config-dir",
                DATA_PATH.as_posix(),
                "--work-dir",
                WORK_DIR,
                "--logs-dir",
                LOGS_DIR,
            ],
            stdin=DEVNULL,
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
            env=env,
            check=False,
        )

        if proc.returncode == 0:
            certificate_blocks = proc.stdout.split("Certificate Name: ")[1:]
            for block in certificate_blocks:
                cert_name = block.split("\n", 1)[0].strip()

                # Skip certificates that are in our active list
                if cert_name in active_cert_names:
                    LOGGER.info(f"Keeping active certificate: {cert_name}")
                    continue

                LOGGER.warning(f"Removing old certificate {cert_name} "
                              "(not in active certificates list)")

                # Use certbot's delete command
                delete_proc = run(
                    [
                        CERTBOT_BIN,
                        "delete",
                        "--config-dir",
                        DATA_PATH.as_posix(),
                        "--work-dir",
                        WORK_DIR,
                        "--logs-dir",
                        LOGS_DIR,
                        "--cert-name",
                        cert_name,
                        "-n",
                    ],
                    stdin=DEVNULL,
                    stdout=PIPE,
                    stderr=STDOUT,
                    text=True,
                    env=env,
                    check=False,
                )

                if delete_proc.returncode == 0:
                    LOGGER.info(f"Successfully deleted certificate {cert_name}")
                    cert_dir = DATA_PATH.joinpath("live", cert_name)
                    archive_dir = DATA_PATH.joinpath("archive", cert_name)
                    renewal_file = DATA_PATH.joinpath("renewal", f"{cert_name}.conf")
                    for path in (cert_dir, archive_dir):
                        if path.exists():
                            try:
                                for file in path.glob("*"):
                                    try:
                                        file.unlink()
                                    except Exception as e:
                                        LOGGER.error(f"Failed to remove file {file}: {e}")
                                path.rmdir()
                                LOGGER.info(f"Removed directory {path}")
                            except Exception as e:
                                LOGGER.error(f"Failed to remove directory {path}: {e}")
                        if renewal_file.exists():
                            try:
                                renewal_file.unlink()
                                LOGGER.info(f"Removed renewal file {renewal_file}")
                            except Exception as e:
                                LOGGER.error(f"Failed to remove renewal file "
                                           f"{renewal_file}: {e}")
                else:
                    LOGGER.error(f"Failed to delete certificate {cert_name}: "
                               f"{delete_proc.stdout}")
        else:
            LOGGER.error(f"Error listing certificates: {proc.stdout}")

    # Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        cached, err = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached:
            LOGGER.error(f"Error while saving data to db cache : {err}")
        else:
            LOGGER.info("Successfully saved data to db cache")
            
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-new.py :\n{e}")

sys_exit(status)