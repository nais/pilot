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

## One tenant at a time

naisdevice connects to exactly one tenant. There is no second connection alongside it, so nothing can query two tenants in the same session: no comparison of `dev-nais` against `nav`, no loop over the tenant list, no fan-out. A plan that needs two tenants needs two sessions with a human switching in between.

Which one is connected:

```bash
nais device status --output json | jq -r '.Tenants[]? | select(.active) | .name'
```

`AgentStatus.Tenants[]` holds one entry per tenant with `name` and `active`, and exactly one carries `active: true`. Do not print the whole document: `Tenants[].session.key` is the connected tenant's session token.

**The name is not the short tenant name.** A stock agent is compiled with one tenant, `NAV`. With the hidden `ILoveNinetiesBoybands` setting on, whose own help text reads "Enable tenant switching":

```bash
nais device config set ILoveNinetiesBoybands true
```

the agent appends the object names from the `naisdevice-enroll-discovery` bucket, which are **domains**: `nav.no`, `dev-nais.io`, `ssb.no`, `arbeidstilsynet.no`, `ci-nais.io`, `test-nais.no`, `miljodir.no`, `landbruksdirektoratet.no`, plus `default` and `nais.io`.

So the command above answers `NAV`, or something like `dev-nais.io`. Map it before you use it anywhere: drop the `.no` or `.io`, lowercase it, and apply the short names `arbeidstilsynet` → `atil` and `landbruksdirektoratet` → `ldir`. Hosts, cluster names and kubectl contexts all use the short form; comparing a domain against one of those is a silent mismatch, not an error.

**There is no command to switch.** `nais device` has `status`, `connect`, `disconnect`, `gateway`, `doctor` and `config`, and nothing else. The agent does expose a `SetActiveTenant` RPC, but no CLI command calls it; switching is a person choosing the tenant in the naisdevice menu.

So when the tenant you were asked about is not the connected one, stop there and say so:

> naisdevice is connected to `dev-nais`, so I cannot reach `nav` from here. Switching is the naisdevice menu and I have no command for it. Switch and say when to carry on.

Do not answer for the connected tenant instead. That is a real answer to a question nobody asked, and it reads like the right one.

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
