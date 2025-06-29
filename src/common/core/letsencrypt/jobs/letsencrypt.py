# -*- coding: utf-8 -*-
from os import getenv
from pathlib import Path
from sys import path as sys_path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

# Define paths
LIB_PATH = Path("/var/lib/bunkerweb/letsencrypt")
PYTHON_PATH = LIB_PATH / "python"

# Add to sys.path if not already present
python_path_str = PYTHON_PATH.as_posix()
if python_path_str not in sys_path:
    sys_path.append(python_path_str)


def alias_model_validator(field_map: dict):
    # Factory function for creating a model_validator for alias mapping.
    # This allows DNS providers to accept credentials under multiple field 
    # names for better compatibility with different configuration formats.
    # 
    # Args:
    #     field_map: Dictionary mapping canonical field names to list of 
    #               aliases
    # 
    # Returns:
    #     Configured model_validator function
    def validator(cls, values):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Processing aliases for {cls.__name__}")
            print(f"DEBUG: Input values: {list(values.keys())}")
            print(f"DEBUG: Field mapping has {len(field_map)} canonical fields")
        
        for field, aliases in field_map.items():
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                print(f"DEBUG: Checking field '{field}' with {len(aliases)} aliases")
            
            for alias in aliases:
                if alias in values:
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        print(f"DEBUG: Found alias '{alias}' for field '{field}'")
                        print(f"DEBUG: Mapping alias '{alias}' to canonical field '{field}'")
                    values[field] = values[alias]
                    break
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Final mapped values: {list(values.keys())}")
            print(f"DEBUG: Alias processing completed for {cls.__name__}")
        
        return values

    return model_validator(mode="before")(validator)


class Provider(BaseModel):
    # Base class for DNS providers.
    # Provides common functionality for credential formatting and file type 
    # handling. All DNS provider classes inherit from this base class.

    model_config = ConfigDict(extra="ignore")

    def get_formatted_credentials(self) -> bytes:
        # Return the formatted credentials to be written to a file.
        # Default implementation creates INI-style key=value format.
        # 
        # Returns:
        #     bytes - UTF-8 encoded credential content
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            excluded_fields = {"file_type"}
            fields = self.model_dump(exclude=excluded_fields)
            print(f"DEBUG: {self.__class__.__name__} formatting {len(fields)} fields")
            print(f"DEBUG: Excluded fields: {excluded_fields}")
            print(f"DEBUG: Using default INI-style key=value format")
        
        content = "\n".join(
            f"{key} = {value}" 
            for key, value in self.model_dump(exclude={"file_type"}).items()
        ).encode("utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated {len(content)} bytes of credential content")
            print(f"DEBUG: Content will be written as UTF-8 encoded text")
        
        return content

    @staticmethod
    def get_file_type() -> Literal["ini"]:
        # Return the file type that the credentials should be written to.
        # Default implementation returns 'ini' for most providers.
        # 
        # Returns:
        #     Literal type indicating file extension
        return "ini"


