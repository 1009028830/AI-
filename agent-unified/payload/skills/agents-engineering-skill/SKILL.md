---
name: agents-engineering-skill
description: Create, audit, or upgrade a reusable AGENTS.md engineering system with a compact repository map, risk-based workflow routing, focused skills, plans, Definition of Done, problem memory, and deterministic validation. Use when Codex needs to initialize AGENTS.md in a new project, reduce an oversized rules file, adopt agent workflows in an existing repository, standardize nested guidance, or verify that AGENTS and SKILL files remain consistent.
---

# AGENTS Engineering Skill

Turn repository guidance into a small, discoverable, testable system. Keep the root
`AGENTS.md` as a map; put detailed procedures in skills, durable facts in docs, and
mechanical guarantees in scripts.

## Select the mode

- **Initialize:** the target has no usable AGENTS system.
- **Audit:** the user wants findings or recommendations only. Do not write files.
- **Upgrade:** the target already has AGENTS/rules/skills that must be preserved and improved.

For an existing repository, read [references/adoption-guide.md](references/adoption-guide.md)
before proposing changes. For design or quality review, read
[references/design-principles.md](references/design-principles.md).

## Workflow

1. **Inspect before writing**

   - Resolve the target root and current Git status.
   - Find all `AGENTS.md`, `AGENTS.override.md`, tool-specific rules, skills, build files,
     CI workflows, test entry points, architecture docs, and known-problem records.
   - Identify existing user changes. Never replace or normalize them without evidence.

2. **Build a source-of-truth map**

   Classify each rule as one of:

   - always-needed repository instruction -> root `AGENTS.md`
   - subtree-specific instruction -> nested `AGENTS.md`
   - reusable workflow -> `skills/<name>/SKILL.md`
   - durable architecture/product fact -> `docs/`
   - template/checklist -> `references/`
   - deterministic or repetitive check -> `scripts/`

   Remove duplication by linking to one authority. Do not copy the same workflow into
   AGENTS, skills, and docs.

3. **Choose the smallest adoption**

   - Initialize: use the installer.
   - Upgrade: patch only the files needed to fix confirmed gaps; do not use
     `--overwrite` on an existing repository.
   - Audit: report gaps by priority with file evidence and stop without mutations.

4. **Customize facts and commands**

   Replace generic descriptions with the repository's actual runtime, package manager,
   build/test commands, validation boundaries, dangerous areas, and nested ownership.
   Delete skills that have no realistic trigger in the target.

5. **Validate**

   Run both the target's normal checks and this skill's validator. Treat warnings as
   prompts for judgment, not automatic failures.

## Initialize a project

```bash
python3 scripts/init_agents_project.py \
  --target /path/to/project \
  --project-name "Project Name" \
  --project-overview "Product, runtime, and success criteria." \
  --build-command "actual build command" \
  --test-command "actual test command" \
  --run-command "actual smoke-test command"
```

The installer skips existing files by default and validates the result. Use `--dry-run`
first for an existing directory. Use `--overwrite` only when the user explicitly approves
replacement after reviewing the diff.

## Audit or validate

```bash
python3 scripts/validate_agents_project.py /path/to/project
python3 scripts/validate_agents_project.py \
  assets/agents-project-template --template --json
```

The validator checks UTF-8, JSON, root AGENTS structure and size, skill frontmatter,
skill-directory naming, unresolved placeholders, and local Markdown links.

From this skill repository, run the cross-platform local gate:

```bash
python3 scripts/check_project.py
```

It validates this skill, its bundled template, workspace-level `.agents/skills`, and
regression tests. It reports CodeGraph readiness and runs Ruff, `markdownlint-cli2`,
Lychee, actionlint, zizmor, ShellCheck, and Gitleaks when relevant and available. Use
`python` instead of `python3` when that is the environment's Python 3 command. POSIX
users may run `sh scripts/check-project.sh`; Windows users may run
`scripts\check-project.cmd`. These wrappers are optional and do not contain check logic.
Use `--skip-optional-tools` for the dependency-free gate. The tools, CI policy, and
reversible CodeGraph adoption path are documented in
[references/code-intelligence-tools.md](references/code-intelligence-tools.md).

## Exit criteria

- Root `AGENTS.md` is a concise map rather than a duplicated manual.
- Exact build/test/run commands or explicit TODO warnings are visible.
- Read-only, small, standard, and high-risk tasks route differently.
- Detailed workflows live in focused skills with clear trigger descriptions.
- Project-wide completion criteria are defined once.
- Nested guidance is used only where subtree rules differ.
- Existing user changes and authoritative docs remain intact.
- The validator has no errors, and all unaddressed warnings are explained.
