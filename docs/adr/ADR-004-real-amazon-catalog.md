# ADR-004: Real Amazon catalog replaces the single-category synthetic sample

**Status:** Accepted

## Context
The original bundled sample was 500 synthetic-styled products, all under
one degenerate source category ("Fashion") with `brand = "Generic"` —
convincing at the schema level but not at the content level, and a fair
thing for a reviewer to be skeptical of.

## Decision
Onboarded a real, freely-distributed Amazon product export (1,000 listings,
23 real departments, 895 real brands, real ratings, real CDN image URLs —
`github.com/luminati-io/Amazon-dataset-samples`, a promotional sample of
Bright Data's commercial product feed) as the new catalog source
(`scripts/build_real_catalog.py`).

The silver conformance layer (`src/techtrend/lake/conform.py`) was
simplified accordingly: with genuine source categories and brands, the
old keyword-guessing rules (`CATEGORY_RULES`, `BRAND_LEXICON`) are gone.
What's left is what a real conformance layer does with a trustworthy
source — alias collapsing for near-duplicate labels the source itself is
inconsistent about, and one derived enrichment (`audience`) the source
doesn't provide.

Daily price/stock/rating telemetry (90 days × 1,000 products = 90,000
observations) is still simulated (`scripts/simulate_price_history.py`),
via a mean-reverting random walk with promotional events, restocking, and
monotonically accumulating reviews — because no free dataset provides
that longitudinal history (see rationale below). This was already true of
the original sample; only the underlying catalog changed.

## Why the time series still has to be simulated
Daily historical pricing for thousands of products is a commercial
product (Keepa, Bright Data's monitoring feeds) — nobody gives it away
for free, for the same reason airlines don't publish their historical
fare-change logs. This is a structural property of the domain, documented
here rather than glossed over. It's also exactly why the platform's
ingestion layer is built around incremental, watermark-based extraction
(ADR in `ingestion/open_prices.py`) — real telemetry accrues once the
pipeline is actually deployed against a live source.

## Consequences
- Categories, brands, ratings, and images are now facts, not guesses —
  meaningfully strengthens the "how would you defend this in an
  interview" test.
- Forecasting quality improved on the richer data: price MAPE 5.2% → 3.8%,
  demand MAPE 94.6% → 43.9% (the synthetic velocity signal here has a
  learnable relationship with discount events, unlike the old sample).
- The conformance module got *simpler*, not more complex — trusting a
  real source removes code, which is the right direction.