class CloudflareProvider(Provider):
    # Supports both API token (recommended) and legacy email/API key 
    # authentication. Requires either api_token OR both email and api_key 
    # for authentication.

    dns_cloudflare_api_token: str = ""
    dns_cloudflare_email: str = ""
    dns_cloudflare_api_key: str = ""

    _validate_aliases = alias_model_validator(
        {
            "dns_cloudflare_api_token": (
                "dns_cloudflare_api_token", "cloudflare_api_token", "api_token"
            ),
            "dns_cloudflare_email": (
                "dns_cloudflare_email", "cloudflare_email", "email"
            ),
            "dns_cloudflare_api_key": (
                "dns_cloudflare_api_key", "cloudflare_api_key", "api_key"
            ),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        # Return the formatted credentials, excluding defaults.
        # Only includes non-empty credential fields to avoid cluttering 
        # output.
        # 
        # Returns:
        #     bytes - UTF-8 encoded credential content
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            all_fields = self.model_dump(exclude={"file_type"})
            non_default_fields = self.model_dump(
                exclude={"file_type"}, exclude_defaults=True
            )
            print(f"DEBUG: Cloudflare provider has {len(all_fields)} total fields")
            print(f"DEBUG: {len(non_default_fields)} non-default fields will be included")
            print(f"DEBUG: Excluding empty/default values to minimize credential file")
        
        content = "\n".join(
            f"{key} = {value}" 
            for key, value in self.model_dump(
                exclude={"file_type"}, exclude_defaults=True
            ).items()
        ).encode("utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated {len(content)} bytes of Cloudflare credentials")
        
        return content

    @model_validator(mode="after")
    def validate_cloudflare_credentials(self):
        # Validate Cloudflare credentials.
        # Ensures either API token or email+API key combination is provided.
        # 
        # Raises:
        #     ValueError if neither authentication method is complete
        has_token = bool(self.dns_cloudflare_api_token)
        has_legacy = bool(self.dns_cloudflare_email and self.dns_cloudflare_api_key)
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print("DEBUG: Cloudflare credential validation:")
            print(f"DEBUG: API token provided: {has_token}")
            print(f"DEBUG: Legacy email+key provided: {has_legacy}")
            print("DEBUG: At least one authentication method must be complete")
        
        if not has_token and not has_legacy:
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                print("DEBUG: Neither authentication method is complete")
                print("DEBUG: Validation will fail")
            raise ValueError(
                "Either 'dns_cloudflare_api_token' or both "
                "'dns_cloudflare_email' and 'dns_cloudflare_api_key' must be provided."
            )
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print("DEBUG: Cloudflare credentials validation passed")
            auth_method = "API token" if has_token else "email+API key"
            print(f"DEBUG: Using {auth_method} authentication method")
        
        return self


class DesecProvider(Provider):
    # Requires only an API token for authentication.

    dns_desec_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_desec_token": ("dns_desec_token", "desec_token", "token"),
        }
    )


class DigitalOceanProvider(Provider):
    # Requires a personal access token with read/write scope.

    dns_digitalocean_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_digitalocean_token": (
                "dns_digitalocean_token", "digitalocean_token", "token"
            ),
        }
    )


class DnsimpleProvider(Provider):
    # Requires an API token for authentication.

    dns_dnsimple_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsimple_token": ("dns_dnsimple_token", "dnsimple_token", "token"),
        }
    )


class DnsMadeEasyProvider(Provider):
    # Requires API key and secret key.
    # Both keys are required for authentication.

    dns_dnsmadeeasy_api_key: str
    dns_dnsmadeeasy_secret_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_dnsmadeeasy_api_key": (
                "dns_dnsmadeeasy_api_key", "dnsmadeeasy_api_key", "api_key"
            ),
            "dns_dnsmadeeasy_secret_key": (
                "dns_dnsmadeeasy_secret_key", "dnsmadeeasy_secret_key", 
                "secret_key"
            ),
        }
    )


class GehirnProvider(Provider):
    # Requires both API token and API secret for authentication.

    dns_gehirn_api_token: str
    dns_gehirn_api_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_gehirn_api_token": (
                "dns_gehirn_api_token", "gehirn_api_token", "api_token"
            ),
            "dns_gehirn_api_secret": (
                "dns_gehirn_api_secret", "gehirn_api_secret", "api_secret"
            ),
        }
    )


class GoogleProvider(Provider):
    # Uses Google Cloud service account credentials in JSON format.
    # Requires a service account with DNS admin permissions.

    type: str = "service_account"
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://accounts.google.com/o/oauth2/token"
    auth_provider_x509_cert_url: str = ("https://www.googleapis.com/"
                                       "oauth2/v1/certs")
    client_x509_cert_url: str

    _validate_aliases = alias_model_validator(
        {
            "type": ("type", "google_type", "dns_google_type"),
            "project_id": ("project_id", "google_project_id", 
                          "dns_google_project_id"),
            "private_key_id": (
                "private_key_id", "google_private_key_id", 
                "dns_google_private_key_id"
            ),
            "private_key": (
                "private_key", "google_private_key", "dns_google_private_key"
            ),
            "client_email": (
                "client_email", "google_client_email", "dns_google_client_email"
            ),
            "client_id": ("client_id", "google_client_id", 
                         "dns_google_client_id"),
            "auth_uri": ("auth_uri", "google_auth_uri", "dns_google_auth_uri"),
            "token_uri": ("token_uri", "google_token_uri", 
                         "dns_google_token_uri"),
            "auth_provider_x509_cert_url": (
                "auth_provider_x509_cert_url", 
                "google_auth_provider_x509_cert_url", 
                "dns_google_auth_provider_x509_cert_url"
            ),
            "client_x509_cert_url": (
                "client_x509_cert_url", 
                "google_client_x509_cert_url", 
                "dns_google_client_x509_cert_url"
            ),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        # Return the formatted credentials in JSON format.
        # Google Cloud requires credentials in JSON service account format.
        # 
        # Returns:
        #     bytes - UTF-8 encoded JSON content
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print("DEBUG: Google provider formatting credentials as JSON")
            print("DEBUG: Using service account JSON format required by Google Cloud")
        
        json_content = self.model_dump_json(
            indent=2, exclude={"file_type"}
        ).encode("utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated {len(json_content)} bytes of JSON credentials")
            print("DEBUG: JSON format includes proper indentation for readability")
        
        return json_content

    @staticmethod
    def get_file_type() -> Literal["json"]:
        # Return the file type that the credentials should be written to.
        # Google provider requires JSON format for service account 
        # credentials.
        # 
        # Returns:
        #     Literal type indicating JSON file extension
        return "json"


class InfomaniakProvider(Provider):
    # Requires an API token for authentication.

    dns_infomaniak_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_infomaniak_token": (
                "dns_infomaniak_token", "infomaniak_token", "token"
            ),
        }
    )


