# AGENTS engineering design principles

Apply these principles when auditing or upgrading an AGENTS system.

## Map, not manual

Keep the root entry small and stable. It should answer:

- What is this repository?
- Where are authoritative facts?
- Which exact commands matter?
- How is work routed?
- What is unsafe or impossible to verify locally?

Move detailed workflows, domain references, and templates out of the root file.

## Progressive disclosure

Load context in this order:

1. Root and nearest scoped AGENTS guidance.
2. Task-relevant knowledge-map entries.
3. The selected skill body.
4. Only the source files and references required by the current step.

Do not preload every specification or skill.

## Risk-proportional process

Read-only work should not create implementation artifacts. A tiny local edit should not require
the same ceremony as an API migration, data rewrite, security change, device-control change, or
production deployment.

Use four levels:

- L0 read-only: inspect and report.
- L1 small/reversible: micro-plan, edit, focused verification.
- L2 standard: necessary persisted plan, existing authorization check, incremental
  implementation, review. Request confirmation only for uncovered decisions or actions.
- L3 high-risk: L2 plus rollback, compatibility/security analysis, and target-environment proof.

An existing explicit authorization remains valid for the same scope. Writing a new plan
does not by itself require another approval. Honor an explicit separate-approval request,
and do not infer device, publication, or irreversible-action authority from a general
implementation request.

## Evidence over confidence

Every completion claim must identify:

- command or operation performed;
- expected result;
- actual result;
- environment;
- unverified boundary.

Static inspection is not runtime proof. A mock is not a hardware test. A sandbox result is not
production validation.

## One source of truth

Keep a fact in one authoritative place. Other files link to it. Add ownership, status, or
verification dates where staleness would be costly.

## Exact rules beat slogans

Prefer:

> Run `cmake --build build --target app` after changing `src/`.

over:

> Ensure the project builds correctly.

Use prohibitions only for recurrent, high-impact failures. Explain the safer alternative.

## Mechanical enforcement

If a rule can be checked deterministically, encode it in a script, lint rule, test, or CI job.
Reserve AGENTS text for judgment, navigation, and constraints that cannot be enforced mechanically.

## Skill quality

Each skill should have:

- a description containing both capability and trigger;
- actionable ordered steps;
- references loaded only when needed;
- failure/stop conditions;
- evidence-based exit criteria;
- fewer than 500 lines unless splitting would harm usability.

Treat skill changes as behavior changes: test them with realistic prompts and compare results.
