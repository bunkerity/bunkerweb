#!/bin/bash
set -eEuo pipefail
trap 'echo "Error on line $LINENO with command: $BASH_COMMAND"; exit 1' ERR

# read restricted-files.data, strip filepaths, and entries less than 4 characters
restricted_files="$(grep -v "^\#" rules/restricted-files.data | \

    # Strip filepaths and match on naked file
    sed -E "s#^/?(\w+/)+##g" | \

    # Exclude entries less than 4 characters
    sed -E "/^.{1,3}$/d")"

# Split restricted-files.data into substring matches and non substring matches,
# [a-z0-9] and dot files without trailing slash tend to cause false positives based
#on historical false positive reports.
non_substring_matches="$(echo "${restricted_files}" | grep -E '^\.?\w+[^/_]{1}$' )"
substring_matches="$(echo "${restricted_files}"| grep -vE '^\.?\w+[^/_]{1}$' )"

# Delete all lines that aren't whitespace or a comment
sed -i -E "/^[^#]/d" regex-assembly/include/932180-non-substring-matches.ra
sed -i -E "/^[^#]/d" regex-assembly/include/932180-substring-matches.ra

# Write results to regex-assembly rule and do some cleanup
# Sort result, remove duplicates, replace whitespace with newline, and escape special characters, and strip newline characters
echo "${non_substring_matches}" | sort | uniq | tr ' ' '\n' | sed -E "s/\./\\\./g" | sed '/^$/d'>> regex-assembly/include/932180-non-substring-matches.ra
echo "${substring_matches}" | sort | uniq | tr ' ' '\n' | sed -E "s/\./\\\./g"| sed '/^$/d' >> regex-assembly/include/932180-substring-matches.ra