class IonosProvider(Provider):
    # Requires prefix and secret for authentication, with configurable 
    # endpoint.

    dns_ionos_prefix: str
    dns_ionos_secret: str
    dns_ionos_endpoint: str = "https://api.hosting.ionos.com"

    _validate_aliases = alias_model_validator(
        {
            "dns_ionos_prefix": ("dns_ionos_prefix", "ionos_prefix", "prefix"),
            "dns_ionos_secret": ("dns_ionos_secret", "ionos_secret", "secret"),
            "dns_ionos_endpoint": ("dns_ionos_endpoint", "ionos_endpoint", 
                                  "endpoint"),
        }
    )


class LinodeProvider(Provider):
    # Requires an API key for authentication.

    dns_linode_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_linode_key": ("dns_linode_key", "linode_key", "key"),
        }
    )


class LuaDnsProvider(Provider):
    # Requires email and token authentication.
    # Both email and token are required for API access.

    dns_luadns_email: str
    dns_luadns_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_luadns_email": ("dns_luadns_email", "luadns_email", "email"),
            "dns_luadns_token": ("dns_luadns_token", "luadns_token", "token"),
        }
    )


class NSOneProvider(Provider):
    # Requires an API key for authentication.

    dns_nsone_api_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_nsone_api_key": ("dns_nsone_api_key", "nsone_api_key", 
                                 "api_key"),
        }
    )


class OvhProvider(Provider):
    # Requires application key, secret, and consumer key for authentication.

    dns_ovh_endpoint: str = "ovh-eu"
    dns_ovh_application_key: str
    dns_ovh_application_secret: str
    dns_ovh_consumer_key: str

    _validate_aliases = alias_model_validator(
        {
            "dns_ovh_endpoint": ("dns_ovh_endpoint", "ovh_endpoint", "endpoint"),
            "dns_ovh_application_key": (
                "dns_ovh_application_key", "ovh_application_key", 
                "application_key"
            ),
            "dns_ovh_application_secret": (
                "dns_ovh_application_secret", "ovh_application_secret", 
                "application_secret"
            ),
            "dns_ovh_consumer_key": (
                "dns_ovh_consumer_key", "ovh_consumer_key", "consumer_key"
            ),
        }
    )


