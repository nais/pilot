---
name: nais-observability
description: Query the Nais platform's own telemetry in Loki, Mimir and Tempo — platform components, not tenant workloads
license: MIT
compatibility: Nais platform development, naisdevice connected to the target tenant
metadata:
  domain: observability
  tags: loki mimir tempo grafana logql promql traceql nais-system platform
---

# Nais platform observability

## The header decides what you get

`X-Scope-OrgID` takes one of exactly two values per tenant:

| Value | Data |
|---|---|
| `nais` | Platform: `nais-system` components, node-exporter, kube-prometheus-stack rules, alerts |
| `tenant` | The tenant's application workloads — what teams see |

Same endpoint. The header is the only difference, so a wrong value returns real data answering a different question. **Platform work uses `nais`.**

- Omitting it returns **401**, not a default.
- Tenant federation is off: `X-Scope-OrgID: nais|tenant` is rejected. Two requests.
- Not a clean split: `kube_*` and `container_*` come from unlabelled monitors in `nais-system` and land in **both** orgs.

## Endpoints

Loki, Mimir and Grafana run on the management cluster — one per tenant:

```
https://loki.<tenant>.cloud.nais.io
https://mimir.<tenant>.cloud.nais.io
https://grafana.<tenant>.cloud.nais.io
```

Tempo runs in both `tenant` and `management` environments, so its host follows the `subdomain` rule and carries the environment:

```
https://tempo.<env>.<tenant>.cloud.nais.io
```

Use `dev-nais`. Other tenants are real customers; `nav` is production.

## Queries

```bash
# Mimir / PromQL
curl -s -H "X-Scope-OrgID: nais" \
  "https://mimir.dev-nais.cloud.nais.io/prometheus/api/v1/query?query=up{namespace=\"nais-system\"}" | jq .

# Loki / LogQL
curl -s -H "X-Scope-OrgID: nais" \
  --data-urlencode 'query={namespace="nais-system"} |= "error"' \
  --data-urlencode 'limit=100' \
  -G "https://loki.dev-nais.cloud.nais.io/loki/api/v1/query_range" | jq .

# Tempo / TraceQL — note <env> in the host
curl -s -H "X-Scope-OrgID: nais" \
  --data-urlencode 'q={resource.service.name="nais-api"}' \
  -G "https://tempo.dev.dev-nais.cloud.nais.io/api/search" | jq .
```

Range queries: `/prometheus/api/v1/query_range` with `start`, `end`, `step`.

## Traps

- **DNS proves nothing.** The management load balancer claims `*.<tenant>.cloud.nais.io`, so a typo'd host resolves and fails later as 404/503 from haproxy. Verify with an HTTP response, never `dig`.
- **Empty result, wrong org.** Check the header before concluding a component is silent.
- **Missing metric ≠ broken component.** Alloy routes by label selector. Check the other org.

## Source of truth

`nais/helm-charts` (internal), under `features/`:

- `mimir/`, `loki/`, `tempo/` — each `Feature.yaml` declares `environmentKinds`, which is why Tempo differs.
- `alloy/templates/config.yaml` — which metrics go to which org.
- `grafana/Feature.yaml` — provisioned datasources and the header each sends.

Read those when behaviour disagrees with this file.
