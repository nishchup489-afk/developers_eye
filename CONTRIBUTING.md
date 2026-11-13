# Contributing to Developer's Eye

Thank you for contributing to Developer's Eye. It is a complex project that is
meant to be easy to contribute to: the repo is organized, every decision is
written down, and generated docs keep the maps in step with the code. Please
keep that discipline when you contribute, so the next person finds it just as
easy.

New here? Start with the [setup guide](setup-guide.md), then pick a
[good first issue](https://github.com/nishchup489-afk/developers_eye/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
or open an issue to discuss your idea. Questions are welcome on
[Discord](https://discord.gg/jxbRsFj3d).

## The workflow

1. **Fork and branch.** Create a branch from `main` named after the change, such
   as `fix/robots-redirect` or `feat/version-filter`.
2. **Read before you change.** Each subsystem has an overview and decision
   records in [`0_tech_docs/`](0_tech_docs/README.md). Check the
   [record index](0_tech_docs/record-index.md) for anything that touches your area.
3. **Make the change, with tests.**
4. **Follow the rules below** for tests, experiments, APIs and bugs.
5. **Run the tests** with `python scripts/run_all_tests.py`.
6. **Commit in small steps** and open a pull request.

## The rules

### 1. After every new test, experiment or diagnostic

- Put the test in **its own file**, in the matching `tests/` folder of the part
  you changed.
- Update the **test case write-up** for that part (`backend/tests/test_case.md`,
  `crawler/tests/test_case.md` or `frontend/tests/test_case.md`) with what you
  tested and what you found.
- Run `python scripts/update_test_index.py` to refresh the
  [test index](tests/test-index-of-whole-app.md) and the
  [list of all test cases](tests/all-test-cases-that-were-tested/index.md).
- If you measured something, document it as an experiment, **`EXP-XXXX`**, from
  the [experiment template](0_tech_docs/_templates/experiment.md).
- If the experiment led to a decision, record it as **`ADR-XXXX`** from the
  [decision template](0_tech_docs/_templates/decision.md), and link the two
  records to each other.
- Run `python scripts/update_record_index.py` and
  `python scripts/update_docs_nav.py`.

### 2. After adding or changing an API, in the backend or the frontend

- Document it. If it is a critical design choice (a new public endpoint, a
  change in who can reach it, a new limit), write an **ADR**. Otherwise, update
  the docs next to the code.
- Run `python scripts/update_api_map.py` to regenerate the
  [API map](0_tech_docs/infra/system-architecture/api-map.md), then
  `python scripts/update_docs_nav.py`.

### 3. When you find a critical bug

- Write it up as an incident, **`INC-XXXX`**, from the
  [incident template](0_tech_docs/_templates/incident.md): what broke, the root
  cause and the fix.
- Link it to the experiment or decision it relates to, in both directions.
- Run `python scripts/update_record_index.py` and
  `python scripts/update_docs_nav.py`.

### Numbering and placement

Take the next free number for each prefix from the
[record index](0_tech_docs/record-index.md). Put the record in the
`0_tech_docs/<area>/<feature>/` folder it belongs to, next to related records.

### Let the hook do it for you

```bash
python scripts/update_test_index.py --install-hook
```

This installs a git pre-commit hook that refreshes the test index and the record
index on every commit. Every generator also has a `--check` mode that exits
with an error when its output is out of date, so you can confirm nothing is
stale before you push.

## Commits

- Keep commits **small and focused**: one logical change each.
- Start the message with a prefix:
  - `feat:` a new feature
  - `fix:` a bug fix
  - `docs:` documentation only
  - `test:` tests only
  - `refactor:` a code change that neither fixes a bug nor adds a feature
- Write the rest in plain words, such as
  `fix: release the lease when a fetch times out`.

## Pull requests

- Describe **what** changed and **why**, and link the issue and any ADR, INC or
  EXP records.
- Make sure `python scripts/run_all_tests.py` passes and the generated docs are
  current.
- Include screenshots for any UI change, on desktop and on a phone width.
- Keep one pull request to one topic. Two unrelated fixes are two pull requests.

## Code style

- **Python:** type hints on public functions, async I/O through the existing
  helpers, and no new dependencies without a reason in the pull request.
- **Frontend:** run `npm run lint` and `npx tsc --noEmit` in `frontend/` before
  pushing. CI runs both.
- Follow the patterns already in the file you are editing.

## Where to talk

- Bugs and feature ideas: [GitHub issues](https://github.com/nishchup489-afk/developers_eye/issues)
- Questions and chat: [Discord](https://discord.gg/jxbRsFj3d)

By contributing you agree that your work is released under the project's
[MIT License](LICENSE).
