# ETF Quant Portfolio Dashboard

This repository now includes a deployable Next.js dashboard for the ETF quant research stack.

The dashboard is designed to present the saved outputs from the notebooks:

- `01_data_hub.ipynb`: data hub, universe, benchmarks, macro and regime inputs
- `02_layer1_alpha_signals.ipynb`: alpha signal research and validation
- `03_layer2a_strategy_logic.ipynb`: strategy sleeves and benchmark strategies
- `04_layer2b_risk_regime_engine.ipynb`: risk metrics, regime states, overlays
- `05_layer3_portfolio_construction.ipynb`: portfolio construction comparison

The app does not recompute research. It reads the generated CSV / JSON artifacts and turns them into a dashboard data bundle.

## What The Dashboard Shows

- Executive summary with the current default production allocator candidate
- Best-by-Sharpe, most-robust, drawdown-controlled, and low-turnover candidates
- Current regime state and latest available research date
- Portfolio wealth curves, drawdowns, and rolling Sharpe
- Sortable method comparison table with return, risk, drawdown, tail risk, turnover, concentration, and robustness metrics
- Regime split, subperiod, cost, and diagnostic views
- Layer 2 strategy / sleeve summaries
- Latest ETF look-through weights and sleeve allocations
- Layer 1 signal validation, IC decay, and redundancy heatmap

The dashboard intentionally makes clear that complex optimizers are not automatically better and that the default allocator should be chosen by robustness, not headline Sharpe alone.

The latest improvement pass also adds a dedicated comparison workflow that answers:

- why the current portfolio can end up defensive
- whether the stack is over-damped by overlays and smoothing
- which Layer 1 signals add real incremental value
- which Layer 2 sleeves improve the final allocator versus just adding another brake
- whether the improved finalists actually beat the original baseline out of sample
- whether recovery-state re-risking improves upside capture without giving back too much drawdown control
- how much rally participation is lost to overlay cash, slow re-risking, or weak sleeve selection

## Data Layout Expected

The ingestion script expects the existing numbered data folders:

```text
data/01_data_hub/
data/02_layer1_signals/
data/03_layer2a_strategy_logic/
data/04_layer2b_risk_regime_engine/
data/05_layer3_portfolio_construction/
```

Important files include:

```text
data/05_layer3_portfolio_construction/portfolio_method_comparison.csv
data/05_layer3_portfolio_construction/portfolio_metrics_summary.csv
data/05_layer3_portfolio_construction/portfolio_returns_<method>.csv
data/05_layer3_portfolio_construction/portfolio_weights_<method>.csv
data/05_layer3_portfolio_construction/portfolio_sleeve_weights_<method>.csv
data/03_layer2a_strategy_logic/strategy_summary_table.csv
data/03_layer2a_strategy_logic/strategy_returns_baseline_*.csv
data/04_layer2b_risk_regime_engine/regime_states.csv
data/04_layer2b_risk_regime_engine/regime_score.csv
data/02_layer1_signals/signal_summary_table.csv
data/02_layer1_signals/signal_ic_by_horizon.csv
data/02_layer1_signals/signal_redundancy_matrix.csv
```

If optional sensitivity outputs such as `portfolio_dampener_sensitivity.csv` or `portfolio_bl_confidence_sensitivity.csv` are missing, the dashboard will show a clear note and populate those tables after the Layer 3 notebook is rerun.

## Local Setup

Install Node.js 20 or newer, then run:

```bash
npm install
npm run refresh:data
npm run dev
```

Open the local URL printed by Next.js.

The `refresh:data` command reads the notebook outputs and writes:

```text
public/dashboard-data.json
```

The app reads that bundle in the browser, which keeps the deployment simple and avoids a database or custom backend.
The homepage now preloads that bundle on the server, so the dashboard renders directly instead of waiting on a large client-side loading shell in the normal path.

## Refresh Workflow

When research outputs change:

1. Rerun the notebooks in order: `01`, `02`, `03`, `04`, `05`.
2. Rebuild the improvement-lab artifacts:

```bash
npm run refresh:improvement-lab
```

3. Rebuild the dashboard bundle:

```bash
npm run refresh:data
```

4. Restart the local dev server if needed, or redeploy to Vercel.

The Vercel build command also runs `npm run refresh:data`, so committed CSV / JSON research outputs are ingested automatically during deployment.

For local research iteration, the convenience command below runs both refresh steps in order:

```bash
npm run refresh:full
```

## Vercel Deployment

This is a standard Next.js project.

Recommended deployment path:

1. Push the repository to GitHub.
2. Import the repository in Vercel.
3. Use the default Next.js framework detection.
4. Keep the build command as:

```bash
npm run build
```

The included `vercel.json` explicitly marks the project as a Next.js app and uses that build command.

## Scripts

```bash
npm run refresh:improvement-lab   # rebuild baseline-vs-improved, signal, sleeve, and allocation-driver comparison artifacts
npm run refresh:full              # rebuild improvement artifacts, then rebuild public/dashboard-data.json
npm run refresh:data   # rebuild public/dashboard-data.json from research artifacts
npm run dev            # refresh data, then start Next.js locally
npm run build          # refresh data, then build for production / Vercel
npm run start          # start a production build locally
npm run typecheck      # TypeScript check
```

## Design Notes

- No database is required.
- No live trading or brokerage integration is included.
- The dashboard is a research/product presentation layer over saved artifacts.
- Data updates are reproducible because the source of truth remains the notebook-generated files.
- The static bundle architecture is compatible with future scheduled rebuild workflows.
