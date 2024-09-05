#!/usr/bin/env python3

"""Analyze the test outcomes from a full CI run.

This script can also run on outcomes from a partial run, but the results are
less likely to be useful.
"""

import argparse
import sys
import traceback
import re
import subprocess
import os
import typing

import check_test_cases


# `ComponentOutcomes` is a named tuple which is defined as:
# ComponentOutcomes(
#     successes = {
#         "<suite_case>",
#         ...
#     },
#     failures = {
#         "<suite_case>",
#         ...
#     }
# )
# suite_case = "<suite>;<case>"
ComponentOutcomes = typing.NamedTuple('ComponentOutcomes',
                                      [('successes', typing.Set[str]),
                                       ('failures', typing.Set[str])])

# `Outcomes` is a representation of the outcomes file,
# which defined as:
# Outcomes = {
#     "<component>": ComponentOutcomes,
#     ...
# }
Outcomes = typing.Dict[str, ComponentOutcomes]


class Results:
    """Process analysis results."""

    def __init__(self):
        self.error_count = 0
        self.warning_count = 0

    def new_section(self, fmt, *args, **kwargs):
        self._print_line('\n*** ' + fmt + ' ***\n', *args, **kwargs)

    def info(self, fmt, *args, **kwargs):
        self._print_line('Info: ' + fmt, *args, **kwargs)

    def error(self, fmt, *args, **kwargs):
        self.error_count += 1
        self._print_line('Error: ' + fmt, *args, **kwargs)

    def warning(self, fmt, *args, **kwargs):
        self.warning_count += 1
        self._print_line('Warning: ' + fmt, *args, **kwargs)

    @staticmethod
    def _print_line(fmt, *args, **kwargs):
        sys.stderr.write((fmt + '\n').format(*args, **kwargs))

def execute_reference_driver_tests(results: Results, ref_component: str, driver_component: str, \
                                   outcome_file: str) -> None:
    """Run the tests specified in ref_component and driver_component. Results
    are stored in the output_file and they will be used for the following
    coverage analysis"""
    results.new_section("Test {} and {}", ref_component, driver_component)

    shell_command = "tests/scripts/all.sh --outcome-file " + outcome_file + \
                    " " + ref_component + " " + driver_component
    results.info("Running: {}", shell_command)
    ret_val = subprocess.run(shell_command.split(), check=False).returncode

    if ret_val != 0:
        results.error("failed to run reference/driver components")

def analyze_coverage(results: Results, outcomes: Outcomes,
                     allow_list: typing.List[str], full_coverage: bool) -> None:
    """Check that all available test cases are executed at least once."""
    # Make sure that the generated data files are present (and up-to-date).
    # This allows analyze_outcomes.py to run correctly on a fresh Git
    # checkout.
    cp = subprocess.run(['make', 'generated_files'],
                        cwd='tests',
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        check=False)
    if cp.returncode != 0:
        sys.stderr.write(cp.stdout.decode('utf-8'))
        results.error("Failed \"make generated_files\" in tests. "
                      "Coverage analysis may be incorrect.")
    available = check_test_cases.collect_available_test_cases()
    for suite_case in available:
        hit = any(suite_case in comp_outcomes.successes or
                  suite_case in comp_outcomes.failures
                  for comp_outcomes in outcomes.values())

        if not hit and suite_case not in allow_list:
            if full_coverage:
                results.error('Test case not executed: {}', suite_case)
            else:
                results.warning('Test case not executed: {}', suite_case)
        elif hit and suite_case in allow_list:
            # Test Case should be removed from the allow list.
            if full_coverage:
                results.error('Allow listed test case was executed: {}', suite_case)
            else:
                results.warning('Allow listed test case was executed: {}', suite_case)

def name_matches_pattern(name: str, str_or_re) -> bool:
    """Check if name matches a pattern, that may be a string or regex.
    - If the pattern is a string, name must be equal to match.
    - If the pattern is a regex, name must fully match.
    """
    # The CI's python is too old for re.Pattern
    #if isinstance(str_or_re, re.Pattern):
    if not isinstance(str_or_re, str):
        return str_or_re.fullmatch(name) is not None
    else:
        return str_or_re == name

