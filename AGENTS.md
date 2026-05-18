# AI Agent Conventions for Audio Processor

This file documents the conventions that apply when AI agents (Claude Code,
Gemini CLI, or other coding assistants) work in this repository.

For project guidelines, code standards, and branch workflow rules, see
[CLAUDE.md](./CLAUDE.md) (checked in at project root) and the global rules at
`~/.claude/CLAUDE.md`.

---

## Model Selection

Use the right model to balance quality and cost. The table below extends the
global standard with audio-processor-specific guidance.

| Task type                                       | Model         | Notes                                        |
|-------------------------------------------------|---------------|----------------------------------------------|
| Architecture decisions, ADR authoring, deep security review | Opus 4.7 | Multi-step reasoning required |
| Standard development: coding, refactoring, PR descriptions | Sonnet 4.6 | Default for most work in this repo |
| Read-only exploration, file scanning, structure mapping | Haiku 4.5 | Use for the built-in Explore subagent |

Do not use a more expensive model when a cheaper one is sufficient. Haiku
for read-only exploration is the most common savings opportunity.

---

## Tool Permissions

The following tools are permitted for agents working in this repo:

- File read/write/edit within the repo tree
- `git` commands (status, diff, log, add, commit, branch, worktree)
- `uv run <tool>` for project tooling (ruff, basedpyright, pytest, bandit,
  pip-audit, pre-commit)
- `docker` and `docker-compose` for local container operations
- GitHub CLI (`gh`) for PR and issue operations on this repo

Tools that are **not** permitted without explicit user instruction:

- `git push` (do not push to remote without explicit request)
- `git reset --hard`, `git clean -f`, or other destructive git commands
- Production environment access or external API calls using production keys
- Installing packages outside of `uv add` / `uv sync` (no bare `pip install`)

---

## Subagent Patterns

The project CLAUDE.md designates Claude Code as the supervisor for all
development tasks. Subagent assignments follow this pattern:

```text
Security tasks           -> Security Agent  (mcp__zen__secaudit)
Code reviews             -> Code Review Agent (mcp__zen__codereview)
Testing                  -> Test Engineer Agent (mcp__zen__testgen)
Documentation            -> Documentation Agent (mcp__zen__docgen)
Debugging                -> Debug Agent (mcp__zen__debug)
Analysis                 -> Analysis Agent (mcp__zen__analyze)
Refactoring              -> Refactor Agent (mcp__zen__refactor)
Read-only exploration    -> Explore subagent (Haiku, built-in)
```

The built-in `Plan` subagent inherits the caller's model; do not set it
explicitly.

---

## Project-Specific Agent Notes

### Audio file handling

Agents must never write or log raw audio file paths derived from user input
without first resolving and validating them. Path traversal is a key risk
surface in this repo (see SECURITY.md). All file I/O involving audio assets
must use `pathlib.Path.resolve()` and validate against the configured upload
directory before proceeding.

### FFmpeg command construction

Do not construct FFmpeg invocations via shell string concatenation. Use the
`ffmpeg-python` Python API exclusively. Subagents generating audio-processing
code must follow this rule to avoid pipeline injection.

### API key handling

Deepgram and any other third-party API keys are loaded via Pydantic Settings
from environment variables. Agents must not hardcode keys in source files,
test fixtures, or commit messages.

### Dependency changes

When adding new dependencies, run `uv run pip-audit` after `uv add` and
review the output before committing. If a new CVE is introduced, document it
in `docs/known-vulnerabilities.md` per the schema in that file.

---

## Commit and Branch Rules

- Never commit directly to `main`. Create a feature branch first.
- Branch naming: `{type}/{descriptive-slug}` (e.g., `feat/vad-preprocessing`).
- Commit messages follow Conventional Commits.
- All commits must be GPG-signed (project requirement).
- Run `pre-commit run --all-files` before creating a commit.

---

## References

- Project guidelines: [CLAUDE.md](./CLAUDE.md)
- Global agent and skill catalog: `~/.claude/AGENTS-AND-SKILLS.md`
- Global model selection rules: `~/.claude/CLAUDE.md` (Model Selection section)
- Security policy: [SECURITY.md](./SECURITY.md)
- Known vulnerabilities: [docs/known-vulnerabilities.md](./docs/known-vulnerabilities.md)
