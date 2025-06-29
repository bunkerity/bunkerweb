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
from typing import Dict, Literal, Optional, Type, Union

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
CERTBOT_BIN = join(sep, "usr", "share", "bunkerweb", "deps", "python", 
                  "bin", "certbot")
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
PSL_STATIC_FILE = Path("public_suffix_list.dat")

# ZeroSSL Configuration
ZEROSSL_ACME_SERVER = "https://acme.zerossl.com/v2/DV90"
ZEROSSL_STAGING_SERVER = "https://acme.zerossl.com/v2/DV90"
LETSENCRYPT_ACME_SERVER = "https://acme-v02.api.letsencrypt.org/directory"
LETSENCRYPT_STAGING_SERVER = (
    "https://acme-staging-v02.api.letsencrypt.org/directory"
)


def load_public_suffix_list(job):
    # Load and cache the public suffix list for domain validation.
    # Fetches the PSL from the official source and caches it locally.
    # Returns cached version if available and fresh (less than 1 day old).
    # 
    # Args:
    #     job: Job instance for caching operations
    # 
    # Returns:
    #     list: Lines from the public suffix list file
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Loading public suffix list from cache or {PSL_URL}")
        LOGGER.debug("Checking if cached PSL is available and fresh")
    
    job_cache = job.get_cache(PSL_STATIC_FILE.name, with_info=True, 
                             with_data=True)
    if (
        isinstance(job_cache, dict)
        and job_cache.get("last_update")
        and job_cache["last_update"] < (
            datetime.now().astimezone() - timedelta(days=1)
        ).timestamp()
    ):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Using cached public suffix list")
            cache_age_hours = ((datetime.now().astimezone().timestamp() - 
                               job_cache['last_update']) / 3600)
            LOGGER.debug(f"Cache age: {cache_age_hours:.1f} hours")
        return job_cache["data"].decode("utf-8").splitlines()

    try:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Downloading fresh PSL from {PSL_URL}")
            LOGGER.debug("Cached PSL is missing or older than 1 day")
        
        resp = get(PSL_URL, timeout=5)
        resp.raise_for_status()
        content = resp.text
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Downloaded PSL successfully, {len(content)} bytes")
            LOGGER.debug(f"PSL contains {len(content.splitlines())} lines")
        
        cached, err = JOB.cache_file(PSL_STATIC_FILE.name, 
                                    content.encode("utf-8"))
        if not cached:
            LOGGER.error(f"Error while saving public suffix list to cache: "
                        f"{err}")
        else:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("PSL successfully cached for future use")
        
        return content.splitlines()
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error while downloading public suffix list: {e}")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Download failed, checking for existing static file")
        
        if PSL_STATIC_FILE.exists():
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Using existing static PSL file: "
                           f"{PSL_STATIC_FILE}")
            with PSL_STATIC_FILE.open("r", encoding="utf-8") as f:
                return f.read().splitlines()
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("No PSL data available - returning empty list")
        return []


def parse_psl(psl_lines):
    # Parse PSL lines into rules and exceptions sets.
    # Processes the public suffix list format, handling comments,
    # exceptions (lines starting with !), and regular rules.
    # 
    # Args:
    #     psl_lines: List of lines from the PSL file
    # 
    # Returns:
    #     dict: Contains 'rules' and 'exceptions' sets
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Parsing {len(psl_lines)} PSL lines")
        LOGGER.debug("Processing rules, exceptions, and filtering comments")
    
    rules = set()
    exceptions = set()
    comments_skipped = 0
    empty_lines_skipped = 0
    
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
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Parsed {len(rules)} rules and {len(exceptions)} "
                    f"exceptions")
        LOGGER.debug(f"Skipped {comments_skipped} comments and "
                    f"{empty_lines_skipped} empty lines")
        LOGGER.debug("PSL parsing completed successfully")
    
    return {"rules": rules, "exceptions": exceptions}


def is_domain_blacklisted(domain, psl):
    # Check if domain is forbidden by PSL rules.
    # Validates whether a domain would be blacklisted according to the
    # Public Suffix List rules and exceptions.
    # 
    # Args:
    #     domain: Domain name to check
    #     psl: Parsed PSL data (dict with 'rules' and 'exceptions')
    # 
    # Returns:
    #     bool: True if domain is blacklisted
    domain = domain.lower().strip(".")
    labels = domain.split(".")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Checking domain {domain} against PSL rules")
        LOGGER.debug(f"Domain has {len(labels)} labels: {labels}")
        LOGGER.debug(f"PSL contains {len(psl['rules'])} rules and "
                    f"{len(psl['exceptions'])} exceptions")
    
    for i in range(len(labels)):
        candidate = ".".join(str(label) for label in labels[i:])
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Checking candidate: {candidate}")
        
        if candidate in psl["exceptions"]:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Domain {domain} allowed by PSL exception "
                           f"{candidate}")
            return False
        
        if candidate in psl["rules"]:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Found PSL rule match: {candidate}")
                LOGGER.debug(f"Checking blacklist conditions for i={i}")
            
            if i == 0:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Domain {domain} blacklisted - exact PSL "
                               f"rule match")
                return True
            if i == 0 and domain.startswith("*."):
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Wildcard domain {domain} blacklisted - "
                               f"exact PSL rule match")
                return True
            if i == 0 or (i == 1 and labels[0] == "*"):
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Domain {domain} blacklisted - PSL rule "
                               f"violation")
                return True
            if len(labels[i:]) == len(labels):
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Domain {domain} blacklisted - full label "
                               f"match")
                return True
        
        wildcard_candidate = f"*.{candidate}"
        if wildcard_candidate in psl["rules"]:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Found PSL wildcard rule match: "
                           f"{wildcard_candidate}")
            
            if len(labels[i:]) == 2:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Domain {domain} blacklisted - wildcard "
                               f"PSL rule match")
                return True
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Domain {domain} not blacklisted by PSL")
    return False


def get_certificate_authority_config(ca_provider, staging=False):
    # Get ACME server configuration for the specified CA provider.
    # Returns the appropriate ACME server URL and name for the given
    # certificate authority and environment (staging/production).
    # 
    # Args:
    #     ca_provider: Certificate authority name ('zerossl' or 'letsencrypt')
    #     staging: Whether to use staging environment
    # 
    # Returns:
    #     dict: Server URL and CA name
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Getting CA config for {ca_provider}, "
                    f"staging={staging}")
    
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
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"CA config: {config}")
    
    return config


def setup_zerossl_eab_credentials(email, api_key=None):
    # Setup External Account Binding (EAB) credentials for ZeroSSL.
    # Contacts the ZeroSSL API to obtain EAB credentials required for
    # ACME certificate issuance with ZeroSSL.
    # 
    # Args:
    #     email: Email address for the account
    #     api_key: ZeroSSL API key
    # 
    # Returns:
    #     tuple: (eab_kid, eab_hmac_key) or (None, None) on failure
    LOGGER.info(f"Setting up ZeroSSL EAB credentials for email: {email}")
    
    if not api_key:
        LOGGER.error("❌ ZeroSSL API key not provided")
        LOGGER.warning(
            "ZeroSSL API key not provided, attempting registration with email"
        )
        return None, None
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Making request to ZeroSSL API for EAB credentials")
        LOGGER.debug(f"Email: {email}")
        LOGGER.debug(f"API key provided: {bool(api_key)}")
    
    LOGGER.info("Making request to ZeroSSL API for EAB credentials")
    
    # Try the correct ZeroSSL API endpoint
    try:
        # The correct endpoint for ZeroSSL EAB credentials
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Attempting primary ZeroSSL EAB endpoint")
        
        response = get(
            "https://api.zerossl.com/acme/eab-credentials",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30
        )
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"ZeroSSL API response status: "
                        f"{response.status_code}")
            LOGGER.debug(f"Response headers: {dict(response.headers)}")
        LOGGER.info(f"ZeroSSL API response status: {response.status_code}")
        
        if response.status_code == 200:
            response.raise_for_status()
            eab_data = response.json()
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"ZeroSSL API response data: {eab_data}")
            LOGGER.info(f"ZeroSSL API response data: {eab_data}")
            
            # ZeroSSL typically returns eab_kid and eab_hmac_key directly
            if "eab_kid" in eab_data and "eab_hmac_key" in eab_data:
                eab_kid = eab_data.get("eab_kid")
                eab_hmac_key = eab_data.get("eab_hmac_key")
                LOGGER.info(f"✓ Successfully obtained EAB credentials from "
                          f"ZeroSSL")
                kid_display = f"{eab_kid[:10]}..." if eab_kid else "None"
                hmac_display = (f"{eab_hmac_key[:10]}..." if eab_hmac_key 
                              else "None")
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
            response_text = response.text
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Primary endpoint response: {response_text}")
            LOGGER.info(f"Primary endpoint response: {response_text}")
            
            # Try alternative endpoint with email parameter
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Attempting alternative ZeroSSL EAB endpoint")
            
            response = get(
                "https://api.zerossl.com/acme/eab-credentials-email",
                params={"email": email},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30
            )
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                alt_status = response.status_code
                LOGGER.debug(f"Alternative ZeroSSL API response status: "
                           f"{alt_status}")
            LOGGER.info(f"Alternative ZeroSSL API response status: "
                       f"{response.status_code}")
            response.raise_for_status()
            eab_data = response.json()
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Alternative ZeroSSL API response data: "
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
                LOGGER.error(f"❌ ZeroSSL EAB registration failed: {eab_data}")
                return None, None
            
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"❌ Error setting up ZeroSSL EAB credentials: {e}")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("ZeroSSL EAB setup failed with exception")
        
        # Additional troubleshooting info
        LOGGER.error("Troubleshooting steps:")
        LOGGER.error("1. Verify your ZeroSSL API key is valid")
        LOGGER.error("2. Check your ZeroSSL account has ACME access enabled")
        LOGGER.error("3. Ensure the API key has the correct permissions")
        LOGGER.error("4. Try regenerating your ZeroSSL API key")
        
        return None, None


