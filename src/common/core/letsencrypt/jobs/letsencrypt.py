# -*- coding: utf-8 -*-
from os import sep
from os.path import join
from pathlib import Path
from sys import path as sys_path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module for Let's Encrypt provider classes
logger = setup_logger(
    title="letsencrypt-providers",
    log_file_path="/var/log/bunkerweb/letsencrypt.log"
)

logger.debug("Debug mode enabled for letsencrypt-providers")

# Define paths for Let's Encrypt operations
LIB_PATH = Path("/var/lib/bunkerweb/letsencrypt")
PYTHON_PATH = LIB_PATH / "python"

# Add to sys.path if not already present
python_path_str = PYTHON_PATH.as_posix()
if python_path_str not in sys_path:
    sys_path.append(python_path_str)

logger.debug(f"Python path configured: {python_path_str}")

# Factory function for creating model validators with alias mapping.
# Enables flexible credential field naming across different providers.
def alias_model_validator(field_map: dict):
    logger.debug(f"Creating alias validator for {len(field_map)} field mappings")
    
    def validator(cls, values):
        logger.debug(f"Validating aliases for {cls.__name__} with {len(values)} input values")
        
        for field, aliases in field_map.items():
            for alias in aliases:
                if alias in values:
                    logger.debug(f"Found alias '{alias}' for field '{field}' in {cls.__name__}")
                    values[field] = values[alias]
                    break
        return values

    return model_validator(mode="before")(validator)

# Base class for all DNS providers with common credential formatting.
# Provides standard INI file format for most providers.
class Provider(BaseModel):
    logger.debug("Initializing Provider base class")
    
    model_config = ConfigDict(extra="ignore")

    # Format credentials as INI-style key-value pairs for file output.
    # Standard format used by most certbot DNS plugins.
    def get_formatted_credentials(self) -> bytes:
        logger.debug(f"Formatting credentials for {self.__class__.__name__}")
        
        credentials = self.model_dump(exclude={"file_type"})
        formatted = "\n".join(f"{key} = {value}" for key, value in credentials.items())
        
        logger.debug(f"Generated {len(credentials)} credential lines for {self.__class__.__name__}")
        return formatted.encode("utf-8")

    # Return the standard file extension for credential files.
    # Most providers use INI format for certbot compatibility.
    @staticmethod
    def get_file_type() -> Literal["ini"]:
        return "ini"

# Cloudflare DNS provider supporting both API token and email/key authentication.
# Flexible credential handling for different Cloudflare API access methods.
class CloudflareProvider(Provider):
    logger.debug("Initializing CloudflareProvider class")
    
    dns_cloudflare_api_token: str = ""
    dns_cloudflare_email: str = ""
    dns_cloudflare_api_key: str = ""

    _validate_aliases = alias_model_validator(
        {
            "dns_cloudflare_api_token": ("dns_cloudflare_api_token", "cloudflare_api_token", "api_token"),
            "dns_cloudflare_email": ("dns_cloudflare_email", "cloudflare_email", "email"),
            "dns_cloudflare_api_key": ("dns_cloudflare_api_key", "cloudflare_api_key", "api_key"),
        }
    )

    # Format Cloudflare credentials excluding empty default values.
    # Only includes actually provided credential fields.
    def get_formatted_credentials(self) -> bytes:
        logger.debug("Formatting Cloudflare credentials with exclude_defaults")
        
        credentials = self.model_dump(exclude={"file_type"}, exclude_defaults=True)
        formatted = "\n".join(f"{key} = {value}" for key, value in credentials.items())
        
        logger.debug(f"Generated Cloudflare credentials with {len(credentials)} non-default fields")
        return formatted.encode("utf-8")

    # Validate Cloudflare authentication requirements.
    # Ensures either API token or email+key combination is provided.
    @model_validator(mode="after")
    def validate_cloudflare_credentials(self):
        logger.debug("Validating Cloudflare credential requirements")
        
        has_token = bool(self.dns_cloudflare_api_token)
        has_email_key = bool(self.dns_cloudflare_email and self.dns_cloudflare_api_key)
        
        logger.debug(f"Cloudflare validation - has_token: {has_token}, has_email_key: {has_email_key}")
        
        if not has_token and not has_email_key:
            logger.error("Cloudflare credentials validation failed - missing required fields")
            raise ValueError("Either 'dns_cloudflare_api_token' or both 'dns_cloudflare_email' and 'dns_cloudflare_api_key' must be provided.")
        
        logger.debug("Cloudflare credentials validation successful")
        return self

