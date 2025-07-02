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
from typing import (
    Any, Dict, List, Literal, Optional, Set, Tuple, cast, Union 
)

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

LOGGER: Any = setup_logger("LETS-ENCRYPT.new")
CERTBOT_BIN: str = join(sep, "usr", "share", "bunkerweb", "deps", "python", 
                        "bin", "certbot")
DEPS_PATH: str = join(sep, "usr", "share", "bunkerweb", "deps", "python")

LOGGER_CERTBOT: Any = setup_logger("LETS-ENCRYPT.new.certbot")
status: int = 0

PLUGIN_PATH: Any = Path(sep, "usr", "share", "bunkerweb", "core", 
                        "letsencrypt")
JOBS_PATH: Any = PLUGIN_PATH.joinpath("jobs")
CACHE_PATH: Any = Path(sep, "var", "cache", "bunkerweb", "letsencrypt")
DATA_PATH: Any = CACHE_PATH.joinpath("etc")
WORK_DIR: str = join(sep, "var", "lib", "bunkerweb", "letsencrypt")
LOGS_DIR: str = join(sep, "var", "log", "bunkerweb", "letsencrypt")

PSL_URL: str = "https://publicsuffix.org/list/public_suffix_list.dat"
PSL_STATIC_FILE: Any = Path("public_suffix_list.dat")

# ZeroSSL Configuration
ZEROSSL_ACME_SERVER: str = "https://acme.zerossl.com/v2/DV90"
ZEROSSL_STAGING_SERVER: str = "https://acme.zerossl.com/v2/DV90"
LETSENCRYPT_ACME_SERVER: str = (
    "https://acme-v02.api.letsencrypt.org/directory"
)
LETSENCRYPT_STAGING_SERVER: str = (
    "https://acme-staging-v02.api.letsencrypt.org/directory"
)


def debug_log(logger: Any, message: str) -> None:
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def load_public_suffix_list(job: Any) -> List[str]:
    # Load and cache the public suffix list for domain validation.
    # Fetches the PSL from the official source and caches it locally.
    # Returns cached version if available and fresh (less than 1 day old).
    debug_log(LOGGER, f"Loading public suffix list from cache or {PSL_URL}")
    debug_log(LOGGER, "Checking if cached PSL is available and fresh")
    
    job_cache: Union[Dict[str, Any], bool] = job.get_cache(
        PSL_STATIC_FILE.name, with_info=True, with_data=True
    )
    if (
        isinstance(job_cache, dict)
        and "last_update" in job_cache
        and job_cache["last_update"] < (
            datetime.now().astimezone() - timedelta(days=1)
        ).timestamp()
    ):
        debug_log(LOGGER, "Using cached public suffix list")
        cache_last_update: float = float(job_cache['last_update'])
        cache_age_hours: float = (
            (datetime.now().astimezone().timestamp() - 
             cache_last_update) / 3600
        )
        debug_log(LOGGER, f"Cache age: {cache_age_hours:.1f} hours")
        cache_data: bytes = cast(bytes, job_cache["data"])
        return cache_data.decode("utf-8").splitlines()

    try:
        debug_log(LOGGER, f"Downloading fresh PSL from {PSL_URL}")
        debug_log(LOGGER, "Cached PSL is missing or older than 1 day")
        
        resp = get(PSL_URL, timeout=5)
        resp.raise_for_status()
        content: str = resp.text
        
        debug_log(LOGGER, 
                  f"Downloaded PSL successfully, {len(content)} bytes")
        debug_log(LOGGER, 
                  f"PSL contains {len(content.splitlines())} lines")
        
        cached: Any
        err: Any
        cached, err = JOB.cache_file(PSL_STATIC_FILE.name, 
                                     content.encode("utf-8"))
        if not cached:
            LOGGER.error(f"Error while saving public suffix list to cache: "
                         f"{err}")
        else:
            debug_log(LOGGER, "PSL successfully cached for future use")
        
        return content.splitlines()
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while downloading public suffix list: {e}")
        
        debug_log(LOGGER, 
                  "Download failed, checking for existing static file")
        
        if PSL_STATIC_FILE.exists():
            debug_log(LOGGER, 
                      f"Using existing static PSL file: {PSL_STATIC_FILE}")
            with PSL_STATIC_FILE.open("r", encoding="utf-8") as f:
                return f.read().splitlines()
        
        debug_log(LOGGER, "No PSL data available - returning empty list")
        return []


def parse_psl(psl_lines: List[str]) -> Dict[str, Set[str]]:
    # Parse PSL lines into rules and exceptions sets.
    # Processes the public suffix list format, handling comments,
    # exceptions (lines starting with !), and regular rules.
    debug_log(LOGGER, f"Parsing {len(psl_lines)} PSL lines")
    debug_log(LOGGER, "Processing rules, exceptions, and filtering comments")
    
    rules: Set[str] = set()
    exceptions: Set[str] = set()
    comments_skipped: int = 0
    empty_lines_skipped: int = 0
    
    for line in psl_lines:
        line = line.strip()
        if not line:
            empty_lines_skipped += 1
            continue
        if line.startswith("//"):
            comments_skipped += 1
            continue
        if line.startswith("!"):
            exceptions.add(line[1:])
            continue
        rules.add(line)
    
    debug_log(LOGGER, f"Parsed {len(rules)} rules and {len(exceptions)} "
                      f"exceptions")
    debug_log(LOGGER, f"Skipped {comments_skipped} comments and "
                      f"{empty_lines_skipped} empty lines")
    debug_log(LOGGER, "PSL parsing completed successfully")
    
    return {"rules": rules, "exceptions": exceptions}


def is_domain_blacklisted(domain: str, psl: Dict[str, Set[str]]) -> bool:
    # Check if domain is forbidden by PSL rules.
    # Validates whether a domain would be blacklisted according to the
    # Public Suffix List rules and exceptions.
    domain = domain.lower().strip(".")
    labels: List[str] = domain.split(".")
    
    debug_log(LOGGER, f"Checking domain {domain} against PSL rules")
    debug_log(LOGGER, f"Domain has {len(labels)} labels: {labels}")
    debug_log(LOGGER, f"PSL contains {len(psl['rules'])} rules and "
                      f"{len(psl['exceptions'])} exceptions")
    
    for i in range(len(labels)):
        candidate: str = ".".join(str(label) for label in labels[i:])
        
        debug_log(LOGGER, f"Checking candidate: {candidate}")
        
        if candidate in psl["exceptions"]:
            debug_log(LOGGER, f"Domain {domain} allowed by PSL exception "
                              f"{candidate}")
            return False
        
        if candidate in psl["rules"]:
            debug_log(LOGGER, f"Found PSL rule match: {candidate}")
            debug_log(LOGGER, f"Checking blacklist conditions for i={i}")
            
            if i == 0:
                debug_log(LOGGER, f"Domain {domain} blacklisted - exact PSL "
                                  f"rule match")
                return True
            if i == 0 and domain.startswith("*."):
                debug_log(LOGGER, f"Wildcard domain {domain} blacklisted - "
                                  f"exact PSL rule match")
                return True
            if i == 0 or (i == 1 and labels[0] == "*"):
                debug_log(LOGGER, f"Domain {domain} blacklisted - PSL rule "
                                  f"violation")
                return True
            if len(labels[i:]) == len(labels):
                debug_log(LOGGER, f"Domain {domain} blacklisted - full label "
                                  f"match")
                return True
        
        wildcard_candidate: str = f"*.{candidate}"
        if wildcard_candidate in psl["rules"]:
            debug_log(LOGGER, f"Found PSL wildcard rule match: "
                              f"{wildcard_candidate}")
            
            if len(labels[i:]) == 2:
                debug_log(LOGGER, f"Domain {domain} blacklisted - wildcard "
                                  f"PSL rule match")
                return True
    
    debug_log(LOGGER, f"Domain {domain} not blacklisted by PSL")
    return False


def get_certificate_authority_config(
    ca_provider: str, 
    staging: bool = False
) -> Dict[str, str]:
    # Get ACME server configuration for the specified CA provider.
    # Returns the appropriate ACME server URL and name for the given
    # certificate authority and environment (staging/production).
    debug_log(LOGGER, f"Getting CA config for {ca_provider}, "
                      f"staging={staging}")
    
    config: Dict[str, str]
    if ca_provider.lower() == "zerossl":
        config = {
            "server": (ZEROSSL_STAGING_SERVER if staging 
                       else ZEROSSL_ACME_SERVER),
            "name": "ZeroSSL"
        }
    else:  # Default to Let's Encrypt
        config = {
            "server": (LETSENCRYPT_STAGING_SERVER if staging 
                       else LETSENCRYPT_ACME_SERVER),
            "name": "Let's Encrypt"
        }
    
    debug_log(LOGGER, f"CA config: {config}")
    
    return config


def setup_zerossl_eab_credentials(
    email: str, 
    api_key: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    # Setup External Account Binding (EAB) credentials for ZeroSSL.
    # Contacts the ZeroSSL API to obtain EAB credentials required for
    # ACME certificate issuance with ZeroSSL.
    LOGGER.info(f"Setting up ZeroSSL EAB credentials for email: {email}")
    
    if not api_key:
        LOGGER.error("❌ ZeroSSL API key not provided")
        LOGGER.warning(
            "ZeroSSL API key not provided, attempting registration with "
            "email"
        )
        return None, None
    
    debug_log(LOGGER, "Making request to ZeroSSL API for EAB credentials")
    debug_log(LOGGER, f"Email: {email}")
    debug_log(LOGGER, f"API key provided: {bool(api_key)}")
    
    LOGGER.info("Making request to ZeroSSL API for EAB credentials")
    
    # Try the correct ZeroSSL API endpoint
    try:
        # The correct endpoint for ZeroSSL EAB credentials
        debug_log(LOGGER, "Attempting primary ZeroSSL EAB endpoint")
        
        response = get(
            "https://api.zerossl.com/acme/eab-credentials",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )
        
        debug_log(LOGGER, f"ZeroSSL API response status: "
                          f"{response.status_code}")
        debug_log(LOGGER, f"Response headers: {dict(response.headers)}")
        LOGGER.info(f"ZeroSSL API response status: {response.status_code}")
        
        if response.status_code == 200:
            response.raise_for_status()
            eab_data: Dict[str, Any] = response.json()
            
            debug_log(LOGGER, f"ZeroSSL API response data: {eab_data}")
            LOGGER.info(f"ZeroSSL API response data: {eab_data}")
            
            # ZeroSSL typically returns eab_kid and eab_hmac_key directly
            if "eab_kid" in eab_data and "eab_hmac_key" in eab_data:
                eab_kid: Optional[str] = eab_data.get("eab_kid")
                eab_hmac_key: Optional[str] = eab_data.get("eab_hmac_key")
                LOGGER.info(f"✓ Successfully obtained EAB credentials from "
                            f"ZeroSSL")
                kid_display: str = (f"{eab_kid[:10]}..." if eab_kid 
                                    else "None")
                hmac_display: str = (f"{eab_hmac_key[:10]}..." 
                                     if eab_hmac_key else "None")
                LOGGER.info(f"EAB Kid: {kid_display}")
                LOGGER.info(f"EAB HMAC Key: {hmac_display}")
                return eab_kid, eab_hmac_key
            else:
                LOGGER.error(f"❌ Invalid ZeroSSL API response format: "
                             f"{eab_data}")
                return None, None
        else:
            # Try alternative endpoint if first one fails
            LOGGER.warning(
                f"Primary endpoint failed with {response.status_code}, "
                "trying alternative"
            )
            response_text: str = response.text
            
            debug_log(LOGGER, f"Primary endpoint response: {response_text}")
            LOGGER.info(f"Primary endpoint response: {response_text}")
            
            # Try alternative endpoint with email parameter
            debug_log(LOGGER, "Attempting alternative ZeroSSL EAB endpoint")
            
            response = get(
                "https://api.zerossl.com/acme/eab-credentials-email",
                params={"email": email},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30
            )
            
            alt_status: int = response.status_code
            debug_log(LOGGER, f"Alternative ZeroSSL API response status: "
                              f"{alt_status}")
            LOGGER.info(f"Alternative ZeroSSL API response status: "
                        f"{response.status_code}")
            response.raise_for_status()
            eab_data = response.json()
            
            debug_log(LOGGER, f"Alternative ZeroSSL API response data: "
                              f"{eab_data}")
            LOGGER.info(f"Alternative ZeroSSL API response data: {eab_data}")
            
            if eab_data.get("success"):
                eab_kid = eab_data.get("eab_kid")
                eab_hmac_key = eab_data.get("eab_hmac_key")
                LOGGER.info(
                    "✓ Successfully obtained EAB credentials from ZeroSSL "
                    "(alternative endpoint)"
                )
                kid_display = f"{eab_kid[:10]}..." if eab_kid else "None"
                hmac_display = (f"{eab_hmac_key[:10]}..." if eab_hmac_key 
                                else "None")
                LOGGER.info(f"EAB Kid: {kid_display}")
                LOGGER.info(f"EAB HMAC Key: {hmac_display}")
                return eab_kid, eab_hmac_key
            else:
                LOGGER.error(f"❌ ZeroSSL EAB registration failed: "
                             f"{eab_data}")
                return None, None
            
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"❌ Error setting up ZeroSSL EAB credentials: {e}")
        
        debug_log(LOGGER, "ZeroSSL EAB setup failed with exception")
        
        # Additional troubleshooting info
        LOGGER.error("Troubleshooting steps:")
        LOGGER.error("1. Verify your ZeroSSL API key is valid")
        LOGGER.error("2. Check your ZeroSSL account has ACME access enabled")
        LOGGER.error("3. Ensure the API key has the correct permissions")
        LOGGER.error("4. Try regenerating your ZeroSSL API key")
        
        return None, None


