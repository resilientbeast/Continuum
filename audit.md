# Production-Bound Audit — Continuum Audio Pipeline

**Scope:** `main.py`, `api.py`, `placement_agent_harness.py`, `adm_renderer.py`,
`ffmpeg_fallback.py`, `binaural_renderer.py`, `caption_extractor.py`,
`stem_feature_extractor.py`, `dashboard.py`, `test_models.py`, `Dockerfile`,
`run_instructions.sh`, `.env.example`, and the `web/` Next.js frontend
(`src/**`, `next.config.ts`, `middleware.ts`, `package.json`).

**Method:** Static read-only review. No files were modified. Findings are cited
as `file:line`. Severities are **Critical / High / Medium / Low**.

The README itself states (line 103): *"Auth and job storage are prototype-level,
not production-hardened."* This audit confirms that and enumerates the concrete,
exploitable issues that must be closed before this is treated as production.

---

## Executive summary

The spatial-audio pipeline logic (ADM assembly, FFmpeg fallback, binaural
convolution, coherence checking) is thoughtfully designed and largely correct in
single-process, single-user use. **It is not safe to run as the deployed
multi-tenant service in its current form.** Three issues block production on
their own:

1. **Authentication is disabled by default and bypassable when enabled.** The
   shipped config (`CLERK_ISSUER=""`) makes `get_current_user` skip JWT signature
   verification entirely, so any client can impersonate any user. Even with
   `CLERK_ISSUER` set, `iss`/`aud` are not verified.
2. **Cross-tenant S3 object access (IDOR).** `/job` trusts a client-supplied
   `s3_key` and downloads any object in the bucket, letting a user exfiltrate
   other users' uploads or rendered results.
3. **The agent stage writes to a hardcoded shared `output/` directory**, not the
   per-job `output_dir`. Concurrent jobs corrupt each other's coherence memory,
   overwrite each other's placement files, leak disk, and silently fail to
   upload the coherence evidence the product claims to preserve.

Beyond those: no concurrency limit or queue (DoS / OOM), no subprocess timeout,
non-durable SQLite job state, container runs as root, no `.dockerignore`/no
root `.gitignore`, frontend bypasses the very proxy added to avoid
mixed-content/plaintext tokens, a `7.1.4` format offered in the UI that always
fails, and **effectively zero automated test coverage**.

---

## Security

### S1 — Critical: JWT signature verification is skipped when `CLERK_ISSUER` is unset (default)

`api.py:63-81` — `get_current_user`:

```python
if jwks_client:
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    decoded = jwt.decode(token, signing_key.key, algorithms=["RS256"], ...)
else:
    print("WARNING: CLERK_ISSUER not set, skipping JWT signature verification")
    decoded = jwt.decode(token, options={"verify_signature": False})
return decoded.get("sub")
```

`jwks_client` is only created when `CLERK_ISSUER` is set (`api.py:37-39`).
`.env.example:9`, `run_instructions.sh:22`, and the README docker run all ship
`CLERK_ISSUER=""` (empty). In that default state every endpoint accepts **any**
JWT with **no signature check** — a client crafts `{"alg":"none","sub":"<victim
user id>"}` (or any unsigned token) and fully impersonates that user: list their
history, poll their jobs, download their results, and submit jobs billed to the
operator. This is a total authentication bypass.

**Fix:** treat missing `CLERK_ISSUER` as a hard startup failure (refuse to serve)
rather than silently downgrading to unsigned decode. Never ship with verification
off.

### S2 — High: `iss`/`aud` are not verified even when signatures are checked

`api.py:70-75` — `jwt.decode(...)` is called without `audience=` or
`options={"verify_aud": True, "verify_iss": ...}`. PyJWT verifies `exp` by
default but not issuer/audience. A token minted for a different Clerk app or any
resource sharing the JWKS would be accepted. Verify `iss == CLERK_ISSUER` and the
expected `aud`.

### S3 — High: Cross-tenant S3 read via client-supplied `s3_key` (IDOR)

`api.py:106-117` — `run_pipeline_task` downloads whatever `s3_key` the client
sent in the `JobCreate` body:

