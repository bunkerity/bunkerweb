#!/bin/bash

# WARNING: This script is too overzealous in disabling commands and disables commands that are highly unlike to cause false positives.
# TODO: This script takes a very long time to run.

NL=$'\n'
original="$(grep -vE '^[#$]' regex-assembly/exclude/unix-shell-fps-pl1.ra)"
# strip suffixes from words for fp-finder
english_upto3=$(sed -E 's/[@~]$//' regex-assembly/include/unix-shell-upto3.ra | uniq)
english_upto3="$(crs-toolchain util fp-finder - <<<"${english_upto3}")"
# strip suffixes from words for fp-finder
rest=$(sed -E 's/[@~]$//' regex-assembly/include/unix-shell-4andup.ra | uniq)
english_rest="$(crs-toolchain util fp-finder - <<<"${rest}")"
result=""

function update_existing {
  if [ -z "${1}" ]; then
    return
  fi
  first_letter=""
  while read -r oword; do
    next_first_letter="$(cut -c 1 <<<"${oword}")"
    if [ "${next_first_letter}" != "${first_letter}" ]; then
      first_letter="${next_first_letter}"
      echo "Processing updates of ${first_letter}..."
    fi

    found=0
    while read -r eword; do
      if grep -qE "^${eword}[@~]?$" <<<"${oword}"; then
        result="${result}${eword}${NL}"
        result="${result}${eword}@${NL}"
        result="${result}${eword}~${NL}"
        found=1
        break
      fi
    done <<<"${1}"
    if [ ${found} -eq 0 ]; then
      result="${result}${oword}${NL}"
    fi
  done <<<"${original}"
}
function add_new {
  if [ -z "${1}" ]; then
    return
  fi
  first_letter=""
  while read -r eword; do
    next_first_letter="$(cut -c 1 <<<"${eword}")"
    if [ "${next_first_letter}" != "${first_letter}" ]; then
      first_letter="${next_first_letter}"
      echo "Processing additions of ${first_letter}..."
    fi

    if ! grep -qE "^${eword}[@~]?" <<<"${original}"; then
      result="${result}${eword}${NL}"
      result="${result}${eword}@${NL}"
      result="${result}${eword}~${NL}"
    fi
  done <<<"${1}"
}
update_existing "${english_upto3}"
update_existing "${english_rest}"
add_new "${english_upto3}"
add_new "${english_rest}"

body_start=$(grep -n -E -m 1 '^[^#$]' regex-assembly/exclude/unix-shell-fps-pl1.ra | cut -d: -f1)
ed -s regex-assembly/exclude/unix-shell-fps-pl1.ra <<EOF
$((body_start - 1)),\$d
w
q
EOF
echo "${result}" | sort | uniq >> regex-assembly/exclude/unix-shell-fps-pl1.ra
