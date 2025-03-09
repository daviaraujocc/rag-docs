{{/*
Expand the name of the chart.
*/}}
{{- define "rag-docs.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "rag-docs.fullname" -}}
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
{{- define "rag-docs.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rag-docs.labels" -}}
helm.sh/chart: {{ include "rag-docs.chart" . }}
{{ include "rag-docs.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rag-docs.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-docs.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "rag-docs.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "rag-docs.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Component specific name
*/}}
{{- define "rag-docs.componentName" -}}
{{- $name := default .componentValues.name .componentNameOverride -}}
{{- printf "%s-%s" .releaseName $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Component labels
*/}}
{{- define "rag-docs.componentLabels" -}}
{{- $compName := .componentValues.name -}}
app.kubernetes.io/component: {{ $compName }}
{{- end -}}

{{/*
Postgres connection environment variables
*/}}
{{- define "rag-docs.postgresEnv" -}}
- name: POSTGRES_USER
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-postgres
      key: username
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-postgres
      key: password
- name: POSTGRES_CONNECTION_STRING
  value: {{ .Values.database.connectionString }}
{{- end -}}

{{/*
MinIO connection environment variables
*/}}
{{- define "rag-docs.minioEnv" -}}
- name: MINIO_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-minio
      key: rootUser
- name: MINIO_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-minio
      key: rootPassword
- name: MINIO_ENDPOINT
  value: {{ .Release.Name }}-minio:9000
{{- end -}}