def get_caa_records(domain):
    # Get CAA records for a domain using dig command.
    # Queries DNS CAA records to check certificate authority authorization.
    # Returns None if dig command is not available.
    # 
    # Args:
    #     domain: Domain name to query
    # 
    # Returns:
    #     list or None: List of CAA record dicts or None if unavailable
    
    # Check if dig command is available
    if not which("dig"):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("dig command not available for CAA record checking")
        LOGGER.info("dig command not available for CAA record checking")
        return None
    
    try:
        # Use dig to query CAA records
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Querying CAA records for domain: {domain}")
            LOGGER.debug("Using dig command with +short flag")
        LOGGER.info(f"Querying CAA records for domain: {domain}")
        
        result = run(
            ["dig", "+short", domain, "CAA"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"dig command return code: {result.returncode}")
            LOGGER.debug(f"dig stdout: {result.stdout}")
            LOGGER.debug(f"dig stderr: {result.stderr}")
        
        if result.returncode == 0 and result.stdout.strip():
            LOGGER.info(f"Found CAA records for domain {domain}")
            caa_records = []
            raw_lines = result.stdout.strip().split('\n')
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Processing {len(raw_lines)} CAA record lines")
            
            for line in raw_lines:
                line = line.strip()
                if line:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Parsing CAA record line: {line}")
                    
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
                        
                        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                            LOGGER.debug(f"Parsed CAA record: flags={flags}, "
                                       f"tag={tag}, value={value}")
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                record_count = len(caa_records)
                LOGGER.debug(f"Successfully parsed {record_count} CAA records "
                           f"for domain {domain}")
            LOGGER.info(f"Parsed {len(caa_records)} CAA records for domain "
                       f"{domain}")
            return caa_records
        else:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(
                    f"No CAA records found for domain {domain} "
                    f"(dig return code: {result.returncode})"
                )
            LOGGER.info(
                f"No CAA records found for domain {domain} "
                f"(dig return code: {result.returncode})"
            )
            return []
            
    except BaseException as e:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Error querying CAA records for {domain}: {e}")
        LOGGER.info(f"Error querying CAA records for {domain}: {e}")
        return None


def check_caa_authorization(domain, ca_provider, is_wildcard=False):
    # Check if the CA provider is authorized by CAA records.
    # Validates whether the certificate authority is permitted to issue
    # certificates for the domain according to CAA DNS records.
    # 
    # Args:
    #     domain: Domain name to check
    #     ca_provider: Certificate authority provider name
    #     is_wildcard: Whether this is for a wildcard certificate
    # 
    # Returns:
    #     bool: True if CA is authorized or no CAA restrictions exist
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(
            f"Checking CAA authorization for domain: {domain}, "
            f"CA: {ca_provider}, wildcard: {is_wildcard}"
        )
    
    LOGGER.info(
        f"Checking CAA authorization for domain: {domain}, "
        f"CA: {ca_provider}, wildcard: {is_wildcard}"
    )
    
    # Map CA providers to their CAA identifiers
    ca_identifiers = {
        "letsencrypt": ["letsencrypt.org"],
        "zerossl": ["sectigo.com", "zerossl.com"]  # ZeroSSL uses Sectigo
    }
    
    allowed_identifiers = ca_identifiers.get(ca_provider.lower(), [])
    if not allowed_identifiers:
        LOGGER.warning(f"Unknown CA provider for CAA check: {ca_provider}")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Returning True for unknown CA provider "
                        "(conservative approach)")
        return True  # Allow unknown providers (conservative approach)
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"CA identifiers for {ca_provider}: "
                    f"{allowed_identifiers}")
    
    # Check CAA records for the domain and parent domains
    check_domain = domain.lstrip("*.")
    domain_parts = check_domain.split(".")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Will check CAA records for domain chain: "
                    f"{check_domain}")
        LOGGER.debug(f"Domain parts: {domain_parts}")
    LOGGER.info(f"Will check CAA records for domain chain: {check_domain}")
    
    for i in range(len(domain_parts)):
        current_domain = ".".join(str(part) for part in domain_parts[i:])
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Checking CAA records for: {current_domain}")
        LOGGER.info(f"Checking CAA records for: {current_domain}")
        caa_records = get_caa_records(current_domain)
        
        if caa_records is None:
            # dig not available, skip CAA check
            LOGGER.info("CAA record checking skipped (dig command not "
                       "available)")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Returning True due to unavailable dig command")
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
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"CAA issue records: "
                               f"{', '.join(str(record) for record in issue_records)}")
                LOGGER.info(f"CAA issue records: "
                           f"{', '.join(str(record) for record in issue_records)}")
            if issuewild_records:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"CAA issuewild records: "
                               f"{', '.join(str(record) for record in issuewild_records)}")
                LOGGER.info(f"CAA issuewild records: "
                           f"{', '.join(str(record) for record in issuewild_records)}")
            
            # Check authorization based on certificate type
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
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Using CAA {record_type} records for "
                           f"authorization check")
                LOGGER.debug(f"Records to check: {check_records}")
            LOGGER.info(f"Using CAA {record_type} records for authorization "
                       f"check")
            
            if not check_records:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(
                        f"No relevant CAA {record_type} records found for "
                        f"{current_domain}"
                    )
                LOGGER.info(
                    f"No relevant CAA {record_type} records found for "
                    f"{current_domain}"
                )
                continue
            
            # Check if any of our CA identifiers are authorized
            authorized = False
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                identifier_list = ', '.join(str(id) for id in allowed_identifiers)
                LOGGER.debug(
                    f"Checking authorization for CA identifiers: "
                    f"{identifier_list}"
                )
            identifier_list = ', '.join(str(id) for id in allowed_identifiers)
            LOGGER.info(
                f"Checking authorization for CA identifiers: "
                f"{identifier_list}"
            )
            for identifier in allowed_identifiers:
                for record in check_records:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Comparing identifier '{identifier}' "
                                   f"with record '{record}'")
                    
                    # Handle explicit deny (empty value or semicolon)
                    if record == ";" or record.strip() == "":
                        LOGGER.warning(
                            f"CAA {record_type} record explicitly denies "
                            f"all CAs"
                        )
                        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                            LOGGER.debug("Found explicit deny record - "
                                       "authorization failed")
                        return False
                    
                    # Check for CA authorization
                    if identifier in record:
                        authorized = True
                        LOGGER.info(
                            f"✓ CA {ca_provider} ({identifier}) authorized "
                            f"by CAA {record_type} record"
                        )
                        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                            LOGGER.debug(f"Authorization found: {identifier} "
                                       f"in {record}")
                        break
                if authorized:
                    break
            
            if not authorized:
                LOGGER.error(
                    f"❌ CA {ca_provider} is NOT authorized by "
                    f"CAA {record_type} records"
                )
                allowed_list = ', '.join(str(record) for record in check_records)
                identifier_list = ', '.join(str(id) for id in allowed_identifiers)
                LOGGER.error(
                    f"Domain {current_domain} CAA {record_type} allows: "
                    f"{allowed_list}"
                )
                LOGGER.error(
                    f"But {ca_provider} uses: {identifier_list}"
                )
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug("CAA authorization failed - no matching "
                               "identifiers")
                return False
            
            # If we found CAA records and we're authorized, we can stop 
            # checking parent domains
            LOGGER.info(f"✓ CAA authorization successful for {domain}")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("CAA authorization successful - stopping parent "
                           "domain checks")
            return True
    
    # No CAA records found in the entire chain
    LOGGER.info(
        f"No CAA records found for {check_domain} or parent domains - "
        f"any CA allowed"
    )
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("No CAA records found in entire domain chain - "
                    "allowing any CA")
    return True


