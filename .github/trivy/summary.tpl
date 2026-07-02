{{- $c := 0 }}{{- $h := 0 }}{{- $m := 0 }}{{- $l := 0 }}{{- $u := 0 }}
{{- range . }}{{- range .Vulnerabilities }}
{{- if eq .Severity "CRITICAL" }}{{- $c = add $c 1 }}
{{- else if eq .Severity "HIGH" }}{{- $h = add $h 1 }}
{{- else if eq .Severity "MEDIUM" }}{{- $m = add $m 1 }}
{{- else if eq .Severity "LOW" }}{{- $l = add $l 1 }}
{{- else }}{{- $u = add $u 1 }}{{- end }}
{{- end }}{{- end }}
{{- $total := add $c $h $m $l $u }}
{{- if eq $total 0 }}
✅ No vulnerabilities found.
{{- else }}
🔴 **{{ $c }}** Critical &nbsp; 🟠 **{{ $h }}** High &nbsp; 🟡 **{{ $m }}** Medium &nbsp; ⚪ **{{ $l }}** Low &nbsp; ❔ **{{ $u }}** Unknown &nbsp;&mdash;&nbsp; **{{ $total }}** total
{{- range . }}{{- if .Vulnerabilities }}
<details><summary>{{ escapeXML .Target }} ({{ .Type }}) &mdash; {{ len .Vulnerabilities }}</summary>
<table>
<tr><th>Severity</th><th>ID</th><th>Package</th><th>Installed</th><th>Fixed</th></tr>
{{- range .Vulnerabilities }}
<tr><td>{{ escapeXML .Severity }}</td><td><a href={{ escapeXML .PrimaryURL | printf "%q" }}>{{ escapeXML .VulnerabilityID }}</a></td><td><code>{{ escapeXML .PkgName }}</code></td><td>{{ escapeXML .InstalledVersion }}</td><td>{{ escapeXML .FixedVersion }}</td></tr>
{{- end }}
</table>
</details>
{{- end }}{{- end }}
{{- end }}