def analyze_driver_vs_reference(results: Results, outcomes: Outcomes,
                                component_ref: str, component_driver: str,
                                ignored_suites: typing.List[str], ignored_tests=None) -> None:
    """Check that all tests passing in the reference component are also
    passing in the corresponding driver component.
    Skip:
    - full test suites provided in ignored_suites list
    - only some specific test inside a test suite, for which the corresponding
      output string is provided
    """
    ref_outcomes = outcomes.get("component_" + component_ref)
    driver_outcomes = outcomes.get("component_" + component_driver)

    if ref_outcomes is None or driver_outcomes is None:
        results.error("required components are missing: bad outcome file?")
        return

    if not ref_outcomes.successes:
        results.error("no passing test in reference component: bad outcome file?")
        return

    for suite_case in ref_outcomes.successes:
        # suite_case is like "test_suite_foo.bar;Description of test case"
        (full_test_suite, test_string) = suite_case.split(';')
        test_suite = full_test_suite.split('.')[0] # retrieve main part of test suite name

        # Immediately skip fully-ignored test suites
        if test_suite in ignored_suites or full_test_suite in ignored_suites:
            continue

        # For ignored test cases inside test suites, just remember and:
        # don't issue an error if they're skipped with drivers,
        # but issue an error if they're not (means we have a bad entry).
        ignored = False
        for str_or_re in (ignored_tests.get(full_test_suite, []) +
                          ignored_tests.get(test_suite, [])):
            if name_matches_pattern(test_string, str_or_re):
                ignored = True

        if not ignored and not suite_case in driver_outcomes.successes:
            results.error("PASS -> SKIP/FAIL: {}", suite_case)
        if ignored and suite_case in driver_outcomes.successes:
            results.error("uselessly ignored: {}", suite_case)

def analyze_outcomes(results: Results, outcomes: Outcomes, args) -> None:
    """Run all analyses on the given outcome collection."""
    analyze_coverage(results, outcomes, args['allow_list'],
                     args['full_coverage'])

def read_outcome_file(outcome_file: str) -> Outcomes:
    """Parse an outcome file and return an outcome collection.
    """
    outcomes = {}
    with open(outcome_file, 'r', encoding='utf-8') as input_file:
        for line in input_file:
            (_platform, component, suite, case, result, _cause) = line.split(';')
            # Note that `component` is not unique. If a test case passes on Linux
            # and fails on FreeBSD, it'll end up in both the successes set and
            # the failures set.
            suite_case = ';'.join([suite, case])
            if component not in outcomes:
                outcomes[component] = ComponentOutcomes(set(), set())
            if result == 'PASS':
                outcomes[component].successes.add(suite_case)
            elif result == 'FAIL':
                outcomes[component].failures.add(suite_case)

    return outcomes

def do_analyze_coverage(results: Results, outcomes: Outcomes, args) -> None:
    """Perform coverage analysis."""
    results.new_section("Analyze coverage")
    analyze_outcomes(results, outcomes, args)

def do_analyze_driver_vs_reference(results: Results, outcomes: Outcomes, args) -> None:
    """Perform driver vs reference analyze."""
    results.new_section("Analyze driver {} vs reference {}",
                        args['component_driver'], args['component_ref'])

    ignored_suites = ['test_suite_' + x for x in args['ignored_suites']]

    analyze_driver_vs_reference(results, outcomes,
                                args['component_ref'], args['component_driver'],
                                ignored_suites, args['ignored_tests'])

