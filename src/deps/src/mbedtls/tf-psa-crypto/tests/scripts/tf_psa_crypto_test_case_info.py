"""Information about TF-PSA-Crypto test cases that Mbed TLS can access."""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

# This is a temporary relay for backward compatibility, until Mbed TLS
# is updated to look in the new location.

import os

_NEW_LOCATION = os.path.join(os.path.dirname(__file__),
                             os.pardir, os.pardir,
                             'scripts', 'project_knowledge',
                             os.path.basename(__file__))
exec(open(_NEW_LOCATION).read()) #pylint: disable=exec-used
