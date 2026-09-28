#!/bin/bash

NL=$'\n'
original="$(grep -vE '^[#$]' regex-assembly/include/unix-shell-4andup.ra)"
# Exclude entries starting with `(dev/|etc/|proc/|#)` and empty lines, they are not commands
source="$(grep -vEh '^(dev/|etc/|proc/|#|$)' rules/unix-{shell-aliases,shell,shell-builtins}.data | \
  awk '/^[^#$]/ {split($0,x,"/"); y=x[length(x)]} length(y) > 3 {print y}' | \
  sort | uniq)"
# retain all unmodified entries in this list and skip removed ones; ignore the manually added suffixes
while read -r oword; do
  # strip suffixes from end of words
  oword_raw="${oword/%@/}"
  oword_raw="${oword_raw/%~/}"
  while read -r sword; do
    # handle "clang++"
    sword="${sword//++/\+\+}"
    # handle "." in commands
    sword="${sword//./\.}"
    if [ "${oword_raw}" = "${sword}" ]; then
      result="${result}${oword}${NL}"
      break
    fi
  done <<<"${source}"
done <<<"${original}"

# add new entries to this list
while read -r sword; do
  # handle "clang++"
  sword="${sword/%++/\+\+}"
  # handle "." in commands
  sword="${sword//./\.}"
  found=0
  while read -r oword; do
    # strip suffixes from end of words
    oword_raw="${oword/%@/}"
    oword_raw="${oword_raw/%~/}"
    if [ "${oword_raw}" = "${sword}" ]; then
      found=1
      break
    fi
  done <<<"${original}"
  if [ ${found} -eq 0 ]; then
    result="${result}${sword}${NL}"
  fi
done <<<"${source}"

# Suffix all English words or words shorter than 5 characters with `@`
original="${result}"
tmpfile="$(mktemp)"
wget https://raw.githubusercontent.com/coreruleset/coreruleset/refs/tags/v4.0.0/util/fp-finder/english-extended.txt
english="$(crs-toolchain util fp-finder "$tmpfile" -e english-extended.txt <<<"${result}")"
rm -f "$tmpfile" english-extended.txt
result=""
while read -r oword; do
  found=0
  if [ -n "${oword}" ]; then
    if [ ${#oword} -lt 5 ]; then
      found=1
    else
      while read -r eword; do
        if ([ "${oword}" = "${eword}" ]); then
          result="${result}${oword}@${NL}"
          found=1
          break
        fi
      done <<<"${english}"
    fi
  fi
  if [ ${found} -eq 0 ]; then
    result="${result}${oword}${NL}"
  fi
done <<<"${original}"

body_start=$(grep -n -E -m 1 '^[^#$]' regex-assembly/include/unix-shell-4andup.ra | cut -d: -f1)
ed -s regex-assembly/include/unix-shell-4andup.ra <<EOF
$((body_start - 1)),\$d
w
q
EOF
echo "${result}" | sort | uniq >> regex-assembly/include/unix-shell-4andup.ra
