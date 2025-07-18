#!/bin/bash

# Validate and set the rules directory
if [[ -z "$1" ]]; then
  echo "Error: No argument provided. Specify a version number or directory path."
  exit 1
fi

if [[ "$1" =~ ^[0-9]+$ ]]; then
  rules_dir="./files/coreruleset-v$1/rules"
else
  rules_dir="$1"
fi

# Ensure the directory exists
if [[ ! -d "$rules_dir" ]]; then
  echo "Error: Rules directory '$rules_dir' does not exist."
  exit 1
fi

# Define score types and variables
score_types=("critical" "error" "warning" "notice")
score_variables=("inbound" "outbound")

# Process rule files
find "$rules_dir" -type f -name '*.conf' | while read -r file; do
  for score_type in "${score_types[@]}"; do
    for score_variable in "${score_variables[@]}"; do
      sed -i \
        "/setvar:'tx\.${score_variable}_anomaly_score_pl[0-9]=+%{tx\.${score_type}_anomaly_score}'/ s#\(setvar:'tx\.${score_variable}_anomaly_score_pl[0-9]=+%{tx\.${score_type}_anomaly_score}'\)#\1,\
setvar:'tx.bunkerweb_rules=%{tx.bunkerweb_rules} %{rule.id}',\
setvar:'tx.bunkerweb_msgs=%{tx.bunkerweb_msgs}|%{unique_id}|%{rule.msg}',\
setvar:'tx.bunkerweb_matched_vars=%{tx.bunkerweb_matched_vars}|%{unique_id}|%{matched_var}',\
setvar:'tx.bunkerweb_matched_var_names=%{tx.bunkerweb_matched_var_names}|%{unique_id}|%{matched_var_name}',\
setvar:'tx.bunkerweb_anomaly_score=+%{tx.${score_type}_anomaly_score}'#g" \
        "$file"
    done
  done

  sed -i \
    "/setvar:'tx\.anomaly_score_pl[0-9]=+%{tx\.critical_anomaly_score}'/ s#\(setvar:'tx\.anomaly_score_pl[0-9]=+%{tx\.critical_anomaly_score}'\)#\1,\
setvar:'tx.bunkerweb_rules=%{tx.bunkerweb_rules} %{rule.id}',\
setvar:'tx.bunkerweb_msgs=%{tx.bunkerweb_msgs}|%{unique_id}|%{rule.msg}',\
setvar:'tx.bunkerweb_matched_vars=%{tx.bunkerweb_matched_vars}|%{unique_id}|%{matched_var}',\
setvar:'tx.bunkerweb_matched_var_names=%{tx.bunkerweb_matched_var_names}|%{unique_id}|%{matched_var_name}',\
setvar:'tx.bunkerweb_anomaly_score=+%{tx.critical_anomaly_score}'#g" \
    "$file"
done