# deSEC DNS provider with token-based authentication.
# Simple token-only authentication for deSEC DNS service.
class DesecProvider(Provider):
    logger.debug("Initializing DesecProvider class")
    
    dns_desec_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_desec_token": ("dns_desec_token", "desec_token", "token"),
        }
    )

# DigitalOcean DNS provider with token-based authentication.
# Uses DigitalOcean API token for DNS record management.
class DigitalOceanProvider(Provider):
    logger.debug("Initializing DigitalOceanProvider class")
    
    dns_digitalocean_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_digitalocean_token": ("dns_digitalocean_token", "digitalocean_token", "token"),
        }
    )

# DNSimple DNS provider with token-based authentication.
# Uses DNSimple API token for domain management.
class DnsimpleProvider(Provider):
    logger.debug("Initializing DnsimpleProvider class")
    
    dns_dnsimple_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsimple_token": ("dns_dnsimple_token", "dnsimple_token", "token"),
        }
    )

# DNS Made Easy provider with API key and secret authentication.
# Requires both API key and secret key for authentication.
class DnsMadeEasyProvider(Provider):
    logger.debug("Initializing DnsMadeEasyProvider class")
    
    dns_dnsmadeeasy_api_key: str
    dns_dnsmadeeasy_secret_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsmadeeasy_api_key": ("dns_dnsmadeeasy_api_key", "dnsmadeeasy_api_key", "api_key"),
            "dns_dnsmadeeasy_secret_key": ("dns_dnsmadeeasy_secret_key", "dnsmadeeasy_secret_key", "secret_key"),
        }
    )

# Gehirn DNS provider with API token and secret authentication.
# Requires both API token and secret for Gehirn DNS service.
class GehirnProvider(Provider):
    logger.debug("Initializing GehirnProvider class")
    
    dns_gehirn_api_token: str
    dns_gehirn_api_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_gehirn_api_token": ("dns_gehirn_api_token", "gehirn_api_token", "api_token"),
            "dns_gehirn_api_secret": ("dns_gehirn_api_secret", "gehirn_api_secret", "api_secret"),
        }
    )

# Google Cloud DNS provider with service account JSON credentials.
# Uses service account format for Google Cloud DNS integration.
class GoogleProvider(Provider):
    logger.debug("Initializing GoogleProvider class")
    
    type: str = "service_account"
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://accounts.google.com/o/oauth2/token"
    auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url: str

    _validate_aliases = alias_model_validator(
        {
            "type": ("type", "google_type", "dns_google_type"),
            "project_id": ("project_id", "google_project_id", "dns_google_project_id"),
            "private_key_id": ("private_key_id", "google_private_key_id", "dns_google_private_key_id"),
            "private_key": ("private_key", "google_private_key", "dns_google_private_key"),
            "client_email": ("client_email", "google_client_email", "dns_google_client_email"),
            "client_id": ("client_id", "google_client_id", "dns_google_client_id"),
            "auth_uri": ("auth_uri", "google_auth_uri", "dns_google_auth_uri"),
            "token_uri": ("token_uri", "google_token_uri", "dns_google_token_uri"),
            "auth_provider_x509_cert_url": ("auth_provider_x509_cert_url", "google_auth_provider_x509_cert_url", "dns_google_auth_provider_x509_cert_url"),
            "client_x509_cert_url": ("client_x509_cert_url", "google_client_x509_cert_url", "dns_google_client_x509_cert_url"),
        }
    )

    # Format Google credentials as JSON for service account file.
    # Google Cloud requires JSON format for service account credentials.
    def get_formatted_credentials(self) -> bytes:
        logger.debug("Formatting Google Cloud credentials as JSON")
        
        json_output = self.model_dump_json(indent=2, exclude={"file_type"})
        logger.debug(f"Generated Google Cloud JSON credentials with {len(json_output)} characters")
        
        return json_output.encode("utf-8")

    # Return JSON file type for Google Cloud credentials.
    # Google Cloud service accounts require JSON format.
    @staticmethod
    def get_file_type() -> Literal["json"]:
        return "json"

# Infomaniak DNS provider with token-based authentication.
# Uses Infomaniak API token for DNS management.
class InfomaniakProvider(Provider):
    logger.debug("Initializing InfomaniakProvider class")
    
    dns_infomaniak_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_infomaniak_token": ("dns_infomaniak_token", "infomaniak_token", "token"),
        }
    )