def validate_domains_for_http_challenge(domains_list, 
                                       ca_provider="letsencrypt", 
                                       is_wildcard=False):
    # Validate that all domains have valid A/AAAA records and CAA authorization 
    # for HTTP challenge.
    # Checks DNS resolution and certificate authority authorization for each
    # domain in the list to ensure HTTP challenge will succeed.
    # 
    # Args:
    #     domains_list: List of domain names to validate
    #     ca_provider: Certificate authority provider name
    #     is_wildcard: Whether this is for wildcard certificates
    # 
    # Returns:
    #     bool: True if all domains are valid for HTTP challenge
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        domain_count = len(domains_list)
        domain_list = ', '.join(str(domain) for domain in domains_list)
        LOGGER.debug(
            f"Validating {domain_count} domains for HTTP challenge: "
            f"{domain_list}"
        )
        LOGGER.debug(f"CA provider: {ca_provider}, wildcard: {is_wildcard}")
    domain_list = ', '.join(str(domain) for domain in domains_list)
    LOGGER.info(
        f"Validating {len(domains_list)} domains for HTTP challenge: "
        f"{domain_list}"
    )
    invalid_domains = []
    caa_blocked_domains = []
    
    # Check if CAA validation should be skipped
    skip_caa_check = getenv("ACME_SKIP_CAA_CHECK", "no") == "yes"
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        caa_status = 'skipped' if skip_caa_check else 'performed'
        LOGGER.debug(f"CAA check will be {caa_status}")
    
    # Get external IPs once for all domain checks
    external_ips = get_external_ip()
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
    
    validation_passed = 0
    validation_failed = 0
    
    for domain in domains_list:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Validating domain: {domain}")
        
        # Check DNS A/AAAA records with retry mechanism
        if not check_domain_a_record(domain, external_ips):
            invalid_domains.append(domain)
            validation_failed += 1
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"DNS validation failed for {domain}")
            continue
        
        # Check CAA authorization
        if not skip_caa_check:
            if not check_caa_authorization(domain, ca_provider, is_wildcard):
                caa_blocked_domains.append(domain)
                validation_failed += 1
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"CAA authorization failed for {domain}")
        else:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"CAA check skipped for {domain} "
                           f"(ACME_SKIP_CAA_CHECK=yes)")
            LOGGER.info(f"CAA check skipped for {domain} "
                       f"(ACME_SKIP_CAA_CHECK=yes)")
        
        validation_passed += 1
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Validation passed for {domain}")
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Validation summary: {validation_passed} passed, "
                    f"{validation_failed} failed")
    
    # Report results
    if invalid_domains:
        invalid_list = ', '.join(str(domain) for domain in invalid_domains)
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
        blocked_list = ', '.join(str(domain) for domain in caa_blocked_domains)
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
    
    valid_list = ', '.join(str(domain) for domain in domains_list)
    LOGGER.info(
        f"All domains have valid DNS records and CAA authorization for "
        f"HTTP challenge: {valid_list}"
    )
    return True


def get_external_ip():
    # Get the external/public IP addresses of this server (both IPv4 and IPv6).
    # Queries multiple external services to determine the server's public
    # IP addresses for DNS validation purposes.
    # 
    # Returns:
    #     dict or None: Dict with 'ipv4' and 'ipv6' keys, or None if all fail
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Getting external IP addresses for server")
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
    
    external_ips: Dict[str, Optional[str]] = {"ipv4": None, "ipv6": None}
    
    # Try to get IPv4 address
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Attempting to get external IPv4 address")
        LOGGER.debug(f"Trying {len(ipv4_services)} IPv4 services")
    LOGGER.info("Attempting to get external IPv4 address")
    
    for i, service in enumerate(ipv4_services):
        try:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                service_num = f"{i+1}/{len(ipv4_services)}"
                LOGGER.debug(f"Trying IPv4 service {service_num}: {service}")
            
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
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Service returned: {ip}")
            
            # Basic IPv4 validation
            if ip and "." in ip and len(ip.split(".")) == 4:
                try:
                    # Validate it's a proper IPv4 address
                    getaddrinfo(ip, None, AF_INET)
                    # Type-safe assignment
                    ipv4_addr: str = str(ip)
                    external_ips["ipv4"] = ipv4_addr
                    
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Successfully obtained external IPv4 "
                                   f"address: {ipv4_addr}")
                    LOGGER.info(f"Successfully obtained external IPv4 "
                               f"address: {ipv4_addr}")
                    break
                except gaierror:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Invalid IPv4 address returned: {ip}")
                    continue
        except BaseException as e:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Failed to get IPv4 address from {service}: "
                           f"{e}")
            LOGGER.info(f"Failed to get IPv4 address from {service}: {e}")
            continue
    
    # Try to get IPv6 address
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Attempting to get external IPv6 address")
        LOGGER.debug(f"Trying {len(ipv6_services)} IPv6 services")
    LOGGER.info("Attempting to get external IPv6 address")
    
    for i, service in enumerate(ipv6_services):
        try:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                service_num = f"{i+1}/{len(ipv6_services)}"
                LOGGER.debug(f"Trying IPv6 service {service_num}: {service}")
            
            if "jsonip.com" in service:
                response = get(service, timeout=5)
                response.raise_for_status()
                data = response.json()
                ip = data.get("ip", "").strip()
            else:
                response = get(service, timeout=5)
                response.raise_for_status()
                ip = response.text.strip()
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Service returned: {ip}")
            
            # Basic IPv6 validation
            if ip and ":" in ip:
                try:
                    # Validate it's a proper IPv6 address
                    getaddrinfo(ip, None, AF_INET6)
                    # Type-safe assignment
                    ipv6_addr: str = str(ip)
                    external_ips["ipv6"] = ipv6_addr
                    
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Successfully obtained external IPv6 "
                                   f"address: {ipv6_addr}")
                    LOGGER.info(f"Successfully obtained external IPv6 "
                               f"address: {ipv6_addr}")
                    break
                except gaierror:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Invalid IPv6 address returned: {ip}")
                    continue
        except BaseException as e:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Failed to get IPv6 address from {service}: "
                           f"{e}")
            LOGGER.info(f"Failed to get IPv6 address from {service}: {e}")
            continue
    
    if not external_ips["ipv4"] and not external_ips["ipv6"]:
        LOGGER.warning(
            "Could not determine external IP address (IPv4 or IPv6) from "
            "any service"
        )
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("All external IP services failed")
        return None
    
    ipv4_status = external_ips['ipv4'] or 'not found'
    ipv6_status = external_ips['ipv6'] or 'not found'
    LOGGER.info(
        f"External IP detection completed - "
        f"IPv4: {ipv4_status}, IPv6: {ipv6_status}"
    )
    return external_ips