```python
s3_client.download_file(AWS_S3_BUCKET_NAME, s3_key, str(video_path))
```

`/s3/upload-url` generates keys scoped to `uploads/{user_id}/{uuid}_{filename}`
(`api.py:88`), but `/job` (`api.py:186-201`) **never re-checks** that the supplied
`s3_key` matches that pattern or belongs to the caller. A user can submit
`s3_key = "results/<other_job_id>/mastered.wav"` (or any other user's
`uploads/...` key). The backend downloads it, re-renders it, uploads the result
to `results/{this_job_id}/mastered.wav`, and hands the caller a presigned
download URL (`api.py:160-175`, `226-251`). Net effect: **arbitrary in-bucket
object exfiltration** of other tenants' source media and mastered audio.

**Fix:** validate `s3_key` starts with `f"uploads/{user_id}/"` and reject
anything else before downloading; consider a server-generated key stored on the
job row rather than trusting the client.

### S4 — High: No concurrency limit, no queue, no rate limiting → DoS / OOM

`api.py:198-199` — every `/job` call spawns a bare `threading.Thread` that runs
Demucs + ffmpeg + EAR on a full video. There is no queue, no semaphore, no
per-user rate limit, and no cap on concurrent jobs. Each job is heavy
(CPU/memory). A single user (or, given S1, an unauthenticated one) can submit
dozens of jobs and exhaust the Lightsail instance's memory/CPU, crashing the
server for everyone. The README describes this as "a running product" on a
single Lightsail instance.

**Fix:** bound concurrency (a `Semaphore` or a real task queue), enforce per-user
rate limits, and set container memory/CPU limits.

### S5 — High: No subprocess timeout; worker threads can hang forever

`api.py:136-146` — the pipeline runs via `Popen` and the stdout is drained in a
`readline` loop with no timeout. A hung ffmpeg/demucs/EAR process or a stalled
LLM call blocks the worker thread indefinitely. Threads are never joined or
cancelled, so hung processes accumulate. Combined with S4, a few hung jobs
exhaust the thread/process pool permanently.

**Fix:** `process.wait(timeout=...)` with kill-on-timeout, and per-stage timeouts.

### S6 — Medium: CORS misconfiguration

`api.py:18-24` — `allow_origins=["*"]` together with `allow_credentials=True`.
This is a flagged invalid combination (browsers reject credentialed requests
with a wildcard origin). Auth uses a Bearer header rather than cookies, so it is
not directly exploitable today, but it is a misconfiguration that will trip
audits and will break if cookie-based credentials are ever added. Set an explicit
origin allowlist (the known Vercel frontend URL) and drop `allow_credentials`
unless actually needed.

### S7 — Medium: Bearer tokens likely transmitted in plaintext / mixed content

The frontend computes `API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`
(`web/src/app/dashboard/page.tsx:31`) and calls the backend **directly** at that
absolute URL with `Authorization: Bearer <token>` (e.g. lines 37, 63, 127, 161,
436). `next.config.ts:4-12` defines a `/api/:path*` rewrite to `BACKEND_URL`
specifically "to bypass browser Mixed Content blocks," but the dashboard never
uses `/api` — it uses `NEXT_PUBLIC_API_URL`. So in production (HTTPS frontend on
Vercel → backend), either (a) `NEXT_PUBLIC_API_URL` is `http://` → mixed-content
block *and* the Clerk token crosses the internet in plaintext, or (b) it must be
an HTTPS backend URL configured separately. The protective proxy is dead code.

**Fix:** route frontend calls through the `/api` rewrite (relative URLs), and
ensure the backend terminates TLS. Do not send Bearer tokens over plaintext.

### S8 — Medium: Container runs as root; no `.dockerignore`; build context bloat

`Dockerfile` has no `USER` directive, so the service (ffmpeg/demucs/EAR parsing
**untrusted user-uploaded media**) runs as root. ffmpeg/demucs have had
media-parsing CVEs; root maximizes blast radius. Additionally, `COPY . /app`
(`Dockerfile:44`) with no `.dockerignore` copies the entire build context —
including `web/`, `web/node_modules`, `web/.next`, and `.git/` — into the Python
backend image, bloating it and shipping unrelated source. `git` is installed and
retained in the final image (attack surface). `run_instructions.sh` runs the
container with no `--memory`/`--cpus` limits.

