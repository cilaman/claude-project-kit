# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

## Where to start

- Rules for people and AI agents: [CLAUDE.md](CLAUDE.md)
- Documentation map: [docs/index.md](docs/index.md)
- Active work: [backlog/BACKLOG.md](backlog/BACKLOG.md) — what is `BL-NN`:
  `grep '^BL-NN' backlog/tasks.tsv`

## Running it

*(How to install, configure and run — the one home of these commands.)*

## Checks

```bash
python3 scripts/check_repo.py          # structure, backlog, docs, links
{{TEST_COMMAND}}
```

## For maintainers

The label vocabulary lives in `.github/labels.yml` and is applied with
`python3 scripts/github_labels.py` (needs `gh auth login`). A label clicked in the web
UI disappears on the next run.
