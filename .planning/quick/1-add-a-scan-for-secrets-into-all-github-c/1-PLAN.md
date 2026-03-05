---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - .pre-commit-config.yaml
  - .secrets.baseline
autonomous: true
requirements: []
must_haves:
  truths:
    - "Any commit containing a hardcoded secret (password, API key, token) is blocked by pre-commit"
    - "A baseline file captures known false positives so legitimate constants in vw_const.py are not flagged"
    - "The hook runs automatically on every `git commit` with no manual steps"
  artifacts:
    - path: ".secrets.baseline"
      provides: "Baseline of known non-secret strings to suppress false positives"
      contains: "detect-secrets baseline JSON"
    - path: ".pre-commit-config.yaml"
      provides: "detect-secrets hook wired into pre-commit"
      contains: "detect-secrets"
  key_links:
    - from: ".pre-commit-config.yaml"
      to: ".secrets.baseline"
      via: "detect-secrets hook --baseline flag"
      pattern: "--baseline .secrets.baseline"
---

<objective>
Add `detect-secrets` to the pre-commit hook pipeline so every `git commit` is automatically scanned for accidentally committed secrets (passwords, API keys, tokens).

Purpose: This codebase stores real VW OAuth credentials in vw_const.py and the e2e tests read VW_TEST_USERNAME/VW_TEST_PASSWORD from env. One accidental `git add` of a .env file or hardcoded credential would leak live auth tokens publicly.

Output: `.pre-commit-config.yaml` updated with detect-secrets hook, `.secrets.baseline` created to capture known safe constants so the scanner does not block legitimate commits.
</objective>

<execution_context>
@/home/pascal/.claude/get-shit-done/workflows/execute-plan.md
@/home/pascal/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Generate detect-secrets baseline</name>
  <files>.secrets.baseline</files>
  <action>
Run detect-secrets to scan the current repo and generate a baseline file. This captures any strings that look like secrets in vw_const.py (client IDs, endpoint strings) so they are classified as known non-secrets and do not block future commits.

Steps:
1. Install detect-secrets into the venv: `./venv/bin/pip install detect-secrets`
2. Generate baseline, excluding known-safe paths: `./venv/bin/detect-secrets scan --exclude-files 'tests/fixtures/resources/responses/.*' > .secrets.baseline`
3. Review the baseline output — if any entries are obvious false positives (e.g., client_id constants in vw_const.py that are already public), they are captured and marked as safe by virtue of being in the baseline file.

Do NOT manually edit the baseline JSON — the scan output is canonical.
  </action>
  <verify>
    <automated>./venv/bin/python -c "import json; d=json.load(open('.secrets.baseline')); print('OK, version:', d['version'])"</automated>
    <manual>Confirm .secrets.baseline exists and contains a "results" key</manual>
  </verify>
  <done>.secrets.baseline exists, is valid JSON, and contains a "version" field from detect-secrets schema</done>
</task>

<task type="auto">
  <name>Task 2: Add detect-secrets hook to pre-commit config</name>
  <files>.pre-commit-config.yaml</files>
  <action>
Append the detect-secrets repo block to `.pre-commit-config.yaml`. Use the Yelp detect-secrets hook which runs on every commit and compares staged files against the baseline.

Add this block at the end of the `repos:` list:

```yaml
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package.lock.json
```

Use rev `v1.4.0` (latest stable as of 2025). Do NOT use `v1.5.0` or above — the hook interface changed and it requires additional config.

After editing the file, run `pre-commit autoupdate --repo https://github.com/Yelp/detect-secrets` to pin to the latest stable tag, then verify the yaml is still valid.

Also add `.secrets.baseline` to `.gitignore` ONLY if it does not already appear there. In this project, `.gitignore` has `.planning/` excluded — `.secrets.baseline` should be committed (it needs to be shared so all contributors share the same baseline), so do NOT add it to `.gitignore`.
  </action>
  <verify>
    <automated>./venv/bin/pre-commit run detect-secrets --all-files</automated>
    <manual>Run `git commit --dry-run` on a file with a fake password string to confirm it is blocked (optional manual spot-check)</manual>
  </verify>
  <done>
`pre-commit run detect-secrets --all-files` exits 0 (no new secrets beyond baseline). Hook appears in `pre-commit run --list-hooks` output.
  </done>
</task>

</tasks>

<verification>
After both tasks:
- `pre-commit run detect-secrets --all-files` exits 0
- `.secrets.baseline` is tracked by git (`git status` shows it as new file)
- `.pre-commit-config.yaml` contains `detect-secrets` entry
- A test: create a temp file with `password = "abc123secret"`, stage it, attempt commit — pre-commit should block it with a secrets detection error (then discard the temp file)
</verification>

<success_criteria>
Every `git commit` in this repo now automatically scans staged files for secrets. Known safe constants (VW client IDs, endpoint URLs) are baselined and do not produce false-positive blocks. New secrets added to staged files are caught before they reach the remote.
</success_criteria>

<output>
After completion, create `.planning/quick/1-add-a-scan-for-secrets-into-all-github-c/1-SUMMARY.md` summarising what was done, files changed, and the detect-secrets version pinned.
</output>
