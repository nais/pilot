---
name: nais-observability
description: Guide for getting metrics and logs to analyze nais platform services. Use this when asked to check how services are performing, debug problems etc. This is the main observability skill, only use other when specifically stated. Questions about clusters, tenants, services, metrics or logs should always use this skill.
license: MIT
compatibility: Nais platform development, naisdevice connected to the target tenant
metadata:
  domain: observability
  tags: loki mimir tempo grafana logql promql traceql nais-system platform
---

# Nais platform observability

Nais is run for multiple tenants. Each has their own clusters and observability installations.

## Once per machine

`nais device connect`, and one private-domain waiver: every `*.cloud.nais.io` name resolves to a private IP over naisdevice, which cplt blocks by default with `403 Private target blocked by cplt`.

```bash
cplt config set proxy.allow_private_domains cloud.nais.io
```

The match is suffix-based, so that one entry covers every tenant. Do not add one per tenant.

## Queries

For mimir queries, use the script `~/.copilot/skills/nais-observability/mimir-query.sh`. Usage:

```
bash ~/.copilot/skills/nais-observability/mimir-query.sh <tenant> <promql> [--range <start> <end> <step>] [--org nais|tenant]
```

Similar for loki queries, use the script `~/.copilot/skills/nais-observability/loki-query.sh`. Usage:

```
bash ~/.copilot/skills/nais-observability/loki-query.sh <tenant> <logql> [--range <start> <end> [step]] [--limit <n>] [--org nais|tenant]
```

Both are invoked through `bash` because a skill's files install without the executable bit: running code is a different trust question and has its own artifact kinds.

Both default to `--org nais`, the platform's own data, since this package is for people building the platform. Pass `--org tenant` for a tenant's application workloads.

Both print what the API returns and nothing else, so pipe them to `jq` yourself.

```bash
bash ~/.copilot/skills/nais-observability/mimir-query.sh dev-nais 'up{namespace="nais-system"}' | jq .
bash ~/.copilot/skills/nais-observability/loki-query.sh dev-nais '{service_name="kube-events"}' --limit 20 | jq .
```

## The header the scripts send

`X-Scope-OrgID` takes one of exactly two values per tenant:

| Value | Data |
|---|---|
| `nais` | Platform: `nais-system` components, node-exporter, kube-prometheus-stack rules, alerts |
| `tenant` | The tenant's application workloads: what teams see |

Same endpoint. The header is the only difference, so a wrong value returns real data answering a different question.

- Omitting it returns **401**, not a default.
- Tenant federation is off: `X-Scope-OrgID: nais|tenant` is rejected. Needing both means two requests.
- Not a clean split: `kube_*` and `container_*` come from unlabelled monitors in `nais-system` and land in **both** orgs, so neither value is a clean split.

## Tenants

To find the tenant to use, run the command `narc tenant get`. Tenant name must be lowercase and without the .no or .io suffix. `arbeidstilsynet` uses the short name `atil`, `landbruksdirektoratet` uses `ldir`. Always check tenant before determining urls and doing queries, never reuse the value from an earlier prompt as current tenant can change between prompts.

## Clusters

Each tenant have one or more clusters, a "management" cluster and other that can be found in the label `cluster_name` of the `naas:cluster:info` metric. When querying other metrics and logs, cluster name must be specified in the `k8s_cluster_name` label.

## Logs

Logs in loki have the labels `k8s_cluster_name`, `service_namespace`, `service_name`. Structured metadata:

- k8s_node_name
- k8s_pod_name
- k8s_container_name
- detected_level

Use this to create queries like this: `{<label matchers>} | <structured metadata matchers>`

Kubernetes events are also stored in loki with `service_name="kube-events"` with details of the involved object in the log message. Access logs from the ingress controllers is available with `service_name="nais-ingress"`.

## Tempo

The scripts cover Mimir and Loki. Tempo has no wrapper and is queried directly. Its host carries the environment, because Tempo runs in both the `tenant` and `management` environment kinds:

```
https://tempo.<env>.<tenant>.cloud.nais.io
```

```bash
curl -sS -H "X-Scope-OrgID: nais" \
  --data-urlencode 'q={resource.service.name="nais-api"}' \
  -G "https://tempo.dev.dev-nais.cloud.nais.io/api/search" | jq .
```
