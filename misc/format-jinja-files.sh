#!/bin/bash

first_arg=$1
args=("$@")

if [ "$first_arg" == "manual" ]; then
  echo "⏳ Running djLint for web UI Jinja files..."
  djlint --reformat --profile=jinja --exclude=src/ui/templates/setup.html src/ui/templates
  ret=$?
  if [ $ret -ne 0 ]; then
      echo "❌ djLint failed for web UI template files. Exiting..."
      exit $ret
  fi
  echo "✅ djLint for web UI template files passed."


  echo "⏳ Running djLint for core plugins UI Jinja files..."
  djlint --reformat --profile=jinja src/common/core/*/ui
  ret=$?
  if [ $ret -ne 0 ]; then
      echo "❌ djLint failed for core plugins UI template files. Exiting..."
      exit $ret
  fi
  echo "✅ djLint for core plugins UI template files passed."

  echo "⏳ Running djLint for documentation Jinja files..."
  djlint --reformat --profile=jinja docs/
  ret=$?
  if [ $ret -ne 0 ]; then
      echo "❌ djLint failed for documentation files. Exiting..."
      exit $ret
  fi
  echo "✅ djLint for documentation files passed."

  echo "✅ All djLint commands passed"
else
  echo "⏳ Running custom djLint command with args: ${args[*]}"
  djlint --reformat --profile=jinja "${args[@]}"
  ret=$?
  if [ $ret -ne 0 ]; then
      echo "❌ djLint failed for custom command. Exiting..."
      exit $ret
  fi
  echo "✅ djLint for custom command passed."
fi
