# MINI-SPEC I0 — Release Gate: Windows Package & Production Integrity

- **Parent phase:** Phase I — Kịch bản thành chỉ đạo hình ảnh
- **Author:** Perplexity
- **Date:** 2026-09-21
- **Status:** Ready for audit; no product/visual-direction feature work may begin before this gate closes.

---

## Context

### Required reading before any code change

- `FEATURES.md` (updated 2026-09-21)
- `MINI_SPEC_PLAYBOOK.md`
- `docs/ARCH.md`
- `docs/API.md`
- `docs/TEST_LOG.md`
- Existing CI/release workflows, PyInstaller build scripts, Dockerfiles, and deploy verification scripts

### Confirmed current state

1. The latest released Windows application is **v3.17.19**.
2. `main` contains newer work than v3.17.19, including D1/D3/D5 and a dub-worker build fix, but no new `.exe` has been built from that state.
3. Production services `voxdub-app` and `voxdub-dub-worker` are reported to match `main`; job `kiem-prod-theo-main` was green on 2026-09-21.
4. One Python test is currently red: `test_d3_deploy_integrity.py::test_DAU_CUOI_hai_commit_chi_khac_TAI_LIEU_thi_thu_muc_build_KHONG_doi`.
5. The documented cause is a **test classifier defect**, not a confirmed product defect: the test excludes `control_server/`, `website/`, and `autodub/` when looking for a documentation-only commit pair, but fails to exclude `scripts/`. This is wrong because `scripts/setup_*.py` are build inputs copied into the dub-worker Docker image.
6. CI performs a real dub run on a Windows runner using source code; the packaged `.exe` currently receives only startup smoke coverage and worker-file presence checks.
7. Heavy AI engines must remain outside the PyInstaller main process, in dedicated child virtual environments invoked through subprocesses. Importing heavy engines in the main process has failed four times in prior releases.
8. The project has repeatedly suffered from missing packaged files and deploys that reported success while production served stale code. D5 now verifies production against `main`; this protection must not be weakened.

### Architecture decisions that must remain unchanged

- Windows remains the supported desktop release target for this phase.
- PyInstaller `onedir` packaging remains the current distribution mechanism unless audit proves it is broken.
- Heavy engines (Whisper, Paraformer, Demucs, VieNeu, NLLB, diarization, lipsync, OCR and equivalent future engines) remain subprocess workers in `.venv-*`; do not import their heavy libraries in the GUI/main process.
- Existing automated deployment branch generation and `kiem-prod-theo-main` remain the single production-integrity path; do not introduce a parallel deploy workflow.
- The release may not be declared successful based only on CI green status, HTTP 200, a PyInstaller build success, or a startup smoke test.

---

## Goal

Produce and verify a new Windows release built from the current approved `main` state, so a real user can install or upgrade VoxDub, execute an end-to-end local dub successfully, and receive a release whose packaged workers and production services are demonstrably aligned with the approved source revision.

---

## Constraints (Guardrails)

1. **Audit before mutation.** Do not edit the D3 test, build scripts, packaging list, release workflow, or deploy workflow until the actual current implementation and failing commit pair have been inspected.
2. **Fix the cause, not the symptom.** The D3 test must not simply be skipped, weakened, marked xfail, or changed to accept arbitrary `scripts/` changes.
3. **No green-by-exclusion.** A test suite with skipped GUI/import tests due to a broken environment is not evidence of a successful release. Record test totals, skips, and reason for every skip.
4. **No hidden packaging fallback.** If a required worker/script/file is missing from the package, the release must fail loudly; do not silently rely on files from a developer checkout or an older installation.
5. **No heavy-engine imports in the main process.** This work may adjust packaging and subprocess invocation only; it must not move Whisper, Demucs, VieNeu, NLLB, OCR, diarization, torch, PIL, or comparable dependencies into the GUI executable process.
6. **No manual production declaration.** `/health` evidence and the existing production-vs-main verification path are required. A platform deploy job reporting success is insufficient.
7. **No release tag before gates pass.** The Windows version tag may only be pushed after required suites, package audit, clean-install validation, upgrade validation, and packaged end-to-end dub evidence pass.
8. **Upgrade must preserve user investment.** The test must cover reuse of existing sibling-install `.venv-*`, `models/`, `bin/`, and configuration/token migration behavior. Do not overwrite or delete user models/configuration without an explicit user action.
9. **Every exception path needs evidence.** Any new `except` block, fallback, or skipped verification must log why it occurred and surface an actionable outcome.
10. **Scope discipline.** I0 does not add visual-direction prompts, new AI providers, H4d activation, new video effects, TTS engines, or new product features.