**Fix:** add a non-root `USER`, add a `.dockerignore` (exclude `web/`, `.git`,
`output/`, `api_output/`, `*.db`), drop `git` from the runtime image (or use
multi-stage), and run with resource limits.

### S9 — Medium: No root `.gitignore` — risk of committing live secrets

There is **no `.gitignore` at the repo root** (only `web/.gitignore`). The
project loads `LLM_API_KEY`, `VISION_LLM_API_KEY`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, and Clerk keys from the environment (`.env.example`).
An operator who creates a root `.env` with real Fireworks/AWS/Clerk credentials
has no protection against committing it. (A history scan found no live secrets
today — only empty placeholders — so this is preventive but important for a
production-bound repo.)

**Fix:** add a root `.gitignore` covering `.env`, `output/`, `api_output/`,
`jobs.db`, `__pycache__/`, etc.

### S10 — Low: Internal error details leaked to clients

`api.py:81` (`f"Invalid token: {str(e)}"`), `api.py:101`/`253`
(`detail=str(e)` / `content={"error": str(e)}` for `ClientError`), and
`api.py:180` (`f"Error: {str(e)}"`). These can expose boto3/S3 internals, JWT
decode internals, or filesystem paths to callers. Return generic messages; log
the detail server-side.

### S11 — Low: Unsanitized LLM-derived stem names flow into filesystem paths

In the API path, placement stem names come from LLM output
(`placement_agent_harness.py` `p["stem"]`) and are used as filenames in the
FFmpeg fallback (`ffmpeg_fallback.py:109` `path = tmp / f"{name}.wav"`). Channel
labels are validated (`adm_renderer._position_for` raises on unknown labels),
but **stem names are not**. A stem name containing `/` or `..` would write
outside the temp directory. The LLM is not fully adversarial, but its inputs
(stems + a VLM caption of attacker-uploaded video) are derived from untrusted
media, so prompt-injection-style manipulation is a realistic concern. Sanitize
stem names to a safe charset before using them as filenames or ADM identifiers.

---

## Reliability

### R1 — High (also correctness): Agent stage writes to a hardcoded shared `output/`, not the per-job `output_dir`

Every pipeline stage writes under the `output_dir` passed to `main.py`
(`api_output/{job_id}` in the API) **except** the placement agent:

- `placement_agent_harness.py:27` — `MEMORY_PATH = Path("output/coherence_memory.json")` (fixed)
- `placement_agent_harness.py:146` — `out_path = Path(f"output/scene_{scene_id}_placements.json")` (fixed)
- `placement_agent_harness.py:158` — `run_pipeline` does `MEMORY_PATH.unlink()` at start

In the API, each job is a separate `python3 main.py` subprocess whose CWD is
`/app`, so these resolve to a **single shared `/app/output/`** across all jobs.
Consequences:

1. **Coherence-memory corruption across concurrent jobs.** `process_scene` does a
   read-modify-write of `output/coherence_memory.json` per scene
   (`placement_agent_harness.py:110,143-144`); concurrent processes interleave and
   clobber each other's memory. `run_pipeline`'s `unlink()` (line 158) can delete
   another job's memory mid-run.
2. **Placement-file collisions.** `scene_{id}_placements.json` is keyed only by
   scene id, so concurrent jobs overwrite each other's files.
3. **Disk leak.** `api.py:183-184` only `rmtree`s `job_dir` (`api_output/{job_id}`);
   the shared `output/` is never cleaned, so placement JSONs and coherence memory
   accumulate forever.
4. **Broken artifact upload.** `api.py:166-173` looks for `coherence_memory.json`
   and `scene_*_placements.json` **inside `job_dir`**, but those files were
   written to `/app/output/`. They are silently never uploaded to S3 — the
   "preserve evidence of coherence for judging walkthroughs" feature
   (`api.py:165`) is non-functional in the API path.

**Fix:** thread `output_dir` into the harness (pass it through `run_pipeline` /
`process_scene`) and write memory + placement JSONs under it.

