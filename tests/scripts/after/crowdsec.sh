#!/bin/bash

# The bot-detection scenario in tests/core/crowdsec.yml swaps tests/misc/conf/appsec.yaml for a
# variant listing `crowdsecurity/appsec-bot-*` and swaps it back three actions later. An aborted
# run in between would leave the glob in place, and CrowdSec treats an appsec_configs entry that
# matches no installed config as fatal at startup -- which would then red a later category that
# inherits the container (start.sh recreates it on any full_clean). This hook runs on failure too,
# so the restore is unconditional. Restored from the spec's own fixture rather than with `git
# checkout` so it also works on a checkout where the change is not committed yet; the fixture is
# byte-identical to the shipped file and tests/core/crowdsec.yml asserts nothing else about it.
cp tests/core/crowdsec/fixtures/appsec-default-only.yaml tests/misc/conf/appsec.yaml