def get_caa_records(domain: str) -> Optional[List[Dict[str, str]]]:
    # Get CAA records for a domain using dig command.
    # Queries DNS CAA records to check certificate authority authorization.
    # Returns None if dig command is not available.
    
    # Check if dig command is available
    if not which("dig"):
        debug_log(LOGGER, 
                  "dig command not available for CAA record checking")
        LOGGER.info("dig command not available for CAA record checking")
        return None
    
    try:
        # Use dig to query CAA records
        debug_log(LOGGER, f"Querying CAA records for domain: {domain}")
        debug_log(LOGGER, "Using dig command with +short flag")
        LOGGER.info(f"Querying CAA records for domain: {domain}")
        
        result = run(
            ["dig", "+short", domain, "CAA"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        debug_log(LOGGER, f"dig command return code: {result.returncode}")
        debug_log(LOGGER, f"dig stdout: {result.stdout}")
        debug_log(LOGGER, f"dig stderr: {result.stderr}")
        
        if result.returncode == 0 and result.stdout.strip():
            LOGGER.info(f"Found CAA records for domain {domain}")
            caa_records: List[Dict[str, str]] = []
            raw_lines: List[str] = result.stdout.strip().split('\n')
            
            debug_log(LOGGER, f"Processing {len(raw_lines)} CAA record lines")
            
            for line in raw_lines:
                line = line.strip()
                if line:
                    debug_log(LOGGER, f"Parsing CAA record line: {line}")
                    
                    # CAA record format: flags tag "value"
                    # Example: 0 issue "letsencrypt.org"
                    parts: List[str] = line.split(' ', 2)
                    if len(parts) >= 3:
                        flags: str = parts[0]
                        tag: str = parts[1]
                        value: str = parts[2].strip('"')
                        caa_records.append({
                            'flags': flags,
                            'tag': tag,
                            'value': value
                        })
                        
                        debug_log(LOGGER, 
                                  f"Parsed CAA record: flags={flags}, "
                                  f"tag={tag}, value={value}")
            
            record_count: int = len(caa_records)
            debug_log(LOGGER, 
                      f"Successfully parsed {record_count} CAA records "
                      f"for domain {domain}")
            LOGGER.info(f"Parsed {len(caa_records)} CAA records for domain "
                        f"{domain}")
            return caa_records
        else:
            debug_log(LOGGER, 
                      f"No CAA records found for domain {domain} "
                      f"(dig return code: {result.returncode})")
            LOGGER.info(
                f"No CAA records found for domain {domain} "
                f"(dig return code: {result.returncode})"
            )
            return []
            
    except BaseException as e:
        debug_log(LOGGER, f"Error querying CAA records for {domain}: {e}")
        LOGGER.info(f"Error querying CAA records for {domain}: {e}")
        return None


def check_caa_authorization(
    domain: str, 
    ca_provider: str, 
    is_wildcard: bool = False
) -> bool:
    # Check if the CA provider is authorized by CAA records.
    # Validates whether the certificate authority is permitted to issue
    # certificates for the domain according to CAA DNS records.
    debug_log(LOGGER, 
              f"Checking CAA authorization for domain: {domain}, "
              f"CA: {ca_provider}, wildcard: {is_wildcard}")
    
    LOGGER.info(
        f"Checking CAA authorization for domain: {domain}, "
        f"CA: {ca_provider}, wildcard: {is_wildcard}"
    )
    
    # Map CA providers to their CAA identifiers
    ca_identifiers: Dict[str, List[str]] = {
        "letsencrypt": ["letsencrypt.org"],
        "zerossl": ["sectigo.com", "zerossl.com"]  # ZeroSSL uses Sectigo
    }
    
    allowed_identifiers: List[str] = ca_identifiers.get(
        ca_provider.lower(), []
    )
    if not allowed_identifiers:
        LOGGER.warning(f"Unknown CA provider for CAA check: {ca_provider}")
        debug_log(LOGGER, "Returning True for unknown CA provider "
                          "(conservative approach)")
        return True  # Allow unknown providers (conservative approach)
    
    debug_log(LOGGER, f"CA identifiers for {ca_provider}: "
                      f"{allowed_identifiers}")
    
    # Check CAA records for the domain and parent domains
    check_domain: str = domain.lstrip("*.")
    domain_parts: List[str] = check_domain.split(".")
    
    debug_log(LOGGER, f"Will check CAA records for domain chain: "
                      f"{check_domain}")
    debug_log(LOGGER, f"Domain parts: {domain_parts}")
    LOGGER.info(f"Will check CAA records for domain chain: {check_domain}")
    
    for i in range(len(domain_parts)):
        current_domain: str = ".".join(
            str(part) for part in domain_parts[i:]
        )
        
        debug_log(LOGGER, f"Checking CAA records for: {current_domain}")
        LOGGER.info(f"Checking CAA records for: {current_domain}")
        caa_records: Optional[List[Dict[str, str]]] = get_caa_records(
            current_domain
        )
        
        if caa_records is None:
            # dig not available, skip CAA check
            LOGGER.info("CAA record checking skipped (dig command not "
                        "available)")
            debug_log(LOGGER, "Returning True due to unavailable dig command")
            return True
        
        if caa_records:
            LOGGER.info(f"Found CAA records for {current_domain}")
            
            # Check relevant CAA records
            issue_records: List[str] = []
            issuewild_records: List[str] = []
            
            for record in caa_records:
                if record['tag'] == 'issue':
                    issue_records.append(record['value'])
                elif record['tag'] == 'issuewild':
                    issuewild_records.append(record['value'])
            
            # Log found records
            if issue_records:
                debug_log(LOGGER, f"CAA issue records: "
                          f"{', '.join(str(record) for record in issue_records)}")
                LOGGER.info(f"CAA issue records: "
                            f"{', '.join(str(record) for record in issue_records)}")
            if issuewild_records:
                debug_log(LOGGER, f"CAA issuewild records: "
                          f"{', '.join(str(record) for record in issuewild_records)}")
                LOGGER.info(f"CAA issuewild records: "
                            f"{', '.join(str(record) for record in issuewild_records)}")
            
            # Check authorization based on certificate type
            check_records: List[str]
            record_type: str
            if is_wildcard:
                # For wildcard certificates, check issuewild first, 
                # then fall back to issue
                check_records = (issuewild_records if issuewild_records 
                                 else issue_records)
                record_type = ("issuewild" if issuewild_records 
                               else "issue")
            else:
                # For regular certificates, check issue records
                check_records = issue_records
                record_type = "issue"
            
            debug_log(LOGGER, f"Using CAA {record_type} records for "
                              f"authorization check")
            debug_log(LOGGER, f"Records to check: {check_records}")
            LOGGER.info(f"Using CAA {record_type} records for authorization "
                        f"check")
            
            if not check_records:
                debug_log(LOGGER, 
                          f"No relevant CAA {record_type} records found for "
                          f"{current_domain}")
                LOGGER.info(
                    f"No relevant CAA {record_type} records found for "
                    f"{current_domain}"
                )
                continue
            
            # Check if any of our CA identifiers are authorized
            authorized: bool = False
            
            identifier_list: str = ', '.join(
                str(id) for id in allowed_identifiers
            )
            debug_log(LOGGER, 
                      f"Checking authorization for CA identifiers: "
                      f"{identifier_list}")
            LOGGER.info(
                f"Checking authorization for CA identifiers: "
                f"{identifier_list}"
            )
            for identifier in allowed_identifiers:
                for record in check_records:
                    debug_log(LOGGER, 
                              f"Comparing identifier '{identifier}' "
                              f"with record '{record}'")
                    
                    # Handle explicit deny (empty value or semicolon)

                    if record == ";" or record.strip() == "":
                        LOGGER.warning(
                            f"CAA {record_type} record explicitly denies "
                            f"all CAs"
                        )
                        debug_log(LOGGER, "Found explicit deny record - "
                                          "authorization failed")
                        return False
                    
                    # Check for CA authorization
                    if identifier in record:
                        authorized = True
                        LOGGER.info(
                            f"✓ CA {ca_provider} ({identifier}) authorized "
                            f"by CAA {record_type} record"
                        )
                        debug_log(LOGGER, 
                                  f"Authorization found: {identifier} "
                                  f"in {record}")
                        break
                if authorized:
                    break
            
            if not authorized:
                LOGGER.error(
                    f"❌ CA {ca_provider} is NOT authorized by "
                    f"CAA {record_type} records"
                )
                allowed_list: str = ', '.join(
                    str(record) for record in check_records
                )
                identifier_list = ', '.join(
                    str(id) for id in allowed_identifiers
                )
                LOGGER.error(
                    f"Domain {current_domain} CAA {record_type} allows: "
                    f"{allowed_list}"
                )
                LOGGER.error(
                    f"But {ca_provider} uses: {identifier_list}"
                )
                debug_log(LOGGER, "CAA authorization failed - no matching "
                                  "identifiers")
                return False
            
            # If we found CAA records and we're authorized, we can stop 
            # checking parent domains
            LOGGER.info(f"✓ CAA authorization successful for {domain}")
            debug_log(LOGGER, 
                      "CAA authorization successful - stopping parent "
                      "domain checks")
            return True
    
    # No CAA records found in the entire chain
    LOGGER.info(
        f"No CAA records found for {check_domain} or parent domains - "
        f"any CA allowed"
    )
    debug_log(LOGGER, "No CAA records found in entire domain chain - "
                      "allowing any CA")
    return True


def validate_domains_for_http_challenge(
    domains_list: List[str], 
    ca_provider: str = "letsencrypt", 
    is_wildcard: bool = False
) -> bool:
    # Validate that all domains have valid A/AAAA records and CAA 
    # authorization for HTTP challenge.
    # Checks DNS resolution and certificate authority authorization for each
    # domain in the list to ensure HTTP challenge will succeed.
    domain_count: int = len(domains_list)
    domain_list: str = ', '.join(str(domain) for domain in domains_list)
    debug_log(LOGGER, 
              f"Validating {domain_count} domains for HTTP challenge: "
              f"{domain_list}")
    debug_log(LOGGER, 
              f"CA provider: {ca_provider}, wildcard: {is_wildcard}")
    LOGGER.info(
        f"Validating {len(domains_list)} domains for HTTP challenge: "
        f"{domain_list}"
    )
    invalid_domains: List[str] = []
    caa_blocked_domains: List[str] = []
    
    # Check if CAA validation should be skipped
    skip_caa_check: bool = getenv("ACME_SKIP_CAA_CHECK", "no") == "yes"
    
    caa_status: str = 'skipped' if skip_caa_check else 'performed'
    debug_log(LOGGER, f"CAA check will be {caa_status}")
    
    # Get external IPs once for all domain checks
    external_ips: Optional[Dict[str, Optional[str]]] = get_external_ip()
    if external_ips:
        if external_ips.get("ipv4"):
            LOGGER.info(f"Server external IPv4 address: "
                        f"{external_ips['ipv4']}")
        if external_ips.get("ipv6"):
            LOGGER.info(f"Server external IPv6 address: "
                        f"{external_ips['ipv6']}")
    else:
        LOGGER.warning(
            "Could not determine server external IP - skipping IP match "
            "validation"
        )
    
    validation_passed: int = 0
    validation_failed: int = 0
    
    for domain in domains_list:
        debug_log(LOGGER, f"Validating domain: {domain}")
        
        # Check DNS A/AAAA records with retry mechanism
        if not check_domain_a_record(domain, external_ips):
            invalid_domains.append(domain)
            validation_failed += 1
            debug_log(LOGGER, f"DNS validation failed for {domain}")
            continue
        
        # Check CAA authorization
        if not skip_caa_check:
            if not check_caa_authorization(domain, ca_provider, is_wildcard):
                caa_blocked_domains.append(domain)
                validation_failed += 1
                debug_log(LOGGER, f"CAA authorization failed for {domain}")
        else:
            debug_log(LOGGER, f"CAA check skipped for {domain} "
                              f"(ACME_SKIP_CAA_CHECK=yes)")
            LOGGER.info(f"CAA check skipped for {domain} "
                        f"(ACME_SKIP_CAA_CHECK=yes)")
        
        validation_passed += 1
        debug_log(LOGGER, f"Validation passed for {domain}")
    
    debug_log(LOGGER, f"Validation summary: {validation_passed} passed, "
                      f"{validation_failed} failed")
    
    # Report results
    if invalid_domains:
        invalid_list: str = ', '.join(
            str(domain) for domain in invalid_domains
        )
        LOGGER.error(
            f"The following domains do not have valid A/AAAA records and "
            f"cannot be used for HTTP challenge: {invalid_list}"
        )
        LOGGER.error(
            "Please ensure domains resolve to this server before requesting "
            "certificates"
        )
        return False
    
    if caa_blocked_domains:
        blocked_list: str = ', '.join(
            str(domain) for domain in caa_blocked_domains
        )
        LOGGER.error(
            f"The following domains have CAA records that block "
            f"{ca_provider}: {blocked_list}"
        )
        LOGGER.error(
            "Please update CAA records to authorize the certificate "
            "authority or use a different CA"
        )
        LOGGER.info("You can skip CAA checking by setting "
                    "ACME_SKIP_CAA_CHECK=yes")
        return False
    
    valid_list: str = ', '.join(str(domain) for domain in domains_list)
    LOGGER.info(
        f"All domains have valid DNS records and CAA authorization for "
        f"HTTP challenge: {valid_list}"
    )
    return True


def get_external_ip() -> Optional[Dict[str, Optional[str]]]:
    # Get the external/public IP addresses of this server (both IPv4 
    # and IPv6).
    # Queries multiple external services to determine the server's public
    # IP addresses for DNS validation purposes.
    debug_log(LOGGER, "Getting external IP addresses for server")
    LOGGER.info("Getting external IP addresses for server")
    
    ipv4_services: List[str] = [
        "https://ipv4.icanhazip.com",
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "https://ipv4.jsonip.com"
    ]
    
    ipv6_services: List[str] = [
        "https://ipv6.icanhazip.com",
        "https://api6.ipify.org",
        "https://ipv6.jsonip.com"
    ]
    
    external_ips: Dict[str, Optional[str]] = {"ipv4": None, "ipv6": None}
    
    # Try to get IPv4 address
    debug_log(LOGGER, "Attempting to get external IPv4 address")
    debug_log(LOGGER, f"Trying {len(ipv4_services)} IPv4 services")
    LOGGER.info("Attempting to get external IPv4 address")
    
    for i, service in enumerate(ipv4_services):
        try:
            service_num: str = f"{i+1}/{len(ipv4_services)}"
            debug_log(LOGGER, 
                      f"Trying IPv4 service {service_num}: {service}")
            
            if "jsonip.com" in service:
                # This service returns JSON format
                response = get(service, timeout=5)
                response.raise_for_status()
                json_data: Dict[str, Any] = response.json()
                ip_str: str = json_data.get("ip", "").strip()
            else:
                # These services return plain text IP
                response = get(service, timeout=5)
                response.raise_for_status()
                ip_str = response.text.strip()
            
            debug_log(LOGGER, f"Service returned: {ip_str}")
            
            # Basic IPv4 validation
            if ip_str and "." in ip_str and len(ip_str.split(".")) == 4:
                try:
                    # Validate it's a proper IPv4 address
                    getaddrinfo(ip_str, None, AF_INET)
                    # Type-safe assignment
                    ipv4_addr: str = str(ip_str)
                    external_ips["ipv4"] = ipv4_addr
                    
                    debug_log(LOGGER, 
                              f"Successfully obtained external IPv4 "
                              f"address: {ipv4_addr}")
                    LOGGER.info(f"Successfully obtained external IPv4 "
                                f"address: {ipv4_addr}")
                    break
                except gaierror:
                    debug_log(LOGGER, 
                              f"Invalid IPv4 address returned: {ip_str}")
                    continue
        except BaseException as e:
            debug_log(LOGGER, 
                      f"Failed to get IPv4 address from {service}: {e}")
            LOGGER.info(f"Failed to get IPv4 address from {service}: {e}")
            continue
    
    # Try to get IPv6 address
    debug_log(LOGGER, "Attempting to get external IPv6 address")
    debug_log(LOGGER, f"Trying {len(ipv6_services)} IPv6 services")
    LOGGER.info("Attempting to get external IPv6 address")
    
    for i, service in enumerate(ipv6_services):
        try:
            service_num = f"{i+1}/{len(ipv6_services)}"
            debug_log(LOGGER, 
                      f"Trying IPv6 service {service_num}: {service}")
            
            if "jsonip.com" in service:
                response = get(service, timeout=5)
                response.raise_for_status()
                json_data: Dict[str, Any] = response.json()
                ip_str = json_data.get("ip", "").strip()
            else:
                response = get(service, timeout=5)
                response.raise_for_status()
                ip_str = response.text.strip()
            
            debug_log(LOGGER, f"Service returned: {ip_str}")
            
            # Basic IPv6 validation
            if ip_str and ":" in ip_str:
                try:
                    # Validate it's a proper IPv6 address
                    getaddrinfo(ip_str, None, AF_INET6)
                    # Type-safe assignment
                    ipv6_addr: str = str(ip_str)
                    external_ips["ipv6"] = ipv6_addr
                    
                    debug_log(LOGGER, 
                              f"Successfully obtained external IPv6 "
                              f"address: {ipv6_addr}")
                    LOGGER.info(f"Successfully obtained external IPv6 "
                                f"address: {ipv6_addr}")
                    break
                except gaierror:
                    debug_log(LOGGER, 
                              f"Invalid IPv6 address returned: {ip_str}")
                    continue
        except BaseException as e:
            debug_log(LOGGER, 
                      f"Failed to get IPv6 address from {service}: {e}")
            LOGGER.info(f"Failed to get IPv6 address from {service}: {e}")
            continue
    
    if not external_ips["ipv4"] and not external_ips["ipv6"]:
        LOGGER.warning(
            "Could not determine external IP address (IPv4 or IPv6) from "
            "any service"
        )
        debug_log(LOGGER, "All external IP services failed")
        return None
    
    ipv4_status: str = external_ips['ipv4'] or 'not found'
    ipv6_status: str = external_ips['ipv6'] or 'not found'
    LOGGER.info(
        f"External IP detection completed - "
        f"IPv4: {ipv4_status}, IPv6: {ipv6_status}"
    )
    return external_ips


def check_domain_a_record(
    domain: str, 
    external_ips: Optional[Dict[str, Optional[str]]] = None
) -> bool:
    # Check if domain has valid A/AAAA records for HTTP challenge.
    # Validates DNS resolution and optionally checks if the domain's
    # IP addresses match the server's external IPs.
    debug_log(LOGGER, f"Checking DNS A/AAAA records for domain: {domain}")
    LOGGER.info(f"Checking DNS A/AAAA records for domain: {domain}")
    
    # Remove wildcard prefix if present
    check_domain: str = domain.lstrip("*.")
    
    try:
        
        debug_log(LOGGER, f"Checking domain after wildcard removal: "
                          f"{check_domain}")
        
        # Attempt to resolve the domain to IP addresses
        result: List[Tuple[Any, ...]] = getaddrinfo(check_domain, None)
        if result:
            ipv4_addresses: List[str] = [
                addr[4][0] for addr in result if addr[0] == AF_INET
            ]
            ipv6_addresses: List[str] = [
                addr[4][0] for addr in result if addr[0] == AF_INET6
            ]
            
            debug_log(LOGGER, "DNS resolution results:")
            debug_log(LOGGER, f"  IPv4 addresses: {ipv4_addresses}")
            debug_log(LOGGER, f"  IPv6 addresses: {ipv6_addresses}")
            
            if not ipv4_addresses and not ipv6_addresses:
                LOGGER.warning(f"Domain {check_domain} has no A or AAAA "
                               f"records")
                debug_log(LOGGER, "No valid IP addresses found in DNS "
                                  "resolution")
                return False
            
            # Log found addresses
            if ipv4_addresses:
                ipv4_display: str = ', '.join(
                    str(addr) for addr in ipv4_addresses[:3]
                )
                debug_log(LOGGER, 
                          f"Domain {check_domain} IPv4 A records: "
                          f"{ipv4_display}")
                LOGGER.info(
                    f"Domain {check_domain} IPv4 A records: {ipv4_display}"
                )
            if ipv6_addresses:
                ipv6_display: str = ', '.join(
                    str(addr) for addr in ipv6_addresses[:3]
                )
                debug_log(LOGGER, 
                          f"Domain {check_domain} IPv6 AAAA records: "
                          f"{ipv6_display}")
                LOGGER.info(
                    f"Domain {check_domain} IPv6 AAAA records: "
                    f"{ipv6_display}"
                )
            
            # Check if any record matches the external IPs
            if external_ips:
                ipv4_match: bool = False
                ipv6_match: bool = False
                
                debug_log(LOGGER, 
                          "Checking IP address matches with server "
                          "external IPs")
                
                # Check IPv4 match
                if external_ips.get("ipv4") and ipv4_addresses:
                    if external_ips["ipv4"] in ipv4_addresses:
                        external_ipv4: str = external_ips['ipv4']
                        LOGGER.info(
                            f"✓ Domain {check_domain} IPv4 A record matches "
                            f"server external IP ({external_ipv4})"
                        )
                        ipv4_match = True
                    else:
                        LOGGER.warning(
                            f"⚠ Domain {check_domain} IPv4 A record does "
                            "not match server external IP"
                        )
                        ipv4_list: str = ', '.join(
                            str(addr) for addr in ipv4_addresses
                        )
                        LOGGER.warning(f"  Domain IPv4: {ipv4_list}")
                        LOGGER.warning(f"  Server IPv4: "
                                       f"{external_ips['ipv4']}")
                
                # Check IPv6 match
                if external_ips.get("ipv6") and ipv6_addresses:
                    if external_ips["ipv6"] in ipv6_addresses:
                        external_ipv6: str = external_ips['ipv6']
                        LOGGER.info(
                            f"✓ Domain {check_domain} IPv6 AAAA record "
                            f"matches server external IP ({external_ipv6})"
                        )
                        ipv6_match = True
                    else:
                        LOGGER.warning(
                            f"⚠ Domain {check_domain} IPv6 AAAA record does "
                            "not match server external IP"
                        )
                        ipv6_list: str = ', '.join(
                            str(addr) for addr in ipv6_addresses
                        )
                        LOGGER.warning(f"  Domain IPv6: {ipv6_list}")
                        LOGGER.warning(f"  Server IPv6: "
                                       f"{external_ips['ipv6']}")
                
                # Determine if we have any matching records
                has_any_match: bool = ipv4_match or ipv6_match
                has_external_ip: bool = bool(
                    external_ips.get("ipv4") or external_ips.get("ipv6")
                )
                
                debug_log(LOGGER, f"IP match results: IPv4={ipv4_match}, "
                                  f"IPv6={ipv6_match}")
                debug_log(LOGGER, f"Has external IP: {has_external_ip}, "
                                  f"Has match: {has_any_match}")
                
                if has_external_ip and not has_any_match:
                    LOGGER.warning(
                        f"⚠ Domain {check_domain} records do not match "
                        "any server external IP"
                    )
                    LOGGER.warning(
                        f"  HTTP challenge may fail - ensure domain points "
                        f"to this server"
                    )
                    
                    # Check if we should treat this as an error
                    strict_ip_check: bool = (
                        getenv("ACME_HTTP_STRICT_IP_CHECK", "no") == "yes"
                    )
                    if strict_ip_check:
                        LOGGER.error(
                            f"Strict IP check enabled - rejecting "
                            f"certificate request for {check_domain}"
                        )
                        debug_log(LOGGER, "Strict IP check failed - "
                                          "returning False")
                        return False
            
            LOGGER.info(f"✓ Domain {check_domain} DNS validation passed")
            debug_log(LOGGER, "DNS validation completed successfully")
            return True
        else:
            debug_log(LOGGER, 
                      f"Domain {check_domain} validation failed - no DNS "
                      f"resolution")
            LOGGER.info(f"Domain {check_domain} validation failed - no DNS "
                        f"resolution")
            LOGGER.warning(f"Domain {check_domain} does not resolve")
            return False
            
    except gaierror as e:
        debug_log(LOGGER, f"Domain {check_domain} DNS resolution failed "
                          f"(gaierror): {e}")
        LOGGER.info(f"Domain {check_domain} DNS resolution failed "
                    f"(gaierror): {e}")
        LOGGER.warning(f"DNS resolution failed for domain {check_domain}: "
                       f"{e}")
        return False
    except BaseException as e:
        LOGGER.info(format_exc())
        LOGGER.error(f"Error checking DNS records for domain "
                     f"{check_domain}: {e}")
        debug_log(LOGGER, "DNS check failed with unexpected exception")
        return False


def certbot_new_with_retry(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: Optional[str] = None,
    credentials_path: Optional[Any] = None,
    propagation: str = "default",
    profile: str = "classic",
    staging: bool = False,
    force: bool = False,
    cmd_env: Optional[Dict[str, str]] = None,
    max_retries: int = 0,
    ca_provider: str = "letsencrypt",
    api_key: Optional[str] = None,
    server_name: Optional[str] = None,
) -> int:
    # Execute certbot with retry mechanism.
    # Wrapper around certbot_new that implements automatic retries with
    # exponential backoff for failed certificate generation attempts.
    debug_log(LOGGER, f"Starting certbot with retry for domains: {domains}")
    debug_log(LOGGER, f"Max retries: {max_retries}, CA: {ca_provider}")
    debug_log(LOGGER, f"Challenge: {challenge_type}, Provider: {provider}")
    
    attempt: int = 1
    result: int = 1  # Initialize result
    while attempt <= max_retries + 1:
        if attempt > 1:
            LOGGER.warning(
                f"Certificate generation failed, retrying... "
                f"(attempt {attempt}/{max_retries + 1})"
            )
            wait_time: int = min(30 * (2 ** (attempt - 2)), 300)
            
            debug_log(LOGGER, 
                      f"Waiting {wait_time} seconds before retry...")
            debug_log(LOGGER, f"Exponential backoff: base=30s, "
                              f"attempt={attempt}")
            LOGGER.info(f"Waiting {wait_time} seconds before retry...")
            sleep(wait_time)

        debug_log(LOGGER, f"Executing certbot attempt {attempt}")

        certbot_result: int = certbot_new(
            challenge_type,
            domains,
            email,
            provider,
            credentials_path,
            propagation,
            profile,
            staging,
            force,
            cmd_env or {},
            ca_provider,
            api_key,
            server_name,
        )

        if certbot_result == 0:
            if attempt > 1:
                LOGGER.info(f"Certificate generation succeeded on attempt "
                            f"{attempt}")
            debug_log(LOGGER, "Certbot completed successfully")
            return certbot_result

        if attempt >= max_retries + 1:
            LOGGER.error(f"Certificate generation failed after "
                         f"{max_retries + 1} attempts")
            debug_log(LOGGER, "Maximum retries reached - giving up")
            return certbot_result

        result = certbot_result  # Update the outer result

        debug_log(LOGGER, f"Attempt {attempt} failed, will retry")
        attempt += 1

    return result


def certbot_new(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: Optional[str] = None,
    credentials_path: Optional[Any] = None,
    propagation: str = "default",
    profile: str = "classic",
    staging: bool = False,
    force: bool = False,
    cmd_env: Optional[Dict[str, str]] = None,
    ca_provider: str = "letsencrypt",
    api_key: Optional[str] = None,
    server_name: Optional[str] = None,
) -> int:
    # Generate new certificate using certbot.
    # Main function to request SSL/TLS certificates from a certificate 
    # authority using the ACME protocol via certbot.
    if isinstance(credentials_path, str):
        credentials_path = Path(credentials_path)

    ca_config: Dict[str, str] = get_certificate_authority_config(
        ca_provider, staging
    )
    
    debug_log(LOGGER, f"Building certbot command for {domains}")
    debug_log(LOGGER, f"CA config: {ca_config}")
    debug_log(LOGGER, f"Challenge type: {challenge_type}")
    debug_log(LOGGER, f"Profile: {profile}")
    
    command: List[str] = [
        CERTBOT_BIN,
        "certonly",
        "--config-dir",
        str(DATA_PATH),
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

    # Ensure we have a valid environment dictionary to work with
    if cmd_env is None:
        cmd_env = {}
    
    # Create a properly typed working environment dictionary
    working_env: Dict[str, str] = {}
    working_env.update(cmd_env)  # Copy existing values if any

    # Handle certificate key type based on DNS provider and CA
    if challenge_type == "dns" and provider in ("infomaniak", "ionos"):
        # Infomaniak and IONOS require RSA certificates with 4096-bit keys
        command.extend(["--rsa-key-size", "4096"])
        
        debug_log(LOGGER, f"Using RSA-4096 for {provider} provider with "
                          f"{domains}")
        LOGGER.info(f"Using RSA-4096 for {provider} provider with {domains}")
    else:
        # Use elliptic curve certificates for all other providers
        if ca_provider.lower() == "zerossl":
            # Use P-384 elliptic curve for ZeroSSL certificates
            command.extend(["--elliptic-curve", "secp384r1"])
            
            debug_log(LOGGER, f"Using ZeroSSL P-384 curve for {domains}")
            LOGGER.info(f"Using ZeroSSL P-384 curve for {domains}")
        else:
            # Use P-256 elliptic curve for Let's Encrypt certificates
            command.extend(["--elliptic-curve", "secp256r1"])
            
            debug_log(LOGGER, 
                      f"Using Let's Encrypt P-256 curve for {domains}")
            LOGGER.info(f"Using Let's Encrypt P-256 curve for {domains}")
    
    # Handle ZeroSSL EAB credentials
    if ca_provider.lower() == "zerossl":
        debug_log(LOGGER, f"ZeroSSL detected as CA provider for {domains}")
        LOGGER.info(f"ZeroSSL detected as CA provider for {domains}")
        
        # Check for manually provided EAB credentials first
        eab_kid_env: str = (
            getenv("ACME_ZEROSSL_EAB_KID", "") or 
            (getenv(f"{server_name}_ACME_ZEROSSL_EAB_KID", "") 
             if server_name else "")
        )
        eab_hmac_env: str = (
            getenv("ACME_ZEROSSL_EAB_HMAC_KEY", "") or 
            (getenv(f"{server_name}_ACME_ZEROSSL_EAB_HMAC_KEY", "") 
             if server_name else "")
        )
        
        debug_log(LOGGER, "Manual EAB credentials check:")
        debug_log(LOGGER, f"  EAB KID provided: {bool(eab_kid_env)}")
        debug_log(LOGGER, f"  EAB HMAC provided: {bool(eab_hmac_env)}")
        
        if eab_kid_env and eab_hmac_env:
            LOGGER.info("✓ Using manually provided ZeroSSL EAB credentials "
                        "from environment")
            command.extend(["--eab-kid", eab_kid_env, "--eab-hmac-key", 
                            eab_hmac_env])
            LOGGER.info(f"✓ Using ZeroSSL EAB credentials for {domains}")
            LOGGER.info(f"EAB Kid: {eab_kid_env[:10]}...")
        elif api_key:
            debug_log(LOGGER, f"ZeroSSL API key provided, setting up EAB "
                              f"credentials")
            LOGGER.info(f"ZeroSSL API key provided, setting up EAB "
                        f"credentials")
            eab_kid: Optional[str]
            eab_hmac: Optional[str]
            eab_kid, eab_hmac = setup_zerossl_eab_credentials(email, api_key)
            if eab_kid and eab_hmac:
                command.extend(["--eab-kid", eab_kid, "--eab-hmac-key", 
                                eab_hmac])
                LOGGER.info(f"✓ Using ZeroSSL EAB credentials for {domains}")
                LOGGER.info(f"EAB Kid: {eab_kid[:10]}...")
            else:
                LOGGER.error("❌ Failed to obtain ZeroSSL EAB credentials")
                LOGGER.error(
                    "Alternative: Set ACME_ZEROSSL_EAB_KID and "
                    "ACME_ZEROSSL_EAB_HMAC_KEY environment variables"
                )
                LOGGER.warning("Proceeding without EAB - this will likely "
                               "fail")
        else:
            LOGGER.error("❌ No ZeroSSL API key provided!")
            LOGGER.error("Set ACME_ZEROSSL_API_KEY environment variable")
            LOGGER.error(
                "Or set ACME_ZEROSSL_EAB_KID and ACME_ZEROSSL_EAB_HMAC_KEY "
                "directly"
            )
            LOGGER.warning("Proceeding without EAB - this will likely fail")

    if challenge_type == "dns":
        command.append("--preferred-challenges=dns")

        debug_log(LOGGER, "DNS challenge configuration:")
        debug_log(LOGGER, f"  Provider: {provider}")
        debug_log(LOGGER, f"  Propagation: {propagation}")
        debug_log(LOGGER, f"  Credentials path: {credentials_path}")

        if propagation != "default":
            if not propagation.isdigit():
                LOGGER.warning(
                    f"Invalid propagation time: {propagation}, "
                    "using provider's default..."
                )
            else:
                command.extend([f"--dns-{provider}-propagation-seconds", 
                                propagation])
                debug_log(LOGGER, f"Set DNS propagation time to "
                                  f"{propagation} seconds")

        if provider == "route53":
            debug_log(LOGGER, "Route53 provider - setting environment "
                              "variables")
            if credentials_path:
                with open(credentials_path, "r") as file:
                    for line in file:
                        if '=' in line:
                            key, value = line.strip().split("=", 1)
                            # Explicit type-safe assignment
                            env_key: str = str(key)
                            env_value: str = str(value)
                            working_env[env_key] = env_value
        else:
            if credentials_path:
                command.extend([f"--dns-{provider}-credentials", 
                                str(credentials_path)])

        if provider in ("desec", "infomaniak", "ionos", "njalla", 
                        "scaleway"):
            command.extend(["--authenticator", f"dns-{provider}"])
            debug_log(LOGGER, f"Using explicit authenticator for {provider}")
        else:
            command.append(f"--dns-{provider}")

    elif challenge_type == "http":
        auth_hook: Any = JOBS_PATH.joinpath('certbot-auth.py')
        cleanup_hook: Any = JOBS_PATH.joinpath('certbot-cleanup.py')
        debug_log(LOGGER, "HTTP challenge configuration:")
        debug_log(LOGGER, f"  Auth hook: {auth_hook}")
        debug_log(LOGGER, f"  Cleanup hook: {cleanup_hook}")
        
        command.extend(
            [
                "--manual",
                "--preferred-challenges=http",
                "--manual-auth-hook",
                str(auth_hook),
                "--manual-cleanup-hook",
                str(cleanup_hook),
            ]
        )

    if force:
        command.append("--force-renewal")
        debug_log(LOGGER, "Force renewal enabled")

    log_level: str = getenv("CUSTOM_LOG_LEVEL", 
                            getenv("LOG_LEVEL", "INFO"))
    if log_level.upper() == "DEBUG":
        command.append("-v")
        debug_log(LOGGER, "Verbose mode enabled for certbot")

    LOGGER.info(f"Executing certbot command for {domains}")
    # Show command but mask sensitive EAB values for security
    safe_command: List[str] = []
    mask_next: bool = False
    for item in command:
        if mask_next:
            safe_command.append("***MASKED***")
            mask_next = False
        elif item in ["--eab-kid", "--eab-hmac-key"]:
            safe_command.append(item)
            mask_next = True
        else:
            safe_command.append(item)
    
    debug_log(LOGGER, f"Command: {' '.join(safe_command)}")
    debug_log(LOGGER, f"Environment variables: {len(working_env)} items")
    for key in working_env.keys():
        is_sensitive: bool = any(
            sensitive in key.lower() 
            for sensitive in ['key', 'secret', 'token']
        )
        value_display: str = '***MASKED***' if is_sensitive else 'set'
        debug_log(LOGGER, f"  {key}: {value_display}")
    LOGGER.info(f"Command: {' '.join(safe_command)}")
    
    current_date: datetime = datetime.now()
    debug_log(LOGGER, "Starting certbot process")
    
    process: Popen[str] = Popen(
        command, stdin=DEVNULL, stderr=PIPE, 
        universal_newlines=True, env=working_env
    )

    lines_processed: int = 0
    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    lines_processed += 1
                    break

        if datetime.now() - current_date > timedelta(seconds=5):
            challenge_info: str = (
                " (this may take a while depending on the provider)" 
                if challenge_type == "dns" else ""
            )
            LOGGER.info(
                f"⏳ Still generating {ca_config['name']} certificate(s)"
                f"{challenge_info}..."
            )
            current_date = datetime.now()
            
            debug_log(LOGGER, f"Certbot still running, processed "
                              f"{lines_processed} output lines")

    final_return_code: Optional[int] = process.returncode
    if final_return_code is None:
        final_return_code = 1
    
    debug_log(LOGGER, f"Certbot process completed with return code: "
                      f"{final_return_code}")
    debug_log(LOGGER, f"Total output lines processed: {lines_processed}")

    return final_return_code


# Global configuration and setup
IS_MULTISITE: bool = getenv("MULTISITE", "no") == "yes"

try:
    # Main execution block for certificate generation
    servers_env: str = getenv("SERVER_NAME", "www.example.com").lower() or ""
    servers: List[str] = servers_env.split(" ") if servers_env else []

    debug_log(LOGGER, "Server configuration detected:")
    debug_log(LOGGER, f"  Multisite mode: {IS_MULTISITE}")
    debug_log(LOGGER, f"  Server count: {len(servers)}")
    debug_log(LOGGER, f"  Servers: {servers}")

    if not servers:
        LOGGER.warning("There are no server names, skipping generation...")
        sys_exit(0)

    use_letsencrypt: bool = False
    use_letsencrypt_dns: bool = False

    domains_server_names: Dict[str, str]
    if not IS_MULTISITE:
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        use_letsencrypt_dns = (
            getenv("LETS_ENCRYPT_CHALLENGE", "http") == "dns"
        )
        all_servers: str = " ".join(servers).lower()
        domains_server_names = {servers[0]: all_servers}
        
        debug_log(LOGGER, "Single-site configuration:")
        debug_log(LOGGER, f"  Let's Encrypt enabled: {use_letsencrypt}")
        debug_log(LOGGER, f"  DNS challenge: {use_letsencrypt_dns}")
    else:
        domains_server_names = {}

        for first_server in servers:
            auto_le_env: str = f"{first_server}_AUTO_LETS_ENCRYPT"
            if (first_server and 
                getenv(auto_le_env, "no") == "yes"):
                use_letsencrypt = True

            challenge_env: str = f"{first_server}_LETS_ENCRYPT_CHALLENGE"
            if (first_server and 
                getenv(challenge_env, "http") == "dns"):
                use_letsencrypt_dns = True

            server_name_env: str = f"{first_server}_SERVER_NAME"
            domains_server_names[first_server] = getenv(
                server_name_env, first_server
            ).lower()
        
        debug_log(LOGGER, "Multi-site configuration:")
        debug_log(LOGGER, f"  Let's Encrypt enabled anywhere: "
                          f"{use_letsencrypt}")
        debug_log(LOGGER, f"  DNS challenge used anywhere: "
                          f"{use_letsencrypt_dns}")
        debug_log(LOGGER, f"  Domain mappings: {domains_server_names}")

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping generation...")
        sys_exit(0)

    provider_classes: Dict[str, Any] = {}

    if use_letsencrypt_dns:
        debug_log(LOGGER, "DNS challenge detected - loading provider classes")
        
        provider_classes = {
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

    JOB: Any = Job(LOGGER, __file__)

    # Restore data from db cache of certbot-renew job
    debug_log(LOGGER, "Restoring certificate data from database cache")
    JOB.restore_cache(job_name="certbot-renew")

    # Initialize environment variables for certbot execution
    env: Dict[str, str] = {
        "PATH": getenv("PATH") or "",
        "PYTHONPATH": getenv("PYTHONPATH") or "",
        "RELOAD_MIN_TIMEOUT": getenv("RELOAD_MIN_TIMEOUT") or "5",
        "DISABLE_CONFIGURATION_TESTING": (
            getenv("DISABLE_CONFIGURATION_TESTING") or "no"
        ).lower(),
    }
    
    env["PYTHONPATH"] = env["PYTHONPATH"] + (
        f":{DEPS_PATH}" if DEPS_PATH not in env["PYTHONPATH"] else ""
    )
    database_uri: Optional[str] = getenv("DATABASE_URI")
    if database_uri:  # Only assign if not None and not empty
        # Explicit assignment with type safety
        env_key: str = "DATABASE_URI"
        env_value: str = str(database_uri)
        env[env_key] = env_value

    debug_log(LOGGER, "Checking existing certificates")
    
    proc = run(
        [
            CERTBOT_BIN,
            "certificates",
            "--config-dir",
            str(DATA_PATH),
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
    stdout: str = proc.stdout or ""

    WILDCARD_GENERATOR: Any = WildcardGenerator()
    credential_paths: Set[Any] = set()
    generated_domains: Set[str] = set()
    domains_to_ask: Dict[str, int] = {}
    active_cert_names: Set[str] = set()

    if proc.returncode != 0:
        LOGGER.error(f"Error while checking certificates:\n{proc.stdout}")
        debug_log(LOGGER, "Certificate listing failed - proceeding anyway")
    else:
        debug_log(LOGGER, "Certificate listing successful - analyzing "
                          "existing certificates")
        
        certificate_blocks: List[str] = stdout.split("Certificate Name: ")[1:]
        
        debug_log(LOGGER, f"Found {len(certificate_blocks)} existing "
                          f"certificates")
        
        for first_server, domains in domains_server_names.items():
            auto_le_check: str = (
                getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") 
                if IS_MULTISITE 
                else getenv("AUTO_LETS_ENCRYPT", "no")
            )
            if auto_le_check != "yes":
                continue

            challenge_check: str = (
                getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") 
                if IS_MULTISITE 
                else getenv("LETS_ENCRYPT_CHALLENGE", "http")
            )
            original_first_server: str = deepcopy(first_server)

            debug_log(LOGGER, f"Processing server: {first_server}")
            debug_log(LOGGER, f"  Challenge: {challenge_check}")
            debug_log(LOGGER, f"  Domains: {domains}")

            wildcard_check: str = (
                getenv(f"{original_first_server}_USE_LETS_ENCRYPT_WILDCARD", 
                       "no") 
                if IS_MULTISITE 
                else getenv("USE_LETS_ENCRYPT_WILDCARD", "no")
            )
            
            domains_set: Set[str]
            if (challenge_check == "dns" and wildcard_check == "yes"):
                debug_log(LOGGER, f"Using wildcard mode for {first_server}")
                
                wildcard_domains: List[str] = (
                    WILDCARD_GENERATOR.extract_wildcards_from_domains(
                        (first_server,)
                    )
                )
                first_server = wildcard_domains[0].lstrip("*.")
                domains_set = set(wildcard_domains)
            else:
                domains_set = set(str(domains).split(" "))

            # Add the certificate name to our active set regardless 
            # if we're generating it or not
            active_cert_names.add(first_server)

            certificate_block: Optional[str] = None
            for block in certificate_blocks:
                if block.startswith(f"{first_server}\n"):
                    certificate_block = block
                    break

            if not certificate_block:
                domains_to_ask[first_server] = 1
                LOGGER.warning(
                    f"[{original_first_server}] Certificate block for "
                    f"{first_server} not found, asking new certificate..."
                )
                continue

            # Validating the credentials
            try:
                cert_domains_match = search(
                    r"Domains: (?P<domains>.*)\n\s*Expiry Date: "
                    r"(?P<expiry_date>.*)\n", 
                    certificate_block, 
                    MULTILINE
                )
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(
                    f"[{original_first_server}] Error while parsing "
                    f"certificate block: {e}"
                )
                continue

            if not cert_domains_match:
                LOGGER.error(
                    f"[{original_first_server}] Failed to parse domains "
                    "and expiry date from certificate block."
                )
                continue

            cert_domains_list: List[str] = (
                cert_domains_match.group("domains").strip().split()
            )
            cert_domains_set: Set[str] = set(cert_domains_list)
            desired_domains_set: Set[str] = (
                set(domains_set) if isinstance(domains_set, (list, set)) 
                else set(str(domains_set).split())
            )

            debug_log(LOGGER, f"Certificate domain comparison for "
                              f"{first_server}:")
            debug_log(LOGGER, 
                      f"  Existing: {sorted(str(d) for d in cert_domains_set)}")
            debug_log(LOGGER, 
                      f"  Desired: {sorted(str(d) for d in desired_domains_set)}")

            if cert_domains_set != desired_domains_set:
                domains_to_ask[first_server] = 2
                existing_sorted: List[str] = sorted(
                    str(d) for d in cert_domains_set
                )
                desired_sorted: List[str] = sorted(
                    str(d) for d in desired_domains_set
                )
                LOGGER.warning(
                    f"[{original_first_server}] Domains for {first_server} "
                    f"differ from desired set (existing: {existing_sorted}, "
                    f"desired: {desired_sorted}), asking new certificate..."
                )
                continue

            # Check if CA provider has changed
            ca_provider_env: str = (
                f"{original_first_server}_ACME_SSL_CA_PROVIDER" 
                if IS_MULTISITE 
                else "ACME_SSL_CA_PROVIDER"
            )
            ca_provider: str = getenv(ca_provider_env, "letsencrypt")
            
            renewal_file: Any = DATA_PATH.joinpath("renewal", 
                                                    f"{first_server}.conf")
            if renewal_file.is_file():
                current_server: Optional[str] = None
                with renewal_file.open("r") as file:
                    for line in file:
                        if line.startswith("server"):
                            current_server = line.strip().split("=", 1)[1].strip()
                            break
                
                staging_env: str = (
                    f"{original_first_server}_USE_LETS_ENCRYPT_STAGING" 
                    if IS_MULTISITE 
                    else "USE_LETS_ENCRYPT_STAGING"
                )
                staging_mode: bool = getenv(staging_env, "no") == "yes"
                expected_config: Dict[str, str] = (
                    get_certificate_authority_config(
                        ca_provider, staging_mode
                    )
                )
                
                debug_log(LOGGER, f"CA server comparison for {first_server}:")
                debug_log(LOGGER, f"  Current: {current_server}")
                debug_log(LOGGER, f"  Expected: {expected_config['server']}")
                
                if (current_server and 
                    current_server != expected_config["server"]):
                    domains_to_ask[first_server] = 2
                    LOGGER.warning(
                        f"[{original_first_server}] CA provider for "
                        f"{first_server} has changed, asking new "
                        f"certificate..."
                    )
                    continue

            staging_env = (
                f"{original_first_server}_USE_LETS_ENCRYPT_STAGING" 
                if IS_MULTISITE 
                else "USE_LETS_ENCRYPT_STAGING"
            )
            use_staging: bool = getenv(staging_env, "no") == "yes"
            is_test_cert: bool = (
                "TEST_CERT" in cert_domains_match.group("expiry_date")
            )

            debug_log(LOGGER, f"Staging environment check for {first_server}:")
            debug_log(LOGGER, f"  Use staging: {use_staging}")
            debug_log(LOGGER, f"  Is test cert: {is_test_cert}")

            staging_mismatch: bool = (
                (is_test_cert and not use_staging) or 
                (not is_test_cert and use_staging)
            )
            if staging_mismatch:
                domains_to_ask[first_server] = 2
                LOGGER.warning(
                    f"[{original_first_server}] Certificate environment "
                    f"(staging/production) changed for {first_server}, "
                    "asking new certificate..."
                )
                continue

            provider_env: str = (
                f"{original_first_server}_LETS_ENCRYPT_DNS_PROVIDER" 
                if IS_MULTISITE 
                else "LETS_ENCRYPT_DNS_PROVIDER"
            )
            provider: str = getenv(provider_env, "")

            if not renewal_file.is_file():
                LOGGER.error(
                    f"[{original_first_server}] Renewal file for "
                    f"{first_server} not found, asking new certificate..."
                )
                domains_to_ask[first_server] = 1
                continue

            current_provider: Optional[str] = None
            with renewal_file.open("r") as file:
                for line in file:
                    if line.startswith("authenticator"):
                        key, value = line.strip().split("=", 1)
                        current_provider = value.strip().replace("dns-", "")
                        break

            debug_log(LOGGER, f"Provider comparison for {first_server}:")
            debug_log(LOGGER, f"  Current: {current_provider}")
            debug_log(LOGGER, f"  Configured: {provider}")

            if challenge_check == "dns":
                if provider and current_provider != provider:
                    domains_to_ask[first_server] = 2
                    LOGGER.warning(
                        f"[{original_first_server}] Provider for "
                        f"{first_server} is not the same as in the "
                        "certificate, asking new certificate..."
                    )
                    continue

                # Check if DNS credentials have changed
                if provider and current_provider == provider:
                    debug_log(LOGGER, f"Checking DNS credentials for "
                                      f"{first_server}")
                    
                    credential_key: str = (
                        f"{original_first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
                        if IS_MULTISITE 
                        else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
                    )
                    current_credential_items: Dict[str, str] = {}

                    for env_key, env_value in environ.items():
                        if env_value and env_key.startswith(credential_key):
                            if " " not in env_value:
                                current_credential_items["json_data"] = env_value
                                continue
                            key, value = env_value.split(" ", 1)
                            cleaned_value: str = (
                                value.removeprefix("= ").replace("\\n", "\n")
                                     .replace("\\t", "\t").replace("\\r", "\r")
                                     .strip()
                            )
                            current_credential_items[key.lower()] = cleaned_value

                    if "json_data" in current_credential_items:
                        value = current_credential_items.pop("json_data")
                        is_base64_like: bool = (
                            not current_credential_items and 
                            len(value) % 4 == 0 and 
                            match(r"^[A-Za-z0-9+/=]+$", value) is not None
                        )
                        if is_base64_like:
                            with suppress(BaseException):
                                decoded: str = b64decode(value).decode("utf-8")
                                json_data: Dict[str, Any] = loads(decoded)
                                if isinstance(json_data, dict):
                                    new_items: Dict[str, str] = {}
                                    for k, v in json_data.items():
                                        cleaned_v: str = (
                                            str(v).removeprefix("= ")
                                                  .replace("\\n", "\n")
                                                  .replace("\\t", "\t")
                                                  .replace("\\r", "\r")
                                                  .strip()
                                        )
                                        new_items[k.lower()] = cleaned_v
                                    current_credential_items = new_items

                    if current_credential_items:
                        for key, value in current_credential_items.items():
                            is_base64_candidate: bool = (
                                provider != "rfc2136" and 
                                len(value) % 4 == 0 and 
                                match(r"^[A-Za-z0-9+/=]+$", value) is not None
                            )
                            if is_base64_candidate:
                                with suppress(BaseException):
                                    decoded = b64decode(value).decode("utf-8")
                                    if decoded != value:
                                        cleaned_decoded: str = (
                                            decoded.removeprefix("= ")
                                                   .replace("\\n", "\n")
                                                   .replace("\\t", "\t")
                                                   .replace("\\r", "\r")
                                                   .strip()
                                        )
                                        current_credential_items[key] = (
                                            cleaned_decoded
                                        )

                        if provider in provider_classes:
                            with suppress(ValidationError, KeyError):
                                provider_instance: Any = provider_classes[provider](
                                    **current_credential_items
                                )
                                current_credentials_content: bytes = (
                                    provider_instance.get_formatted_credentials()
                                )

                                file_type: str = (
                                    provider_instance.get_file_type()
                                )
                                stored_credentials_path: Any = (
                                    CACHE_PATH.joinpath(
                                        first_server, 
                                        f"credentials.{file_type}"
                                    )
                                )

                                if stored_credentials_path.is_file():
                                    stored_credentials_content: bytes = (
                                        stored_credentials_path.read_bytes()
                                    )
                                    content_differs: bool = (
                                        stored_credentials_content != 
                                        current_credentials_content
                                    )
                                    if content_differs:
                                        domains_to_ask[first_server] = 2
                                        LOGGER.warning(
                                            f"[{original_first_server}] DNS "
                                            f"credentials for {first_server} "
                                            f"have changed, asking new "
                                            f"certificate..."
                                        )
                                        continue
            elif (current_provider != "manual" and 
                  challenge_check == "http"):
                domains_to_ask[first_server] = 2
                LOGGER.warning(
                    f"[{original_first_server}] {first_server} is no longer "
                    "using DNS challenge, asking new certificate..."
                )
                continue

            domains_to_ask[first_server] = 0
            LOGGER.info(
                f"[{original_first_server}] Certificates already exist for "
                f"domain(s) {domains_set}, expiry date: "
                f"{cert_domains_match.group('expiry_date')}"
            )

    psl_lines: Optional[List[str]] = None
    psl_rules: Optional[Dict[str, Set[str]]] = None

    certificates_generated: int = 0
    certificates_failed: int = 0

    # Process each server configuration
    for first_server, domains in domains_server_names.items():
        auto_le_check = (
            getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") 
            if IS_MULTISITE 
            else getenv("AUTO_LETS_ENCRYPT", "no")
        )
        if auto_le_check != "yes":
            LOGGER.info(
                f"SSL certificate generation is not activated for "
                f"{first_server}, skipping..."
            )
            continue

        # Getting all the necessary data
        email_env: str = (
            f"{first_server}_EMAIL_LETS_ENCRYPT" if IS_MULTISITE 
            else "EMAIL_LETS_ENCRYPT"
        )
        challenge_env = (
            f"{first_server}_LETS_ENCRYPT_CHALLENGE" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_CHALLENGE"
        )
        staging_env = (
            f"{first_server}_USE_LETS_ENCRYPT_STAGING" 
            if IS_MULTISITE 
            else "USE_LETS_ENCRYPT_STAGING"
        )
        wildcard_env = (
            f"{first_server}_USE_LETS_ENCRYPT_WILDCARD" 
            if IS_MULTISITE 
            else "USE_LETS_ENCRYPT_WILDCARD"
        )
        provider_env = (
            f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_DNS_PROVIDER"
        )
        propagation_env = (
            f"{first_server}_LETS_ENCRYPT_DNS_PROPAGATION" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_DNS_PROPAGATION"
        )
        profile_env = (
            f"{first_server}_LETS_ENCRYPT_PROFILE" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_PROFILE"
        )
        psl_env = (
            f"{first_server}_LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES"
        )
        retries_env = (
            f"{first_server}_LETS_ENCRYPT_MAX_RETRIES" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_MAX_RETRIES"
        )
        ca_env = (
            f"{first_server}_ACME_SSL_CA_PROVIDER" if IS_MULTISITE 
            else "ACME_SSL_CA_PROVIDER"
        )
        api_key_env = (
            f"{first_server}_ACME_ZEROSSL_API_KEY" 
            if IS_MULTISITE 
            else "ACME_ZEROSSL_API_KEY"
        )

        server_data: Dict[str, Any] = {
            "email": (getenv(email_env, "") or f"contact@{first_server}"),
            "challenge": getenv(challenge_env, "http"),
            "staging": getenv(staging_env, "no") == "yes",
            "use_wildcard": getenv(wildcard_env, "no") == "yes",
            "provider": getenv(provider_env, ""),
            "propagation": getenv(propagation_env, "default"),
            "profile": getenv(profile_env, "classic"),
            "check_psl": getenv(psl_env, "yes") == "no",
            "max_retries": getenv(retries_env, "0"),
            "ca_provider": getenv(ca_env, "letsencrypt"),
            "api_key": getenv(api_key_env, ""),
            "credential_items": {},
        }
        
        debug_log(LOGGER, f"Service {first_server} configuration: {server_data}")
        
        LOGGER.info(f"Service {first_server} configuration:")
        LOGGER.info(f"  CA Provider: {server_data['ca_provider']}")
        api_key_status: str = 'Yes' if server_data['api_key'] else 'No'
        LOGGER.info(f"  API Key provided: {api_key_status}")
        LOGGER.info(f"  Challenge type: {server_data['challenge']}")
        LOGGER.info(f"  Staging: {server_data['staging']}")
        LOGGER.info(f"  Wildcard: {server_data['use_wildcard']}")

        # Override profile if custom profile is set
        custom_profile_env: str = (
            f"{first_server}_LETS_ENCRYPT_CUSTOM_PROFILE" 
            if IS_MULTISITE 
            else "LETS_ENCRYPT_CUSTOM_PROFILE"
        )
        custom_profile_str: str = getenv(custom_profile_env, "").strip()
        if custom_profile_str:
            server_data["profile"] = custom_profile_str
            debug_log(LOGGER, f"Using custom profile: {custom_profile_str}")

        if server_data["challenge"] == "http" and server_data["use_wildcard"]:
            LOGGER.warning(
                f"Wildcard is not supported with HTTP challenge, "
                f"disabling wildcard for service {first_server}..."
            )
            server_data["use_wildcard"] = False

        should_skip_cert_check: bool = (
            (not server_data["use_wildcard"] and 
             not domains_to_ask.get(first_server)) or
            (server_data["use_wildcard"] and not domains_to_ask.get(
                WILDCARD_GENERATOR.extract_wildcards_from_domains(
                    (first_server,)
                )[0].lstrip("*.")
            ))
        )
        if should_skip_cert_check:
            debug_log(LOGGER, f"No certificate needed for {first_server}")
            continue

        if not server_data["max_retries"].isdigit():
            LOGGER.warning(
                f"Invalid max retries value for service {first_server}: "
                f"{server_data['max_retries']}, using default value of 0..."
            )
            server_data["max_retries"] = 0
        else:
            server_data["max_retries"] = int(server_data["max_retries"])

        # Getting the DNS provider data if necessary
        if server_data["challenge"] == "dns":
            debug_log(LOGGER, 
                      f"Processing DNS credentials for {first_server}")
            
            credential_key = (
                f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
                if IS_MULTISITE 
                else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
            )
            credential_items: Dict[str, str] = {}

            # Collect all credential items
            for env_key, env_value in environ.items():
                if env_value and env_key.startswith(credential_key):
                    if " " not in env_value:
                        credential_items["json_data"] = env_value
                        continue
                    key, value = env_value.split(" ", 1)
                    cleaned_value = (
                        value.removeprefix("= ")
                             .replace("\\n", "\n")
                             .replace("\\t", "\t")
                             .replace("\\r", "\r").strip()
                    )
                    credential_items[key.lower()] = cleaned_value

            if "json_data" in credential_items:
                value = credential_items.pop("json_data")
                # Handle the case of a single credential that might be 
                # base64-encoded JSON
                is_potential_json: bool = (
                    not credential_items and 
                    len(value) % 4 == 0 and 
                    match(r"^[A-Za-z0-9+/=]+$", value) is not None
                )
                if is_potential_json:
                    try:
                        decoded = b64decode(value).decode("utf-8")
                        json_data = loads(decoded)
                        if isinstance(json_data, dict):
                            new_items = {}
                            for k, v in json_data.items():
                                cleaned_v = (
                                    str(v).removeprefix("= ")
                                          .replace("\\n", "\n")
                                          .replace("\\t", "\t")
                                          .replace("\\r", "\r").strip()
                                )
                                new_items[k.lower()] = cleaned_v
                            server_data["credential_items"] = new_items
                    except BaseException as e:
                        LOGGER.debug(format_exc())
                        LOGGER.error(
                            f"Error while decoding JSON data for service "
                            f"{first_server}: {value} : \n{e}"
                        )

            if not server_data["credential_items"]:
                # Process regular credentials
                server_data["credential_items"] = {}
                for key, value in credential_items.items():
                    # Check for base64 encoding
                    is_base64_candidate = (
                        server_data["provider"] != "rfc2136" and 
                        len(value) % 4 == 0 and 
                        match(r"^[A-Za-z0-9+/=]+$", value) is not None
                    )
                    if is_base64_candidate:
                        try:
                            decoded = b64decode(value).decode("utf-8")
                            if decoded != value:
                                value = (
                                    decoded.removeprefix("= ")
                                           .replace("\\n", "\n")
                                           .replace("\\t", "\t")
                                           .replace("\\r", "\r").strip()
                                )
                        except BaseException as e:
                            LOGGER.debug(format_exc())
                            LOGGER.debug(
                                f"Error while decoding credential item {key} "
                                f"for service {first_server}: {value} : \n{e}"
                            )
                    server_data["credential_items"][key] = value

        safe_data: Dict[str, Any] = server_data.copy()
        masked_items: Dict[str, str] = {
            k: "***MASKED***" 
            for k in server_data["credential_items"].keys()
        }
        safe_data["credential_items"] = masked_items
        if server_data["api_key"]:
            safe_data["api_key"] = "***MASKED***"
        debug_log(LOGGER, f"Safe data for service {first_server}: "
                          f"{dumps(safe_data)}")

        # Validate CA provider and API key requirements
        api_key_status = 'Yes' if server_data['api_key'] else 'No'
        LOGGER.info(
            f"Service {first_server} - CA Provider: {server_data['ca_provider']}, "
            f"API Key provided: {api_key_status}"
        )
        
        if server_data["ca_provider"].lower() == "zerossl":
            if not server_data["api_key"]:
                LOGGER.warning(
                    f"ZeroSSL API key not provided for service "
                    f"{first_server}, falling back to Let's Encrypt..."
                )
                server_data["ca_provider"] = "letsencrypt"
            else:
                LOGGER.info(f"✓ ZeroSSL configuration valid for service "
                            f"{first_server}")

        # Checking if the DNS data is valid
        if server_data["challenge"] == "dns":
            if not server_data["provider"]:
                available_providers: str = ', '.join(
                    str(p) for p in provider_classes.keys()
                )
                LOGGER.warning(
                    f"No provider found for service {first_server} "
                    f"(available providers: {available_providers}), "
                    "skipping certificate(s) generation..."
                )
                continue
            elif server_data["provider"] not in provider_classes:
                available_providers = ', '.join(
                    str(p) for p in provider_classes.keys()
                )
                LOGGER.warning(
                    f"Provider {server_data['provider']} not found for service "
                    f"{first_server} (available providers: "
                    f"{available_providers}), skipping certificate(s) "
                    f"generation..."
                )
                continue
            elif not server_data["credential_items"]:
                LOGGER.warning(
                    f"No valid credentials items found for service "
                    f"{first_server} (you should have at least one), "
                    f"skipping certificate(s) generation..."
                )
                continue

            try:
                dns_provider_instance: Any = provider_classes[server_data["provider"]](
                    **server_data["credential_items"]
                )
            except ValidationError as ve:
                LOGGER.debug(format_exc())
                LOGGER.error(
                    f"Error while validating credentials for service "
                    f"{first_server}:\n{ve}"
                )
                continue

            content: bytes = dns_provider_instance.get_formatted_credentials()
        else:
            content = b"http_challenge"

        is_blacklisted: bool = False

        # Adding the domains to Wildcard Generator if necessary
        file_type_str: str = (
            dns_provider_instance.get_file_type() if server_data["challenge"] == "dns" 
            else "txt"
        )
        file_path: Tuple[str, ...] = (first_server, 
                                      f"credentials.{file_type_str}")
        
        if server_data["use_wildcard"]:
            # Use the improved method for generating consistent group names
            hash_value: Any = bytes_hash(content, algorithm="sha1")
            group: str = WILDCARD_GENERATOR.create_group_name(
                domain=first_server,
                provider=(server_data["provider"] if server_data["challenge"] == "dns" 
                          else "http"),
                challenge_type=server_data["challenge"],
                staging=server_data["staging"],
                content_hash=hash_value,
                profile=server_data["profile"],
            )

            wildcard_info: str = (
                "the propagation time will be the provider's default and " 
                if server_data["challenge"] == "dns" else ""
            )
            LOGGER.info(
                f"Service {first_server} is using wildcard, "
                f"{wildcard_info}the email will be the same as the first "
                f"domain that created the group..."
            )

            if server_data["check_psl"]:
                if psl_lines is None:
                    debug_log(LOGGER, "Loading PSL for wildcard domain "
                                      "validation")
                    psl_lines = load_public_suffix_list(JOB)
                if psl_rules is None:
                    debug_log(LOGGER, "Parsing PSL rules")
                    psl_rules = parse_psl(psl_lines)

                wildcards_list: List[str] = (
                    WILDCARD_GENERATOR.extract_wildcards_from_domains(
                        str(domains).split(" ")
                    )
                )

                wildcard_str: str = ', '.join(
                    str(w) for w in wildcards_list
                )
                LOGGER.info(f"Wildcard domains for {first_server}: "
                            f"{wildcard_str}")

                for d in wildcards_list:
                    if is_domain_blacklisted(d, psl_rules):
                        LOGGER.error(
                            f"Wildcard domain {d} is blacklisted by Public "
                            f"Suffix List, refusing certificate request for "
                            f"{first_server}."
                        )
                        is_blacklisted = True
                        break

            if not is_blacklisted:
                WILDCARD_GENERATOR.extend(
                    group, str(domains).split(" "), server_data["email"], 
                    server_data["staging"]
                )
                file_path = (f"{group}.{file_type_str}",)
                LOGGER.info(f"[{first_server}] Wildcard group {group}")
        elif server_data["check_psl"]:
            if psl_lines is None:
                debug_log(LOGGER, 
                          "Loading PSL for regular domain validation")
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                debug_log(LOGGER, "Parsing PSL rules")
                psl_rules = parse_psl(psl_lines)

            for d in str(domains).split():
                if is_domain_blacklisted(d, psl_rules):
                    LOGGER.error(
                        f"Domain {d} is blacklisted by Public Suffix List, "
                        f"refusing certificate request for {first_server}."
                    )
                    is_blacklisted = True
                    break

        if is_blacklisted:
            debug_log(LOGGER, f"Skipping {first_server} due to PSL blacklist")
            continue

        # Generating the credentials file
        credentials_path: Any = CACHE_PATH.joinpath(*file_path)

        if server_data["challenge"] == "dns":
            debug_log(LOGGER, 
                      f"Managing credentials file for {first_server}: "
                      f"{credentials_path}")
            
            if not credentials_path.is_file():
                service_id: str = (first_server if not server_data["use_wildcard"] 
                                   else "")
                cached: Any
                err: Any
                cached, err = JOB.cache_file(
                    credentials_path.name, content, job_name="certbot-renew", 
                    service_id=service_id
                )
                if not cached:
                    LOGGER.error(
                        f"Error while saving service {first_server}'s "
                        f"credentials file in cache: {err}"
                    )
                    continue
                LOGGER.info(
                    f"Successfully saved service {first_server}'s "
                    "credentials file in cache"
                )
            elif server_data["use_wildcard"]:
                LOGGER.info(
                    f"Service {first_server}'s wildcard credentials file "
                    "has already been generated"
                )
            else:
                old_content: bytes = credentials_path.read_bytes()
                if old_content != content:
                    LOGGER.warning(
                        f"Service {first_server}'s credentials file is "
                        "outdated, updating it..."
                    )
                    cached_updated: Any
                    err_updated: Any
                    cached_updated, err_updated = JOB.cache_file(
                        credentials_path.name, content, 
                        job_name="certbot-renew", 
                        service_id=first_server
                    )
                    if not cached_updated:
                        LOGGER.error(
                            f"Error while updating service {first_server}'s "
                            f"credentials file in cache: {err_updated}"
                        )
                        continue
                    LOGGER.info(
                        f"Successfully updated service {first_server}'s "
                        "credentials file in cache"
                    )
                else:
                    LOGGER.info(
                        f"Service {first_server}'s credentials file is "
                        f"up to date"
                    )

            credential_paths.add(credentials_path)
            # Setting the permissions to 600 (this is important to avoid 
            # warnings from certbot)
            credentials_path.chmod(0o600)

        if server_data["use_wildcard"]:
            debug_log(LOGGER, f"Wildcard processing complete for "
                              f"{first_server}")
            continue

        domains_str: str = str(domains).replace(" ", ",")
        ca_name: str = get_certificate_authority_config(
            server_data["ca_provider"]
        )["name"]
        staging_info: str = ' using staging' if server_data['staging'] else ''
        LOGGER.info(
            f"Asking {ca_name} certificates for domain(s): {domains_str} "
            f"(email = {server_data['email']}){staging_info} "
            f" with {server_data['challenge']} challenge, using "
            f"{server_data['profile']!r} profile..."
        )

        debug_log(LOGGER, f"Requesting certificate for {domains_str}")

        cert_result: int = certbot_new_with_retry(
            cast(Literal["dns", "http"], server_data["challenge"]),
            domains_str,
            server_data["email"],
            server_data["provider"],
            credentials_path,
            server_data["propagation"],
            server_data["profile"],
            server_data["staging"],
            domains_to_ask[first_server] == 2,
            cmd_env=env,
            max_retries=server_data["max_retries"],
            ca_provider=server_data["ca_provider"],
            api_key=server_data["api_key"],
            server_name=first_server,
        )
        
        if cert_result != 0:
            status = 2
            certificates_failed += 1
            LOGGER.error(f"Certificate generation failed for domain(s) "
                         f"{domains_str}...")
        else:
            status = 1 if status == 0 else status
            certificates_generated += 1
            LOGGER.info(f"Certificate generation succeeded for domain(s): "
                        f"{domains_str}")

        generated_domains.update(domains_str.split(","))

    # Generating the wildcards if necessary
    wildcard_groups: Dict[str, Any] = WILDCARD_GENERATOR.get_wildcards()
    if wildcard_groups:
        debug_log(LOGGER, f"Processing {len(wildcard_groups)} wildcard groups")
        
        for group, group_data in wildcard_groups.items():
            if not group_data:
                continue
            
            # Generating the certificate from the generated credentials
            group_parts: List[str] = group.split("_")
            provider_name: str = group_parts[0]
            profile: str = group_parts[2]
            base_domain: str = group_parts[3]

            debug_log(LOGGER, f"Processing wildcard group: {group}")
            debug_log(LOGGER, f"  Provider: {provider_name}")
            debug_log(LOGGER, f"  Profile: {profile}")
            debug_log(LOGGER, f"  Base domain: {base_domain}")

            email: str = group_data.pop("email")
            wildcard_file_type: str = (
                str(provider_classes[provider_name].get_file_type())
                if provider_name in provider_classes else 'txt'
            )
            credentials_file: Any = CACHE_PATH.joinpath(
                f"{group}.{wildcard_file_type}"
            )

            # Get CA provider for this group
            original_server: Optional[str] = None
            for server in domains_server_names.keys():
                if base_domain in server or server in base_domain:
                    original_server = server
                    break
            
            ca_provider = "letsencrypt"  # default
            api_key: Optional[str] = None
            if original_server:
                ca_env = (
                    f"{original_server}_ACME_SSL_CA_PROVIDER" 
                    if IS_MULTISITE 
                    else "ACME_SSL_CA_PROVIDER"
                )
                ca_provider = getenv(ca_env, "letsencrypt")
                
                api_key_env = (
                    f"{original_server}_ACME_ZEROSSL_API_KEY" 
                    if IS_MULTISITE 
                    else "ACME_ZEROSSL_API_KEY"
                )
                api_key = getenv(api_key_env, "") or None

            # Process different environment types (staging/prod)
            for key, domains in group_data.items():
                if not domains:
                    continue

                staging: bool = key == "staging"
                ca_name = get_certificate_authority_config(
                    ca_provider
                )["name"]
                staging_info = ' using staging ' if staging else ''
                challenge_type: str = (
                    'dns' if provider_name in provider_classes else 'http'
                )
                LOGGER.info(
                    f"Asking {ca_name} wildcard certificates for domain(s): "
                    f"{domains} (email = {email}){staging_info} "
                    f"with {challenge_type} challenge, "
                    f"using {profile!r} profile..."
                )

                domains_split: List[str] = domains.split(",")

                # Add wildcard certificate names to active set
                for domain in domains_split:
                    # Extract the base domain from the wildcard domain
                    base_domain = WILDCARD_GENERATOR.get_base_domain(domain)
                    active_cert_names.add(base_domain)

                debug_log(LOGGER, f"Requesting wildcard certificate for "
                                  f"{domains}")

                wildcard_result: int = certbot_new_with_retry(
                    "dns",
                    domains,
                    email,
                    provider_name,
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
                
                if wildcard_result != 0:
                    status = 2
                    certificates_failed += 1
                    LOGGER.error(f"Certificate generation failed for "
                                 f"domain(s) {domains}...")
                else:
                    status = 1 if status == 0 else status
                    certificates_generated += 1
                    LOGGER.info(f"Certificate generation succeeded for "
                                f"domain(s): {domains}")

                generated_domains.update(domains_split)
    else:
        LOGGER.info(
            "No wildcard domains found, skipping wildcard certificate(s) "
            "generation..."
        )

    debug_log(LOGGER, "Certificate generation summary:")
    debug_log(LOGGER, f"  Generated: {certificates_generated}")
    debug_log(LOGGER, f"  Failed: {certificates_failed}")
    debug_log(LOGGER, f"  Total domains: {len(generated_domains)}")

    if CACHE_PATH.is_dir():
        # Clearing all missing credentials files
        debug_log(LOGGER, "Cleaning up old credentials files")
        
        cleaned_files: int = 0
        ext_patterns: Tuple[str, ...] = ("*.ini", "*.env", "*.json")
        for ext in ext_patterns:
            for file in list(CACHE_PATH.rglob(ext)):
                if "etc" in file.parts or not file.is_file():
                    continue
                # If the file is not in the wildcard groups, remove it
                if file not in credential_paths:
                    LOGGER.info(f"Removing old credentials file {file}")
                    service_id = (
                        file.parent.name 
                        if file.parent.name != "letsencrypt" else ""
                    )
                    JOB.del_cache(
                        file.name, job_name="certbot-renew", 
                        service_id=service_id
                    )
                    cleaned_files += 1
        
        debug_log(LOGGER, 
                  f"Cleaned up {cleaned_files} old credentials files")

    # Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info(
            "Clear old certificates is activated, removing old / no longer "
            "used certificates..."
        )

        debug_log(LOGGER, "Starting certificate cleanup process")

        # Get list of all certificates
        proc = run(
            [
                CERTBOT_BIN,
                "certificates",
                "--config-dir",
                str(DATA_PATH),
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
            certificates_removed: int = 0
            
            debug_log(LOGGER, 
                      f"Found {len(certificate_blocks)} certificates "
                      f"to evaluate")
            debug_log(LOGGER, f"Active certificates: "
                      f"{sorted(str(name) for name in active_cert_names)}")
            
            for block in certificate_blocks:
                cert_name: str = block.split("\n", 1)[0].strip()

                # Skip certificates that are in our active list
                if cert_name in active_cert_names:
                    LOGGER.info(f"Keeping active certificate: {cert_name}")
                    continue

                LOGGER.warning(
                    f"Removing old certificate {cert_name} "
                    "(not in active certificates list)"
                )

                # Use certbot's delete command
                delete_proc = run(
                    [
                        CERTBOT_BIN,
                        "delete",
                        "--config-dir",
                        str(DATA_PATH),
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
                    LOGGER.info(f"Successfully deleted certificate "
                                f"{cert_name}")
                    certificates_removed += 1
                    cert_dir: Any = DATA_PATH.joinpath("live", cert_name)
                    archive_dir: Any = DATA_PATH.joinpath("archive", 
                                                          cert_name)
                    cert_renewal_file: Any = DATA_PATH.joinpath("renewal", 
                                                          f"{cert_name}.conf")
                    path: Any
                    for path in (cert_dir, archive_dir):
                        if path.exists():
                            try:
                                for file in path.glob("*"):
                                    try:
                                        file.unlink()
                                    except Exception as e:
                                        LOGGER.error(
                                            f"Failed to remove file "
                                            f"{file}: {e}"
                                        )
                                path.rmdir()
                                LOGGER.info(f"Removed directory {path}")
                            except Exception as e:
                                LOGGER.error(f"Failed to remove directory "
                                             f"{path}: {e}")
                        if cert_renewal_file.exists():
                            try:
                                cert_renewal_file.unlink()
                                LOGGER.info(f"Removed renewal file "
                                            f"{cert_renewal_file}")
                            except Exception as e:
                                LOGGER.error(
                                    f"Failed to remove renewal file "
                                    f"{cert_renewal_file}: {e}"
                                )
                else:
                    LOGGER.error(
                        f"Failed to delete certificate {cert_name}: "
                        f"{delete_proc.stdout}"
                    )
            
            debug_log(LOGGER, f"Certificate cleanup completed - removed "
                              f"{certificates_removed} certificates")
        else:
            LOGGER.error(f"Error listing certificates: {proc.stdout}")

    # Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        debug_log(LOGGER, "Saving certificate data to database cache")
        
        cached_final: Any
        err_final: Any
        cached_final, err_final = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached_final:
            LOGGER.error(f"Error while saving data to db cache: {err_final}")
        else:
            LOGGER.info("Successfully saved data to db cache")
            debug_log(LOGGER, "Database cache update completed")
    else:
        debug_log(LOGGER, "No certificate data to cache")
            
except SystemExit as e:
    exit_code: int = cast(int, e.code)
    status = exit_code
    debug_log(LOGGER, f"Script exiting via SystemExit with code: {exit_code}")
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-new.py:\n{e}")
    debug_log(LOGGER, "Script failed with unexpected exception")

debug_log(LOGGER, f"Certificate generation process completed with status: "
                  f"{status}")

sys_exit(status)