---

## Scope

### A. Domain model and release evidence

Audit first; add only fields/artifacts that are proven absent.

Required release evidence must identify:

- Source commit SHA selected for release.
- Release tag/version.
- PyInstaller artifact name and SHA-256 checksum.
- Build workflow run URL/ID.
- Test suite totals: passed, failed, skipped, environment used, and timestamp.
- Packaged worker/file manifest result.
- Clean-install validation result.
- Upgrade validation result.
- Packaged end-to-end dub result, including output paths and measured audio/video checks.
- Production service health evidence for `voxdub-app` and `voxdub-dub-worker`, including source SHA where supported.

**Preferred implementation:** reuse existing CI artifacts, GitHub Actions summaries, release metadata, health verification output, and test logs. Do not create a new database table or dashboard unless audit proves the existing release evidence cannot carry these fields.

### B. D3 test classifier repair

#### Required audit

1. Open the failing test and identify exactly how it selects its candidate “documentation-only” commit pair.
2. Identify every repository path that contributes to a deployable build artifact for:
   - `voxdub-app` / `control_server`
   - `voxdub-dub-worker`
   - Windows `.exe` packaging
3. Confirm from Dockerfiles/workflows whether `scripts/setup_*.py` are copied, executed, or otherwise affect either service build.
4. Reproduce the currently failing classification using the exact commit pair chosen by the test.

#### Required change

Repair the classifier so it treats build-affecting paths as source/build changes, not documentation-only changes. The expected minimum correction is to include `scripts/` in the set of paths that disqualify a candidate pair from being called documentation-only, **if and only if the audit confirms those scripts are build inputs**.

Do not hard-code a specific commit SHA as the only fixture. Prefer a deterministic fixture or explicit test fixture repository history if the current test discovers commits dynamically and can become flaky.

#### Required regression tests

- A commit pair differing only in documentation must remain classified as documentation-only and must not require a service deployment.
- A pair touching `scripts/setup_vieneu.py` or another confirmed build input must be classified as build-affecting.
- A pair touching only an unrelated non-build path must follow the documented classification rule.
- Removing the `scripts/` protection must make at least one regression test fail.

### C. Packaging-manifest audit

#### Required audit

1. Locate the single source of truth for install/setup worker scripts and the single source of truth used by PyInstaller packaging.
2. Confirm the packaging list is derived rather than duplicated by hand. If it is duplicated, identify the smallest safe convergence change.
3. Enumerate workers/scripts required by the user-visible install flows and local pipeline:
   - ASR/Whisper or Paraformer
   - Demucs
   - VieNeu
   - NLLB
   - OCR
   - diarization/lipsync only where their UI/install path exposes them
4. Verify that every required worker has a package inclusion rule and is reachable from the packaged executable through the existing subprocess mechanism.

#### Required change

Add or strengthen a deterministic package-manifest check that compares:

- Required worker/install script inventory derived from the source-of-truth directory/configuration;
- Files included in the build/staging manifest;
- Files physically present in the generated release artifact.

The check must fail with the missing file names. It must not merely count files.

### D. Windows clean-install verification

#### Test environment

Use a clean Windows environment or a fresh isolated directory with no prior VoxDub parent/sibling install available to be discovered.

#### Required steps

1. Download/use the exact generated release artifact, not source checkout output.
2. Extract/install into a clean folder.
3. Launch the `.exe` and confirm basic startup.
4. Verify all declared worker setup scripts/resources are present in the artifact.
5. Exercise the existing user-visible engine installation paths needed for the selected smoke pipeline, recording any network requirement explicitly.
6. Run a minimal packaged local dub using a controlled fixture:
   - local input video;
   - known transcript/manual translation if external translation would create unnecessary cost or network dependence;
   - VieNeu local TTS;
   - FFmpeg merge/export;
   - no cloud-only capability required.
7. Verify output file exists and is readable.
8. Measure output audio stream, non-silence/mean volume, and audio/video duration relationship using the project’s existing verification tooling where available.
9. Preserve logs and the output artifact as CI evidence where practical.

#### Acceptance behavior

If an engine is intentionally not installed in clean state, UI must state that it is unavailable and how to install it; it must not report a false “no content” or generic unexpected error.

