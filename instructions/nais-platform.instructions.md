---
applyTo: "**"
name: nais-platform
description: Cross-cutting conventions for working in the Nais platform repositories
license: MIT
metadata:
  domain: platform
  tags: nais mise conventions delivery
---

# Working in the Nais platform repos

## mise is the task runner

Shared names across Go, Rust, Kotlin and TypeScript repos: `mise run check`, `test`, `generate`, `fmt`. Reach for those before inventing a `go test` invocation.

`nais/helm-charts` is outside this convention; its validation lives in `.github/validate/README.md`, which nothing loads automatically.

## A merge is usually a deploy

Merging a feature repo builds an image, packages a chart, and hands it to Fasit, which canaries to `ci-nais` then fans out to every tenant. Merging `nais/liberator` ships CRDs everywhere and auto-commits docs into `nais/doc`.

No separate release step to hesitate at. The pull request is the decision point.

## Local development rarely needs credentials

`nais/api`, `v13s`, `api-reconcilers` and `naiserator` run offline: docker compose, kind or Tilt, seeded Postgres, fake Kubernetes clients. Reaching for a real tenant is slower and riskier.

## Generated code

Never hand-edit it; always commit the regenerated output in the same change. `nais/api` generates `nais/console-frontend`'s `schema.graphql`; do not edit it there.

## Access is just-in-time and interactive

naisdevice connects to one tenant at a time, so nothing reaches two tenants in one session, and the switch is a choice in the naisdevice menu: the `nais` CLI has no command for it.

Switching tenant, minting kubeconfigs and `narc jita grant` are interactive by design. `--reason` is mandatory, logged and read by the tenant. Do not propose automating any of it.

## Language

Repo conventions and review threads are largely Norwegian; several repos carry a Norwegian `AGENTS.md`. Follow the language of the repo you are in for commits and PR text.

## Read the repo's AGENTS.md first

Where one exists it outranks this file. `nais/fasit` has three nested ones plus a `CONTEXT.md` glossary. Several repos have none. That is not permission to assume there are no conventions.
