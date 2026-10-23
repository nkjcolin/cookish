# Recommendation scenarios

This suite contains **70 development scenarios: 40 Cook and 30 Shop**. They
exercise the pure recommendation engines with declared synthetic inputs. They
are available for inspection and debugging, so their results are development
correctness evidence. They are not held-out results, a user study, database
integration evidence or a deployed load test.

The specification targets 100 scenarios in total. The remaining **30 held-out
scenarios are reserved and have not been authored or evaluated here**. See the
protocol below before creating them.

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

This CLI deliberately accepts only development IDs. A separate held-out
execution path still needs to be prepared and checked using development copies
before the freeze. Do not bypass this separation by relabelling reserved cases
as development cases.

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