### E. Windows upgrade verification

#### Test environment

Create a representative prior-version sibling installation under the same parent directory, with safe dummy or real reusable data as permitted:

- `.venv-*` directories or marker fixtures;
- `models/` marker fixture;
- `bin/` marker fixture;
- `.env`/settings/token migration fixture using non-production credentials.

#### Required steps

1. Place the new release side-by-side with the previous installation under one parent folder.
2. Launch the new `.exe`.
3. Verify detection/reuse behavior for engines/models/binaries and one-time configuration migration.
4. Verify no source folder is modified destructively and no old configuration/model is deleted.
5. Verify the app’s displayed state is internally truthful: reused means reused; unavailable means unavailable.
6. Run the same minimal packaged local dub if reuse makes its engines available.

#### Negative cases

- New release in a different parent folder: it must not falsely claim automatic reuse.
- Old installation missing a component: new release must not claim it reused it.
- Invalid old `.env`/token: migration must not leak secrets in UI/logs and must produce an actionable state.

### F. Packaged end-to-end dub gate

This is the release-critical evidence.

#### Required pipeline

Use the generated Windows `.exe`, not Python source invocation:

1. Local video input.
2. Audio extraction.
3. ASR path supported by the release fixture.
4. Manual translation or deterministic local path.
5. VieNeu local TTS through child worker/subprocess.
6. Video/audio merge/export.
7. Output verification.

#### Required assertions

- The main GUI/process did not import a heavy engine directly; worker execution is observable as subprocess behavior through existing logs/process evidence.
- Output video exists and opens.
- Output includes an audio stream.
- Output audio is not silent according to the project’s existing measurable threshold/tool.
- Audio and video streams have valid durations; duration mismatch is within the existing product contract or is explicitly reported as a failure.
- The final frame/coda is not visually truncated when the output route uses the H4/D1 timing path; if the fixture does not use H4, record that this assertion is out of route rather than claiming coverage.
- Cancellation/error paths preserve intermediate files according to the existing resumability contract.

### G. Production integrity verification

Do not redesign D5. Verify that current protections still operate after I0 changes.

Required checks:

1. `kiem-prod-theo-main` executes for the release candidate workflow state, including the no-deploy/failed-deploy path where the existing test harness supports it.
2. `voxdub-app` health response confirms application readiness and database connectivity according to current contract.
3. `voxdub-dub-worker` health response exposes the deployed SHA or the already-approved equivalent provenance evidence. If it still cannot do so, this is a **blocker** for declaring I0 complete, not a warning to hide.
4. The deployed SHA is equal to the release candidate SHA or is a confirmed descendant/ancestor relationship allowed by documented rollout policy; direction of drift must be checked, not just difference.
5. A simulated or fixture-based stale-production case must cause the verification gate to fail visibly.

### H. Release procedure and documentation

Update existing documents rather than inventing a second release manual:

- `FEATURES.md`: released Windows version, what has now been verified, and remaining limits.
- `docs/ARCH.md`: package/worker boundary only if audit changed it.
- `docs/API.md`: only if health contract or release evidence API changes.
- `docs/TEST_LOG.md`: exact test totals, environment, Windows package verification, bugs found, and fixes.
- Existing release runbook/CI documentation: release checklist and required evidence links.

The release notes must distinguish:

- Changes included in the `.exe`;
- Server changes already in production;
- Features present in code but still administratively locked or unconfigured;
- Known limits.

---

## Audit Before Build

The implementing agent must complete this checklist in the report before writing production code.

### 1. Current workflow inventory

- [ ] Locate the release tag workflow.
- [ ] Locate the PyInstaller build entry point and staging directory.
- [ ] Locate every place that enumerates or discovers worker/setup scripts.
- [ ] Locate the Windows source-based real-dub CI job.
- [ ] Locate `.exe` smoke/package checks.
- [ ] Locate deploy-branch generation, deploy decisions, and `kiem-prod-theo-main`.
- [ ] Locate health endpoints for `voxdub-app` and `voxdub-dub-worker`.

### 2. D3 failing-test evidence

- [ ] Capture the exact current failure output.
- [ ] Record the commit pair selected by the test.
- [ ] List changed paths for that pair.
- [ ] Prove from Dockerfile/workflow that each disputed path is or is not a build input.
- [ ] Determine whether test history scanning can produce nondeterministic candidate selection.

### 3. Package truth table

For each user-exposed local engine/install route, record:

