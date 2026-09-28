#!/usr/bin/env python3
"""Generate ML-DSA test cases.

This is a transitional script that does not handle different feature sets
in different states of TF-PSA-Crypto. The live version of this script
is `scripts/maintainer/generate_mldsa_tests.py` in TF-PSA-Crypto.
"""

import sys

import scripts_path # pylint: disable=unused-import
from mbedtls_framework import test_data_generation
from mbedtls_maintainer import mldsa_test_generator

class MLDSATestGenerator(test_data_generation.TestGenerator):
    """Generate test cases for ML-DSA."""

    def __init__(self, settings) -> None:
        self.targets = {
            'test_suite_pqcp_mldsa.dilithium_py': mldsa_test_generator.gen_pqcp_mldsa_all,
        }
        super().__init__(settings)


if __name__ == '__main__':
    test_data_generation.main(sys.argv[1:], __doc__, MLDSATestGenerator)
