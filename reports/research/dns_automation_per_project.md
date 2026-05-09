# DNS Automation per Project — Design

**Date:** 2026-05-09
**Status:** Shipped (local registry + IONOS provider module + `gad domains` CLI)

---

## Bottom Line

A subdomain is part of the per-project/per-customer onboarding bundle, the same layer as soul, route, BYOK env, and retain bank. Today every new subdomain requires a manual dashboard click inside the IONOS interface. This design makes subdomain provisioning a one-liner callable from `gad new-project`, `gad new-customer`, or any CI pipeline, with the registry as the durable source of truth.

---

## Architecture

Three layers:

**1. Local TOML registry** — `<projectroot>/.planning/dns-records/<zone>.toml`

One file per DNS zone using TOML block-table arrays (`[[records]]`). Each record carries the full `dns_record` schema: type, value, TTL, provider, provider_record_id, purpose, project_link (projectid + soul_id + customer_id), and lifecycle status (`planned → provisioning → active → failed → deleted`). This file is the source of truth. The provider is downstream.

**2. Provider modules** — `lib/dns/providers/<provider>.cjs`

IONOS is the first provider (`ionos.cjs`). Exposes `listZones`, `listRecords`, `createRecord`, `deleteRecord`, `findZoneByName`. Auth via `IONOS_API_KEY` / `IONOS_API_TOKEN`. Uses native `fetch` — no new dependencies. Dry-run mode (`GAD_DOMAINS_DRY_RUN=1`) returns mock responses; all CI/test usage passes through dry-run. Cloudflare and Route53 are placeholders — the interface contract is stable, adding a new provider is a single new file.

**3. `gad domains` CLI** — `bin/commands/domains.cjs`

Subcommands:
- `list [--zone] [--live]` — read registry; optionally diff against live provider
- `add <subdomain> <value> --zone --type [--apply]` — plan (status=planned) or provision (`--apply` hits IONOS and sets status=active)
- `remove <subdomain> --zone [--apply]` — plan deletion or execute it
- `verify [--zone]` — DNS-resolve all active records, flag drift, update `last_verified_at`
- `import --provider ionos --zone [--apply]` — pull live records into registry as baseline
- `describe <subdomain> --zone [--live]` — show full record detail

Settings managed via `settings-registry.cjs`: `domains.default_provider`, `domains.default_zone` (env: `GAD_DEFAULT_ZONE`), `domains.ionos.api_endpoint`, `domains.auto_verify_after_apply`.

---

## Onboarding Flow Sketch

When `gad new-project` (or future `gad new-customer`) fires, optionally invoke:

```sh
gad domains add <slug> <ip-or-cname> \
  --zone magicbornstudios.com \
  --type A \
  --purpose project_root \
  --project-link <projectid> \
  --apply
```

This provisions the subdomain in the same atomic step as the planning scaffolding. Without `--apply`, the record lands in the registry at `status=planned` and can be provisioned in a second pass once infrastructure is ready. The two-phase model lets ops teams plan the DNS topology before the servers exist.

---

## Connection to Soul-Routes

`dns_record.project_link.soul_id` maps a subdomain to a soul's serving endpoint. When `client1.magicbornstudios.com` resolves, it lands on the proxy or ingress that reads the subdomain label, looks up the soul_id in the tenant registry, and routes the request to the `customer_private` soul adapter. The chain:

```
DNS (client1.magicbornstudios.com A→IP)
  → ingress reads host header
  → looks up soul_route by subdomain
  → routes to soul adapter (customer_private)
  → BYOK env injected
  → retain bank scoped to customer_id
```

The `dns_record` schema carries both `soul_id` and `customer_id` so a single lookup can resolve the full tenant context.

---

## Operator Action: Bootstrap from Live State

To seed the registry from the current IONOS state:

1. Generate an API key at [https://developer.hosting.ionos.com/](https://developer.hosting.ionos.com/) under "Manage API Keys".
2. Store it: `gad env set IONOS_API_KEY --projectid global`
3. Import live records: `gad domains import --provider ionos --zone magicbornstudios.com --apply`
4. Review: `gad domains list --zone magicbornstudios.com`
5. Verify: `gad domains verify --zone magicbornstudios.com`

The import assigns `purpose=other` and `project_link=null` to all imported records. Update purpose and project_link manually with `gad domains add` (upsert by record_id) or via the TOML file directly.

---

## Open Questions / Follow-up Gaps

| Gap | Priority | Notes |
|---|---|---|
| Cloudflare provider module | Medium | Same interface as ionos.cjs; needed if any projects move off IONOS |
| Route53 provider module | Low | AWS-specific; needed for platform infra records |
| Bulk operations (e.g. provision 50 customer subdomains from a CSV) | Medium | `gad domains bulk-add --from customers.csv` |
| TTL drift policy | Low | Records older than N days without a verify run should alarm |
| Cert provisioning hook | Medium | After `--apply`, optionally trigger Let's Encrypt cert via certbot or cert-manager |
| `gad new-customer` integration | High | DNS provisioning as a step in the customer onboarding flow |
| Record ID collision on upsert | Low | Two records with same subdomain+type → currently last write wins; should detect and warn |
| `--project-link` flag accepts full object | Low | Currently only projectid; soul_id + customer_id need separate flags (--soul-id, --customer-id exist) |
| Registrar abstraction (IONOS Domains API vs Cloud DNS API) | Medium | IONOS has two APIs: Domains/DNS (hosting) and Cloud DNS. This implementation uses the hosting API. |
