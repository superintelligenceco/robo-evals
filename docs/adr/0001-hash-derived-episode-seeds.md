# 0001 Derive episode seeds by hashing

Status: accepted

## Context

An evaluation is only comparable across runs if episode `i` of a task is the same scene every
time. Drawing all scenes from one shared random stream breaks that: adding an episode, reordering
tasks, or skipping a task shifts every later scene.

## Decision

Each episode seed is a hash of the base seed, the task name, and the episode index. Scenes and the
random baseline both draw from that seed.

## Consequences

- Running 20 episodes and then 50 gives the same first 20 scenes.
- Tasks can run in any order, or alone, without changing their scenes.
- Changing the derivation changes every success rate for a fixed seed, so it counts as a breaking
  change and gets called out in the changelog.
