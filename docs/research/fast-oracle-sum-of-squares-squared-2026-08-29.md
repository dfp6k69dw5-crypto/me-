# Fast Oracle: sum-of-squares-squared R

Date: 2026-08-29

## Observed problem
The current displayed R is `sqrt(x_1000)` after the 1,000-stage modular recurrence. Because `x_1000 < 1,000,003`, displayed R is capped near 1,000 and reflects only the final stage rather than the full recurrence path.

## Research question
Can R be redefined exactly as the square of the sum of squared recurrence-stage values while preserving the existing non-market seed, modular recurrence, logging, and comparison machinery?

## Evidence and constraints
This is a user-defined mathematical experiment, not a claim that this statistic has predictive validity. The recurrence remains modular at every stage so stage values stay bounded and computation remains tractable. The requested statistic is interpreted literally as `R = (sum_{n=1}^{1000} x_n^2)^2`.

JavaScript `BigInt` is required for the exact integer because the result can be on the order of 10^30, well beyond exact integer representation in IEEE-754 `Number`. The browser may use a `Number` approximation for plotting and correlation calculations while the recorder preserves the exact decimal integer string.

## Competing explanations / limitations
A larger numeric range does not create information or predictive power. Squaring stage values makes large stages dominate the statistic, and squaring the sum amplifies differences further. The distribution of this R is not expected to be uniform over its theoretical range, so the existing simple linear forecast normalization may be biased. That behavior should be measured rather than silently optimized away.

## 10-level gate
1. Observed problem: established from the formula and visible ~1,000 ceiling.
2. Foundational evidence: elementary algebra and bounded modular arithmetic are sufficient for the requested deterministic transformation.
3. Current evidence: implementation constraint is current JavaScript BigInt/Number behavior.
4. Natural-behavior evidence: not applicable.
5. Mechanism: accumulate every recurrence stage as `sumSquares += x*x`, then set `R = sumSquares*sumSquares`.
6. Competing explanations: increased range may only magnify noise; documented above.
7. Replication/correction limits: deterministic calculation can be cross-checked independently; no empirical predictive claim is assumed.
8. Context transfer: same seed and recurrence are retained, so only the R summary changes.
9. Implementation mapping: update browser `alex`, display formatting, R theoretical maximum, model-specific localStorage key, and persistent recorder model/version.
10. Validation: verify the browser and recorder calculate the same R for the same seed, R is no longer capped near 1,000, old prediction history is not mixed with the new model, and exact logged R is preserved as a decimal string.

## Pre-change baseline
`R = sqrt(x_1000)`, theoretical maximum approximately 1000.001. Browser history key: `fastOracleResults`. Recorder model: `nonmarket-wikimedia-r-v4-positive-market-prices`.

## Validation criteria
- `R = (sum x_n^2)^2` over exactly 1,000 modular stages.
- Exact R retained in recorder as a decimal string.
- Browser renders large R values in scientific notation without overflow.
- Forecast history uses a new model-specific storage key.
- Non-market Wikimedia seed and market-exclusion rule remain unchanged.
- Recorder and browser implementations use the same recurrence and R definition.

## Post-change result
Pending deployment verification.