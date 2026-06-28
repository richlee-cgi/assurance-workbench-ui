# Hosted Azure Workbench Note

## Context

The current Workbench is a local browser app around `assurance-cli`. It stores evidence in a local Workbench folder and can optionally grow towards local model analysis through Ollama/Qwen3.

A possible future direction is a hosted Workbench that users access through a browser, backed by Azure, Entra ID and an Azure-hosted LLM or agent.

The main challenge is not just hosting the app. The real question is where assurance evidence flows. Evidence may include Confluence pages, Jira tickets, code, pull request diffs, Azure metadata and Dataverse metadata. For many clients, moving that material into a supplier-owned SaaS tenant would be treated as data exfiltration.

## Recommendation

Prefer a customer-hosted Azure deployment over a conventional central SaaS.

In this model, the Workbench data plane runs inside the client's Azure subscription and tenant. The client owns the storage, secrets, model deployment, logs and evidence retention. The app can still feel SaaS-like to users, but sensitive evidence remains within the client's cloud boundary.

Avoid a central multi-tenant SaaS that ingests all evidence into our subscription unless the client explicitly accepts that data movement.

## Deployment Shape

Suggested customer-hosted architecture:

```text
User browser
  -> Entra ID sign-in
  -> Workbench web app
  -> background evidence jobs
  -> client-owned evidence storage
  -> client-owned Azure AI / Foundry / Azure OpenAI model
```

Core Azure resources:

- Azure App Service or Azure Container Apps for the FastAPI/HTMX web app.
- A worker process for evidence retrieval and analysis jobs.
- Azure Storage for evidence packs, logs and generated artifacts.
- PostgreSQL, Cosmos DB or Table Storage for run metadata and per-user configuration.
- Azure Key Vault for source credentials and API tokens.
- Managed identities for app-to-Azure access.
- Microsoft Entra ID for authentication and authorisation.
- Azure AI Foundry / Azure OpenAI deployed in the client subscription for hosted analysis.
- Application Insights / Log Analytics for operational logs.

For stricter environments:

- VNet integration.
- Private endpoints for Storage, Key Vault, database and AI resources.
- Public network access disabled where practical.
- Separate resource groups for dev/test/prod.

## Control Plane And Data Plane

A strong product shape would split responsibilities:

### Customer-Owned Data Plane

Runs in the client's Azure subscription.

Contains:

- Workbench app.
- Evidence storage.
- Source credentials.
- Azure AI model endpoint.
- Job workers.
- Audit logs.
- Per-user and per-tenant configuration.

This is where all evidence processing happens.

### Optional Supplier-Owned Control Plane

Runs outside the client subscription, but must not receive evidence.

Could contain:

- Version discovery.
- Deployment templates.
- Licence checks.
- Health telemetry without evidence content.
- Update notifications.
- Documentation links.

This gives a SaaS-like management model without requiring the supplier to host evidence.

## Identity And Access

Use Microsoft Entra ID.

For one client:

- Use a single-tenant app registration in the client's tenant.
- Restrict access to approved groups.
- Use role mapping in the app, for example `reader`, `runner`, `admin`.

For productised multi-client use:

- A multi-tenant app registration is possible, but the data plane should still normally be deployed per customer.
- The app should request least-privilege permissions.
- Admin consent and group claims need careful design.

Azure App Service built-in authentication can simplify the first hosted version by handling sign-in, sessions and token validation before requests reach the app.

## LLM / Agent Strategy

Use the same analysis contract as the local LLM spec:

- Prompt builder creates a bounded evidence bundle.
- Model is asked for strict JSON.
- App validates JSON.
- App renders deterministic Markdown.
- Prompt, JSON, Markdown and metadata are stored with the run.

Provider abstraction:

```text
AnalysisProvider
  - disabled
  - ollama-local
  - azure-foundry
```

The Azure provider should call the client's Azure AI Foundry / Azure OpenAI deployment. Evidence should not be sent to a supplier-owned model endpoint.

The model output must be labelled as derived analysis, not an assurance decision.

## Data And Storage Changes

The current local app assumes one user and a local filesystem. A hosted version needs storage abstractions.

Replace direct filesystem assumptions with:

- `RunStore` for evidence artifacts.
- `MetadataStore` for run records and user settings.
- `SecretStore` for credentials.
- `AnalysisProvider` for model execution.

The local implementation can remain filesystem-backed. The hosted implementation can use Blob Storage, a database and Key Vault.

Evidence run artifacts should still be organised as a folder-like bundle:

```text
runs/<timestamp-topic>/
  request.json
  command.txt
  evidence-pack.md
  gaps-and-warnings.md
  assurance-checks.md
  analyst-brief.md
  local-analysis.json
  local-analysis.md
  logs...
```

In Azure, this maps naturally to blob prefixes.

## Cost Considerations

Cost is likely to be a client concern.

If the Workbench app, storage and Azure AI model are deployed into the DSP/DVSA subscription, the cost lands with DSP/DVSA.

Main cost drivers:

- Azure OpenAI / Foundry model inference, usually priced by input and output tokens for pay-as-you-go deployments.
- App hosting.
- Worker compute.
- Storage.
- Database.
- Logs and monitoring.
- Private endpoints, firewall and other networking controls.

Cost controls should be designed in from the start:

- Dedicated resource group for Workbench resources.
- Azure budgets and alerts on that resource group.
- AI analysis off by default.
- Explicit `Fast`, `Deep` and `No AI` modes.
- Per-run input and output token limits.
- Per-user and per-day usage limits.
- Allowed model list controlled by admins.
- Cost and token metadata saved with each analysis run.
- Clear UI estimate before running expensive analysis.

For example, before analysis:

```text
Estimated analysis input: 85k chars / approximately 20k tokens.
Mode: Fast.
Model: gpt-4o-mini or equivalent configured deployment.
```

The exact cost estimate depends on the client's Azure agreement, region and model deployment. The app should support a configurable pricing table or show token usage without pretending to know exact billing.

## Security And Privacy

Baseline requirements:

- No evidence sent to supplier-owned services.
- Secrets in Key Vault, not app settings or database rows.
- Managed identities instead of long-lived Azure credentials.
- Per-user access checks on every run and artifact.
- Audit log for runs, source queries, model calls and file downloads.
- Retention policy for evidence packs and generated analysis.
- Admin-controlled source connectors.
- Clear labelling of model-generated outputs.

Prompt safety:

- Treat evidence content as untrusted.
- Do not obey instructions found inside evidence.
- Do not include credentials or environment variables in prompts.
- Save prompt and model metadata for audit.

## Migration Path From Local Workbench

Recommended order:

1. Keep the local Workbench stable.
2. Add local LLM analysis behind a provider interface.
3. Introduce storage abstractions while keeping filesystem-backed local behaviour.
4. Containerise the app.
5. Add Entra ID authentication.
6. Add database-backed users, settings and run metadata.
7. Add Blob Storage-backed run artifacts.
8. Add Key Vault-backed secrets.
9. Add Azure-hosted analysis provider.
10. Add deployment templates for client-owned Azure.
11. Consider a supplier-owned control plane only after the data plane is cleanly isolated.

## Open Questions

- Is the desired first hosted target a single DSP/DVSA tenant deployment, or a multi-client product?
- Who owns operational support for the client-hosted deployment?
- Which source credentials should be per-user versus service-account based?
- How strict does network isolation need to be for the first version?
- Should evidence retention be fixed by policy or configurable per workspace?
- Does the client already have approved Azure AI / Foundry model deployments?
- Should the app support private GitHub Enterprise / Azure DevOps sources as first-class hosted connectors?