def check_domain_a_record(domain, external_ips=None):
    # Check if domain has valid A/AAAA records for HTTP challenge.
    # Validates DNS resolution and optionally checks if the domain's
    # IP addresses match the server's external IPs.
    # 
    # Args:
    #     domain: Domain name to check
    #     external_ips: Dict with server's external IPv4/IPv6 addresses
    # 
    # Returns:
    #     bool: True if domain has valid DNS records
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Checking DNS A/AAAA records for domain: {domain}")
    LOGGER.info(f"Checking DNS A/AAAA records for domain: {domain}")
    try:
        # Remove wildcard prefix if present
        check_domain = domain.lstrip("*.")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Checking domain after wildcard removal: "
                        f"{check_domain}")
        
        # Attempt to resolve the domain to IP addresses
        result = getaddrinfo(check_domain, None)
        if result:
            ipv4_addresses = [addr[4][0] for addr in result 
                            if addr[0] == AF_INET]
            ipv6_addresses = [addr[4][0] for addr in result 
                            if addr[0] == AF_INET6]
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"DNS resolution results:")
                LOGGER.debug(f"  IPv4 addresses: {ipv4_addresses}")
                LOGGER.debug(f"  IPv6 addresses: {ipv6_addresses}")
            
            if not ipv4_addresses and not ipv6_addresses:
                LOGGER.warning(f"Domain {check_domain} has no A or AAAA "
                             f"records")
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug("No valid IP addresses found in DNS "
                               "resolution")
                return False
            
            # Log found addresses
            if ipv4_addresses:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    ipv4_display = ', '.join(str(addr) for addr in ipv4_addresses[:3])
                    LOGGER.debug(
                        f"Domain {check_domain} IPv4 A records: "
                        f"{ipv4_display}"
                    )
                ipv4_display = ', '.join(str(addr) for addr in ipv4_addresses[:3])
                LOGGER.info(
                    f"Domain {check_domain} IPv4 A records: {ipv4_display}"
                )
            if ipv6_addresses:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    ipv6_display = ', '.join(str(addr) for addr in ipv6_addresses[:3])
                    LOGGER.debug(
                        f"Domain {check_domain} IPv6 AAAA records: "
                        f"{ipv6_display}"
                    )
                ipv6_display = ', '.join(str(addr) for addr in ipv6_addresses[:3])
                LOGGER.info(
                    f"Domain {check_domain} IPv6 AAAA records: "
                    f"{ipv6_display}"
                )
            
            # Check if any record matches the external IPs
            if external_ips:
                ipv4_match = False
                ipv6_match = False
                
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug("Checking IP address matches with server "
                               "external IPs")
                
                # Check IPv4 match
                if external_ips.get("ipv4") and ipv4_addresses:
                    if external_ips["ipv4"] in ipv4_addresses:
                        external_ipv4 = external_ips['ipv4']
                        LOGGER.info(
                            f"✓ Domain {check_domain} IPv4 A record matches "
                            f"server external IP ({external_ipv4})"
                        )
                        ipv4_match = True
                    else:
                        LOGGER.warning(
                            f"⚠ Domain {check_domain} IPv4 A record does not "
                            "match server external IP"
                        )
                        ipv4_list = ', '.join(str(addr) for addr in ipv4_addresses)
                        LOGGER.warning(f"  Domain IPv4: {ipv4_list}")
                        LOGGER.warning(f"  Server IPv4: "
                                     f"{external_ips['ipv4']}")
                
                # Check IPv6 match
                if external_ips.get("ipv6") and ipv6_addresses:
                    if external_ips["ipv6"] in ipv6_addresses:
                        external_ipv6 = external_ips['ipv6']
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
                        ipv6_list = ', '.join(str(addr) for addr in ipv6_addresses)
                        LOGGER.warning(f"  Domain IPv6: {ipv6_list}")
                        LOGGER.warning(f"  Server IPv6: "
                                     f"{external_ips['ipv6']}")
                
                # Determine if we have any matching records
                has_any_match = ipv4_match or ipv6_match
                has_external_ip = (external_ips.get("ipv4") or 
                                 external_ips.get("ipv6"))
                
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"IP match results: IPv4={ipv4_match}, "
                               f"IPv6={ipv6_match}")
                    LOGGER.debug(f"Has external IP: {has_external_ip}, "
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
                    strict_ip_check = (getenv("ACME_HTTP_STRICT_IP_CHECK", 
                                             "no") == "yes")
                    if strict_ip_check:
                        LOGGER.error(
                            f"Strict IP check enabled - rejecting certificate "
                            f"request for {check_domain}"
                        )
                        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                            LOGGER.debug("Strict IP check failed - "
                                       "returning False")
                        return False
            
            LOGGER.info(f"✓ Domain {check_domain} DNS validation passed")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("DNS validation completed successfully")
            return True
        else:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(
                    f"Domain {check_domain} validation failed - no DNS "
                    f"resolution"
                )
            LOGGER.info(f"Domain {check_domain} validation failed - no DNS "
                       f"resolution")
            LOGGER.warning(f"Domain {check_domain} does not resolve")
            return False
            
    except gaierror as e:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Domain {check_domain} DNS resolution failed "
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
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("DNS check failed with unexpected exception")
        return False


def certbot_new_with_retry(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: Optional[str] = None,
    credentials_path: Optional[Union[str, Path]] = None,
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
    # 
    # Args:
    #     challenge_type: Type of ACME challenge ('dns' or 'http')
    #     domains: Comma-separated list of domain names
    #     email: Email address for certificate registration
    #     provider: DNS provider name (for DNS challenge)
    #     credentials_path: Path to credentials file
    #     propagation: DNS propagation time in seconds
    #     profile: Certificate profile to use
    #     staging: Whether to use staging environment
    #     force: Force renewal of existing certificates
    #     cmd_env: Environment variables for certbot process
    #     max_retries: Maximum number of retry attempts
    #     ca_provider: Certificate authority provider
    #     api_key: API key for CA (if required)
    #     server_name: Server name for multisite configurations
    # 
    # Returns:
    #     int: Exit code (0 for success)
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Starting certbot with retry for domains: {domains}")
        LOGGER.debug(f"Max retries: {max_retries}, CA: {ca_provider}")
        LOGGER.debug(f"Challenge: {challenge_type}, Provider: {provider}")
    
    attempt = 1
    while attempt <= max_retries + 1:
        if attempt > 1:
            LOGGER.warning(
                f"Certificate generation failed, retrying... "
                f"(attempt {attempt}/{max_retries + 1})"
            )
            wait_time = min(30 * (2 ** (attempt - 2)), 300)
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Waiting {wait_time} seconds before retry...")
                LOGGER.debug(f"Exponential backoff: base=30s, "
                           f"attempt={attempt}")
            LOGGER.info(f"Waiting {wait_time} seconds before retry...")
            sleep(wait_time)

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Executing certbot attempt {attempt}")

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
            cmd_env or {},
            ca_provider,
            api_key,
            server_name,
        )

        if result == 0:
            if attempt > 1:
                LOGGER.info(f"Certificate generation succeeded on attempt "
                          f"{attempt}")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Certbot completed successfully")
            return result

        if attempt >= max_retries + 1:
            LOGGER.error(f"Certificate generation failed after "
                        f"{max_retries + 1} attempts")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Maximum retries reached - giving up")
            return result

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Attempt {attempt} failed, will retry")
        attempt += 1

    return result


def certbot_new(
    challenge_type: Literal["dns", "http"],
    domains: str,
    email: str,
    provider: Optional[str] = None,
    credentials_path: Optional[Union[str, Path]] = None,
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
    # Main function to request SSL/TLS certificates from a certificate authority
    # using the ACME protocol via certbot.
    # 
    # Args:
    #     challenge_type: Type of ACME challenge ('dns' or 'http')
    #     domains: Comma-separated list of domain names
    #     email: Email address for certificate registration
    #     provider: DNS provider name (for DNS challenge)
    #     credentials_path: Path to credentials file
    #     propagation: DNS propagation time in seconds
    #     profile: Certificate profile to use
    #     staging: Whether to use staging environment
    #     force: Force renewal of existing certificates
    #     cmd_env: Environment variables for certbot process
    #     ca_provider: Certificate authority provider
    #     api_key: API key for CA (if required)
    #     server_name: Server name for multisite configurations
    # 
    # Returns:
    #     int: Exit code (0 for success)
    if isinstance(credentials_path, str):
        credentials_path = Path(credentials_path)

    ca_config = get_certificate_authority_config(ca_provider, staging)
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Building certbot command for {domains}")
        LOGGER.debug(f"CA config: {ca_config}")
        LOGGER.debug(f"Challenge type: {challenge_type}")
        LOGGER.debug(f"Profile: {profile}")
    
    command = [
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
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Using RSA-4096 for {provider} provider with "
                        f"{domains}")
        LOGGER.info(f"Using RSA-4096 for {provider} provider with {domains}")
    else:
        # Use elliptic curve certificates for all other providers
        if ca_provider.lower() == "zerossl":
            # Use P-384 elliptic curve for ZeroSSL certificates
            command.extend(["--elliptic-curve", "secp384r1"])
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Using ZeroSSL P-384 curve for {domains}")
            LOGGER.info(f"Using ZeroSSL P-384 curve for {domains}")
        else:
            # Use P-256 elliptic curve for Let's Encrypt certificates
            command.extend(["--elliptic-curve", "secp256r1"])
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Using Let's Encrypt P-256 curve for {domains}")
            LOGGER.info(f"Using Let's Encrypt P-256 curve for {domains}")
    
    # Handle ZeroSSL EAB credentials
    if ca_provider.lower() == "zerossl":
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"ZeroSSL detected as CA provider for {domains}")
        LOGGER.info(f"ZeroSSL detected as CA provider for {domains}")
        
        # Check for manually provided EAB credentials first
        eab_kid_env = (getenv("ACME_ZEROSSL_EAB_KID", "") or 
                       (getenv(f"{server_name}_ACME_ZEROSSL_EAB_KID", "") 
                        if server_name else ""))
        eab_hmac_env = (getenv("ACME_ZEROSSL_EAB_HMAC_KEY", "") or 
                        (getenv(f"{server_name}_ACME_ZEROSSL_EAB_HMAC_KEY", "") 
                         if server_name else ""))
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Manual EAB credentials check:")
            LOGGER.debug(f"  EAB KID provided: {bool(eab_kid_env)}")
            LOGGER.debug(f"  EAB HMAC provided: {bool(eab_hmac_env)}")
        
        if eab_kid_env and eab_hmac_env:
            LOGGER.info("✓ Using manually provided ZeroSSL EAB credentials "
                       "from environment")
            command.extend(["--eab-kid", eab_kid_env, "--eab-hmac-key", 
                          eab_hmac_env])
            LOGGER.info(f"✓ Using ZeroSSL EAB credentials for {domains}")
            LOGGER.info(f"EAB Kid: {eab_kid_env[:10]}...")
        elif api_key:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"ZeroSSL API key provided, setting up EAB "
                           f"credentials")
            LOGGER.info(f"ZeroSSL API key provided, setting up EAB "
                       f"credentials")
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

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"DNS challenge configuration:")
            LOGGER.debug(f"  Provider: {provider}")
            LOGGER.debug(f"  Propagation: {propagation}")
            LOGGER.debug(f"  Credentials path: {credentials_path}")

        if propagation != "default":
            if not propagation.isdigit():
                LOGGER.warning(
                    f"Invalid propagation time: {propagation}, "
                    "using provider's default..."
                )
            else:
                command.extend([f"--dns-{provider}-propagation-seconds", 
                              propagation])
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Set DNS propagation time to "
                               f"{propagation} seconds")

        if provider == "route53":
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Route53 provider - setting environment "
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

        if provider in ("desec", "infomaniak", "ionos", "njalla", "scaleway"):
            command.extend(["--authenticator", f"dns-{provider}"])
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Using explicit authenticator for {provider}")
        else:
            command.append(f"--dns-{provider}")

    elif challenge_type == "http":
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            auth_hook = JOBS_PATH.joinpath('certbot-auth.py')
            cleanup_hook = JOBS_PATH.joinpath('certbot-cleanup.py')
            LOGGER.debug("HTTP challenge configuration:")
            LOGGER.debug(f"  Auth hook: {auth_hook}")
            LOGGER.debug(f"  Cleanup hook: {cleanup_hook}")
        
        command.extend(
            [
                "--manual",
                "--preferred-challenges=http",
                "--manual-auth-hook",
                str(JOBS_PATH.joinpath("certbot-auth.py")),
                "--manual-cleanup-hook",
                str(JOBS_PATH.joinpath("certbot-cleanup.py")),
            ]
        )

    if force:
        command.append("--force-renewal")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Force renewal enabled")

    if getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper() == "DEBUG":
        command.append("-v")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Verbose mode enabled for certbot")

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
    
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Command: {' '.join(safe_command)}")
        LOGGER.debug(f"Environment variables: {len(working_env)} items")
        for key in working_env.keys():
            is_sensitive = any(sensitive in key.lower() 
                             for sensitive in ['key', 'secret', 'token'])
            value_display = '***MASKED***' if is_sensitive else 'set'
            LOGGER.debug(f"  {key}: {value_display}")
    LOGGER.info(f"Command: {' '.join(safe_command)}")
    
    current_date = datetime.now()
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Starting certbot process")
    
    process = Popen(command, stdin=DEVNULL, stderr=PIPE, 
                   universal_newlines=True, env=working_env)

    lines_processed = 0
    while process.poll() is None:
        if process.stderr:
            rlist, _, _ = select([process.stderr], [], [], 2)
            if rlist:
                for line in process.stderr:
                    LOGGER_CERTBOT.info(line.strip())
                    lines_processed += 1
                    break

        if datetime.now() - current_date > timedelta(seconds=5):
            challenge_info = (
                " (this may take a while depending on the provider)" 
                if challenge_type == "dns" else ""
            )
            LOGGER.info(
                f"⏳ Still generating {ca_config['name']} certificate(s)"
                f"{challenge_info}..."
            )
            current_date = datetime.now()
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Certbot still running, processed "
                           f"{lines_processed} output lines")

    final_return_code = process.returncode
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Certbot process completed with return code: "
                    f"{final_return_code}")
        LOGGER.debug(f"Total output lines processed: {lines_processed}")

    return final_return_code


