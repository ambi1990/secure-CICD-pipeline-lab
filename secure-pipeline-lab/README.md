# Secure CI/CD Pipeline Lab

A small hands-on project for practising DevSecOps: a deliberately vulnerable
Python/Flask app wrapped in a GitHub Actions security pipeline. You run the
pipeline, see what each tool catches, fix the issues, and turn the pipeline
into a real quality gate.

> **Warning:** `app/app.py` is intentionally insecure. Never deploy it.

## What the pipeline does

| Stage | Tool | Catches | Blocks build? |
|---|---|---|---|
| Pre-commit (local) | gitleaks, Bandit | Secrets and obvious bugs before they reach Git | Blocks the commit |
| Secrets scan | Gitleaks | Secrets anywhere in Git history | Yes |
| SAST | Semgrep (registry + custom rules) | Injection, unsafe deserialisation, TLS off, debug mode | Yes |
| SCA | pip-audit | Python dependencies with known CVEs | Yes |
| Config scan | Checkov | Dockerfile and GitHub Actions misconfigurations | Yes |
| Build | Docker | - | - |
| SBOM | Syft (anchore/sbom-action) | CycloneDX inventory of everything in the image | No (artifact) |
| Image scan | Trivy | OS and library CVEs in the container image | Yes (fixable HIGH/CRITICAL) |
| Sign + attest | cosign (keyless, Sigstore) | Proves the image came from this pipeline, attaches the SBOM | main branch only |
| Verify | cosign verify | What a deploy step / admission controller would check | main branch only |

## Planted issues you should find

| # | Where | Issue | Found by |
|---|---|---|---|
| 1 | app.py | Hardcoded token | Gitleaks, Semgrep |
| 2 | app.py `/user` | SQL injection | Semgrep, Bandit |
| 3 | app.py `/ping` | Command injection (`shell=True`) | Semgrep, Bandit |
| 4 | app.py `/config` | Unsafe `yaml.load` | Semgrep, Bandit |
| 5 | app.py `/fetch` | `verify=False` and SSRF | Custom Semgrep rule, Bandit |
| 6 | app.py | Flask `debug=True`, bound to 0.0.0.0 | Custom Semgrep rule, Bandit |
| 7 | requirements.txt | Flask, Werkzeug, PyYAML, requests with known CVEs | pip-audit, Trivy |
| 8 | Dockerfile | End-of-life `python:3.9` full image (many OS CVEs) | Trivy |
| 9 | Dockerfile | Runs as root, no HEALTHCHECK | Checkov |
| 10 | Dockerfile | Secret in `ARG`/`ENV` (baked into image layers) | Manual review / Trivy secret scan |

## Phase 1 - Set up and see it fail (about 1 hour)

1. Create a new **public** GitHub repo (free GitHub Advanced Security features such as the
   Security tab and code scanning are available on public repos).
2. Push this folder to it.
3. Go to **Actions**. The pipeline runs and most jobs should fail. That's expected.
4. Look at each failure:
   - Actions logs for Gitleaks, pip-audit, Checkov and Trivy
   - **Security > Code scanning** for the Semgrep results (uploaded as SARIF)
   - The `sbom.cdx.json` artifact from the build job
5. Optional: install the local hooks with `pip install pre-commit && pre-commit install`, then
   try to commit a fake secret and watch it get blocked.

Take screenshots of the failing runs. They're useful for your notes and blog post.

## Phase 2 - Fix and harden (about 2-4 hours)

Fix each issue on a branch and open a PR, so you can watch the checks turn green one by one.

**Code fixes**
- Secret: read it from an environment variable (`os.environ["API_TOKEN"]`), and in real life
  from a secret manager. Rotate it. Removing it from history is not enough.
- SQL injection: use a parameterised query: `execute("... WHERE name = ?", (name,))`.
- Command injection: no `shell=True`; pass a list, validate the host
  (e.g., `ipaddress.ip_address(host)`), or drop the feature.
- YAML: `yaml.safe_load(...)`.
- TLS/SSRF: remove `verify=False`; allow-list destination hosts.
- Debug: `debug=False`, read host and port from config, and run behind gunicorn in the container.

**Dependency fixes**
- Upgrade to current versions and re-run pip-audit until it's clean.
- Add Dependabot (`.github/dependabot.yml`) for pip, docker and github-actions.

**Dockerfile fixes**
- Use `python:3.12-slim` (or a distroless image) and pin it by digest.
- Add a non-root `USER`, a `HEALTHCHECK`, and `pip install --no-cache-dir`.
- Remove the `ARG`/`ENV` secret; inject secrets at runtime.
- Consider a multi-stage build.

**Pipeline hardening**
- Uncomment `needs:` in `build-scan-sign` so the image is only built when every gate passes.
- Pin each action to a full commit SHA instead of a tag.
- Add branch protection on `main`: required PR review and required status checks.
- Make a deliberate exception: suppress one finding with a justification comment
  (`# nosemgrep: <rule-id> - reason`) and explain your exception process.

## Phase 3 - Stretch goals (pick one or two)

- Add **DAST**: run the container in the job and scan it with OWASP ZAP baseline.
- Upload the SBOM to **OWASP Dependency-Track** (run it locally with Docker) for continuous monitoring.
- Write a **VEX** statement (OpenVEX) for a CVE that doesn't affect you, and pass it to Trivy with `--vex`.
- Add a **Kyverno** or **cosign policy** in a local kind/minikube cluster that only allows signed images.
- Add **OpenSSF Scorecard** to rate the repo's supply-chain security.
- Run Trivy in `config`/`fs` mode as well, and compare its results with Checkov's.

## Turning it into an interview story

Only claim what you actually built and present it as a personal lab project.
Fill in the brackets with your real numbers once you've done the work.

> "To deepen my DevSecOps skills, I built a security pipeline in GitHub Actions around a
> deliberately vulnerable Flask app. It runs Gitleaks for secrets, Semgrep for SAST, including
> custom rules I wrote for TLS verification and debug mode, pip-audit for dependencies, Checkov
> for Dockerfile and workflow misconfiguration, and Trivy for container image scanning. It
> generates a CycloneDX SBOM with Syft and signs images keylessly with cosign, then verifies the
> signature as a deploy step would.
>
> The first run found [N] issues, including SQL and command injection, unsafe YAML parsing,
> [N] vulnerable dependencies and [N] HIGH/CRITICAL image CVEs, mostly from the end-of-life
> base image. Fixing them and moving to a slim, non-root image cut the CVEs from [X] to [Y].
> Then I made the pipeline a real gate: builds only run when every scan passes, actions are
> pinned to SHAs, and main is protected.
>
> The main lessons were about tuning: deciding what blocks and what only warns, handling false
> positives with a documented suppression, and keeping the pipeline fast enough that developers
> don't route around it. I'd apply the same approach to Mujin's pipelines, with SBOMs per release
> feeding CRA vulnerability handling."

**Likely follow-up questions** (see the question bank):
- Why did you choose these tools? What are the alternatives?
- How would you handle 2,000 findings on a real codebase on day one?
- What does keyless signing actually prove? How would a deployment verify it?
- How would this differ for C++ firmware on a robot controller?
  *(Hint: CodeQL/cppcheck/clang-tidy for SAST, compiler hardening flags, fuzzing, firmware
  signing and secure boot instead of container signing, SBOM from the build system, HBOM.)*