### R2 — High: Job state is non-durable and jobs orphan on restart

`api.py:28` `DB_PATH = "jobs.db"` lives in the container CWD with no volume and
no backup. If the container/process restarts, all job history is lost and every
in-flight job is orphaned: its DB row stays `"processing"` forever (never
updated again), and the worker thread is gone. Users polling after a restart get
a stale "processing" that never resolves. There is no job-recovery logic on
startup.

**Fix:** put `jobs.db` on a persistent volume (or use Postgres/DynamoDB), mark
in-flight jobs as `"failed"` (or re-queue) on startup, and persist enough state
to resume or cleanly fail orphaned jobs.

### R3 — Medium: SQLite used concurrently without WAL or busy timeout

Every request and every background `update_job` opens its own `sqlite3`
connection (`api.py:42-61`, `190`, `205`, `219`, `228`). The default busy timeout
is 5s and journal mode is the default (delete), so under concurrent job status
updates (one per matching log line, `api.py:142-143`) you will hit
`database is locked` (`OperationalError`). In `run_pipeline_task` that exception
is caught by the broad `except Exception` (`api.py:179`) and the job is marked
failed with `"Error: database is locked"`; in the request handlers it surfaces as
an unhandled 500. Status updates can also be silently lost.

**Fix:** enable WAL (`PRAGMA journal_mode=WAL`), set a `busy_timeout` (e.g.
5000ms+), and use a single shared connection or a pool rather than opening per
call. Given S4/R2, a real DB is preferable to SQLite here.

### R4 — Medium: S3 data retention is unbounded; no lifecycle policy

`uploads/{user_id}/{uuid}_{filename}` and `results/{job_id}/*` are written to S3
and **never deleted** in code (`api.py:88`, `162-173`). Source user video and
rendered audio accumulate indefinitely — a cost and PII/media-retention concern
for a production service. No S3 lifecycle rule is configured in code.

**Fix:** add an S3 lifecycle policy (or explicit cleanup after download) for both
prefixes, and document retention.

### R5 — Low: Broad `except Exception` masks failures and can mislabel jobs

`api.py:179-180` catches *all* exceptions (including programming errors and the
SQLite lock error from R3) and reports a generic `"Error: {str(e)}"` with
`status="failed"`. This hides real bugs from logs as "expected" failures. Catch
the specific expected exceptions (S3, subprocess) and let unexpected ones
surface.

### R6 — Low: Background threads are non-daemon and untracked

`api.py:198` — `thread = threading.Thread(...)` with no `daemon=True` and not
stored anywhere. The server cannot cancel or await in-flight jobs on shutdown,
and there is no way to enumerate running jobs from the process. Make them
daemon, track them, and implement graceful shutdown/cancellation.

---

## Correctness

### C1 — High: `7.1.4` output format is offered in the UI but always fails

The frontend exposes four formats including `7.1.4`
(`web/src/app/dashboard/page.tsx:26,332`) and the API accepts any string
(`api.py:106` `target_format: str`, no validation). For non-`binaural` targets,
`api.py:125` passes `--target {target_format}` to `main.py`, but `main.py:214`
restricts `--target` to `choices=["5.1", "5.1.4"]`. So a `7.1.4` job makes
`argparse` exit non-zero (`api.py:148-150`) → the job is marked failed. `7.1.4`
is a dead option. Additionally `TARGET_SYSTEMS` in `adm_renderer.py:64-68` *does*
define `7.1.4` → `4+7+0`, but `binaural_renderer.SPEAKER_LAYOUTS`
(`binaural_renderer.py:43-64`) has no `4+7+0` entry, so even if `main.py`
accepted it, a binaural pass for 7.1.4 would raise. The accepted-set is
inconsistent across three layers (frontend 4 options / `main.py` 2 / ADM 3 /
binaural 2).

**Fix:** pick one source of truth for supported formats, validate
`target_format` in the API (`Literal["binaural","5.1","5.1.4","7.1.4"]`), align
`main.py` choices, and add the `4+7+0` binaural layout if 7.1.4 is meant to ship
(or remove it from the UI).

### C2 — Medium: API does not validate `target_format`, relying on `main.py` argparse as a safety net