# Global configuration and setup
IS_MULTISITE = getenv("MULTISITE", "no") == "yes"

try:
    # Main execution block for certificate generation
    servers = getenv("SERVER_NAME", "www.example.com").lower() or []

    if isinstance(servers, str):
        servers = servers.split(" ")

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Server configuration detected:")
        LOGGER.debug(f"  Multisite mode: {IS_MULTISITE}")
        LOGGER.debug(f"  Server count: {len(servers)}")
        LOGGER.debug(f"  Servers: {servers}")

    if not servers:
        LOGGER.warning("There are no server names, skipping generation...")
        sys_exit(0)

    use_letsencrypt = False
    use_letsencrypt_dns = False

    if not IS_MULTISITE:
        use_letsencrypt = getenv("AUTO_LETS_ENCRYPT", "no") == "yes"
        use_letsencrypt_dns = getenv("LETS_ENCRYPT_CHALLENGE", "http") == "dns"
        domains_server_names = {servers[0]: " ".join(servers).lower()}
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Single-site configuration:")
            LOGGER.debug(f"  Let's Encrypt enabled: {use_letsencrypt}")
            LOGGER.debug(f"  DNS challenge: {use_letsencrypt_dns}")
    else:
        domains_server_names = {}

        for first_server in servers:
            auto_le_env = f"{first_server}_AUTO_LETS_ENCRYPT"
            if (first_server and 
                getenv(auto_le_env, "no") == "yes"):
                use_letsencrypt = True

            challenge_env = f"{first_server}_LETS_ENCRYPT_CHALLENGE"
            if (first_server and 
                getenv(challenge_env, "http") == "dns"):
                use_letsencrypt_dns = True

            server_name_env = f"{first_server}_SERVER_NAME"
            domains_server_names[first_server] = getenv(
                server_name_env, first_server
            ).lower()
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Multi-site configuration:")
            LOGGER.debug(f"  Let's Encrypt enabled anywhere: "
                        f"{use_letsencrypt}")
            LOGGER.debug(f"  DNS challenge used anywhere: "
                        f"{use_letsencrypt_dns}")
            LOGGER.debug(f"  Domain mappings: {domains_server_names}")

    if not use_letsencrypt:
        LOGGER.info("Let's Encrypt is not activated, skipping generation...")
        sys_exit(0)

    provider_classes = {}

    if use_letsencrypt_dns:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("DNS challenge detected - loading provider classes")
        
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
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Restoring certificate data from database cache")
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
    database_uri = getenv("DATABASE_URI")
    if database_uri:  # Only assign if not None and not empty
        # Explicit assignment with type safety
        env_key: str = "DATABASE_URI"
        env_value: str = str(database_uri)
        env[env_key] = env_value

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Checking existing certificates")
    
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
    stdout = proc.stdout

    WILDCARD_GENERATOR = WildcardGenerator()
    credential_paths = set()
    generated_domains = set()
    domains_to_ask = {}
    active_cert_names = set()

    if proc.returncode != 0:
        LOGGER.error(f"Error while checking certificates:\n{proc.stdout}")
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Certificate listing failed - proceeding anyway")
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Certificate listing successful - analyzing "
                        "existing certificates")
        
        certificate_blocks = stdout.split("Certificate Name: ")[1:]
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Found {len(certificate_blocks)} existing "
                        f"certificates")
        
        for first_server, domains in domains_server_names.items():
            auto_le_check = (getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") 
                           if IS_MULTISITE 
                           else getenv("AUTO_LETS_ENCRYPT", "no"))
            if auto_le_check != "yes":
                continue

            challenge_check = (
                getenv(f"{first_server}_LETS_ENCRYPT_CHALLENGE", "http") 
                if IS_MULTISITE 
                else getenv("LETS_ENCRYPT_CHALLENGE", "http")
            )
            original_first_server = deepcopy(first_server)

            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Processing server: {first_server}")
                LOGGER.debug(f"  Challenge: {challenge_check}")
                LOGGER.debug(f"  Domains: {domains}")

            wildcard_check = (
                getenv(f"{original_first_server}_USE_LETS_ENCRYPT_WILDCARD", 
                      "no") 
                if IS_MULTISITE 
                else getenv("USE_LETS_ENCRYPT_WILDCARD", "no")
            )
            if (challenge_check == "dns" and wildcard_check == "yes"):
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Using wildcard mode for {first_server}")
                
                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains(
                    (first_server,)
                )
                first_server = wildcards[0].lstrip("*.")
                domains = set(wildcards)
            else:
                domains = set(str(domains).split(" "))

            # Add the certificate name to our active set regardless 
            # if we're generating it or not
            active_cert_names.add(first_server)

            certificate_block = None
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
                cert_domains = search(
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

            if not cert_domains:
                LOGGER.error(
                    f"[{original_first_server}] Failed to parse domains "
                    "and expiry date from certificate block."
                )
                continue

            cert_domains_list = cert_domains.group("domains").strip().split()
            cert_domains_set = set(cert_domains_list)
            desired_domains_set = (
                set(domains) if isinstance(domains, (list, set)) 
                else set(str(domains).split())
            )

            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Certificate domain comparison for "
                           f"{first_server}:")
                LOGGER.debug(f"  Existing: {sorted(str(d) for d in cert_domains_set)}")
                LOGGER.debug(f"  Desired: {sorted(str(d) for d in desired_domains_set)}")

            if cert_domains_set != desired_domains_set:
                domains_to_ask[first_server] = 2
                existing_sorted = sorted(str(d) for d in cert_domains_set)
                desired_sorted = sorted(str(d) for d in desired_domains_set)
                LOGGER.warning(
                    f"[{original_first_server}] Domains for {first_server} "
                    f"differ from desired set (existing: {existing_sorted}, "
                    f"desired: {desired_sorted}), asking new certificate..."
                )
                continue

            # Check if CA provider has changed
            ca_provider_env = (
                f"{original_first_server}_ACME_SSL_CA_PROVIDER" 
                if IS_MULTISITE 
                else "ACME_SSL_CA_PROVIDER"
            )
            ca_provider = getenv(ca_provider_env, "letsencrypt")
            
            renewal_file = DATA_PATH.joinpath("renewal", f"{first_server}.conf")
            if renewal_file.is_file():
                current_server = None
                with renewal_file.open("r") as file:
                    for line in file:
                        if line.startswith("server"):
                            current_server = line.strip().split("=", 1)[1].strip()
                            break
                
                staging_env = (
                    f"{original_first_server}_USE_LETS_ENCRYPT_STAGING" 
                    if IS_MULTISITE 
                    else "USE_LETS_ENCRYPT_STAGING"
                )
                staging_mode = getenv(staging_env, "no") == "yes"
                expected_config = get_certificate_authority_config(
                    ca_provider, staging_mode
                )
                
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"CA server comparison for {first_server}:")
                    LOGGER.debug(f"  Current: {current_server}")
                    LOGGER.debug(f"  Expected: {expected_config['server']}")
                
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
            use_staging = getenv(staging_env, "no") == "yes"
            is_test_cert = "TEST_CERT" in cert_domains.group("expiry_date")

            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Staging environment check for {first_server}:")
                LOGGER.debug(f"  Use staging: {use_staging}")
                LOGGER.debug(f"  Is test cert: {is_test_cert}")

            staging_mismatch = ((is_test_cert and not use_staging) or 
                              (not is_test_cert and use_staging))
            if staging_mismatch:
                domains_to_ask[first_server] = 2
                LOGGER.warning(
                    f"[{original_first_server}] Certificate environment "
                    f"(staging/production) changed for {first_server}, "
                    "asking new certificate..."
                )
                continue

            provider_env = (
                f"{original_first_server}_LETS_ENCRYPT_DNS_PROVIDER" 
                if IS_MULTISITE 
                else "LETS_ENCRYPT_DNS_PROVIDER"
            )
            provider = getenv(provider_env, "")

            if not renewal_file.is_file():
                LOGGER.error(
                    f"[{original_first_server}] Renewal file for "
                    f"{first_server} not found, asking new certificate..."
                )
                domains_to_ask[first_server] = 1
                continue

            current_provider = None
            with renewal_file.open("r") as file:
                for line in file:
                    if line.startswith("authenticator"):
                        key, value = line.strip().split("=", 1)
                        current_provider = value.strip().replace("dns-", "")
                        break

            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Provider comparison for {first_server}:")
                LOGGER.debug(f"  Current: {current_provider}")
                LOGGER.debug(f"  Configured: {provider}")

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
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug(f"Checking DNS credentials for "
                                   f"{first_server}")
                    
                    credential_key = (
                        f"{original_first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
                        if IS_MULTISITE 
                        else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
                    )
                    current_credential_items = {}

                    for env_key, env_value in environ.items():
                        if env_value and env_key.startswith(credential_key):
                            if " " not in env_value:
                                current_credential_items["json_data"] = env_value
                                continue
                            key, value = env_value.split(" ", 1)
                            cleaned_value = (
                                value.removeprefix("= ").replace("\\n", "\n")
                                     .replace("\\t", "\t").replace("\\r", "\r")
                                     .strip()
                            )
                            current_credential_items[key.lower()] = cleaned_value

                    if "json_data" in current_credential_items:
                        value = current_credential_items.pop("json_data")
                        is_base64_like = (not current_credential_items and 
                                        len(value) % 4 == 0 and 
                                        match(r"^[A-Za-z0-9+/=]+$", value))
                        if is_base64_like:
                            with suppress(BaseException):
                                decoded = b64decode(value).decode("utf-8")
                                json_data = loads(decoded)
                                if isinstance(json_data, dict):
                                    new_items = {}
                                    for k, v in json_data.items():
                                        cleaned_v = (
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
                            is_base64_candidate = (provider != "rfc2136" and 
                                                 len(value) % 4 == 0 and 
                                                 match(r"^[A-Za-z0-9+/=]+$", value))
                            if is_base64_candidate:
                                with suppress(BaseException):
                                    decoded = b64decode(value).decode("utf-8")
                                    if decoded != value:
                                        cleaned_decoded = (
                                            decoded.removeprefix("= ")
                                                   .replace("\\n", "\n")
                                                   .replace("\\t", "\t")
                                                   .replace("\\r", "\r")
                                                   .strip()
                                        )
                                        current_credential_items[key] = cleaned_decoded

                        if provider in provider_classes:
                            with suppress(ValidationError, KeyError):
                                provider_instance = provider_classes[provider](
                                    **current_credential_items
                                )
                                current_credentials_content = (
                                    provider_instance.get_formatted_credentials()
                                )

                                file_type = provider_instance.get_file_type()
                                stored_credentials_path = CACHE_PATH.joinpath(
                                    first_server, f"credentials.{file_type}"
                                )

                                if stored_credentials_path.is_file():
                                    stored_credentials_content = (
                                        stored_credentials_path.read_bytes()
                                    )
                                    content_differs = (
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
                f"domain(s) {domains}, expiry date: "
                f"{cert_domains.group('expiry_date')}"
            )

    psl_lines = None
    psl_rules = None

    certificates_generated = 0
    certificates_failed = 0

    # Process each server configuration
    for first_server, domains in domains_server_names.items():
        auto_le_check = (getenv(f"{first_server}_AUTO_LETS_ENCRYPT", "no") 
                       if IS_MULTISITE 
                       else getenv("AUTO_LETS_ENCRYPT", "no"))
        if auto_le_check != "yes":
            LOGGER.info(
                f"SSL certificate generation is not activated for "
                f"{first_server}, skipping..."
            )
            continue

        # Getting all the necessary data
        email_env = (f"{first_server}_EMAIL_LETS_ENCRYPT" if IS_MULTISITE 
                   else "EMAIL_LETS_ENCRYPT")
        challenge_env = (f"{first_server}_LETS_ENCRYPT_CHALLENGE" 
                       if IS_MULTISITE 
                       else "LETS_ENCRYPT_CHALLENGE")
        staging_env = (f"{first_server}_USE_LETS_ENCRYPT_STAGING" 
                     if IS_MULTISITE 
                     else "USE_LETS_ENCRYPT_STAGING")
        wildcard_env = (f"{first_server}_USE_LETS_ENCRYPT_WILDCARD" 
                      if IS_MULTISITE 
                      else "USE_LETS_ENCRYPT_WILDCARD")
        provider_env = (f"{first_server}_LETS_ENCRYPT_DNS_PROVIDER" 
                      if IS_MULTISITE 
                      else "LETS_ENCRYPT_DNS_PROVIDER")
        propagation_env = (f"{first_server}_LETS_ENCRYPT_DNS_PROPAGATION" 
                         if IS_MULTISITE 
                         else "LETS_ENCRYPT_DNS_PROPAGATION")
        profile_env = (f"{first_server}_LETS_ENCRYPT_PROFILE" 
                     if IS_MULTISITE 
                     else "LETS_ENCRYPT_PROFILE")
        psl_env = (f"{first_server}_LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES" 
                 if IS_MULTISITE 
                 else "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES")
        retries_env = (f"{first_server}_LETS_ENCRYPT_MAX_RETRIES" 
                     if IS_MULTISITE 
                     else "LETS_ENCRYPT_MAX_RETRIES")
        ca_env = (f"{first_server}_ACME_SSL_CA_PROVIDER" if IS_MULTISITE 
                else "ACME_SSL_CA_PROVIDER")
        api_key_env = (f"{first_server}_ACME_ZEROSSL_API_KEY" 
                     if IS_MULTISITE 
                     else "ACME_ZEROSSL_API_KEY")

        data = {
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
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Service {first_server} configuration: {data}")
        
        LOGGER.info(f"Service {first_server} configuration:")
        LOGGER.info(f"  CA Provider: {data['ca_provider']}")
        api_key_status = 'Yes' if data['api_key'] else 'No'
        LOGGER.info(f"  API Key provided: {api_key_status}")
        LOGGER.info(f"  Challenge type: {data['challenge']}")
        LOGGER.info(f"  Staging: {data['staging']}")
        LOGGER.info(f"  Wildcard: {data['use_wildcard']}")

        # Override profile if custom profile is set
        custom_profile_env = (f"{first_server}_LETS_ENCRYPT_CUSTOM_PROFILE" 
                            if IS_MULTISITE 
                            else "LETS_ENCRYPT_CUSTOM_PROFILE")
        custom_profile = getenv(custom_profile_env, "").strip()
        if custom_profile:
            data["profile"] = custom_profile
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Using custom profile: {custom_profile}")

        if data["challenge"] == "http" and data["use_wildcard"]:
            LOGGER.warning(
                f"Wildcard is not supported with HTTP challenge, "
                f"disabling wildcard for service {first_server}..."
            )
            data["use_wildcard"] = False

        should_skip_cert_check = (
            (not data["use_wildcard"] and 
             not domains_to_ask.get(first_server)) or
            (data["use_wildcard"] and not domains_to_ask.get(
                WILDCARD_GENERATOR.extract_wildcards_from_domains(
                    (first_server,)
                )[0].lstrip("*.")
            ))
        )
        if should_skip_cert_check:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"No certificate needed for {first_server}")
            continue

        if not data["max_retries"].isdigit():
            LOGGER.warning(
                f"Invalid max retries value for service {first_server}: "
                f"{data['max_retries']}, using default value of 0..."
            )
            data["max_retries"] = 0
        else:
            data["max_retries"] = int(data["max_retries"])

        # Getting the DNS provider data if necessary
        if data["challenge"] == "dns":
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Processing DNS credentials for {first_server}")
            
            credential_key = (
                f"{first_server}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" 
                if IS_MULTISITE 
                else "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"
            )
            credential_items = {}

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
                is_potential_json = (not credential_items and 
                                   len(value) % 4 == 0 and 
                                   match(r"^[A-Za-z0-9+/=]+$", value))
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
                            data["credential_items"] = new_items
                    except BaseException as e:
                        LOGGER.debug(format_exc())
                        LOGGER.error(
                            f"Error while decoding JSON data for service "
                            f"{first_server}: {value} : \n{e}"
                        )

            if not data["credential_items"]:
                # Process regular credentials
                data["credential_items"] = {}
                for key, value in credential_items.items():
                    # Check for base64 encoding
                    is_base64_candidate = (data["provider"] != "rfc2136" and 
                                         len(value) % 4 == 0 and 
                                         match(r"^[A-Za-z0-9+/=]+$", value))
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
                    data["credential_items"][key] = value

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            safe_data = data.copy()
            masked_items = {k: "***MASKED***" 
                          for k in data["credential_items"].keys()}
            safe_data["credential_items"] = masked_items
            if data["api_key"]:
                safe_data["api_key"] = "***MASKED***"
            LOGGER.debug(f"Safe data for service {first_server}: "
                        f"{dumps(safe_data)}")

        # Validate CA provider and API key requirements
        api_key_status = 'Yes' if data['api_key'] else 'No'
        LOGGER.info(
            f"Service {first_server} - CA Provider: {data['ca_provider']}, "
            f"API Key provided: {api_key_status}"
        )
        
        if data["ca_provider"].lower() == "zerossl":
            if not data["api_key"]:
                LOGGER.warning(
                    f"ZeroSSL API key not provided for service "
                    f"{first_server}, falling back to Let's Encrypt..."
                )
                data["ca_provider"] = "letsencrypt"
            else:
                LOGGER.info(f"✓ ZeroSSL configuration valid for service "
                          f"{first_server}")

        # Checking if the DNS data is valid
        if data["challenge"] == "dns":
            if not data["provider"]:
                available_providers = ', '.join(str(p) for p in provider_classes.keys())
                LOGGER.warning(
                    f"No provider found for service {first_server} "
                    f"(available providers: {available_providers}), "
                    "skipping certificate(s) generation..."
                )
                continue
            elif data["provider"] not in provider_classes:
                available_providers = ', '.join(str(p) for p in provider_classes.keys())
                LOGGER.warning(
                    f"Provider {data['provider']} not found for service "
                    f"{first_server} (available providers: "
                    f"{available_providers}), skipping certificate(s) "
                    f"generation..."
                )
                continue
            elif not data["credential_items"]:
                LOGGER.warning(
                    f"No valid credentials items found for service "
                    f"{first_server} (you should have at least one), "
                    f"skipping certificate(s) generation..."
                )
                continue

            try:
                provider = provider_classes[data["provider"]](
                    **data["credential_items"]
                )
            except ValidationError as ve:
                LOGGER.debug(format_exc())
                LOGGER.error(
                    f"Error while validating credentials for service "
                    f"{first_server}:\n{ve}"
                )
                continue

            content = provider.get_formatted_credentials()
        else:
            content = b"http_challenge"

        is_blacklisted = False

        # Adding the domains to Wildcard Generator if necessary
        file_type = (provider.get_file_type() if data["challenge"] == "dns" 
                   else "txt")
        file_path = (first_server, f"credentials.{file_type}")
        
        if data["use_wildcard"]:
            # Use the improved method for generating consistent group names
            group = WILDCARD_GENERATOR.create_group_name(
                domain=first_server,
                provider=(data["provider"] if data["challenge"] == "dns" 
                        else "http"),
                challenge_type=data["challenge"],
                staging=data["staging"],
                content_hash=bytes_hash(content, algorithm="sha1"),
                profile=data["profile"],
            )

            wildcard_info = (
                "the propagation time will be the provider's default and " 
                if data["challenge"] == "dns" else ""
            )
            LOGGER.info(
                f"Service {first_server} is using wildcard, "
                f"{wildcard_info}the email will be the same as the first "
                f"domain that created the group..."
            )

            if data["check_psl"]:
                if psl_lines is None:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug("Loading PSL for wildcard domain "
                                   "validation")
                    psl_lines = load_public_suffix_list(JOB)
                if psl_rules is None:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        LOGGER.debug("Parsing PSL rules")
                    psl_rules = parse_psl(psl_lines)

                wildcards = WILDCARD_GENERATOR.extract_wildcards_from_domains(
                    str(domains).split(" ")
                )

                LOGGER.info(f"Wildcard domains for {first_server}: "
                          f"{wildcards}")

                for d in wildcards:
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
                    group, str(domains).split(" "), data["email"], 
                    data["staging"]
                )
                file_path = (f"{group}.{file_type}",)
                LOGGER.info(f"[{first_server}] Wildcard group {group}")
        elif data["check_psl"]:
            if psl_lines is None:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug("Loading PSL for regular domain validation")
                psl_lines = load_public_suffix_list(JOB)
            if psl_rules is None:
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug("Parsing PSL rules")
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
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Skipping {first_server} due to PSL blacklist")
            continue

        # Generating the credentials file
        credentials_path = CACHE_PATH.joinpath(*file_path)

        if data["challenge"] == "dns":
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Managing credentials file for {first_server}: "
                           f"{credentials_path}")
            
            if not credentials_path.is_file():
                service_id = (first_server if not data["use_wildcard"] 
                            else "")
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
            elif data["use_wildcard"]:
                LOGGER.info(
                    f"Service {first_server}'s wildcard credentials file "
                    "has already been generated"
                )
            else:
                old_content = credentials_path.read_bytes()
                if old_content != content:
                    LOGGER.warning(
                        f"Service {first_server}'s credentials file is "
                        "outdated, updating it..."
                    )
                    cached, err = JOB.cache_file(
                        credentials_path.name, content, 
                        job_name="certbot-renew", 
                        service_id=first_server
                    )
                    if not cached:
                        LOGGER.error(
                            f"Error while updating service {first_server}'s "
                            f"credentials file in cache: {err}"
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

        if data["use_wildcard"]:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Wildcard processing complete for "
                           f"{first_server}")
            continue

        domains = str(domains).replace(" ", ",")
        ca_name = get_certificate_authority_config(data["ca_provider"])["name"]
        staging_info = ' using staging' if data['staging'] else ''
        LOGGER.info(
            f"Asking {ca_name} certificates for domain(s): {domains} "
            f"(email = {data['email']}){staging_info} "
            f" with {data['challenge']} challenge, using "
            f"{data['profile']!r} profile..."
        )

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Requesting certificate for {domains}")

        cert_result = certbot_new_with_retry(
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
        
        if cert_result != 0:
            status = 2
            certificates_failed += 1
            LOGGER.error(f"Certificate generation failed for domain(s) "
                        f"{domains}...")
        else:
            status = 1 if status == 0 else status
            certificates_generated += 1
            LOGGER.info(f"Certificate generation succeeded for domain(s): "
                       f"{domains}")

        generated_domains.update(domains.split(","))

    # Generating the wildcards if necessary
    wildcards = WILDCARD_GENERATOR.get_wildcards()
    if wildcards:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Processing {len(wildcards)} wildcard groups")
        
        for group, data in wildcards.items():
            if not data:
                continue
            
            # Generating the certificate from the generated credentials
            group_parts = group.split("_")
            provider = group_parts[0]
            profile = group_parts[2]
            base_domain = group_parts[3]

            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Processing wildcard group: {group}")
                LOGGER.debug(f"  Provider: {provider}")
                LOGGER.debug(f"  Profile: {profile}")
                LOGGER.debug(f"  Base domain: {base_domain}")

            email = data.pop("email")
            file_type = (provider_classes[provider].get_file_type() 
                       if provider in provider_classes else 'txt')
            credentials_file = CACHE_PATH.joinpath(f"{group}.{file_type}")

            # Get CA provider for this group
            original_server = None
            for server in domains_server_names.keys():
                if base_domain in server or server in base_domain:
                    original_server = server
                    break
            
            ca_provider = "letsencrypt"  # default
            api_key = None
            if original_server:
                ca_env = (f"{original_server}_ACME_SSL_CA_PROVIDER" 
                        if IS_MULTISITE 
                        else "ACME_SSL_CA_PROVIDER")
                ca_provider = getenv(ca_env, "letsencrypt")
                
                api_key_env = (f"{original_server}_ACME_ZEROSSL_API_KEY" 
                             if IS_MULTISITE 
                             else "ACME_ZEROSSL_API_KEY")
                api_key = getenv(api_key_env, "")

            # Process different environment types (staging/prod)
            for key, domains in data.items():
                if not domains:
                    continue

                staging = key == "staging"
                ca_name = get_certificate_authority_config(ca_provider)["name"]
                staging_info = ' using staging ' if staging else ''
                challenge_type = 'dns' if provider in provider_classes else 'http'
                LOGGER.info(
                    f"Asking {ca_name} wildcard certificates for domain(s): "
                    f"{domains} (email = {email}){staging_info} "
                    f"with {challenge_type} challenge, "
                    f"using {profile!r} profile..."
                )

                domains_split = domains.split(",")

                # Add wildcard certificate names to active set
                for domain in domains_split:
                    # Extract the base domain from the wildcard domain
                    base_domain = WILDCARD_GENERATOR.get_base_domain(domain)
                    active_cert_names.add(base_domain)

                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    LOGGER.debug(f"Requesting wildcard certificate for "
                               f"{domains}")

                wildcard_result = certbot_new_with_retry(
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

    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Certificate generation summary:")
        LOGGER.debug(f"  Generated: {certificates_generated}")
        LOGGER.debug(f"  Failed: {certificates_failed}")
        LOGGER.debug(f"  Total domains: {len(generated_domains)}")

    if CACHE_PATH.is_dir():
        # Clearing all missing credentials files
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Cleaning up old credentials files")
        
        cleaned_files = 0
        for ext in ("*.ini", "*.env", "*.json"):
            for file in list(CACHE_PATH.rglob(ext)):
                if "etc" in file.parts or not file.is_file():
                    continue
                # If the file is not in the wildcard groups, remove it
                if file not in credential_paths:
                    LOGGER.info(f"Removing old credentials file {file}")
                    service_id = (file.parent.name 
                                if file.parent.name != "letsencrypt" else "")
                    JOB.del_cache(
                        file.name, job_name="certbot-renew", 
                        service_id=service_id
                    )
                    cleaned_files += 1
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug(f"Cleaned up {cleaned_files} old credentials files")

    # Clearing all no longer needed certificates
    if getenv("LETS_ENCRYPT_CLEAR_OLD_CERTS", "no") == "yes":
        LOGGER.info(
            "Clear old certificates is activated, removing old / no longer "
            "used certificates..."
        )

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Starting certificate cleanup process")

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
            certificates_removed = 0
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Found {len(certificate_blocks)} certificates "
                           f"to evaluate")
                LOGGER.debug(f"Active certificates: "
                           f"{sorted(str(name) for name in active_cert_names)}")
            
            for block in certificate_blocks:
                cert_name = block.split("\n", 1)[0].strip()

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
                    cert_dir = DATA_PATH.joinpath("live", cert_name)
                    archive_dir = DATA_PATH.joinpath("archive", cert_name)
                    renewal_file = DATA_PATH.joinpath("renewal", 
                                                    f"{cert_name}.conf")
                    for path in (cert_dir, archive_dir):
                        if path.exists():
                            try:
                                for file in path.glob("*"):
                                    try:
                                        file.unlink()
                                    except Exception as e:
                                        LOGGER.error(f"Failed to remove file "
                                                   f"{file}: {e}")
                                path.rmdir()
                                LOGGER.info(f"Removed directory {path}")
                            except Exception as e:
                                LOGGER.error(f"Failed to remove directory "
                                           f"{path}: {e}")
                        if renewal_file.exists():
                            try:
                                renewal_file.unlink()
                                LOGGER.info(f"Removed renewal file "
                                           f"{renewal_file}")
                            except Exception as e:
                                LOGGER.error(
                                    f"Failed to remove renewal file "
                                    f"{renewal_file}: {e}"
                                )
                else:
                    LOGGER.error(
                        f"Failed to delete certificate {cert_name}: "
                        f"{delete_proc.stdout}"
                    )
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug(f"Certificate cleanup completed - removed "
                           f"{certificates_removed} certificates")
        else:
            LOGGER.error(f"Error listing certificates: {proc.stdout}")

    # Save data to db cache
    if DATA_PATH.is_dir() and list(DATA_PATH.iterdir()):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("Saving certificate data to database cache")
        
        cached, err = JOB.cache_dir(DATA_PATH, job_name="certbot-renew")
        if not cached:
            LOGGER.error(f"Error while saving data to db cache: {err}")
        else:
            LOGGER.info("Successfully saved data to db cache")
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                LOGGER.debug("Database cache update completed")
    else:
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            LOGGER.debug("No certificate data to cache")
            
except SystemExit as e:
    status = e.code
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug(f"Script exiting via SystemExit with code: {e.code}")
except BaseException as e:
    status = 1
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running certbot-new.py:\n{e}")
    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        LOGGER.debug("Script failed with unexpected exception")

if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
    LOGGER.debug(f"Certificate generation process completed with status: "
                f"{status}")

sys_exit(status)