# Ionos DNS provider with prefix, secret, and endpoint configuration.
# Supports custom endpoint for different Ionos regions.
class IonosProvider(Provider):
    logger.debug("Initializing IonosProvider class")
    
    dns_ionos_prefix: str
    dns_ionos_secret: str
    dns_ionos_endpoint: str = "https://api.hosting.ionos.com"

    _validate_aliases = alias_model_validator(
        {
            "dns_ionos_prefix": ("dns_ionos_prefix", "ionos_prefix", "prefix"),
            "dns_ionos_secret": ("dns_ionos_secret", "ionos_secret", "secret"),
            "dns_ionos_endpoint": ("dns_ionos_endpoint", "ionos_endpoint", "endpoint"),
        }
    )

# Linode DNS provider with API key authentication.
# Uses Linode API key for DNS record management.
class LinodeProvider(Provider):
    logger.debug("Initializing LinodeProvider class")
    
    dns_linode_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_linode_key": ("dns_linode_key", "linode_key", "key"),
        }
    )

# LuaDns provider with email and token authentication.
# Requires both email and token for LuaDns API access.
class LuaDnsProvider(Provider):
    logger.debug("Initializing LuaDnsProvider class")
    
    dns_luadns_email: str
    dns_luadns_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_luadns_email": ("dns_luadns_email", "luadns_email", "email"),
            "dns_luadns_token": ("dns_luadns_token", "luadns_token", "token"),
        }
    )

# NS1 DNS provider with API key authentication.
# Uses NS1 API key for DNS management operations.
class NSOneProvider(Provider):
    logger.debug("Initializing NSOneProvider class")
    
    dns_nsone_api_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_nsone_api_key": ("dns_nsone_api_key", "nsone_api_key", "api_key"),
        }
    )

# OVH DNS provider with endpoint and application credentials.
# Supports different OVH endpoints for various regions.
class OvhProvider(Provider):
    logger.debug("Initializing OvhProvider class")
    
    dns_ovh_endpoint: str = "ovh-eu"
    dns_ovh_application_key: str
    dns_ovh_application_secret: str
    dns_ovh_consumer_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_ovh_endpoint": ("dns_ovh_endpoint", "ovh_endpoint", "endpoint"),
            "dns_ovh_application_key": ("dns_ovh_application_key", "ovh_application_key", "application_key"),
            "dns_ovh_application_secret": ("dns_ovh_application_secret", "ovh_application_secret", "application_secret"),
            "dns_ovh_consumer_key": ("dns_ovh_consumer_key", "ovh_consumer_key", "consumer_key"),
        }
    )

# RFC 2136 DNS provider for TSIG-based dynamic DNS updates.
# Supports TSIG authentication for secure DNS updates.
class Rfc2136Provider(Provider):
    logger.debug("Initializing Rfc2136Provider class")
    
    dns_rfc2136_server: str
    dns_rfc2136_port: Optional[str] = None
    dns_rfc2136_name: str
    dns_rfc2136_secret: str
    dns_rfc2136_algorithm: str = "HMAC-SHA512"
    dns_rfc2136_sign_query: str = "false"

    _validate_aliases = alias_model_validator(
        {
            "dns_rfc2136_server": ("dns_rfc2136_server", "rfc2136_server", "server"),
            "dns_rfc2136_port": ("dns_rfc2136_port", "rfc2136_port", "port"),
            "dns_rfc2136_name": ("dns_rfc2136_name", "rfc2136_name", "name"),
            "dns_rfc2136_secret": ("dns_rfc2136_secret", "rfc2136_secret", "secret"),
            "dns_rfc2136_algorithm": ("dns_rfc2136_algorithm", "rfc2136_algorithm", "algorithm"),
            "dns_rfc2136_sign_query": ("dns_rfc2136_sign_query", "rfc2136_sign_query", "sign_query"),
        }
    )

    # Format RFC 2136 credentials excluding default values.
    # Only includes non-default configuration for TSIG setup.
    def get_formatted_credentials(self) -> bytes:
        logger.debug("Formatting RFC 2136 credentials with exclude_defaults")
        
        credentials = self.model_dump(exclude={"file_type"}, exclude_defaults=True)
        formatted = "\n".join(f"{key} = {value}" for key, value in credentials.items())
        
        logger.debug(f"Generated RFC 2136 credentials with {len(credentials)} non-default fields")
        return formatted.encode("utf-8")

