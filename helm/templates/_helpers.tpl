{{/*
Expand the name of the chart.
*/}}
{{- define "bunkerweb.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "bunkerweb.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "bunkerweb.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "bunkerweb.labels" -}}
helm.sh/chart: {{ include "bunkerweb.chart" . }}
{{ include "bunkerweb.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "bunkerweb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bunkerweb.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "bunkerweb.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "bunkerweb.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Docker secret Generation
*/}}
{{- define "imageRegistrySecret" -}}
{{- if .Values.registry.imageCredentials.enabled }}
{{- printf "{\"auths\": {\"%s\": {\"auth\": \"%s\"}}}" .Values.registry.imageCredentials.registry (printf "%s:%s" .Values.registry.imageCredentials.username .Values.registry.imageCredentials.password | b64enc) | b64enc }}
{{- end }}
{{- end }}