# ORION-X v5

A regime-gated, cost-aware crypto decision engine. This is a research and
decision-support system: it produces auditable signal cards, it does not place
orders, and it is not connected to an exchange.

```
pip install -r requirements.txt

python -m orion_x.cli selftest    # the mathematical identities, checked live
python -m orion_x.cli signal      # one worked signal card
python -m orion_x.cli validate    # walk-forward against eleven published peers

cd rust && cargo test && cargo run --release
```

## What the engine actually computes

Every decision reduces to one calculation:

```
sigma        <- HAR-RV forecast with a jump component     (orion_x/vol.py)
barriers     <- geometry that maximises the Kelly growth rate  (orion_x/engine.py)
mu           <- IC x sigma x z, Grinold's forecasting rule (orion_x/alpha.py)
P(tp,sl,to)  <- exact first-passage under those barriers   (orion_x/barriers.py)
edge         <- probability-weighted return minus modelled costs (orion_x/costs.py)
size         <- the binding one of four caps               (orion_x/sizing.py)
```

The 0-100 score still exists, but it is a *presentation* of the composite
evidence. It is explicitly not what the gates read. Confusing a score with an
expected return was the central structural problem in v4.

## The finding that matters

At an information coefficient of 0.03 -- the optimistic end of what
short-horizon crypto signals sustain out of sample -- a seven-hour trade cannot
pay for its own costs on a typical mid-cap perpetual.

The arithmetic is not subtle. Grinold's rule gives a forecastable move of
`IC x sigma_T x z`. With a seven-hour sigma of 1.6% and a strong 1.7-sigma view
that is about 7 basis points. Round-trip costs -- 9 bps of fees, 3-8 bps of
spread, 3-25 bps of square-root impact across both legs -- run 15 to 50 basis
points. The trade is under water before the first tick.

The engine says so, and it says something more useful with it. Fees, spread and
impact do not scale with the holding period, while the forecastable move grows
like `sqrt(T)`. Every signal card carries the resulting curve:

```
     2h  -11.6bps   hurdle   9.0bps
     7h   -8.5bps   hurdle   9.0bps
    24h   -2.8bps   hurdle  11.5bps
    96h   +9.3bps   hurdle  23.1bps
   168h  +16.9bps   hurdle  30.5bps
   720h  +47.9bps   hurdle  63.2bps
```

The hurdle is 4% of horizon volatility, so it grows like `sqrt(T)` as well. That
matters, because it means horizon extension does not fix everything. Writing the
hurdle as `h * sigma_T` and the edge as `IC |z| sigma_T - C_fixed`, the ratio is

```
    edge / hurdle  ->  IC |z| / h        as T grows and C_fixed stops mattering
```

Extending the horizon buys exactly one thing: it dilutes the fixed cost. What it
cannot buy is information. **Viability in the long-horizon limit requires
`IC |z| > h`** -- with `h = 0.04`, an IC of 0.025 needs a 1.6-sigma view, and no
horizon rescues an IC of 0.01. A strategy at that level is not waiting for a
longer holding period, it is waiting for a better signal.

This is why the engine gates almost everything. It is not conservatism; it is
the same arithmetic v4 never performed.

### The second bind: measuring an IC costs years

The walk-forward exposed a failure the barrier mathematics could not have
caught. With fixed prior weights, one informative evidence block averaged with
six uninformative ones produced a composite whose out-of-sample IC was 0.023
against a planted ceiling of 0.037 -- and the engine could not tell a market
with a planted signal from one with none. The combination rule was the
bottleneck, not the model.

Weighting blocks by `Sigma^-1 IC` instead of by priors (Grinold & Kahn ch. 11)
fixed the extraction: on three and a half years of history the composite now
recovers an IC of 0.030 against a ceiling of 0.032, and the held-out half
confirms it at 0.032.

But measuring an IC is itself a statistical problem, and the first attempt at
it walked straight into the trap the harness exists to detect. Unshrunk block
ICs measured on a training half gave a training composite IC of +0.115 and an
out-of-sample IC of -0.024 -- worse than using no measurement at all. The
standard error is the reason. Twelve assets sharing one BTC factor supply
roughly one independent observation per timestamp, so the effective sample size
is the number of decision times, and a few hundred of those give a standard
error near 0.10. A "measured" IC of 0.13 was one standard error from zero.

Under an empirical-Bayes prior of `true IC ~ N(0, 0.03^2)` -- which is not a
formality but the literature's actual estimate of what survives out of sample --
the posterior mean is `IC_raw * tau^2 / (tau^2 + se^2)`:

```
   decisions   years    se     shrink    0.030 becomes
        200      0.3   0.071    x0.15       0.0045
       1200      1.6   0.029    x0.52       0.0157
       4400      6.0   0.015    x0.80       0.0240
```