class Rfc2136Provider(Provider):
    # Standard protocol for dynamic DNS updates using TSIG authentication.
    # Supports HMAC-based authentication with configurable algorithms.

    dns_rfc2136_server: str
    dns_rfc2136_port: Optional[str] = None
    dns_rfc2136_name: str
    dns_rfc2136_secret: str
    dns_rfc2136_algorithm: str = "HMAC-SHA512"
    dns_rfc2136_sign_query: str = "false"

    _validate_aliases = alias_model_validator(
        {
            "dns_rfc2136_server": ("dns_rfc2136_server", "rfc2136_server", 
                                  "server"),
            "dns_rfc2136_port": ("dns_rfc2136_port", "rfc2136_port", "port"),
            "dns_rfc2136_name": ("dns_rfc2136_name", "rfc2136_name", "name"),
            "dns_rfc2136_secret": ("dns_rfc2136_secret", "rfc2136_secret", 
                                  "secret"),
            "dns_rfc2136_algorithm": (
                "dns_rfc2136_algorithm", "rfc2136_algorithm", "algorithm"
            ),
            "dns_rfc2136_sign_query": (
                "dns_rfc2136_sign_query", "rfc2136_sign_query", "sign_query"
            ),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        # Return the formatted credentials, excluding defaults.
        # RFC2136 provider excludes default values to minimize configuration.
        # 
        # Returns:
        #     bytes - UTF-8 encoded credential content
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            all_fields = self.model_dump(exclude={"file_type"})
            non_default_fields = self.model_dump(
                exclude={"file_type"}, exclude_defaults=True
            )
            print(f"DEBUG: RFC2136 provider has {len(all_fields)} total fields")
            print(f"DEBUG: {len(non_default_fields)} non-default fields included")
            print("DEBUG: Excluding defaults to minimize RFC2136 configuration")
        
        content = "\n".join(
            f"{key} = {value}" 
            for key, value in self.model_dump(
                exclude={"file_type"}, exclude_defaults=True
            ).items()
        ).encode("utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated {len(content)} bytes of RFC2136 credentials")
        
        return content


class Route53Provider(Provider):
    # Uses IAM credentials.
    # Requires AWS access key ID and secret access key.

    aws_access_key_id: str
    aws_secret_access_key: str

    _validate_aliases = alias_model_validator(
        {
            "aws_access_key_id": (
                "aws_access_key_id", "dns_aws_access_key_id", "access_key_id"
            ),
            "aws_secret_access_key": (
                "aws_secret_access_key", "dns_aws_secret_access_key", 
                "secret_access_key"
            ),
        }
    )

    def get_formatted_credentials(self) -> bytes:
        # Return the formatted credentials in environment variable format.
        # Route53 uses environment variables for AWS credentials.
        # 
        # Returns:
        #     bytes - UTF-8 encoded environment variable format
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            fields = self.model_dump(exclude={"file_type"})
            print(f"DEBUG: Route53 provider formatting {len(fields)} fields as env vars")
            print("DEBUG: Using environment variable format for AWS credentials")
        
        content = "\n".join(
            f"{key.upper()}={value!r}" 
            for key, value in self.model_dump(exclude={"file_type"}).items()
        ).encode("utf-8")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated {len(content)} bytes of environment variables")
            print("DEBUG: Variables will be uppercase as per AWS convention")
        
        return content

    @staticmethod
    def get_file_type() -> Literal["env"]:
        # Return the file type that the credentials should be written to.
        # Route53 provider uses environment variable format.
        # 
        # Returns:
        #     Literal type indicating env file extension
        return "env"


class SakuraCloudProvider(Provider):
    # Requires API token and secret for authentication.

    dns_sakuracloud_api_token: str
    dns_sakuracloud_api_secret: str

    _validate_aliases = alias_model_validator(
        {
            "dns_sakuracloud_api_token": (
                "dns_sakuracloud_api_token", "sakuracloud_api_token", 
                "api_token"
            ),
            "dns_sakuracloud_api_secret": (
                "dns_sakuracloud_api_secret", "sakuracloud_api_secret", 
                "api_secret"
            ),
        }
    )


class ScalewayProvider(Provider):
    # Requires an application token for authentication.

    dns_scaleway_application_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_scaleway_application_token": (
                "dns_scaleway_application_token", "scaleway_application_token", 
                "application_token"
            ),
        }
    )


class NjallaProvider(Provider):
    # Requires an API token for authentication.

    dns_njalla_token: str

    _validate_aliases = alias_model_validator(
        {
            "dns_njalla_token": (
                "dns_njalla_token", "njalla_token", "token", "api_token", 
                "auth_token"
            ),
        }
    )