# AWS Route 53 provider with access key and secret authentication.
# Uses AWS credentials for Route 53 DNS management.
class Route53Provider(Provider):
    logger.debug("Initializing Route53Provider class")
    
    aws_access_key_id: str
    aws_secret_access_key: str

    _validate_aliases = alias_model_validator(
        {
            "aws_access_key_id": ("aws_access_key_id", "dns_aws_access_key_id", "access_key_id"),
            "aws_secret_access_key": ("aws_secret_access_key", "dns_aws_secret_access_key", "secret_access_key"),
        }
    )

    # Format Route 53 credentials as environment variables.
    # AWS tools expect uppercase environment variable format.
    def get_formatted_credentials(self) -> bytes:
        logger.debug("Formatting Route 53 credentials as environment variables")
        
        credentials = self.model_dump(exclude={"file_type"})
        formatted = "\n".join(f"{key.upper()}={value!r}" for key, value in credentials.items())
        
        logger.debug(f"Generated Route 53 env credentials with {len(credentials)} variables")
        return formatted.encode("utf-8")

    # Return environment file type for Route 53 credentials.
    # Route 53 plugin uses environment variable format.
    @staticmethod
    def get_file_type() -> Literal["env"]:
        return "env"

# Sakura Cloud DNS provider with API token and secret.
# Requires both token and secret for Sakura Cloud API access.
class SakuraCloudProvider(Provider):
    logger.debug("Initializing SakuraCloudProvider class")
    
    dns_sakuracloud_api_token: str
    dns_sakuracloud_api_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_sakuracloud_api_token": ("dns_sakuracloud_api_token", "sakuracloud_api_token", "api_token"),
            "dns_sakuracloud_api_secret": ("dns_sakuracloud_api_secret", "sakuracloud_api_secret", "api_secret"),
        }
    )

# Scaleway DNS provider with application token authentication.
# Uses Scaleway application token for DNS operations.
class ScalewayProvider(Provider):
    logger.debug("Initializing ScalewayProvider class")
    
    dns_scaleway_application_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_scaleway_application_token": ("dns_scaleway_application_token", "scaleway_application_token", "application_token"),
        }
    )

# Njalla DNS provider with flexible token authentication.
# Supports multiple token field names for flexibility.
class NjallaProvider(Provider):
    logger.debug("Initializing NjallaProvider class")
    
    dns_njalla_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_njalla_token": ("dns_njalla_token", "njalla_token", "token", "api_token", "auth_token"),
        }
    )

