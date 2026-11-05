# Recommendation scenarios

This suite contains **70 development scenarios: 40 Cook and 30 Shop**. They
exercise the pure recommendation engines with declared synthetic inputs. They
are available for inspection and debugging, so their results are development
correctness evidence. They are not held-out results, a user study, database
integration evidence or a deployed load test.

The specification targets 100 scenarios in total. The remaining **30 held-out
scenarios are reserved and have not been authored or evaluated here**. See the
protocol below before creating them.

The [recorded development baseline](results/development.json) passes **70/70
scenarios and 85/85 steps**, with no hard-constraint violations. It was generated
from the clean source commit `6e5c8eb`; the report includes source/input hashes
and runtime versions. This is synthetic development evidence only.

## Inputs and scope

- `development/*.yaml` contains each scenario's ID, purpose, coverage categories,
  preferences, inventory, request, expected result and zero to three adjustments.
- `fixtures.yaml` declares the synthetic ingredient metadata, purchase definitions
  and small recipe records used by these scenarios. Its fixed clock is
  **2026-10-24 at 12:00 Singapore time (`2026-10-24T12:00:00+08:00`)**. Relative
  inventory dates are evaluated against that clock, not the date the script runs.
- [`backend/evaluation/`](../../backend/evaluation/) contains the input schema,
  runner and assertions.

The synthetic recipes are separate from the **48 human-reviewed recipe files**
in [`backend/seed/recipes/`](../../backend/seed/recipes/). Fixture allergens,
diet flags, shelf lives, pack sizes and tracking modes are explicit test inputs.
They are not authoritative catalogue data, nutrition measurements, certification
or shelf-life advice. Do not import them into the production seed catalogue.
These results do not establish that Role 2's eventual ingredient mapping or
purchase conversions are correct; rerun suitable cases against that data during
integration.

## Run the development suite

From `backend/`, with its development dependencies installed:

```powershell
.venv/Scripts/python.exe -m evaluation.run --output ../eval/reco_scenarios/results/development.json
```

Run one case while investigating a failure:

```powershell
.venv/Scripts/python.exe -m evaluation.run --case DEV-C01
```

A subset run only provides evidence for the selected cases. Use the full command
for the development report. Read the generated result rather than assuming a
pass count from the number of YAML files. Invalid input or a failed assertion
makes the command exit unsuccessfully.

## What a scenario checks

Assertions apply to the initial result and again after **every adjustment**.
The runner checks hard constraints against the declared metadata at each step;
they must remain intact as session adjustments accumulate.

Cook scenarios declare an allowed selection set or an explicit no-result
expectation, with checks for ingredient statuses, scaled amounts, stock or
freshness questions and relaxation suggestions where relevant. Shop scenarios
declare the **exact basket ingredient set**, meal count, pack suggestions and
`needs_check` flags at every step. Exact sets detect both missing purchases and
unwanted extra items. Scenarios can also specify the chosen meals and text
fragments needed to verify an amount. Fragments match at token boundaries, so
an expected `200 g` cannot pass against `1200 g`.

Expected answers are written in the scenario files; they are not copied from
the current engine output. When a case fails, check the scenario arithmetic and
the specification before changing either the expectation or the implementation.
An edited development expectation remains development evidence.

The result records per-case and per-step outcomes, category summaries and
source-hash provenance. Preserve that provenance alongside any quoted result:
the engine/configuration, runner, fixtures and scenario inputs determine what
was actually evaluated. A Git revision alone cannot describe uncommitted source
changes; source hashes distinguish the evaluated contents. Record a fresh result
after changes rather than reusing a result from different inputs or code.

## Reserved held-out protocol

**Held-out means examples kept away from the people developing or tuning the
algorithm until it is ready for its final check.** This tests whether the rules
also work on cases they were not adjusted to pass.

The development CLI deliberately accepts only development IDs. The separate
[`evaluation.held_out`](../../backend/evaluation/held_out.py) CLI provides freeze,
rehearsal, first-run and regression commands. Its tests use temporary development
copies; no reserved cases have been authored or evaluated. Do not bypass the
separation by relabelling reserved cases as development cases.

1. Finish development and record the frozen engine, scoring configuration,
   runner and fixture versions with their hashes. Agree the acceptance checks
   before seeing any reserved case results.
2. Have an independent author prepare 30 new scenarios from the requirements.
   Keep their inputs and expected answers separate from development and CI
   until the frozen version is evaluated. The author should not derive expected
   answers by querying the engine.
3. Run the frozen version once and preserve the complete first result, including
   failures, inputs and source hashes, without overwriting it. Report its results
   separately from the 70 development cases.
4. If a failure leads to code or configuration changes, retain the original
   result. Further runs of those now-seen cases are **regression checks**, not a
   new untouched held-out evaluation. A new generalization claim needs fresh
   unseen cases and another recorded freeze.

Do not relabel existing tests or development cases as held-out. Until this
protocol is completed, report the held-out evaluation as pending. Passing this
offline suite also does not satisfy the separate requirement for Cook and Shop
to work on the deployed stack against real inventory.

