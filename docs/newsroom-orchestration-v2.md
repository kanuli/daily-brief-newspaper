# Newsroom Orchestration v2

## Command chain

```text
Scheduled Publisher / production demand
            |
            v
Editor-in-Chief Auto Maintenance
  audits repository + staging + public evidence
            |
            v
Editor-in-Chief Newsroom Assignment
  classifies fault, dependency, mode and priority
            |
            +--> Collector
            +--> General Producer / Verifier
            +--> Live Publisher
            +--> Daily Recovery
            +--> Rolling Desk Merge
            +--> Stock
            +--> Vocab
            +--> Pages
            +--> Voice
                    |
                    v
            workflow completion event
                    |
                    +------> immediate Editor-in-Chief re-evaluation
```

The fixed assignment schedule is only a safety net. Normal continuation is
event-driven from robot completion.

## Authority boundaries

- **Publisher** owns the publication slot. It does not normally assign GitHub
  leaf robots.
- **Editor-in-Chief Auto Maintenance** is the auditor. It determines whether
  production is healthy and delegates faults to the assignment control plane.
- **Editor-in-Chief Newsroom Assignment** is the single normal leaf-robot
  dispatcher.
- **Leaf robots never dispatch other leaf robots.** They perform one bounded
  job and stop.
- **Pages is deployment only.** It deploys the validated repository state; it
  does not rebuild or mutate newsroom data.
- **Voice is asynchronous.** Voice backlog never blocks valid text news.

Robot ownership, supported modes, priorities, runtime limits and outcome
evidence are declared in `config/newsroom-robots.json`.

## Job lifecycle

Every assignment has:

1. an `assignmentId`;
2. a fault class and responsible robot;
3. a normal/deep mode when the robot supports recovery modes;
4. a priority and maximum expected runtime;
5. dependencies / blocked state;
6. an `outcomeBefore` evidence snapshot;
7. `verifyNextCycle` success evidence.

Dispatch is **not** success. The next supervisory cycle compares repository,
staging, validator and public evidence with the prior assignment snapshot.

### No-progress handling

- A healthy in-flight robot is not treated as no-progress.
- Outcome evaluation begins when that robot completes, or when its declared
  runtime plus grace is exceeded.
- A supported normal path that makes no measurable progress escalates to
  **deep** mode.
- Repeated ineffective deep/single-mode execution becomes **STUCK**.
- STUCK blocks an identical retry and requires Editor-in-Chief replanning.

This prevents both infinite retry loops and premature cancellation of healthy
workers.

## Dependency examples

### General news

```text
stale public desk
  |
  +-- no current candidates --> Collector(deep)
  |
  +-- current candidates
        |
        +-- no verified draft --> General Producer
        |
        +-- verified draft --> Live Publisher
                                |
                                v
                           Desk Merge
                                |
                                v
                              Pages
```

Producer, Live and Desk Merge are not launched simultaneously. The next stage
is assigned only after the upstream outcome is observable.

### Stock

```text
strict validator fails
  -> Stock(normal)
  -> verify outcome
  -> no measurable progress => Stock(deep)
  -> verify outcome
  -> repeated no progress => STUCK / replan
```

The 48-hour substantive freshness and 3-hour review gates remain production
hard gates. A workflow start, completion timestamp or fresh review label never
makes old market news current.

### Daily vocabulary

Vocab is **TODAY-FIRST** in Asia/Hong_Kong. Historical missing dates do not
block today's vocabulary. Required production state is:

- `data/vocab/YYYY-MM-DD.json` exists for TODAY HKT;
- its `date` equals TODAY;
- `data/vocab/latest.json.date` equals TODAY.

## CI vs runtime freshness

PR CI validates code, schemas, regression behavior and the orchestration
contract. Wall-clock currentness is also checked in PR CI when the PR changes
live editorial data or currentness validator contracts.

Production freshness itself is continuously enforced by the Editor-in-Chief
runtime using the unchanged strict validators. This separation prevents stale
production data from blocking deployment of the repair code required to fix
that stale state.

## Anti-regression contract

`scripts/test_newsroom_orchestration_contract.py` rejects changes that:

- add autonomous schedule/push/workflow-run triggers back to leaf robots;
- allow one leaf robot to dispatch another;
- make Pages mutate newsroom content;
- restore historical Vocab backfill ahead of TODAY;
- remove durable outcome telemetry or the single-dispatcher contract.

Any intentional architecture change must therefore update the registry,
control plane, tests and this operating model together.