# Manages wildcard domain generation and grouping for Let's Encrypt certificates.
# Handles domain grouping, wildcard pattern generation, and certificate organization.
class WildcardGenerator:
    logger.debug("Initializing WildcardGenerator class")

    def __init__(self):
        self.__domain_groups = {}  # Stores raw domains grouped by identifier
        self.__wildcards = {}  # Stores generated wildcard patterns
        logger.debug("WildcardGenerator initialized with empty domain groups and wildcards")

    # Add domains to a group and regenerate wildcard patterns.
    # Organizes domains by group and environment for certificate generation.
    def extend(self, group: str, domains: List[str], email: str, staging: bool = False):
        logger.debug(f"Extending wildcard group '{group}' with {len(domains)} domains, staging: {staging}")
        
        # Initialize group if it doesn't exist
        if group not in self.__domain_groups:
            self.__domain_groups[group] = {"staging": set(), "prod": set(), "email": email}
            logger.debug(f"Created new domain group: {group}")

        # Add domains to appropriate environment
        env_type = "staging" if staging else "prod"
        added_count = 0
        for domain in domains:
            if domain := domain.strip():
                self.__domain_groups[group][env_type].add(domain)
                added_count += 1

        logger.debug(f"Added {added_count} domains to {group}[{env_type}]")

        # Regenerate wildcards after adding new domains
        self.__generate_wildcards(staging)

    # Generate wildcard patterns for the specified environment.
    # Creates wildcard certificates for efficient domain coverage.
    def __generate_wildcards(self, staging: bool = False):
        logger.debug(f"Generating wildcards for {'staging' if staging else 'production'} environment")
        
        self.__wildcards.clear()
        env_type = "staging" if staging else "prod"
        processed_groups = 0

        # Process each domain group
        for group, types in self.__domain_groups.items():
            if group not in self.__wildcards:
                self.__wildcards[group] = {"staging": set(), "prod": set(), "email": types["email"]}
                processed_groups += 1

            # Process each domain in the group
            domain_count = 0
            for domain in types[env_type]:
                # Convert domain to wildcards and add to appropriate group
                self.__add_domain_wildcards(domain, group, env_type)
                domain_count += 1
            
            logger.debug(f"Processed {domain_count} domains for group {group}")

        logger.debug(f"Generated wildcards for {processed_groups} groups")

    # Convert a domain to wildcard patterns and add to wildcards collection.
    # Creates appropriate wildcard patterns based on domain structure.
    def __add_domain_wildcards(self, domain: str, group: str, env_type: str):
        logger.debug(f"Adding wildcard patterns for domain: {domain}")
        
        parts = domain.split(".")

        # Handle subdomains (domains with more than 2 parts)
        if len(parts) > 2:
            # Create wildcard for the base domain (e.g., *.example.com)
            base_domain = ".".join(parts[1:])
            wildcard_pattern = f"*.{base_domain}"
            
            self.__wildcards[group][env_type].add(wildcard_pattern)
            self.__wildcards[group][env_type].add(base_domain)
            logger.debug(f"Added wildcard pattern: {wildcard_pattern} and base: {base_domain}")
        else:
            # Just add the raw domain for top-level domains
            self.__wildcards[group][env_type].add(domain)
            logger.debug(f"Added top-level domain: {domain}")

    # Get formatted wildcard domains organized by group and environment.
    # Returns ready-to-use domain strings for certificate generation.
    def get_wildcards(self) -> Dict[str, Dict[Literal["staging", "prod", "email"], str]]:
        logger.debug("Retrieving formatted wildcard domains")
        
        result = {}
        for group, data in self.__wildcards.items():
            result[group] = {"email": data["email"]}
            for env_type in ("staging", "prod"):
                if domains := data[env_type]:
                    # Sort domains with wildcards first
                    sorted_domains = sorted(domains, key=lambda x: x[0] != "*")
                    result[group][env_type] = ",".join(sorted_domains)
                    logger.debug(f"Group {group}[{env_type}]: {len(domains)} domains")
        
        logger.debug(f"Returning wildcard data for {len(result)} groups")
        return result

    # Generate wildcard patterns from a list of domains.
    # Static method for creating wildcards without group management.
    @staticmethod
    def extract_wildcards_from_domains(domains: List[str]) -> List[str]:
        logger.debug(f"Extracting wildcards from {len(domains)} domains")
        
        wildcards = set()
        for domain in domains:
            parts = domain.split(".")
            # Generate wildcards for subdomains
            if len(parts) > 2:
                base_domain = ".".join(parts[1:])
                wildcards.add(f"*.{base_domain}")
                wildcards.add(base_domain)
            else:
                # Just add the domain for top-level domains
                wildcards.add(domain)

        # Sort with wildcards first
        result = sorted(wildcards, key=lambda x: x[0] != "*")
        logger.debug(f"Extracted {len(result)} wildcard patterns")
        return result

    # Extract the base domain from a domain name.
    # Removes wildcard prefix to get the actual domain.
    @staticmethod
    def get_base_domain(domain: str) -> str:
        base = domain.lstrip("*.")
        logger.debug(f"Extracted base domain '{base}' from '{domain}'")
        return base

    # Generate a consistent group name for wildcard certificates.
    # Creates unique identifiers for domain grouping and caching.
    @staticmethod
    def create_group_name(domain: str, provider: str, challenge_type: str, staging: bool, content_hash: str, profile: str = "classic") -> str:
        logger.debug(f"Creating group name for domain: {domain}, provider: {provider}, challenge: {challenge_type}")
        
        # Extract base domain and format it for the group name
        base_domain = WildcardGenerator.get_base_domain(domain).replace(".", "-")
        env = "staging" if staging else "prod"

        # Use provider name for DNS challenge, otherwise use 'http'
        challenge_identifier = provider if challenge_type == "dns" else "http"

        group_name = f"{challenge_identifier}_{env}_{profile}_{base_domain}_{content_hash}"
        logger.debug(f"Generated group name: {group_name}")
        return group_name

logger.debug("Let's Encrypt provider classes and wildcard generator initialized successfully")