Combine that with the viability condition `IC |z| > h`: at `h = 0.04` and a
two-sigma view you need a believed IC above 0.02, which needs a standard error
below about 0.03, which needs **something like six years of independent
observations**. And a short-horizon crypto signal is unlikely to survive six
years unchanged.

This is the bind, stated precisely. It is not an argument that the strategy is
impossible; it is an argument about which lever moves it. Grinold's fundamental
law says `IR = IC sqrt(breadth)`, and breadth is the only term here that can be
increased quickly. Ten assets sharing one market factor have a breadth near two,
not ten -- which is exactly what `effective_number_of_bets` measures and reports
on every card. More genuinely independent bets, not a longer horizon and not
more features, is what this arithmetic asks for.

## What changed from v4, and why

### Errors of arithmetic

| v4 | Consequence | v5 |
|---|---|---|
| `abs(funding_rate)` charged as a cost | A long was billed for income it received. On v4's own shipped example, a 10 bps error on a 40 bps edge | Funding is signed by side |
| `clamp(50 + 50*score/100)` in `benchmark_ratio` | `clamp` defaults to `[0,1]`, so the expression is always 1.0. The BTC/ETH benchmark comparison returned a constant | Benchmarks removed until there is real history to compare against |
| `independence_score` counts non-zero feature groups | Returns 1.0 on essentially every real input | Meucci's effective number of bets from the covariance eigenstructure |
| Fixed 8 bps fee plus one spread | Ignores size entirely; a position at 3% of hourly volume walks the book | Square-root impact law on both legs |
| `oi_score = 0.55*price*coherence + 0.45*tanh(-oi_change/0.20)` | The second term rewards falling open interest unconditionally and contradicts the first | Four-quadrant reading of price against open interest |
| `tanh(funding_rate / 0.001)` | A resting 0.01%/8h funding rate scored as meaningful bearish evidence | Percentile-conditional: only the tails speak |

### Errors of construction

**The entry-window search had no objective.** Every term in v4's loop except a
hard-coded hour bonus was constant across iterations, so it always returned the
first slot inside 08:00-10:00 or 14:00-16:00 UTC regardless of the asset. v5
estimates the volume profile from the asset's own history and solves the real
trade-off: waiting for a deeper hour reduces impact, but the signal decays while
you wait.

**Scenario probabilities were disconnected from the barriers.** v4 asserted
`P(continuation) = 0.47` from three hand-written logit equations while placing a
stop 0.4 sigma away. At that distance the stop is hit first with high
probability whatever the evidence says. v5 computes the probabilities from the
barriers, so they cannot disagree.

**Confidence and the scenario probabilities described the same belief and
disagreed by 24 points.** v4's example reported `confidence: 0.714` alongside
`continuation: 0.467`. Neither was derived from anything. v5 defines confidence
as `P(sign correct) = Phi(IC |z| / sqrt(1 - IC^2))`, which at a plausible IC
lands in the low fifties -- and which means `min_confidence: 0.55` was a gate
that could never pass.

**Barriers were fixed ATR multiples.** 1.1x, 2.0x, 3.2x and a stop 0.45 ATR
below the defensive entry, numbers that appear nowhere else in the model. An
ATR-multiple stop is a volatility bet in disguise: the same multiple means a
different probability of being hit in every regime. v5 derives the geometry by
maximising the growth rate against the actual first-passage moments.

**Sizing had no dependence on the edge.** `max_risk_per_trade / risk_distance`
gives the same size to a 1 bp edge and a 100 bp edge whenever their stops are
equidistant. v5 takes the binding one of Kelly, volatility target, liquidity and
loss limit, and reports which bound it.

**Twelve declared fields were never read**, `unlock_next_7d_pct` among them --
one of the few reliably negative scheduled events in the asset class.

**The engine could only say BUY or WAIT.** Every evidence block returned `[0,1]`
"goodness", and a `[0,1]` block cannot express a short. In an asset class that
spends half its life falling, that is not a missing feature, it is a
systematically long-biased scoring function. v5's blocks are signed.

**Nothing enforced the point-in-time contract the README promised.** v5's
`PointInTimeGuard` raises on any snapshot stamped after the decision time, and
the backtester builds features from trailing windows only.

**There was no validation of any kind.** v4's README listed walk-forward,
purged validation and benchmark comparison as research requirements and shipped
none of them.

### Where the model disagrees with the literature v4 implied

v4 treated a positive 15-minute return as evidence of continuation. The
published crypto momentum results -- Liu & Tsyvinski (2021, *RFS* 34(6)); Liu,
Tsyvinski & Wu (2022, *JF* 77(2)) -- are at one-week to four-week horizons. At
intraday horizons the robust effect is the opposite one: short-horizon reversal
(Lehmann 1990; Lo & MacKinlay 1990). v5 treats an impulse as continuation only
when participation confirms it and as reversal risk otherwise, and puts most of
the momentum weight on the horizon where the premium is actually documented.

