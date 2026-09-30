# 0003 Keep policies out of process

Status: accepted

## Context

Real policies run in their own Python environments, on GPUs, or on other machines, and often pin
dependency versions that conflict with the simulator's.

## Decision

Define a small JSON protocol (`robo-evals/1`) over HTTP and WebSocket. The harness is the client
and the policy is a server. Local Python callables stay supported for simple cases.

## Consequences

- A policy needs no MuJoCo install and no robo-evals import.
- Each step costs a network round trip, so remote runs are slower than local ones.
- The message format is versioned, so it can change without breaking old servers silently.