`api.py:106` `target_format: str` is unvalidated and is interpolated into a
result filename `job_dir / f"film_{target_format}.wav"` (`api.py:155`). Today
this is not reachable as a path-traversal because `main.py`'s argparse rejects
unknown targets and the early `return` on non-zero exit (`api.py:148-150`) fires
before the file is touched. But this is fragile defense-in-depth: the API trusts
`main.py` to make its own path expression safe. Validate explicitly at the API
boundary.

### C3 — Medium: `_extract_json` strips backticks from the entire response

`placement_agent_harness.py:96-101`:

```python
if text.startswith("```"):
    text = text.strip("`")
```

`str.strip("`")` removes **all** leading/trailing backticks from the whole
string, not just the fence. If the model's JSON contains a legitimate backtick
inside a `rationale` string at the start/end, the strip mutates the payload and
`json.loads` fails where the response was otherwise valid. Use a targeted
fence-removal (regex `^```(?:json)?\s*|\s*```$`) instead of `strip`.

### C4 — Low: Binaural output written as float WAV, inconsistent with PCM_16 elsewhere

`binaural_renderer.py:161` — `sf.write(str(output_path), stereo.astype(np.float32), sr)`
passes float32 data with no `subtype`, so soundfile writes a **float** WAV. The
ADM and FFmpeg renders write `PCM_16` (`adm_renderer.py:159`,
`ffmpeg_fallback.py:110`). A float WAV "mastered" deliverable may not play in all
consumers/players and is inconsistent with the rest of the pipeline. Pick one
delivery subtype deliberately (PCM_16 or PCM_24) and pass it explicitly.

### C5 — Low: `sub` may be `None`, producing null-owner jobs

`api.py:79` returns `decoded.get("sub")`, which can be `None` if a token lacks
`sub`. Downstream queries scope by `user_id` (`api.py:207,221,230`), so a
`None`-owned job is only visible to other `None`-sub callers — a minor
edge case, but `user_id` should be rejected as 401 if absent rather than
stored as NULL.

### C6 — Low: Sample-rounding can drop/truncate the final sample in ADM assembly

`adm_renderer.py:122-150` — `total_samples` is `round(total_duration * sr)` with
`total_duration` a float sum, while per-scene `start_sample` and
`scene_len_samples` are rounded independently. Rounding drift can make the last
scene's `start_sample + scene_len_samples` exceed `total_samples` by one sample;
numpy slice assignment silently clips, dropping a sample. Use integer sample
arithmetic derived from the `Fraction` scene durations consistently rather than
mixing float and per-scene rounding.

---

## Test coverage

### T1 — High: There is effectively no automated test suite

The only test file is `test_models.py` (5 lines, **untracked** in git). It is not
a test — it reads an env var and contains the comment *"Wait, I don't have the
API key in the sandbox!"*; it imports `requests` (not even a declared
dependency). There is no `pytest` config (`pytest.ini`/`pyproject.toml`/`tox.ini`
absent), no `conftest.py`, and **no tracked test files at all**.

Despite this, `main.py:9-19` annotates stages as *"TESTED in this build"* and the
README (`README.md:46-49`) offers "quantified proof" of coherence. That evidence
is manual/one-off, not automated or repeatable. For production-bound code this is
the central test-coverage finding: correctness is asserted, not verified by any
regression suite.

**High-value, low-cost unit tests to add (no external services needed):**

- `stem_feature_extractor._bucket_energy` / `_empty_features` — boundary values
  at 0.02 and 0.08.
- `placement_agent_harness._extract_json` — fenced, unfenced, and
  backtick-in-payload cases (see C3).
- `placement_agent_harness.check_coherence` — exact_match / justified_change /
  unjustified_change classification (the project's core claim) — construct
  synthetic scene results and assert the counts.
- `ffmpeg_fallback` static routing / majority-vote (`stem_primary_channel`) and
  the generated `filter_complex` shape for a known input.
- `binaural_renderer._to_grid` azimuth/elevation → (azi, zen) mapping, and the
  LFE/silent-channel skip + peak-normalization paths on synthetic signals.
- `adm_renderer.build_adm_bwf` — feed deterministic scene results + tiny stem
  wavs and assert block count, channel order, and that `check_adm_coherence`
  reports identical azimuth/elevation for a recurring stem across scenes (the
  README's strongest claim).
- `api.get_current_user` — assert it **rejects** unsigned tokens and missing
  `CLERK_ISSUER` (directly tests S1/S2), and that `/job` **rejects** an
  out-of-scope `s3_key` (directly tests S3).
- `api` `/status` / `/history` / `/download` authorization scoping (user A
  cannot see user B's jobs) with a stub DB.

None of the LLM/ffmpeg/S3 paths need to be live for these; they are pure logic
or can use stubs/fixtures. There is also no frontend test setup (no Vitest/Jest,
no `coverage` dir).

### T2 — Medium: No CI/lint gate for the untested contract surface

There is no CI configuration in the repo and the web `lint` script
(`web/package.json`) is the only static check, and it is not wired to run
anywhere. The coherence-memory contract (`placement_agent_harness.SYSTEM_PROMPT`
JSON schema) and the ADM channel vocabulary are validated only by runtime LLM
behavior. Add CI: `ruff`/`mypy` + `pytest` for Python, `next lint` + a typecheck
build for the web, and a contract test that the harness rejects placements with
unknown channel labels.

---

## Supply chain & deployment

- **D1 (Medium): No dependency pinning.** `Dockerfile:16-36` installs `torch`,
  `torchaudio`, `torchcodec`, `demucs`, `ear`, `spaudiopy`, etc. with **no version
  pins** and no hashes. `ear==2.1.0` is acknowledged stale
  (`adm_renderer.py:20-21`); the rest floats. Builds are non-reproducible and
  exposed to upstream drift/supply-chain risk. Pin everything (a
  `requirements.txt` with `==` and ideally `--require-hashes`).
- **D2 (Low): Unused dependencies** (`anthropic`, `pydub`, `python-multipart` is
  used) expand the attack/maintenance surface; `anthropic` and `pydub` appear
  unused in the source.
- **D3 (Low): Build-time network dependency for HRIR data.**
  `Dockerfile:40-41` pre-downloads the TU Berlin HRTF set at build time; the
  module itself notes the real download was never verified end-to-end
  (`binaural_renderer.py:15-27`). A failed download silently falls back to
  synthetic, so production audio quality depends on an unverified external host
  with no integrity check (no checksum/pinned URL).
- **D4 (Low): No security headers.** Neither `next.config.ts` nor `api.py` sets
  CSP, `X-Content-Type-Options`, `Referrer-Policy`, etc. Add at least a
  restrictive CSP and `X-Content-Type-Options: nosniff`.
- **D5 (Low): No health/readiness endpoint** on the API for the load
  balancer/container orchestrator.

---

## Prioritized recommendations

**Must fix before any production exposure (Critical/High):**
1. S1 — Make `CLERK_ISSUER` mandatory; never decode JWTs without signature
   verification. Verify `iss`/`aud` (S2).
2. S3 — Validate `s3_key` is scoped to `uploads/{user_id}/` before downloading.
3. R1 — Thread `output_dir` into the placement harness; stop writing to a shared
   `output/`. Fixes corruption, disk leak, and broken artifact upload.
4. S4/S5 — Add a bounded job queue/concurrency limit, per-user rate limiting, and
   subprocess timeouts with kill-on-timeout.
5. C1 — Fix or remove the `7.1.4` format; validate `target_format` at the API
   (C2).
6. S8/S9 — Non-root container, `.dockerignore`, root `.gitignore`, resource
   limits.
7. S7 — Route frontend through the `/api` rewrite; terminate TLS on the backend.
8. T1 — Add the unit tests listed above, starting with `check_coherence`,
   `_extract_json`, and the `api` auth/IDOR tests.

**Should fix (Medium):** R2 (durable job state + orphan recovery), R3 (WAL/busy
timeout or move off SQLite), R4 (S3 lifecycle/retention), S6 (CORS allowlist),
D1 (pin dependencies), T2 (CI gate).

**Nice to have (Low):** S10, S11, R5, R6, C3–C6, D2–D5.