v4 also called itself causal. It conditioned on nothing. The dominant confounder
in crypto -- that most of an altcoin's hourly return is its beta times BTC's --
was never removed, so "strong momentum and strong flow" was usually a
restatement of "BTC moved". v5 residualizes against BTC and ETH before measuring
anything asset-specific, which is the minimum that makes the word defensible.

## Validation design

Exchange APIs are not reachable from the environment this was built in, so the
harness runs on a generator whose statistical properties are matched to
documented crypto behaviour: GJR-GARCH volatility clustering, Student-t
innovations with 4 degrees of freedom, a leverage effect, a dominant common
factor, intraday seasonality in volume and volatility, and spreads inverse to
volume. To validate against real data, feed the same `MarketPath` structure from
an exchange adapter; nothing downstream knows the difference.

It runs in two modes. **Null mode** has no predictability by construction: any
strategy that appears profitable there is overfitting, leaking, or buggy. That
is the more important of the two tests, and it is a test of the harness rather
than of the strategy. **Planted-alpha mode** injects a known OFI-to-return
relation with an IC near 0.04, so recovery can be measured against a ceiling
rather than against zero.

Three bugs that the null test caught, each of which would have produced a
publishable-looking backtest:

1. **Short P&L was inverted.** `return side * tp` books `-tp` when a short
   reaches its target and `+sl` when it is stopped out, crediting losses as
   wins. Every short in the panel had its sign flipped.
2. **The generator leaked the future.** Funding was built from a *centred*
   24-hour moving average, so funding at time `t` depended on returns after `t`.
3. **The Ito term was free money.** A driftless log return implies an arithmetic
   drift of `sigma^2 / 2`, which a barrier strategy books as profit -- tens of
   basis points per trade at these volatilities, enough to make a null market
   look tradeable.

And one methodological error: t-statistics were computed across per-trade
returns as though twelve assets sharing one BTC factor were twelve independent
observations, inflating every one of them by up to `sqrt(12)`. Aggregating each
timestamp into one portfolio return took the best peer's deflated Sharpe from
0.896 to 0.135 -- from "apparently skilled" to "indistinguishable from noise".

One caveat the null test itself surfaces: `reversal_4h` reaches a deflated
Sharpe of 0.70 on the null generator. That is the martingale-plus-leverage
autocorrelation described above being weakly visible at a four-hour horizon. It
stays below the 0.90 bar, and it is a property of the generator rather than of
any real market, but it is the reason the null market is described here as
having no *exploitable* predictability rather than none at all.

The engine is scored against eleven published peers -- time-series momentum
(Moskowitz, Ooi & Pedersen 2012), short-horizon reversal, Donchian breakout,
dual moving-average crossover, RSI(2), Bollinger reversion, funding carry, OFI
(Cont, Kukanov & Stoikov 2014), volatility breakout, buy-and-hold and a coin
flip -- through the same cost model, with the same barrier geometry, judged by
the deflated Sharpe ratio (Bailey & Lopez de Prado 2014), which corrects for
having tried twelve things.

## What the validation actually found

Three and a half years of hourly history, ten assets, a 24-hour horizon,
parameters estimated on the first half and applied to the second. `h` is the
edge hurdle as a fraction of horizon volatility.

```
market   hurdle h  trades   SR/yr    DSR   maxDD   total   rank among 12
null        0.040       0    0.00  0.500    0.0%   0.00%
alpha       0.040       0    0.00  0.500    0.0%   0.00%
null        0.020       0    0.00  0.500    0.0%   0.00%
alpha       0.020      18   +0.49  0.130    0.1%   0.12%       1st
null        0.010       0    0.00  0.500    0.0%   0.00%
alpha       0.010      74   +1.65  0.686    0.2%   0.73%       1st
```

The row that matters is the pairing. **At every hurdle the engine takes zero
trades in the null market**, and where a signal exists it trades and finishes
ahead of all eleven peers:

```
ORION_X_v5           +1.65   DSR 0.686
funding_carry        +0.25   DSR 0.088
rsi2_reversion       +0.21   DSR 0.080
vol_breakout         -0.54
donchian_96h         -1.13
buy_and_hold         -1.25
random_coinflip      -1.34
ofi_microstructure   -1.87
reversal_4h          -2.14
ma_cross_24_200      -3.26
tsmom_7d             -3.55
```

Two things must be said plainly about that table.

**A deflated Sharpe of 0.686 on 74 trades is not evidence of skill.** It is
below the 0.90 bar this repository sets for itself, and 74 trades is a small
sample by any standard. What the result establishes is discrimination -- silence
where there is nothing, activity where there is something -- not profitability.