| Capability | User-facing install/action | Setup script/worker | Source location | Build inclusion rule | Present in artifact? | Invoked as subprocess? |
|---|---|---|---|---|---|---|
| Whisper/ASR | Audit required | Audit required | Audit required | Audit required | Audit required | Audit required |
| Paraformer | Audit required | Audit required | Audit required | Audit required | Audit required | Audit required |
| Demucs | Audit required | Audit required | Audit required | Audit required | Audit required | Audit required |
| VieNeu | Audit required | Audit required | Audit required | Audit required | Audit required | Audit required |
| NLLB | Audit required | Audit required | Audit required | Audit required | Audit required | Audit required |
| OCR | Audit required | Audit required | Audit required | Audit required | Audit required | Audit required |
| Diarization/lipsync | Audit if exposed | Audit if exposed | Audit if exposed | Audit if exposed | Audit if exposed | Audit if exposed |

### 4. Gap classification

Classify every confirmed gap before building:

- Packaging/inclusion gap
- Worker invocation boundary gap
- CI coverage gap
- Windows-only behavior gap
- Deploy provenance/health gap
- Documentation/release-note gap
- Test-fixture/test-classifier defect

Do not expand I0 to a new product capability based on an audit observation.

---

## Design Choice

I0 uses a **single evidence chain** rather than treating build, package, Windows execution, and production deployment as independent success signals:

\[
\text{approved main SHA}
\rightarrow
\text{all required tests}
\rightarrow
\text{artifact manifest verification}
\rightarrow
\text{clean-install packaged dub}
\rightarrow
\text{upgrade packaged dub}
\rightarrow
\text{tag/release artifact}
\rightarrow
\text{production health + provenance verification}
\]

A gate failure stops the chain and leaves a durable artifact/log explaining which step failed. No later green step can overwrite an earlier missing proof.

### Why this design

- PyInstaller success does not prove worker files are included.
- Worker files being included does not prove Windows invocation works.
- Source-based Windows dub success does not prove packaged `.exe` behavior.
- Deploy job success does not prove production runs the intended revision.
- Health HTTP 200 does not prove the service is connected to MongoDB or is running the right build.

This design extends existing CI, package checks, real Windows dub checks, D3 deployment integrity, D5 production-vs-main verification, and sibling-install reuse behavior. It does **not** create a parallel release system, new app feature, or alternative deployment pipeline.

---

## Test Plan

### Unit tests

1. D3 classifier marks documentation-only change sets correctly.
2. D3 classifier marks every confirmed `scripts/` build input as build-affecting.
3. Build input inventory/manifest comparison emits exact missing paths.
4. Artifact verification rejects a worker script present in source but absent from package.
5. Artifact verification rejects duplicated/stale manifest entries if the project’s packaging format permits them.
6. Upgrade discovery logic distinguishes same-parent sibling install from a different-parent directory.
7. Upgrade discovery does not mark missing components as reused.
8. Health provenance comparison checks directionality, not merely SHA inequality.

### Integration tests

1. Build the Windows artifact from the release candidate SHA.
2. Inspect generated artifact/staging output against the manifest.
3. Launch the packaged `.exe` in a clean Windows environment.
4. Run the minimum packaged local dub pipeline with controlled fixture media.
5. Validate output stream presence, non-silence, and duration using existing project tooling.
6. Launch the new package beside a prior sibling install and verify reuse/config migration behavior.
7. Run `kiem-prod-theo-main` against fixture/staging data that represents both aligned and stale production.
8. Verify app and worker health contracts return the required readiness/provenance fields.

### Regression tests

1. Removing a required worker from package configuration must fail the package-manifest test.
2. Changing `scripts/setup_vieneu.py` must not be treated as documentation-only.
3. A real documentation-only change must still avoid an unnecessary worker deployment.
4. A simulated failed deploy followed by a no-code-change run must be caught by production-vs-main verification.
5. Making the main process directly import a banned heavy-engine module must fail an existing/new static boundary test, if a project-standard check exists; otherwise add a narrowly scoped check only for known forbidden imports.
6. A clean install must not use a sibling installation unexpectedly.
7. A different-parent upgrade installation must not falsely show reused engine/model state.
8. A packaged end-to-end dub must fail release gating if output has no audio stream or violates the project non-silence threshold.

### Live verification

Perform and record both runs on Windows using the exact candidate artifact:

