#!/bin/bash

NL=$'\n'
# select words of length <= 3
original="$(grep -vE '^[#$]' regex-assembly/include/unix-shell-upto3.ra)"
# Exclude entries starting with `(dev/|etc/|proc/|#)` and empty lines, they are not commands
source=$(grep -vEh '^(dev/|etc/|proc/|#|$)' rules/unix-{shell-aliases,shell,shell-builtins}.data | \
  awk '/^[^#$]/ {split($0,x,"/"); y=x[length(x)]} length(y) <= 3 {print y}' | \
  sort | uniq)
result=""
# retain all unmodified entries in this list and skip removed ones; ignore the manually added suffixes
while read -r oword; do
  # strip @ and ~ from end of words
  oword_raw="${oword/%@/}"
  oword_raw="${oword_raw/%\~/}"
  while read -r sword; do
    if [ "${oword_raw}" = "${sword}" ]; then
      result="${result}${oword}${NL}"
      break
    fi
  done <<<"${source}"
done <<<"${original}"

# add new entries to this list
while read -r sword; do
  found=0
  while read -r oword; do
    # strip @ and ~ from end of words
    oword_raw="${oword/%@/}"
    oword_raw="${oword_raw/%\~/}"
    if [ "${oword_raw}" = "${sword}" ]; then
      found=1
      break
    fi
  done <<<"${original}"
  if [ ${found} -eq 0 ]; then
    result="${result}${sword}${NL}"
  fi
done <<<"${source}"

# Add `@` suffix to all words, except those suffixed with `~`
original="${result}"
result=""
while read -r oword; do
  oword_raw="${oword/%@/}"
  if [ -n "${oword}" ]; then
    oword_raw="${oword/%@/}"
    if [[ "${oword_raw}" == "${oword_raw/%\~/}" ]]; then
      result="${result}${oword_raw}@${NL}"
    else
      result="${result}${oword_raw}${NL}"
    fi
  fi
done <<<"${original}"

body_start=$(grep -n -E -m 1 '^[^#$]' regex-assembly/include/unix-shell-upto3.ra | cut -d: -f1)
ed -s regex-assembly/include/unix-shell-upto3.ra <<EOF
$((body_start - 1)),\$d
w
q
EOF
echo "${result}" | sort | uniq >> regex-assembly/include/unix-shell-upto3.ra
