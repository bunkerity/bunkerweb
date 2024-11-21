#!/bin/bash

rules_dir="./files/coreruleset-v$1/rules"

score_types=("critical" "error" "warning" "notice")
score_variables=("inbound" "outbound")

find "$rules_dir" -type f -name "*.conf" | while read -r file; do
  for score_type in "${score_types[@]}"; do
    for score_variable in "${score_variables[@]}"; do
      search_pattern="setvar:'tx.${score_variable}_anomaly_score_pl[0-9]=+%{tx.${score_type}_anomaly_score}'"
      sed -i "/$search_pattern/s/\($search_pattern\)/\1,setvar:'tx.bunkerweb_rules=%{tx.bunkerweb_rules} %{rule.id}'/" "$file"
    done
  done
  sed -i "/setvar:'tx.anomaly_score_pl[0-9]=+%{tx.critical_anomaly_score}'/s/\(setvar:'tx.anomaly_score_pl[0-9]=+%{tx.critical_anomaly_score}'\)/\1,setvar:'tx.bunkerweb_rules=%{tx.bunkerweb_rules} %{rule.id}'/" "$file"
done