# List of tasks with a function that can handle this task and additional arguments if required
KNOWN_TASKS = {
    'analyze_coverage':                 {
        'test_function': do_analyze_coverage,
        'args': {
            'allow_list': [
                # Algorithm not supported yet
                'test_suite_psa_crypto_metadata;Asymmetric signature: pure EdDSA',
                # Algorithm not supported yet
                'test_suite_psa_crypto_metadata;Cipher: XTS',
            ],
            'full_coverage': False,
        }
    },
    # There are 2 options to use analyze_driver_vs_reference_xxx locally:
    # 1. Run tests and then analysis:
    #   - tests/scripts/all.sh --outcome-file "$PWD/out.csv" <component_ref> <component_driver>
    #   - tests/scripts/analyze_outcomes.py out.csv analyze_driver_vs_reference_xxx
    # 2. Let this script run both automatically:
    #   - tests/scripts/analyze_outcomes.py out.csv analyze_driver_vs_reference_xxx
    'analyze_driver_vs_reference_hash': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_hash_use_psa',
            'component_driver': 'test_psa_crypto_config_accel_hash_use_psa',
            'ignored_suites': [
                'shax', 'mdx', # the software implementations that are being excluded
                'md.psa',  # purposefully depends on whether drivers are present
                'psa_crypto_low_hash.generated', # testing the builtins
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(MD5|RIPEMD160|SHA[0-9]+)_.*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_hmac': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_hmac',
            'component_driver': 'test_psa_crypto_config_accel_hmac',
            'ignored_suites': [
                # These suites require legacy hash support, which is disabled
                # in the accelerated component.
                'shax', 'mdx',
                # This suite tests builtins directly, but these are missing
                # in the accelerated case.
                'psa_crypto_low_hash.generated',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(MD5|RIPEMD160|SHA[0-9]+)_.*'),
                    re.compile(r'.*\bMBEDTLS_MD_C\b')
                ],
                'test_suite_md': [
                    # Builtin HMAC is not supported in the accelerate component.
                    re.compile('.*HMAC.*'),
                    # Following tests make use of functions which are not available
                    # when MD_C is disabled, as it happens in the accelerated
                    # test component.
                    re.compile('generic .* Hash file .*'),
                    'MD list',
                ],
                'test_suite_md.psa': [
                    # "legacy only" tests require hash algorithms to be NOT
                    # accelerated, but this of course false for the accelerated
                    # test component.
                    re.compile('PSA dispatch .* legacy only'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_cipher_aead_cmac': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_cipher_aead_cmac',
            'component_driver': 'test_psa_crypto_config_accel_cipher_aead_cmac',
            # Modules replaced by drivers.
            'ignored_suites': [
                # low-level (block/stream) cipher modules
                'aes', 'aria', 'camellia', 'des', 'chacha20',
                # AEAD modes and CMAC
                'ccm', 'chachapoly', 'cmac', 'gcm',
                # The Cipher abstraction layer
                'cipher',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(AES|ARIA|CAMELLIA|CHACHA20|DES)_.*'),
                    re.compile(r'.*\bMBEDTLS_(CCM|CHACHAPOLY|CMAC|GCM)_.*'),
                    re.compile(r'.*\bMBEDTLS_AES(\w+)_C\b.*'),
                    re.compile(r'.*\bMBEDTLS_CIPHER_.*'),
                ],
                # PEM decryption is not supported so far.
                # The rest of PEM (write, unencrypted read) works though.
                'test_suite_pem': [
                    re.compile(r'PEM read .*(AES|DES|\bencrypt).*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # Following tests depend on AES_C/DES_C but are not about
                # them really, just need to know some error code is there.
                'test_suite_error': [
                    'Low and high error',
                    'Single low error'
                ],
                # Similar to test_suite_error above.
                'test_suite_version': [
                    'Check for MBEDTLS_AES_C when already present',
                ],
                # The en/decryption part of PKCS#12 is not supported so far.
                # The rest of PKCS#12 (key derivation) works though.
                'test_suite_pkcs12': [
                    re.compile(r'PBE Encrypt, .*'),
                    re.compile(r'PBE Decrypt, .*'),
                ],
                # The en/decryption part of PKCS#5 is not supported so far.
                # The rest of PKCS#5 (PBKDF2) works though.
                'test_suite_pkcs5': [
                    re.compile(r'PBES2 Encrypt, .*'),
                    re.compile(r'PBES2 Decrypt .*'),
                ],
                # Encrypted keys are not supported so far.
                # pylint: disable=line-too-long
                'test_suite_pkparse': [
                    'Key ASN1 (Encrypted key PKCS12, trailing garbage data)',
                    'Key ASN1 (Encrypted key PKCS5, trailing garbage data)',
                    re.compile(r'Parse (RSA|EC) Key .*\(.* ([Ee]ncrypted|password).*\)'),
                ],
                # Encrypted keys are not supported so far.
                'ssl-opt': [
                    'TLS: password protected server key',
                    'TLS: password protected client key',
                    'TLS: password protected server key, two certificates',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ecp_light_only': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_ecp_light_only',
            'component_driver': 'test_psa_crypto_config_accel_ecc_ecp_light_only',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecdsa', 'ecdh', 'ecjpake',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(ECDH|ECDSA|ECJPAKE|ECP)_.*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # This test wants a legacy function that takes f_rng, p_rng
                # arguments, and uses legacy ECDSA for that. The test is
                # really about the wrapper around the PSA RNG, not ECDSA.
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                # In the accelerated test ECP_C is not set (only ECP_LIGHT is)
                # so we must ignore disparities in the tests for which ECP_C
                # is required.
                'test_suite_ecp': [
                    re.compile(r'ECP check public-private .*'),
                    re.compile(r'ECP calculate public: .*'),
                    re.compile(r'ECP gen keypair .*'),
                    re.compile(r'ECP point muladd .*'),
                    re.compile(r'ECP point multiplication .*'),
                    re.compile(r'ECP test vectors .*'),
                ],
                'test_suite_ssl': [
                    # This deprecated function is only present when ECP_C is On.
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_no_ecp_at_all': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_no_ecp_at_all',
            'component_driver': 'test_psa_crypto_config_accel_ecc_no_ecp_at_all',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(ECDH|ECDSA|ECJPAKE|ECP)_.*'),
                    re.compile(r'.*\bMBEDTLS_PK_PARSE_EC_COMPRESSED\b.*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                'test_suite_pkparse': [
                    # When PK_PARSE_C and ECP_C are defined then PK_PARSE_EC_COMPRESSED
                    # is automatically enabled in build_info.h (backward compatibility)
                    # even if it is disabled in config_psa_crypto_no_ecp_at_all(). As a
                    # consequence compressed points are supported in the reference
                    # component but not in the accelerated one, so they should be skipped
                    # while checking driver's coverage.
                    re.compile(r'Parse EC Key .*compressed\)'),
                    re.compile(r'Parse Public EC Key .*compressed\)'),
                ],
                # See ecp_light_only
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ecc_no_bignum': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_no_bignum',
            'component_driver': 'test_psa_crypto_config_accel_ecc_no_bignum',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake',
                'bignum_core', 'bignum_random', 'bignum_mod', 'bignum_mod_raw',
                'bignum.generated', 'bignum.misc',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_BIGNUM_C\b.*'),
                    re.compile(r'.*\bMBEDTLS_(ECDH|ECDSA|ECJPAKE|ECP)_.*'),
                    re.compile(r'.*\bMBEDTLS_PK_PARSE_EC_COMPRESSED\b.*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                # See no_ecp_at_all
                'test_suite_pkparse': [
                    re.compile(r'Parse EC Key .*compressed\)'),
                    re.compile(r'Parse Public EC Key .*compressed\)'),
                ],
                'test_suite_asn1parse': [
                    'INTEGER too large for mpi',
                ],
                'test_suite_asn1write': [
                    re.compile(r'ASN.1 Write mpi.*'),
                ],
                'test_suite_debug': [
                    re.compile(r'Debug print mbedtls_mpi.*'),
                ],
                # See ecp_light_only
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ecc_ffdh_no_bignum': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ecc_ffdh_no_bignum',
            'component_driver': 'test_psa_crypto_config_accel_ecc_ffdh_no_bignum',
            'ignored_suites': [
                # Modules replaced by drivers
                'ecp', 'ecdsa', 'ecdh', 'ecjpake', 'dhm',
                'bignum_core', 'bignum_random', 'bignum_mod', 'bignum_mod_raw',
                'bignum.generated', 'bignum.misc',
            ],
            'ignored_tests': {
                'ssl-opt': [
                    # DHE support in TLS 1.2 requires built-in MBEDTLS_DHM_C
                    # (because it needs custom groups, which PSA does not
                    # provide), even with MBEDTLS_USE_PSA_CRYPTO.
                    re.compile(r'PSK callback:.*\bdhe-psk\b.*'),
                ],
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_BIGNUM_C\b.*'),
                    re.compile(r'.*\bMBEDTLS_DHM_C\b.*'),
                    re.compile(r'.*\bMBEDTLS_(ECDH|ECDSA|ECJPAKE|ECP)_.*'),
                    re.compile(r'.*\bMBEDTLS_KEY_EXCHANGE_DHE_PSK_ENABLED\b.*'),
                    re.compile(r'.*\bMBEDTLS_PK_PARSE_EC_COMPRESSED\b.*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
                # See no_ecp_at_all
                'test_suite_pkparse': [
                    re.compile(r'Parse EC Key .*compressed\)'),
                    re.compile(r'Parse Public EC Key .*compressed\)'),
                ],
                'test_suite_asn1parse': [
                    'INTEGER too large for mpi',
                ],
                'test_suite_asn1write': [
                    re.compile(r'ASN.1 Write mpi.*'),
                ],
                'test_suite_debug': [
                    re.compile(r'Debug print mbedtls_mpi.*'),
                ],
                # See ecp_light_only
                'test_suite_ssl': [
                    'Test configuration of groups for DHE through mbedtls_ssl_conf_curves()',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_ffdh_alg': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_ffdh',
            'component_driver': 'test_psa_crypto_config_accel_ffdh',
            'ignored_suites': ['dhm'],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_DHM_C\b.*'),
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_tfm_config': {
        'test_function':  do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_tfm_config',
            'component_driver': 'test_tfm_config_p256m_driver_accel_ec',
            'ignored_suites': [
                # Modules replaced by drivers
                'asn1parse', 'asn1write',
                'ecp', 'ecdsa', 'ecdh', 'ecjpake',
                'bignum_core', 'bignum_random', 'bignum_mod', 'bignum_mod_raw',
                'bignum.generated', 'bignum.misc',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_BIGNUM_C\b.*'),
                    re.compile(r'.*\bMBEDTLS_(ASN1\w+)_C\b.*'),
                    re.compile(r'.*\bMBEDTLS_(ECDH|ECDSA|ECP)_.*'),
                    re.compile(r'.*\bMBEDTLS_PSA_P256M_DRIVER_ENABLED\b.*')
                ],
                'test_suite_config.crypto_combinations': [
                    'Config: ECC: Weierstrass curves only',
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # See ecp_light_only
                'test_suite_random': [
                    'PSA classic wrapper: ECDSA signature (SECP256R1)',
                ],
            }
        }
    },
    'analyze_driver_vs_reference_rsa': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_psa_crypto_config_reference_rsa_crypto',
            'component_driver': 'test_psa_crypto_config_accel_rsa_crypto',
            'ignored_suites': [
                # Modules replaced by drivers.
                'rsa', 'pkcs1_v15', 'pkcs1_v21',
                # We temporarily don't care about PK stuff.
                'pk', 'pkwrite', 'pkparse'
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(PKCS1|RSA)_.*'),
                    re.compile(r'.*\bMBEDTLS_GENPRIME\b.*')
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
                # Following tests depend on RSA_C but are not about
                # them really, just need to know some error code is there.
                'test_suite_error': [
                    'Low and high error',
                    'Single high error'
                ],
                # Constant time operations only used for PKCS1_V15
                'test_suite_constant_time': [
                    re.compile(r'mbedtls_ct_zeroize_if .*'),
                    re.compile(r'mbedtls_ct_memmove_left .*')
                ],
                'test_suite_psa_crypto': [
                    # We don't support generate_key_custom entry points
                    # in drivers yet.
                    re.compile(r'PSA generate key custom: RSA, e=.*'),
                    re.compile(r'PSA generate key ext: RSA, e=.*'),
                ],
            }
        }
    },
    'analyze_block_cipher_dispatch': {
        'test_function': do_analyze_driver_vs_reference,
        'args': {
            'component_ref': 'test_full_block_cipher_legacy_dispatch',
            'component_driver': 'test_full_block_cipher_psa_dispatch',
            'ignored_suites': [
                # Skipped in the accelerated component
                'aes', 'aria', 'camellia',
                # These require AES_C, ARIA_C or CAMELLIA_C to be enabled in
                # order for the cipher module (actually cipher_wrapper) to work
                # properly. However these symbols are disabled in the accelerated
                # component so we ignore them.
                'cipher.ccm', 'cipher.gcm', 'cipher.aes', 'cipher.aria',
                'cipher.camellia',
            ],
            'ignored_tests': {
                'test_suite_config': [
                    re.compile(r'.*\bMBEDTLS_(AES|ARIA|CAMELLIA)_.*'),
                    re.compile(r'.*\bMBEDTLS_AES(\w+)_C\b.*'),
                ],
                'test_suite_cmac': [
                    # Following tests require AES_C/ARIA_C/CAMELLIA_C to be enabled,
                    # but these are not available in the accelerated component.
                    'CMAC null arguments',
                    re.compile('CMAC.* (AES|ARIA|Camellia).*'),
                ],
                'test_suite_cipher.padding': [
                    # Following tests require AES_C/CAMELLIA_C to be enabled,
                    # but these are not available in the accelerated component.
                    re.compile('Set( non-existent)? padding with (AES|CAMELLIA).*'),
                ],
                'test_suite_pkcs5': [
                    # The AES part of PKCS#5 PBES2 is not yet supported.
                    # The rest of PKCS#5 (PBKDF2) works, though.
                    re.compile(r'PBES2 .* AES-.*')
                ],
                'test_suite_pkparse': [
                    # PEM (called by pkparse) requires AES_C in order to decrypt
                    # the key, but this is not available in the accelerated
                    # component.
                    re.compile('Parse RSA Key.*(password|AES-).*'),
                ],
                'test_suite_pem': [
                    # Following tests require AES_C, but this is diabled in the
                    # accelerated component.
                    re.compile('PEM read .*AES.*'),
                    'PEM read (unknown encryption algorithm)',
                ],
                'test_suite_error': [
                    # Following tests depend on AES_C but are not about them
                    # really, just need to know some error code is there.
                    'Single low error',
                    'Low and high error',
                ],
                'test_suite_version': [
                    # Similar to test_suite_error above.
                    'Check for MBEDTLS_AES_C when already present',
                ],
                'test_suite_platform': [
                    # Incompatible with sanitizers (e.g. ASan). If the driver
                    # component uses a sanitizer but the reference component
                    # doesn't, we have a PASS vs SKIP mismatch.
                    'Check mbedtls_calloc overallocation',
                ],
            }
        }
    }
}

def main():
    main_results = Results()

    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('outcomes', metavar='OUTCOMES.CSV',
                            help='Outcome file to analyze')
        parser.add_argument('specified_tasks', default='all', nargs='?',
                            help='Analysis to be done. By default, run all tasks. '
                                 'With one or more TASK, run only those. '
                                 'TASK can be the name of a single task or '
                                 'comma/space-separated list of tasks. ')
        parser.add_argument('--list', action='store_true',
                            help='List all available tasks and exit.')
        parser.add_argument('--require-full-coverage', action='store_true',
                            dest='full_coverage', help="Require all available "
                            "test cases to be executed and issue an error "
                            "otherwise. This flag is ignored if 'task' is "
                            "neither 'all' nor 'analyze_coverage'")
        options = parser.parse_args()

        if options.list:
            for task in KNOWN_TASKS:
                print(task)
            sys.exit(0)

        if options.specified_tasks == 'all':
            tasks_list = KNOWN_TASKS.keys()
        else:
            tasks_list = re.split(r'[, ]+', options.specified_tasks)
            for task in tasks_list:
                if task not in KNOWN_TASKS:
                    sys.stderr.write('invalid task: {}\n'.format(task))
                    sys.exit(2)

        KNOWN_TASKS['analyze_coverage']['args']['full_coverage'] = options.full_coverage

        # If the outcome file exists, parse it once and share the result
        # among tasks to improve performance.
        # Otherwise, it will be generated by execute_reference_driver_tests.
        if not os.path.exists(options.outcomes):
            if len(tasks_list) > 1:
                sys.stderr.write("mutiple tasks found, please provide a valid outcomes file.\n")
                sys.exit(2)

            task_name = tasks_list[0]
            task = KNOWN_TASKS[task_name]
            if task['test_function'] != do_analyze_driver_vs_reference: # pylint: disable=comparison-with-callable
                sys.stderr.write("please provide valid outcomes file for {}.\n".format(task_name))
                sys.exit(2)

            execute_reference_driver_tests(main_results,
                                           task['args']['component_ref'],
                                           task['args']['component_driver'],
                                           options.outcomes)

        outcomes = read_outcome_file(options.outcomes)

        for task in tasks_list:
            test_function = KNOWN_TASKS[task]['test_function']
            test_args = KNOWN_TASKS[task]['args']
            test_function(main_results, outcomes, test_args)

        main_results.info("Overall results: {} warnings and {} errors",
                          main_results.warning_count, main_results.error_count)

        sys.exit(0 if (main_results.error_count == 0) else 1)

    except Exception: # pylint: disable=broad-except
        # Print the backtrace and exit explicitly with our chosen status.
        traceback.print_exc()
        sys.exit(120)

if __name__ == '__main__':
    main()
