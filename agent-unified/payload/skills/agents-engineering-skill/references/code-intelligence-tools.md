# Code intelligence and quality tools

The project uses a two-tier policy: the core gate has no third-party Python
dependencies, while enhanced tools run when installed locally and are required only
by a pinned Linux CI job. This keeps Linux, macOS, and Windows contributors productive
without weakening the merge gate.

## Tool roles

| Tool | Role | Local behavior |
|---|---|---|
| Ruff | Python lint and format verification | Skip if absent |
| markdownlint-cli2 | Markdown structure and style | Skip if absent |
| Lychee | Local Markdown link validation | Skip if absent |
| actionlint | GitHub Actions syntax and semantics | Skip if absent |
| zizmor | GitHub Actions security audit | Skip if absent |
| ShellCheck | POSIX shell analysis | Skip when absent or irrelevant |
| Gitleaks | Secret scanning with redacted findings | Skip if absent |
| CodeGraph | Local semantic code graph for agent navigation | Adopt only when useful |

Run the dependency-free gate anywhere:

```bash
python3 scripts/check_project.py --skip-optional-tools
```

Run installed enhanced tools too:

```bash
python3 scripts/check_project.py
```

Use `--require-optional-tools` only in an environment that intentionally installs
every relevant tool, such as the enhanced Linux CI job. Do not make global tool
installation a prerequisite for editing or validating the project locally.

## When to adopt CodeGraph

`scripts/codegraph_readiness.py` reports one of three states:

- `defer`: ordinary search and the repository map remain the simpler choice.
- `recommended`: the repository reached an adoption heuristic.
- `active`: a local `.codegraph/` index already exists.

The repository's heuristics recommend a trial at any one of these points:

- 500 supported source files;
- 50,000 supported source lines; or
- 200 supported source files across at least 3 languages.

These values are project policy, not CodeGraph product limits. The checker ignores
Markdown and counts only source types CodeGraph can analyze. It is informational and
never changes the quality-gate result.

```bash
python3 scripts/codegraph_readiness.py /path/to/project
python3 scripts/codegraph_readiness.py /path/to/project --json
```

When the report becomes `recommended`, use a reversible trial:

1. Install CodeGraph using its official platform instructions.
2. Disable telemetry if required by local policy: `codegraph telemetry off`.
3. Preview Codex configuration without writing it:
   `codegraph install --print-config codex`.
4. Review the printed command, permissions, and executable path before applying it.
5. In the project root, run `codegraph init`, then verify with `codegraph status`.
6. Keep `.codegraph/` untracked. Remove the project index with `codegraph uninit`
   if measured navigation quality does not improve.

Do not grant blanket shell or MCP approval. Keep ordinary file search available as a
fallback, and re-check the tool after upgrades because it is an external
supply-chain boundary.

## Primary sources

- [CodeGraph official repository](https://github.com/colbymchenry/codegraph)
- [Ruff official repository](https://github.com/astral-sh/ruff)
- [markdownlint-cli2 package](https://www.npmjs.com/package/markdownlint-cli2)
- [Lychee official repository](https://github.com/lycheeverse/lychee)
- [actionlint official repository](https://github.com/rhysd/actionlint)
- [zizmor usage documentation](https://docs.zizmor.sh/usage/)
- [ShellCheck official repository](https://github.com/koalaman/shellcheck)
- [Gitleaks official repository](https://github.com/gitleaks/gitleaks)
