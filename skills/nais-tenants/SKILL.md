---
name: nais-tenants
description: Nais tenancy — tenants, environments, clusters, how to discover the live list, and how to select one
license: MIT
compatibility: Nais platform development
metadata:
  domain: platform
  tags: tenants clusters environments multi-tenancy naisdevice kubectl gcp
---

# Tenants and environment clusters

A **tenant** is one customer organisation: its own GCP folder tree, its own `<tenant>.cloud.nais.io`, one management cluster, one GKE cluster per environment.

**Environment and cluster are the same thing.** Every environment is a separate cluster; every team is a namespace in it. That is why features declare `environmentKinds`, and why Loki and Mimir exist once per tenant while Tempo exists per environment.

## Discovering tenants

Never hardcode the list. Two sources, neither complete.

Public registry, no auth. `nais/cli` uses it:

```bash
curl -s "https://storage.googleapis.com/storage/v1/b/nais-tenant-data/o?fields=items(name)" | jq -r '.items[].name'
curl -s "https://storage.googleapis.com/nais-tenant-data/nav.no.json" | jq .
```

Keyed by email domain, returns the console URL.

Terraform, in `nais/nais-terraform-modules` (internal):

```bash
gh api repos/nais/nais-terraform-modules/contents/tenants --jq '.[].name'
```

`atlantis-serviceaccounts/serviceaccounts.tf` provisions service accounts and state buckets for **more** tenants than have a `tenants/<name>/` root. Cross-check both before concluding a tenant does or does not exist.

Disagreement means they answer different questions: the bucket says who can log in, Terraform says what is provisioned.

## Which tenant

`dev-nais` for platform work. `ci-nais` takes the first canary of every feature deploy. `test-nais` for testing.

`nav`, `atil`, `ldir`, `ssb` and the rest are real customers. Read from them to investigate something specific; never to try something out.

**The `nais` GitHub org deploys into the `nav` tenant.** `nais` is not a tenant.

## Selecting a cluster

Interactive by design:

1. Switch tenant in the naisdevice GUI.
2. `gcloud config set account <you>@nais.io`
3. `gcloud auth login --update-adc`
4. `narc kubeconfig`
5. `narc jita grant <entitlement> <tenant> --duration 1h --reason "<why>"`
6. `kubectx`

`--reason` is mandatory, logged, and **read by the tenant**. Write a real one.

**Never propose automating this.** Just-in-time elevation is a control; pre-granting it defeats the control rather than saving time.