1. **Clean install run:** no prior sibling installation; execute minimum local dub pipeline.
2. **Upgrade run:** current/new artifact next to a representative previous installation; execute startup, reuse verification, and the same pipeline where available.

For each run, record:

- Windows version and runner/machine class.
- Artifact filename and SHA-256.
- Source SHA/version tag.
- Input fixture ID/hash.
- Selected engine paths.
- Worker subprocess log evidence.
- Output video/audio probe values.
- Any user-visible warning/error text.
- Result: pass, fail, or blocked—with cause.

A source-only run, mocked worker, hand-copied worker, or manual “it opened” statement does not satisfy live verification.

---

## Release Checklist

### Before tag

- [ ] Audit Before Build completed and attached to implementation report.
- [ ] D3 test issue repaired through the confirmed root cause.
- [ ] Full required Python, Node, and React suites passed; all skips listed with justification.
- [ ] Windows source-based real dub remains green.
- [ ] Candidate artifact built from clean checkout at approved SHA.
- [ ] Artifact manifest verification passed.
- [ ] Clean-install packaged live verification passed.
- [ ] Same-parent upgrade packaged live verification passed.
- [ ] `kiem-prod-theo-main` and health/provenance verification passed or documented as not applicable before release deployment.
- [ ] `FEATURES.md`, `TEST_LOG.md`, and release runbook updated truthfully.

### After tag/deploy

- [ ] Release artifact checksum published/recorded.
- [ ] GitHub release links the exact workflow/build evidence.
- [ ] Production deploy completed through existing deploy branches.
- [ ] `voxdub-app` health confirms readiness and database connection.
- [ ] `voxdub-dub-worker` health provides provenance evidence and is aligned with release SHA.
- [ ] `kiem-prod-theo-main` confirms no stale production state.
- [ ] Any mismatch is visible as failed/blocked; do not announce release success.

---

## Success Criteria

I0 is complete only when all statements below are true:

1. The D3 test is green for the correct reason: build-affecting `scripts/` changes cannot be misclassified as documentation-only, while genuine documentation-only changes retain their intended behavior.
2. A new Windows `.exe` release has been built from the approved current `main` SHA and has a recorded artifact checksum.
3. Required local workers/setup resources are physically present in the release artifact and are verified by a deterministic manifest check.
4. A clean Windows installation of the packaged `.exe` completes a controlled local end-to-end dub through the intended subprocess worker path and exports a readable, non-silent output video.
5. A same-parent sibling upgrade preserves/reuses eligible engines/models/binaries/settings without destructive changes, and a different-parent install does not falsely claim reuse.
6. Production verification proves both server services are healthy and running the intended source provenance; stale production produces a visible gate failure.
7. Documentation and release notes distinguish verified behavior, administratively locked capabilities, and known limits without claiming source-only or untested functionality as released.
8. No I0 change introduces a heavy-engine import into the main process, a bypass of D3/D5, or an untracked exception/fallback.

---

## Out of Scope

- Visual direction catalog, `scene_director`, camera/zoom/effect prompts, or UI.
- Configuring `assist` or `image` providers.
- Activating H4d, image calibration, or modifying the image compliance gate.
- New TTS engines, including ZeroTTS.
- New video generation, optical-flow analysis, camera-motion recognition, or editor timeline capabilities.
- Changes to H3 pricing; H3 needs 10–20 real runs before pricing decisions.
- macOS/Linux support.

---

## Required Completion Report

The implementer must report using this exact structure:

1. **Summary** — release candidate version/tag, approved SHA, scope completed.
2. **Audit Before Build** — workflows/files inspected; D3 failure evidence; confirmed package truth table; gaps found.
3. **Design Choice** — exact D3 fix and package-evidence mechanism chosen.
4. **Changed Files** — backend, CI/workflows, packaging, tests, docs; no hand-waving.
5. **New API/DB/State** — explicitly state “none” unless audit required a minimal compatible change.
6. **Tests** — commands, totals, pass/fail/skip counts, environment, and regression proof that guardrails fail when removed.
7. **Windows Live Verification** — artifact hash, clean-install run, upgrade run, subprocess proof, output probes, logs/artifacts.
8. **Production Verification** — app health, worker health/provenance, `kiem-prod-theo-main` result, deployed SHA relationship.
9. **Release Result** — released / blocked; exact reason if blocked.
10. **Remaining Limits / Follow-ups** — only items outside I0; proposed next gate is I1 only if I0 is fully closed.