class WildcardGenerator:
    # Manages the generation of wildcard domains across domain groups.
    # Handles grouping of domains and automatic wildcard pattern generation
    # for efficient certificate management across multiple subdomains.

    def __init__(self):
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print("DEBUG: Initializing WildcardGenerator")
            print("DEBUG: Setting up empty domain groups and wildcard storage")
        
        # Stores raw domains grouped by identifier
        self.__domain_groups = {}
        # Stores generated wildcard patterns  
        self.__wildcards = {}
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print("DEBUG: WildcardGenerator initialized with empty groups")
            print("DEBUG: Ready to accept domain groups for wildcard generation")

    def extend(self, group: str, domains: List[str], email: str, 
               staging: bool = False):
        # Add domains to a group and regenerate wildcards.
        # Organizes domains by group and environment for wildcard generation.
        # 
        # Args:
        #     group: Group identifier for these domains
        #     domains: List of domains to add
        #     email: Contact email for this domain group
        #     staging: Whether these domains are for staging environment
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Extending group '{group}' with {len(domains)} domains")
            print(f"DEBUG: Environment: {'staging' if staging else 'production'}")
            print(f"DEBUG: Contact email: {email}")
            print(f"DEBUG: Domain list: {domains}")
        
        # Initialize group if it doesn't exist
        if group not in self.__domain_groups:
            self.__domain_groups[group] = {
                "staging": set(), 
                "prod": set(), 
                "email": email
            }
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                print(f"DEBUG: Created new domain group '{group}'")
                print("DEBUG: Group initialized with empty staging and prod sets")

        # Add domains to appropriate environment
        env_type = "staging" if staging else "prod"
        domains_added = 0
        for domain in domains:
            if domain := domain.strip():
                self.__domain_groups[group][env_type].add(domain)
                domains_added += 1

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Added {domains_added} valid domains to {env_type} environment")
            total_staging = len(self.__domain_groups[group]["staging"])
            total_prod = len(self.__domain_groups[group]["prod"])
            print(f"DEBUG: Group '{group}' totals: {total_staging} staging, {total_prod} prod domains")

        # Regenerate wildcards after adding new domains
        self.__generate_wildcards(staging)

    def __generate_wildcards(self, staging: bool = False):
        # Generate wildcard patterns for the specified environment.
        # Creates optimized wildcard certificates that cover multiple 
        # subdomains.
        # 
        # Args:
        #     staging: Whether to generate wildcards for staging environment
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            env_type = "staging" if staging else "prod"
            print(f"DEBUG: Generating wildcards for {env_type} environment")
            print(f"DEBUG: Processing {len(self.__domain_groups)} domain groups")
            print("DEBUG: Will convert subdomains to wildcard patterns")
        
        self.__wildcards.clear()
        env_type = "staging" if staging else "prod"
        wildcards_generated = 0

        # Process each domain group
        for group, types in self.__domain_groups.items():
            if group not in self.__wildcards:
                self.__wildcards[group] = {
                    "staging": set(), 
                    "prod": set(), 
                    "email": types["email"]
                }

            # Process each domain in the group
            for domain in types[env_type]:
                # Convert domain to wildcards and add to appropriate group
                self.__add_domain_wildcards(domain, group, env_type)
                wildcards_generated += 1

        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated wildcard patterns for {wildcards_generated} domains")
            print("DEBUG: Wildcard generation completed")

    def __add_domain_wildcards(self, domain: str, group: str, env_type: str):
        # Convert a domain to wildcard patterns and add to the wildcards 
        # collection. Determines optimal wildcard patterns based on domain 
        # structure.
        # 
        # Args:
        #     domain: Domain to process
        #     group: Group identifier  
        #     env_type: Environment type (staging or prod)
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Processing domain '{domain}' for wildcard patterns")
        
        parts = domain.split(".")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Domain has {len(parts)} parts: {parts}")
            print("DEBUG: Analyzing domain structure for wildcard generation")

        # Handle subdomains (domains with more than 2 parts)
        if len(parts) > 2:
            # Create wildcard for the base domain (e.g., *.example.com)
            base_domain = ".".join(parts[1:])
            wildcard_domain = f"*.{base_domain}"
            
            self.__wildcards[group][env_type].add(wildcard_domain)
            self.__wildcards[group][env_type].add(base_domain)
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                print(f"DEBUG: Subdomain detected - created wildcard '{wildcard_domain}'")
                print(f"DEBUG: Also added base domain '{base_domain}'")
                print("DEBUG: Wildcard will cover all subdomains of base")
        else:
            # Just add the raw domain for top-level domains
            self.__wildcards[group][env_type].add(domain)
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                print(f"DEBUG: Top-level domain - added '{domain}' directly")
                print("DEBUG: No wildcard needed for top-level domain")

    def get_wildcards(self) -> Dict[str, Dict[Literal["staging", "prod", 
                                                     "email"], str]]:
        # Get formatted wildcard domains for each group.
        # Returns organized wildcard data ready for certificate generation.
        # 
        # Returns:
        #     Dictionary of group data with formatted wildcard domains
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Formatting wildcards for {len(self.__wildcards)} groups")
            print("DEBUG: Converting wildcard sets to comma-separated strings")
        
        result = {}
        total_domains = 0
        
        for group, data in self.__wildcards.items():
            result[group] = {"email": data["email"]}
            
            for env_type in ("staging", "prod"):
                if domains := data[env_type]:
                    # Sort domains with wildcards first
                    sorted_domains = sorted(domains, key=lambda x: x[0] != "*")
                    result[group][env_type] = ",".join(sorted_domains)
                    total_domains += len(domains)
                    
                    if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                        print(f"DEBUG: Group '{group}' {env_type}: {len(domains)} domains")
                        print(f"DEBUG: Sorted with wildcards first: {sorted_domains[:3]}...")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Formatted {total_domains} total wildcard domains")
            print("DEBUG: Ready for certificate generation")
        
        return result

    @staticmethod
    def extract_wildcards_from_domains(domains: List[str]) -> List[str]:
        # Generate wildcard patterns from a list of domains.
        # Static method for generating wildcards without managing groups.
        # 
        # Args:
        #     domains: List of domains to process
        #     
        # Returns:
        #     List of extracted wildcard domains
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Extracting wildcards from {len(domains)} domains")
            print(f"DEBUG: Input domains: {domains}")
            print("DEBUG: Static method - no group management")
        
        wildcards = set()
        
        for domain in domains:
            parts = domain.split(".")
            
            if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                print(f"DEBUG: Processing '{domain}' with {len(parts)} parts")
            
            # Generate wildcards for subdomains
            if len(parts) > 2:
                base_domain = ".".join(parts[1:])
                wildcards.add(f"*.{base_domain}")
                wildcards.add(base_domain)
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    print(f"DEBUG: Added wildcard *.{base_domain} and base {base_domain}")
            else:
                # Just add the domain for top-level domains
                wildcards.add(domain)
                if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
                    print(f"DEBUG: Added top-level domain {domain} directly")

        # Sort with wildcards first
        result = sorted(wildcards, key=lambda x: x[0] != "*")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Generated {len(result)} wildcard patterns")
            print(f"DEBUG: Final result: {result}")
        
        return result

    @staticmethod
    def get_base_domain(domain: str) -> str:
        # Extract the base domain from a domain name.
        # Removes wildcard prefix if present to get the actual domain.
        # 
        # Args:
        #     domain: Input domain name
        #     
        # Returns:
        #     Base domain (without wildcard prefix if present)
        base = domain.lstrip("*.")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            if domain != base:
                print(f"DEBUG: Extracted base domain '{base}' from wildcard '{domain}'")
            else:
                print(f"DEBUG: Domain '{domain}' is already a base domain")
        
        return base

    @staticmethod
    def create_group_name(domain: str, provider: str, challenge_type: str, 
                         staging: bool, content_hash: str, 
                         profile: str = "classic") -> str:
        # Generate a consistent group name for wildcards.
        # Creates a unique identifier for grouping related wildcard 
        # certificates.
        # 
        # Args:
        #     domain: The domain name
        #     provider: DNS provider name or 'http' for HTTP challenge
        #     challenge_type: Challenge type (dns or http)
        #     staging: Whether this is for staging environment
        #     content_hash: Hash of credential content
        #     profile: Certificate profile (classic, tlsserver or shortlived)
        #     
        # Returns:
        #     A formatted group name string
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Creating group name for domain '{domain}'")
            print(f"DEBUG: Provider: {provider}, Challenge: {challenge_type}")
            print(f"DEBUG: Environment: {'staging' if staging else 'production'}")
            print(f"DEBUG: Profile: {profile}")
            print(f"DEBUG: Content hash: {content_hash[:10]}... (truncated)")
        
        # Extract base domain and format it for the group name
        base_domain = WildcardGenerator.get_base_domain(domain).replace(".", 
                                                                       "-")
        env = "staging" if staging else "prod"

        # Use provider name for DNS challenge, otherwise use 'http'
        challenge_identifier = provider if challenge_type == "dns" else "http"

        group_name = (f"{challenge_identifier}_{env}_{profile}_{base_domain}_"
                     f"{content_hash}")
        
        if getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
            print(f"DEBUG: Base domain formatted: {base_domain}")
            print(f"DEBUG: Challenge identifier: {challenge_identifier}")
            print(f"DEBUG: Generated group name: '{group_name}'")
            print("DEBUG: Group name ensures consistent certificate grouping")
        
        return group_name