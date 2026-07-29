"""TF-PSA-Crypto project knowledge

This directory contains Python modules that describe TF-PSA-Crypto
for the sake of Mbed TLS. Modules in this directory are intended to
be consumed by both TF-PSA-Crypto scripts and Mbed TLS scripts.
To avoid confusion, all modules should have a name starting with
``tf_psa_crypto_``.

Note that depending on which project loads a module in this directory,
the `mbedtls_framework` package may come from either the version of
the framework submodule in TF-PSA-Crypto, or the version in Mbed TLS.
So code in this directory must be careful not to assume a very recent
framework version.
"""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later