**The hurdle is a choice, and it is the thing doing the work.** At `h = 0.04`
the engine never trades even against a real signal, because the shrunk IC of
0.016 needs `|z| > 2.5` to clear it. Lowering the hurdle to 0.01 trades the same
information at a lower risk-adjusted bar. Neither setting is right in the
abstract; what matters is that the trade-off is one line in `EngineConfig`, is
reported on every card, and is not hidden inside a 0-100 score.

Execution costs turned out not to be the binding constraint at a 24-hour
horizon. Running the same test at retail (4.5 bps), VIP (1.8 bps) and
maker-heavy (0.5 bps) fee tiers changed nothing: all three took zero trades at
`h = 0.04`. Confidence in the IC estimate is what binds, and cheaper execution
does not buy confidence.

The probability forecasts are well calibrated where they can be checked --
forecast 0.017 against an observed 0.014 for the profit barrier, with a
reliability term of 0.0000. Resolution is 0.0, though: the barrier optimiser
converges on similar geometries, so `P(target)` barely varies across trades and
the forecast has no discriminating power between them even though its level is
right.

## Layout

```
orion_x/
  barriers.py      triple-barrier first-passage: eigenfunction series + Monte Carlo
  vol.py           HAR-RV forecast with jump and mean-reversion corrections
  alpha.py         Grinold's rule; where the model's discipline lives
  costs.py         fees, spread, square-root impact, signed funding
  sizing.py        fractional Kelly under four caps
  features.py      seven signed evidence blocks
  causal.py        factor residualization, partial correlation, lead-lag
  graph.py         Mantegna MST and centrality
  linalg.py        Ledoit-Wolf, Marchenko-Pastur, effective bets
  calibration.py   Murphy's Brier decomposition, isotonic recalibration
  engine.py        decide()
  backtest/        generator, labeling, purged CV, metrics, peers, walk-forward
rust/              the same barrier, cost and sizing mathematics, with parity tests
```

## Before deploying anything

1. Replace the synthetic generator with point-in-time exchange data and re-run
   `validate`. Nothing in this repository has seen a real price.
2. Measure the information coefficient on your own data. `EngineConfig.assumed_ic`
   is a prior, and the whole edge calculation is linear in it.
3. Put an execution service in front of the exchange, with its own order
   validation, position limits, kill switch, slippage limit and reconciliation.
   The research engine must never talk to a venue directly.
4. Re-fit `DEFAULT_COMPOSITE_DISPERSION` to your universe. The composite is
   standardized by it, and a wrong value rescales every forecast.
5. Treat a deflated Sharpe below about 0.90 as no evidence of skill.

## References

Almgren, Thum, Hauptmann & Li (2005), "Direct Estimation of Equity Market
Impact", *Risk* 18. Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio",
*JPM* 40(5). Barber & Odean (2008), "All That Glitters", *RFS* 21(2).
Barndorff-Nielsen & Shephard (2004), "Power and Bipower Variation", *J. Fin.
Econometrics* 2(1). Cont, Kukanov & Stoikov (2014), "The Price Impact of Order
Book Events", *J. Fin. Econometrics* 12(1). Corsi (2009), "A Simple Approximate
Long-Memory Model of Realized Volatility", *J. Fin. Econometrics* 7(2). Grinold
(1994), "Alpha is Volatility Times IC Times Score", *JPM* 20(4). Kyle (1985),
"Continuous Auctions and Insider Trading", *Econometrica* 53(6). Laloux, Cizeau,
Bouchaud & Potters (1999), "Noise Dressing of Financial Correlation Matrices",
*PRL* 83. Ledoit & Wolf (2004), "Honey, I Shrunk the Sample Covariance Matrix",
*JPM* 30(4). Lehmann (1990), "Fads, Martingales, and Market Efficiency", *QJE*
105(1). Liu & Tsyvinski (2021), "Risks and Returns of Cryptocurrency", *RFS*
34(6). Liu, Tsyvinski & Wu (2022), "Common Risk Factors in Cryptocurrency", *JF*
77(2). Lopez de Prado (2018), *Advances in Financial Machine Learning*.
Mantegna (1999), "Hierarchical Structure in Financial Markets", *EPJ B* 11.
Meucci (2009), "Managing Diversification", *Risk* 22(5). Moskowitz, Ooi &
Pedersen (2012), "Time Series Momentum", *JFE* 104(2). Murphy (1973), "A New
Vector Partition of the Probability Score", *J. Applied Meteorology* 12(4).
Odean (1998), "Are Investors Reluctant to Realize Their Losses?", *JF* 53(5).
Toth et al. (2011), "Anomalous Price Impact and the Critical Nature of
Liquidity", *Physical Review X* 1.

## Licence

MIT.
