# Existing-repository adoption

Use this guide when the target already contains code, documentation, rules, or skills.

## 1. Inventory without mutation

Collect:

- Git status and repository root.
- Every `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `GEMINI.md`,
  `.github/copilot-instructions.md`, `.cursor/rules/`, and skill directory.
- Build manifests, test runners, CI workflows, architecture docs, and operational runbooks.
- Rules that conflict, duplicate one another, or refer to missing commands/files.

Do not interpret a third-party checkout, generated file, or historical snapshot as the
repository's active source of truth without evidence.

## 2. Classify the repository

- **Greenfield:** little code or history; the full template is reasonable.
- **Established:** working commands and conventions already exist; adopt incrementally.
- **Monorepo:** create a short root map and nested AGENTS only for genuinely different subtrees.
- **Hardware/production:** separate local evidence from target-device or production evidence.

## 3. Preserve before improving

1. Record the current file hashes or Git diff.
2. Extract stable facts and exact commands from existing sources.
3. Keep user-specific constraints unless they are contradictory or unsafe.
4. Move duplicated detail to one source and replace copies with links.
5. Never bulk-copy a generic skill pack into a repository. Install only workflows with
   realistic triggers.

## 4. Stage the upgrade

Recommended order:

1. Make root `AGENTS.md` a concise map.
2. Add a knowledge map and Definition of Done.
3. Add routing and one or two high-value skills.
4. Add deterministic validation.
5. Add nested AGENTS only after a subtree demonstrates different commands or constraints.

Each stage must leave the repository usable and independently reviewable.

## 5. Verify adoption

- Ask a read-only question: the agent should inspect without creating a plan file.
- Ask for a one-file safe edit: the agent should use a micro-plan and relevant check.
- Ask for an interface or protocol change: the agent should record the necessary plan and
  check existing authorization. Continue when that authorization covers the scope and
  actions; pause only for uncovered decisions, permissions, or materially expanded risk.
- Explicitly request separate plan approval: the agent should wait at that boundary even
  when implementation has otherwise been requested.
- Ask for a risky external action: the agent should identify the additional authority required.
- Break a local Markdown link or skill name: the validator should fail.
