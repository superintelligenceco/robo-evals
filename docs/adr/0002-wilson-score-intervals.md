# 0002 Score with Wilson intervals

Status: accepted

## Context

Success counts are binomial, and evaluations often have few episodes and rates near 0% or 100%.
The normal-approximation interval collapses to zero width at the extremes and can leave the range
0 to 1.

## Decision

Report the Wilson score interval, at 95% confidence by default, for every task and for the pooled
result.

## Consequences

- A 0-of-50 result shows an upper bound of 7.1%, which is honest about how little 50 episodes
  prove.
- Intervals always stay inside 0 to 1.
- Property-based tests check the interval bounds and extremes for any count and confidence.
