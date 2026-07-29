"""Information about TF-PSA-Crypto test cases that Mbed TLS can access."""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

# This module can be loaded either from a TF-PSA-Crypto script or from
# an Mbed TLS script. As a consequence, it should avoid depending on
# other modules from the project or the framework. It's only intended
# to be a data module anyway.

# At any given time, there may or may not be a test case matcher that's
# built with `re.compile`. Always include the `re` module so that we
# don't keep adding and removing it as the matchers evolve.
import re #pylint: disable=unused-import
from typing import Dict, List, Pattern, Union

# Test cases that it makes sense not to execute in Mbed TLS. Typically
# this is because they relate to implementation details of TF-PSA-Crypto,
# such as optimization options.
#
# This has the same format as `CoverageTask.IGNORED_TESTS` in outcome_analysis:
# ```{ test_suite_name: [matcher, ...], ... }```
# with each ``matcher`` being either of:
# - a string, which is an exact test case description;
# - a regex, which must match the full test case description.
# A test suite with no "." matches all test suites with the same .function
# file. A test suite with a "." only matches that specific .data file.
INTERNAL_TEST_CASES: Dict[str, List[Union[str, Pattern]]] = {
    'test_suite_config.crypto_combinations': [
        'Config: entropy: NV seed only',
        re.compile('.*built-in.*'),
        re.compile('Config: mldsa-native.*'),
    ],
    'test_suite_pqcp_mldsa': [
        re.compile('.*SHAKE.*'),
    ],
}