## Rehearse the runner without exposing reserved cases

The rehearsal command accepts only `DEV-Cnn`/`DEV-Snn` cases with
`split: development`. Its reports say `split: rehearsal`,
`held_out_executed: 0` and `first_held_out_attempt: false`, even when every case
passes. It supports development subsets for testing the harness, not for final
evaluation. The production engines and assertion logic are shared with the
development runner; a second, weaker set of assertions is not introduced.

From a clean checkout, run these commands in `backend/`. Use a **new** output
directory and freeze filename for each rehearsal. `private/` is already ignored
by Git, keeping input/output artifacts from making the checkout dirty.

```powershell
.venv/Scripts/python.exe -m evaluation.held_out freeze --purpose rehearsal --output ../private/rehearsal-freeze.json
.venv/Scripts/python.exe -m evaluation.held_out rehearse --freeze ../private/rehearsal-freeze.json --fixtures ../eval/reco_scenarios/fixtures.yaml --cases-dir ../eval/reco_scenarios/development --output-dir ../private/rehearsal-result
```

Temporary copies of those development files work identically. The automated
harness tests cover split isolation, invalid input, source/runtime changes,
failure retention, interrupted attempts, output protection and regression links.
Some schema-only tests relabel temporary development copies to check the held-out
format; those copies are never run as held-out scenarios and are not reserved cases.

## Freeze and evaluate the independent suite later

Only perform this step after the implementation is ready and the acceptance
checks are agreed. A freeze records the Git commit; hashes of the engine, schemas,
runner, dependency files and clock; scoring configuration; and Python/library
versions. A clean working tree and matching fingerprint are required at execution.
The manifest fixes the target at **30 cases covering both Cook and Shop**, with
every scenario and step passing and no hard-constraint violations. The specification
does not prescribe a 15/15 split; the independent author chooses coverage within
the agreed requirements.

```powershell
.venv/Scripts/python.exe -m evaluation.held_out freeze --purpose evaluation --output ../private/final-freeze.json
```

Have the independent author prepare the scenario inputs and expectations without
consulting engine outputs. Use the same scenario fields and assertion rules as
development, but `split: held-out` and unique `HELD-Cnn`/`HELD-Snn` IDs matching
each case's mode. Supply an explicit fixtures file and exactly 30 scenario YAML
files. Keep these outside development/CI, for example under
`private/final-evaluation-inputs/`, until the frozen evaluation. Do not simply
rename development scenarios. A rehearsal freeze cannot authorize this command:

```powershell
.venv/Scripts/python.exe -m evaluation.held_out run --freeze ../private/final-freeze.json --fixtures ../private/final-evaluation-inputs/fixtures.yaml --cases-dir ../private/final-evaluation-inputs/cases --independent-author "Author name" --output-dir ../private/first-held-out-result
```

There is no case-subset option for a held-out run. All inputs are validated before
any engine call. The runner captures the exact normalized input text and hashes,
then evaluates those captured contents. Duplicate IDs, wrong splits, unknown
references, malformed assertions or a changed freeze fail the run.

## Preserve the first attempt and distinguish regressions

Every attempt uses a new directory. `attempt.json` preserves the frozen source,
input contents/hashes and declared independent author before execution.
`result.json` records all observations and assertion/runtime failures; an
interruption leaves `interrupted.json` with completed case results. A source change
during execution produces an invalid recorded result rather than valid evidence.

Neither manifests nor output directories are overwritten. A first-run reservation
file beside the evaluation manifest prevents a second `run` with that manifest,
even with a different output directory. Keep this marker and the entire attempt,
including failures or interruptions. Copying/deleting manifests or markers can
bypass this local protection; the runner cannot prove an author's independence or
that humans have never seen the inputs. `first_held_out_attempt: true` records a
valid first attempt under this manifest, not proof of unseen data or a passing score.

Once cases have been exposed, further runs are regressions. If code changes,
record a new evaluation freeze and retain the original freeze and result. Use:

```powershell
.venv/Scripts/python.exe -m evaluation.held_out regression --freeze ../private/updated-freeze.json --fixtures ../private/final-evaluation-inputs/fixtures.yaml --cases-dir ../private/final-evaluation-inputs/cases --original ../private/first-held-out-result/result.json --output-dir ../private/held-out-regression
```

After an interruption, `--original` may instead point to the original
`attempt.json`, which preserves the inputs even without a complete result.
Regression reports retain the original artifact's path/hash, require unchanged
input hashes, use `split: held-out-regression`, and set
`first_held_out_attempt: false`. They still count the executed formerly held-out
cases, but cannot be presented as a fresh unseen evaluation. Correcting case
inputs is a separately documented new suite, not a rewrite of original evidence.

Exit codes are **0** for all assertions passing, **1** for scenario failures,
and **2** for invalid input, freeze mismatch or an unusable evidence destination.
Preserve the full artifacts with any reported figures; no held-out files are added
to normal CI by this workflow.
