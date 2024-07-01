#!/bin/bash
#
#

git clone https://github.com/SpiderLabs/owasp-modsecurity-crs.git owasp-v2

echo 'Include "owasp-v2/base_rules/*.conf"' >> basic_rules.conf
echo 'Include "owasp-v2/optional_rules/*.conf"' >> basic_rules.conf
echo 'Include "owasp-v2/experimental_rules/*.conf"' >> basic_rules.conf
echo 'Include "owasp-v2/slr_rules/modsecurity_crs_46_slr_et_xss_attacks.conf"' >> basic_rules.conf
echo 'Include "owasp-v2/slr_rules/modsecurity_crs_46_slr_et_sqli_attacks.conf"' >> basic_rules.conf
echo 'Include "owasp-v2/slr_rules/modsecurity_crs_46_slr_et_rfi_attacks.conf"' >> basic_rules.conf


# Content injection not support in modsec v3
rm owasp-v2/optional_rules/modsecurity_crs_43_csrf_protection.conf


# Slow dos is not yet supported
rm owasp-v2/experimental_rules/modsecurity_crs_11_slow_dos_protection.conf


# WEBSERVER_ERROR_LOG is not supported in v3.
cat owasp-v2/base_rules/modsecurity_crs_20_protocol_violations.conf | sed 's/SecRule WEBSERVER_ERROR_LOG/#SecRule WEBSERVER_ERROR_LOG/g' > owasp-v2/base_rules/modsecurity_crs_20_protocol_violations.conf.tmp
mv owasp-v2/base_rules/modsecurity_crs_20_protocol_violations.conf.tmp owasp-v2/base_rules/modsecurity_crs_20_protocol_violations.conf


# Apache specific configuration.
cat owasp-v2/optional_rules/modsecurity_crs_49_header_tagging.conf | sed 's/RequestHeader/#RequestHeader/g' > owasp-v2/optional_rules/modsecurity_crs_49_header_tagging.conf.tmp
mv owasp-v2/optional_rules/modsecurity_crs_49_header_tagging.conf.tmp owasp-v2/optional_rules/modsecurity_crs_49_header_tagging.conf

cat owasp-v2/optional_rules/modsecurity_crs_55_application_defects.conf | sed 's/Header edit/#Header edit/g' > owasp-v2/optional_rules/modsecurity_crs_55_application_defects.conf.tmp
mv owasp-v2/optional_rules/modsecurity_crs_55_application_defects.conf.tmp owasp-v2/optional_rules/modsecurity_crs_55_application_defects.conf

cat owasp-v2/experimental_rules/modsecurity_crs_42_csp_enforcement.conf | sed 's/Header set/#Header set/g' > owasp-v2/experimental_rules/modsecurity_crs_42_csp_enforcement.conf.tmp
mv owasp-v2/experimental_rules/modsecurity_crs_42_csp_enforcement.conf.tmp owasp-v2/experimental_rules/modsecurity_crs_42_csp_enforcement.conf


# Disables SecGeoLookupDb
cat owasp-v2/experimental_rules/modsecurity_crs_61_ip_forensics.conf | sed 's/SecGeoLookupDb/#SecGeoLookupDb/g' > owasp-v2/experimental_rules/modsecurity_crs_61_ip_forensics.conf.tmp
mv owasp-v2/experimental_rules/modsecurity_crs_61_ip_forensics.conf.tmp owasp-v2/experimental_rules/modsecurity_crs_61_ip_forensics.conf

cat owasp-v2/experimental_rules/modsecurity_crs_11_proxy_abuse.conf | sed 's/SecGeoLookupDb/#SecGeoLookupDb/g' > owasp-v2/experimental_rules/modsecurity_crs_11_proxy_abuse.conf.tmp
mv owasp-v2/experimental_rules/modsecurity_crs_11_proxy_abuse.conf.tmp owasp-v2/experimental_rules/modsecurity_crs_11_proxy_abuse.conf


# STREAM_OUTPUT_BODY is not supported
cat owasp-v2/experimental_rules/modsecurity_crs_40_appsensor_detection_point_2.9_honeytrap.conf | sed 's/SecRule STREAM_OUTPUT_BODY/#SecRule STREAM_OUTPUT_BODY/g' > owasp-v2/experimental_rules/modsecurity_crs_40_appsensor_detection_point_2.9_honeytrap.conf.tmp
mv owasp-v2/experimental_rules/modsecurity_crs_40_appsensor_detection_point_2.9_honeytrap.conf.tmp owasp-v2/experimental_rules/modsecurity_crs_40_appsensor_detection_point_2.9_honeytrap.conf


echo "Done."

