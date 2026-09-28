#!/usr/bin/env python3

"""Analyze the test outcomes from a full CI run.

This script can also run on outcomes from a partial run, but the results are
less likely to be useful.
"""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

import re
import typing

import scripts_path # pylint: disable=unused-import
from mbedtls_framework import outcome_analysis

from project_knowledge import tf_psa_crypto_test_case_info


class CoverageTask(outcome_analysis.CoverageTask):
    """Justify test cases that are never executed."""

    # Tests that may not be covered by TF-PSA-Crypto testing, but are
    # covered by Mbed TLS testing.
    # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/740
    IGNORED_TESTS = {
        'test_suite_aes.xts': [
            re.compile('.*'),
        ],
        'test_suite_block_cipher': [
            re.compile('.*'),
        ],
        'test_suite_cipher.aes': [
            re.compile('.*XTS.*'),
        ],
        'test_suite_config.psa_boolean': [
            re.compile('.* !.*'),
            'Config: MBEDTLS_AES_ONLY_128_BIT_KEY_LENGTH',
            'Config: MBEDTLS_BLOCK_CIPHER_NO_DECRYPT',
            'Config: MBEDTLS_DEPRECATED_WARNING',
            'Config: MBEDTLS_ECDH_VARIANT_EVEREST_ENABLED',
            'Config: MBEDTLS_PSA_ASSUME_EXCLUSIVE_BUFFERS',
            'Config: MBEDTLS_PSA_CRYPTO_CLIENT',
            'Config: MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG',
            'Config: MBEDTLS_PSA_CRYPTO_KEY_ID_ENCODES_OWNER',
            'Config: MBEDTLS_PSA_P256M_DRIVER_ENABLED',
            'Config: MBEDTLS_PSA_STATIC_KEY_SLOTS',
            'Config: MBEDTLS_RSA_NO_CRT',
        ],
        'test_suite_config.psa_combinations': [
            'Config: PSA_WANT_ALG_ECDSA without PSA_WANT_ALG_DETERMINISTIC_ECDSA',
        ],
        'test_suite_ctr_drbg': [
            re.compile('.*AES-128.*'),
            'CTR_DRBG entropy strength: 128 bits',
        ],
        'test_suite_pk': [
            'PK size macro: MBEDTLS_PK_ECP_PRV_DER_MAX_BYTES: only curve is P-256',
            'PK size macro: MBEDTLS_PK_ECP_PUB_DER_MAX_BYTES: only curve is P-256',
            'PK size macro: MBEDTLS_PK_MAX_PUBKEY_RAW_LEN: RSA, !ECC',
        ],
        'test_suite_psa_crypto': [
            'PSA MAC setup: algorithm known but not supported, long key',
            'PSA MAC setup: algorithm known but not supported, short key',
            'PSA MAC setup: bad algorithm (unsupported HMAC hash algorithm)',
            'PSA generate key custom: RSA, e=3 with driver and no fallback (not yet supported)',
            'PSA generate key: RSA, key pair size does not fit in static key buffer',
            'PSA generate key: RSA, key pair size fits in static key buffer',
            'PSA sign hash int (ops=inf): det ECDSA not supported',
            'PSA sign hash int (ops=min): det ECDSA not supported',
            'PSA sign hash int: ECDSA not supported',
            'PSA sign hash: deterministic ECDSA not supported',
            'PSA sign message: deterministic ECDSA not supported',
            'PSA verify hash with keypair: deterministic ECDSA SECP256R1, only randomized supported', #pylint: disable=line-too-long
            'PSA verify hash: deterministic ECDSA SECP256R1, only randomized supported',
        ],
        'test_suite_psa_crypto_driver_wrappers': [
            re.compile('PSA MAC .*'),
            re.compile('PSA decrypt transparent driver: .*'),
            re.compile('PSA encrypt transparent driver: .*'),
            re.compile('PSA encrypt-decrypt transparent driver: .*'),
        ],
        'test_suite_psa_crypto_entropy': [
            'Fake entropy: more than one block in two steps',
            'Fake entropy: one block eventually',
            'Fake entropy: one block in two steps',
            re.compile('PSA external RNG failure: .*'),
        ],
        'test_suite_psa_crypto_not_supported.generated': [
            re.compile('.*'),
        ],
        'test_suite_psa_crypto_op_fail.generated': [
            re.compile('.* !.*'),
        ],
        'test_suite_psa_crypto_op_fail.misc': [
            'PSA sign DETERMINISTIC_ECDSA(SHA_256): !DETERMINISTIC_ECDSA but ECDSA with ECC_KEY_PAIR(SECP_R1)', #pylint: disable=line-too-long
            'PSA sign RSA_PSS(SHA_256): RSA_PSS not enabled, key pair',
        ],
        'test_suite_psa_crypto_persistent_key': [
            re.compile('Load key: owner=[^0].*'),
        ],
        'test_suite_psa_crypto_slot_management': [
            'Copy persistent to persistent, same id but different owner',
            'Create not supported',
            'Non reusable key slots integrity in case of key slot starvation',
        ],
        'test_suite_psa_crypto_storage_format.misc': [
            'PSA storage read: key larger than MBEDTLS_PSA_STATIC_KEY_SLOT_BUFFER_SIZE',
        ],
        'test_suite_random': [
            'PSA classic wrapper: HMAC_DRBG max',
            'PSA classic wrapper: external RNG large',
        ],
    }

    # Tests that are not covered for a tracked reason, and that
    # were also not covered by Mbed TLS testing as of Mbed TLS 4.1.0.
    UNCOVERED_TESTS = {
        'test_suite_config.crypto_combinations': [
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/805
            'Config: built-in SHA3: no SHAKE',
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/805
            'Config: built-in SHA3: no hash',
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/804
            'Config: no built-in AEAD',
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/804
            'Config: no built-in MAC',
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/804
            'Config: no built-in cipher',
            # We don't support any signature algorithm that isn't either
            # hash-then-sign or sign-short-message (raw RSA PKCS#1v1.5).
            # So we don't have built-in multipart signature entry points.
            'Config: some built-in multipart signature',
        ],
        'test_suite_config.psa_boolean': [
            # We don't test with HMAC disabled.
            # https://github.com/Mbed-TLS/mbedtls/issues/9591
            'Config: !PSA_WANT_ALG_HMAC',
            # The DERIVE key type is always enabled.
            'Config: !PSA_WANT_KEY_TYPE_DERIVE',
            # More granularity of key pair type enablement macros
            # than we care to test.
            # https://github.com/Mbed-TLS/mbedtls/issues/9590
            'Config: !PSA_WANT_KEY_TYPE_DH_KEY_PAIR_EXPORT',
            'Config: !PSA_WANT_KEY_TYPE_DH_KEY_PAIR_GENERATE',
            'Config: !PSA_WANT_KEY_TYPE_DH_KEY_PAIR_IMPORT',
            # More granularity of key pair type enablement macros
            # than we care to test.
            # https://github.com/Mbed-TLS/mbedtls/issues/9590
            'Config: !PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_EXPORT',
            'Config: !PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_IMPORT',
            # We don't test with HMAC disabled.
            # https://github.com/Mbed-TLS/mbedtls/issues/9591
            'Config: !PSA_WANT_KEY_TYPE_HMAC',
            # The PASSWORD key type is always enabled.
            'Config: !PSA_WANT_KEY_TYPE_PASSWORD',
            # The PASSWORD_HASH key type is always enabled.
            'Config: !PSA_WANT_KEY_TYPE_PASSWORD_HASH',
            # The RAW_DATA key type is always enabled.
            'Config: !PSA_WANT_KEY_TYPE_RAW_DATA',
            # More granularity of key pair type enablement macros
            # than we care to test.
            # https://github.com/Mbed-TLS/mbedtls/issues/9590
            'Config: !PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_EXPORT',
            'Config: !PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_IMPORT',
            # Algorithm declared but not supported.
            'Config: PSA_WANT_ALG_CBC_MAC',
            # Algorithm declared but not supported.
            'Config: PSA_WANT_ALG_XTS',
            # More granularity of key pair type enablement macros
            # than we care to test.
            # https://github.com/Mbed-TLS/mbedtls/issues/9590
            'Config: PSA_WANT_KEY_TYPE_DH_KEY_PAIR_DERIVE',
            'Config: PSA_WANT_KEY_TYPE_ECC_KEY_PAIR',
            'Config: PSA_WANT_KEY_TYPE_RSA_KEY_PAIR',
            'Config: PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_DERIVE',
            # https://github.com/Mbed-TLS/mbedtls/issues/9583
            'Config: !MBEDTLS_ECP_NIST_OPTIM',
            # We never test without the PSA client code. Should we?
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/112
            'Config: !MBEDTLS_PSA_CRYPTO_CLIENT',
                        # We only test multithreading with pthreads.
            # https://github.com/Mbed-TLS/mbedtls/issues/9584
            'Config: !MBEDTLS_THREADING_PTHREAD',
            # Built but not tested.
            # https://github.com/Mbed-TLS/mbedtls/issues/9587
            'Config: MBEDTLS_AES_USE_HARDWARE_ONLY',
            # Untested platform-specific optimizations.
            # https://github.com/Mbed-TLS/mbedtls/issues/9588
            'Config: MBEDTLS_HAVE_SSE2',
            # Untested aspect of the platform interface.
            # https://github.com/Mbed-TLS/mbedtls/issues/9589
            'Config: MBEDTLS_PLATFORM_NO_STD_FUNCTIONS',
            # In a client-server build, test_suite_config runs in the
            # client configuration, so it will never report
            # MBEDTLS_PSA_CRYPTO_SPM as enabled. That's ok.
            'Config: MBEDTLS_PSA_CRYPTO_SPM',
            # We don't test on armv8 yet.
            'Config: MBEDTLS_SHA256_USE_ARMV8_A_CRYPTO_ONLY',
            'Config: MBEDTLS_SHA512_USE_A64_CRYPTO_ONLY',
            # We don't run test_suite_config when we test this.
            # https://github.com/Mbed-TLS/mbedtls/issues/9586
            'Config: MBEDTLS_TEST_CONSTANT_FLOW_VALGRIND',
        ],
        'test_suite_config.psa_combinations': [
            # We don't test this unusual, but sensible configuration.
            # https://github.com/Mbed-TLS/mbedtls/issues/9592
            'Config: PSA_WANT_ALG_DETERMINSTIC_ECDSA without PSA_WANT_ALG_ECDSA',
        ],
        'test_suite_pkcs12': [
            # We never test with CBC/PKCS5/PKCS12 enabled but
            # PKCS7 padding disabled.
            # https://github.com/Mbed-TLS/mbedtls/issues/9580
            'PBE Decrypt, (Invalid padding & PKCS7 padding disabled)',
            'PBE Encrypt, pad = 8 (PKCS7 padding disabled)',
        ],
        'test_suite_pkcs5': [
            # We never test with CBC/PKCS5/PKCS12 enabled but
            # PKCS7 padding disabled.
            # https://github.com/Mbed-TLS/mbedtls/issues/9580
            'PBES2 Decrypt (Invalid padding & PKCS7 padding disabled)',
            'PBES2 Encrypt, pad=6 (PKCS7 padding disabled)',
            'PBES2 Encrypt, pad=8 (PKCS7 padding disabled)',
        ],
        'test_suite_psa_crypto': [
            # We don't test this unusual, but sensible configuration.
            # https://github.com/Mbed-TLS/mbedtls/issues/9592
            re.compile(r'.*ECDSA.*only deterministic supported'),
        ],
        'test_suite_psa_crypto_metadata': [
            # Algorithms declared but not supported.
            # https://github.com/Mbed-TLS/mbedtls/issues/9579
            'Asymmetric signature: Ed25519ph',
            'Asymmetric signature: Ed448ph',
            'Asymmetric signature: pure EdDSA',
            'Cipher: XTS',
            'MAC: CBC_MAC-3DES',
            'MAC: CBC_MAC-AES-128',
            'MAC: CBC_MAC-AES-192',
            'MAC: CBC_MAC-AES-256',
        ],
        'test_suite_psa_crypto_not_supported.generated': [
            # We never test with DH key support disabled but support
            # for a DH group enabled. The dependencies of these test
            # cases don't really make sense.
            # https://github.com/Mbed-TLS/mbedtls/issues/9574
            re.compile(r'PSA \w+ DH_.*type not supported'),
            # We only test partial support for DH with the 2048-bit group
            # enabled and the other groups disabled.
            # https://github.com/Mbed-TLS/mbedtls/issues/9575
            'PSA generate DH_KEY_PAIR(RFC7919) 2048-bit group not supported',
            'PSA import DH_KEY_PAIR(RFC7919) 2048-bit group not supported',
            'PSA import DH_PUBLIC_KEY(RFC7919) 2048-bit group not supported',
        ],
        'test_suite_psa_crypto_op_fail.generated': [
            # We don't test this unusual, but sensible configuration.
            # https://github.com/Mbed-TLS/mbedtls/issues/9592
            re.compile(r'.*: !ECDSA but DETERMINISTIC_ECDSA with ECC_.*'),
            # We never test with the HMAC algorithm enabled but the HMAC
            # key type disabled. Those dependencies don't really make sense.
            # https://github.com/Mbed-TLS/mbedtls/issues/9573
            re.compile(r'.* !HMAC with HMAC'),
            # We don't test with ECDH disabled but the key type enabled.
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/161
            re.compile(r'PSA key_agreement.* !ECDH with ECC_KEY_PAIR\(.*'),
            # We don't test with FFDH disabled but the key type enabled.
            # https://github.com/Mbed-TLS/TF-PSA-Crypto/issues/160
            re.compile(r'PSA key_agreement.* !FFDH with DH_KEY_PAIR\(.*'),
        ],
        'test_suite_psa_crypto_op_fail.misc': [
            # We don't test this unusual, but sensible configuration.
            # https://github.com/Mbed-TLS/mbedtls/issues/9592
            'PSA sign DETERMINISTIC_ECDSA(SHA_256): !ECDSA but DETERMINISTIC_ECDSA with ECC_KEY_PAIR(SECP_R1)', #pylint: disable=line-too-long
        ],
    }

    def __init__(self, options) -> None:
        super().__init__(options)
        self.internal_test_cases = outcome_analysis.TestCaseSet(
            tf_psa_crypto_test_case_info.INTERNAL_TEST_CASES)

    def note_ignored_test(self, results: outcome_analysis.Results,
                          test_suite: str, test_description: str) -> None:
        """Enforce that we don't tell Mbed TLS to ignore a test case that we also ignore."""
        super().note_ignored_test(results, test_suite, test_description)
        if self.internal_test_cases.contains(test_suite, test_description):
            results.error('Test case was ignored, but Mbed TLS will ignore it too: {};{}',
                          test_suite, test_description)


# List of tasks with a function that can handle this task and additional arguments if required
KNOWN_TASKS: typing.Dict[str, typing.Type[outcome_analysis.Task]] = {
    'analyze_coverage': CoverageTask,
}

if __name__ == '__main__':
    outcome_analysis.main(KNOWN_TASKS)
