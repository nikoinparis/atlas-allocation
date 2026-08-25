/**
 * How each strategy actually works, from raw data to a weight vector.
 *
 * Every step names its inputs, states the rule as a formula, and where it helps
 * carries a worked example with real numbers from the saved record. Nothing here
 * is a claim about future returns; it is a description of the frozen procedure.
 */

export type MethodFormula = { label: string; markup: string };

export type MethodExample = {
  caption: string;
  rows: { label: string; value: string }[];
  outcome?: string;
};

export type DeepStep = {
  number: string;
  label: string;
  title: string;
  description: string;
  inputs: string[];
  formulaKey: string;
  note: string;
  example?: MethodExample;
};

export type DeepMethodology = {
  summary: string;
  cadence: string;
  universe: string;
  dataSources: { name: string; detail: string }[];
  steps: DeepStep[];
};

/* ------------------------------------------------------------------ math */

const m = (inner: string) => `<math display="block"><mrow>${inner}</mrow></math>`;
const sub = (base: string, s: string) => `<msub><mi>${base}</mi><mtext>${s}</mtext></msub>`;

export const deepFormulas: Record<string, MethodFormula> = {
  pointInTime: {
    label: "a feature may only use information available at or before the decision date",
    markup: m(`<msub><mi>x</mi><mi>i</mi></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mi>f</mi><mo stretchy="false">(</mo><mtext>data available at </mtext><mi>u</mi><mo>≤</mo><mi>t</mi><mo stretchy="false">)</mo>`),
  },
  totalReturn: {
    label: "k-week total return of asset i",
    markup: m(`<msub><mi>R</mi><mrow><mi>i</mi><mo>,</mo><mi>k</mi></mrow></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mfrac><mrow><msub><mi>P</mi><mi>i</mi></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo></mrow><mrow><msub><mi>P</mi><mi>i</mi></msub><mo stretchy="false">(</mo><mi>t</mi><mo>−</mo><mi>k</mi><mo stretchy="false">)</mo></mrow></mfrac><mo>−</mo><mn>1</mn>`),
  },
  residualSplit: {
    label: "residual return is the part of a stock's return not explained by market and sector",
    markup: m(`<msub><mi>ε</mi><mi>i</mi></msub><mo>=</mo><msub><mi>R</mi><mi>i</mi></msub><mo>−</mo><msub><mi>β</mi><mrow><mi>i</mi><mo>,</mo><mi>m</mi></mrow></msub><msub><mi>R</mi><mi>m</mi></msub><mo>−</mo><msub><mi>β</mi><mrow><mi>i</mi><mo>,</mo><mi>s</mi></mrow></msub><msub><mi>R</mi><mi>s</mi></msub>`),
  },
  betaEstimate: {
    label: "beta is covariance over variance, estimated on lagged data only",
    markup: m(`<msub><mi>β</mi><mrow><mi>i</mi><mo>,</mo><mi>m</mi></mrow></msub><mo>=</mo><mfrac><mrow><mi>Cov</mi><mo stretchy="false">(</mo><msub><mi>R</mi><mi>i</mi></msub><mo>,</mo><msub><mi>R</mi><mi>m</mi></msub><mo stretchy="false">)</mo></mrow><mrow><mi>Var</mi><mo stretchy="false">(</mo><msub><mi>R</mi><mi>m</mi></msub><mo stretchy="false">)</mo></mrow></mfrac>`),
  },
  zScore: {
    label: "cross-sectional standardisation within a sector",
    markup: m(`<msub><mi>z</mi><mi>i</mi></msub><mo>=</mo><mfrac><mrow><msub><mi>x</mi><mi>i</mi></msub><mo>−</mo><msub><mi>μ</mi><mtext>sector</mtext></msub></mrow><mrow><msub><mi>σ</mi><mtext>sector</mtext></msub></mrow></mfrac>`),
  },
  cashConversion: {
    label: "cash conversion is operating cash flow divided by revenue",
    markup: m(`<mtext>CC</mtext><mo>=</mo><mfrac><mtext>operating cash flow</mtext><mtext>revenue</mtext></mfrac>`),
  },
  compositeRank: {
    label: "composite score is a weighted sum of standardised components",
    markup: m(`<msub><mi>s</mi><mi>i</mi></msub><mo>=</mo><munder><mo>∑</mo><mi>j</mi></munder><msub><mi>w</mi><mi>j</mi></msub><mo>·</mo><msub><mi>z</mi><mrow><mi>i</mi><mo>,</mo><mi>j</mi></mrow></msub>`),
  },
  topN: {
    label: "select the N highest scoring names",
    markup: m(`<mi>S</mi><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><munder><mrow><mi>top</mi></mrow><mrow><mi>N</mi></mrow></munder><mo stretchy="false">{</mo><msub><mi>s</mi><mi>i</mi></msub><mo stretchy="false">}</mo><mo>,</mo><mspace width="0.4em"/><mi>N</mi><mo>=</mo><mn>20</mn>`),
  },
  equalWeight: {
    label: "each selected name receives an equal share",
    markup: m(`<msub><mi>w</mi><mi>i</mi></msub><mo>=</mo><mfrac><mn>1</mn><mrow><mo stretchy="false">|</mo><mi>S</mi><mo stretchy="false">|</mo></mrow></mfrac>`),
  },
  issuerCap: {
    label: "no single issuer above the cap, no sector above its cap",
    markup: m(`<msub><mi>w</mi><mi>i</mi></msub><mo>≤</mo><msub><mi>c</mi><mtext>issuer</mtext></msub><mo>,</mo><mspace width="0.6em"/><munder><mo>∑</mo><mrow><mi>i</mi><mo>∈</mo><mi>s</mi></mrow></munder><msub><mi>w</mi><mi>i</mi></msub><mo>≤</mo><msub><mi>c</mi><mtext>sector</mtext></msub>`),
  },
  lookThrough: {
    label: "a fund's weight is pushed through to the sectors it holds",
    markup: m(`<msub><mi>E</mi><mi>s</mi></msub><mo>=</mo><munder><mo>∑</mo><mi>i</mi></munder><msub><mi>w</mi><mi>i</mi></msub><mo>·</mo><msub><mi>a</mi><mrow><mi>i</mi><mo>,</mo><mi>s</mi></mrow></msub>`),
  },
  blend: {
    label: "the two complete portfolios are mixed at fixed proportions",
    markup: m(`<mi>w</mi><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mo stretchy="false">(</mo><mn>1</mn><mo>−</mo><mi>a</mi><mo stretchy="false">)</mo><mo>·</mo>${sub("w", "control")}<mo>+</mo><mi>a</mi><mo>·</mo>${sub("w", "sleeve")}`),
  },
  turnoverCost: {
    label: "turnover is half the total absolute weight change; cost is turnover times the rate",
    markup: m(`${sub("T", "t")}<mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><munder><mo>∑</mo><mi>i</mi></munder><mo stretchy="false">|</mo><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi></mrow></msub><mo>−</mo><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi><mo>−</mo><mn>1</mn></mrow></msub><mo stretchy="false">|</mo><mo>,</mo><mspace width="0.5em"/><mtext>cost</mtext><mo>=</mo><mn>0.0050</mn><mo>·</mo>${sub("T", "t")}`),
  },
  executionDelay: {
    label: "weights decided at t are executed one week later",
    markup: m(`<msup><mi>w</mi><mtext>exec</mtext></msup><mo stretchy="false">(</mo><mi>t</mi><mo>+</mo><mn>1</mn><mo stretchy="false">)</mo><mo>=</mo><mi>w</mi><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo>`),
  },
  leverage: {
    label: "gross exposure L costs financing on the borrowed part",
    markup: m(`${sub("r", "net")}<mo>=</mo><mi>L</mi><mo>·</mo>${sub("r", "cash")}<mo>−</mo><mo stretchy="false">(</mo><mi>L</mi><mo>−</mo><mn>1</mn><mo stretchy="false">)</mo><mo>·</mo><mfrac><mi>f</mi><mn>52</mn></mfrac>`),
  },
  volTarget: {
    label: "scale exposure toward a volatility target, never above one",
    markup: m(`${sub("k", "t")}<mo>=</mo><mi>min</mi><mo stretchy="false">(</mo><mn>1</mn><mo>,</mo><mfrac><msub><mi>σ</mi><mtext>target</mtext></msub><msub><mi>σ</mi><mtext>realised</mtext></msub></mfrac><mo stretchy="false">)</mo>`),
  },
  breadthGate: {
    label: "raise allocation only when the signal is positive on every checked horizon",
    markup: m(`<mtext>on</mtext><mo>=</mo><mo>[</mo><msub><mi>R</mi><mn>13</mn></msub><mo>&gt;</mo><mn>0</mn><mo>]</mo><mo>∧</mo><mo>[</mo><msub><mi>R</mi><mn>26</mn></msub><mo>&gt;</mo><mn>0</mn><mo>]</mo><mo>∧</mo><mo>[</mo><msub><mi>R</mi><mn>52</mn></msub><mo>&gt;</mo><mn>0</mn><mo>]</mo>`),
  },
  informationCoefficient: {
    label: "information coefficient is the rank correlation between signal and next return",
    markup: m(`<mtext>IC</mtext><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mi>corr</mi><mo stretchy="false">(</mo><mi>rank</mi><mo stretchy="false">(</mo><msub><mi>x</mi><mi>i</mi></msub><mo stretchy="false">)</mo><mo>,</mo><mi>rank</mi><mo stretchy="false">(</mo><msub><mi>R</mi><mrow><mi>i</mi><mo>,</mo><mtext>fwd</mtext></mrow></msub><mo stretchy="false">)</mo><mo stretchy="false">)</mo>`),
  },
  compounding: {
    label: "wealth compounds the net weekly return",
    markup: m(`<mi>W</mi><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mi>W</mi><mo stretchy="false">(</mo><mi>t</mi><mo>−</mo><mn>1</mn><mo stretchy="false">)</mo><mo>·</mo><mo stretchy="false">(</mo><mn>1</mn><mo>+</mo>${sub("r", "net")}<mo stretchy="false">)</mo>`),
  },
  forwardClock: {
    label: "only weeks observed after the freeze count toward the forward record",
    markup: m(`<mi>N</mi><mo>=</mo><mo stretchy="false">|</mo><mo stretchy="false">{</mo><mi>t</mi><mo>:</mo><mi>t</mi><mo>&gt;</mo><msub><mi>t</mi><mtext>freeze</mtext></msub><mo stretchy="false">}</mo><mo stretchy="false">|</mo><mo>,</mo><mspace width="0.5em"/><mtext>require </mtext><mi>N</mi><mo>≥</mo><mn>52</mn>`),
  },
};

/* ------------------------------------------------------- shared pipeline */

const SEC_SOURCES = [
  { name: "SEC company facts", detail: "XBRL financial statements pulled per issuer CIK. Revenue, operating cash flow, and balance-sheet lines. Each fact carries a filing date, and only facts already filed by the decision date are usable." },
  { name: "Point-in-time filer roster", detail: "The set of companies that actually existed and filed as of each historical date, built from SEC records rather than a present-day ticker list filtered backwards. This is what keeps delisted and acquired companies in the universe." },
  { name: "Adjusted daily prices", detail: "Split- and dividend-adjusted closes per issuer, joined to the CIK rather than the ticker so symbol changes do not break the history." },
  { name: "Sector classification", detail: "SIC-derived divisions from the filings themselves, used to make comparisons within a peer group instead of across the whole market." },
];

const ETF_SOURCES = [
  { name: "Liquid ETF price history", detail: "Adjusted closes for the sector and broad-market funds the strategy is allowed to hold, plus a short-treasury fund as the cash equivalent." },
  { name: "Decision calendar", detail: "A fixed weekly decision date. Every feature is computed from prices at or before that date." },
];

const costStep = (n: string): DeepStep => ({
  number: n, label: "COST", title: "Charge for every trade",
  description: "Turnover is measured as half the total absolute change in the weight vector, so a full switch from one book to another counts as 100%. Fifty basis points is charged on that turnover and subtracted from the gross return. Weeks with no rebalance cost nothing.",
  inputs: ["Previous target weights", "New target weights"],
  formulaKey: "turnoverCost",
  note: "50 bps is a research assumption. Real spreads, market impact, and days-to-exit are not modelled anywhere in this project.",
  example: {
    caption: "A real rebalance week, 2026-07-31",
    rows: [
      { label: "Turnover measured", value: "0.1141" },
      { label: "Cost at 50 bps", value: "0.1141 × 0.0050 = 0.000571" },
      { label: "Gross return", value: "+6.918%" },
      { label: "Net return", value: "+6.861%" },
    ],
    outcome: "Cost is small in any one week, but it compounds: this strategy has paid 13.05 percentage points of cumulative drag over its life.",
  },
});

const executeStep = (n: string): DeepStep => ({
  number: n, label: "EXECUTE", title: "Trade a week after deciding",
  description: "A decision made on a Friday is executed the following Friday, not the same day. This gap is the difference between a backtest that can be run and one that quietly assumes you traded on information you did not yet have.",
  inputs: ["Target weights from the decision date"],
  formulaKey: "executionDelay",
  note: "This project has twice found real lookahead bugs that a code read missed. The delay is enforced in the data, and prefix-invariance tests confirm that changing future data leaves past decisions untouched.",
});

const validateStep = (n: string, verdict: string): DeepStep => ({
  number: n, label: "VALIDATE", title: "Record what failed",
  description: "The saved result is put through the same battery as every other strategy: doubled costs, extra financing, a forced crash week, 25% signal decay, concentration limits, moving-block bootstrap, and the forward clock. Failures are recorded, not smoothed over.",
  inputs: ["Full weekly return series", "Weekly holdings"],
  formulaKey: "forwardClock",
  note: verdict,
});

/* ------------------------------------------------------ per strategy */

export const deepMethodology: Record<string, DeepMethodology> = {
  "sec-cash-conversion-breadth20-dynamic-v1": {
    summary:
      "Rank every SEC filer by how much of its revenue turns into actual operating cash, hold the best twenty equally, and only lean in when the signal is confirmed on several horizons at once. No leverage, no shorting, costs charged.",
    cadence: "Quarterly ranking · weekly risk review · 50 bps on turnover",
    universe: "Point-in-time U.S. SEC filers with validated prices, plus sector ETFs and cash",
    dataSources: SEC_SOURCES,
    steps: [
      {
        number: "01", label: "DATA", title: "Start from filings, not a ticker list",
        description:
          "The universe for a given quarter is the set of companies that had actually filed with the SEC by that date. Building it from a present-day ticker list would silently delete every company that later went bankrupt or was acquired, which is the single most common way a backtest invents returns that were never available.",
        inputs: ["SEC filer roster as of the decision date", "Adjusted prices keyed by CIK"],
        formulaKey: "pointInTime",
        note: "3,424 issuers appear across the panel. Companies that disappear stay in history up to the week they disappear.",
        example: {
          caption: "Why this matters",
          rows: [
            { label: "Issuers in the panel", value: "3,424" },
            { label: "Decision dates", value: "14 quarterly" },
            { label: "Issuer-decision rows", value: "40,284" },
          ],
          outcome: "A survivorship-filtered universe would quietly drop the losers and inflate every historical number.",
        },
      },
      {
        number: "02", label: "FEATURE", title: "Measure cash conversion",
        description:
          "For each company, divide operating cash flow by revenue. This asks a simple question: of every dollar of sales, how many cents actually arrived as cash? A company can report growing profit while collecting nothing, and this ratio separates the two.",
        inputs: ["Operating cash flow (XBRL)", "Revenue (XBRL)"],
        formulaKey: "cashConversion",
        note: "Only figures already filed by the decision date are used. A restatement published later never reaches back into an earlier decision.",
        example: {
          caption: "Worked example",
          rows: [
            { label: "Revenue", value: "$4.00B" },
            { label: "Operating cash flow", value: "$0.92B" },
            { label: "Cash conversion", value: "0.92 ÷ 4.00 = 0.23" },
          ],
          outcome: "0.23 means 23 cents of every sales dollar showed up as cash. That number is then compared against sector peers, not against the whole market.",
        },
      },
      {
        number: "03", label: "NORMALISE", title: "Compare inside the sector",
        description:
          "A software company and a utility have structurally different cash profiles, so a raw ratio would just rank sectors. Each company's ratio is standardised against its own sector: subtract the sector mean, divide by the sector standard deviation.",
        inputs: ["Cash conversion per company", "SIC sector label"],
        formulaKey: "zScore",
        note: "This turns the score into 'how unusual is this company for its peer group', which is what the strategy is actually trying to bet on.",
        example: {
          caption: "Same ratio, different verdict",
          rows: [
            { label: "Company ratio", value: "0.23" },
            { label: "Technology sector mean", value: "0.18, sd 0.09" },
            { label: "z inside technology", value: "(0.23 − 0.18) ÷ 0.09 = +0.56" },
            { label: "Utilities sector mean", value: "0.31, sd 0.06" },
            { label: "z inside utilities", value: "(0.23 − 0.31) ÷ 0.06 = −1.33" },
          ],
          outcome: "The identical 0.23 is above average for a tech company and clearly below average for a utility.",
        },
      },
      {
        number: "04", label: "RANK", title: "Score and take the top twenty",
        description:
          "Standardised components are combined into one score per company and sorted. The top twenty are selected. Twenty is a deliberate breadth choice: few enough that the signal is not diluted, many enough that no single company decides the year.",
        inputs: ["Standardised scores for every eligible company"],
        formulaKey: "topN",
        note: "Breadth is the point. This project's chronic failure has been strategies where one name supplied most of the return.",
      },
      {
        number: "05", label: "SIZE", title: "Weight them equally",
        description:
          "Each of the twenty gets 1/20 = 5%. Equal weighting is used rather than score weighting because score-proportional sizing concentrates into whichever name happens to have the most extreme reading, which is usually the noisiest one.",
        inputs: ["Selected names"],
        formulaKey: "equalWeight",
        note: "Equal weighting was compared against inverse-volatility, covariance, and fractional-Kelly sizing in earlier work. None of those passed the gates.",
      },
      {
        number: "06", label: "GATE", title: "Only lean in when several horizons agree",
        description:
          "The allocation between the stock sleeve and the defensive holdings is not constant. It rises only when the signal is positive across the 13, 26 and 52-week horizons simultaneously. One horizon agreeing is a coincidence; three agreeing is a weaker coincidence.",
        inputs: ["13, 26 and 52-week trailing returns, all lagged"],
        formulaKey: "breadthGate",
        note: "Every input to this gate is lagged. It can never see the return it is about to earn.",
      },
      executeStep("07"),
      costStep("08"),
      validateStep(
        "09",
        "Passes the drawdown, cost, decay and Monte Carlo gates. Fails worst-rolling-year at −14.07% and single-position concentration at 90%. Forward record is 0 of 52 weeks. It is the only one of the six whose 5th-percentile simulated year is positive, at +1.83%.",
      ),
    ],
  },

  "sec-residual-controlled-1.25x-5pct-v1": {
    summary:
      "Take the cash-conversion book as the core, add a sleeve that ranks stocks on the return left over after removing market and sector moves, hold them 80/20, then apply a 1.25x exposure assumption. The 20% weight and the leverage were both chosen after seeing the result.",
    cadence: "Quarterly sleeve selection · weekly targets · frozen forward clock",
    universe: "The cash-conversion core plus an independent residual-momentum sleeve",
    dataSources: SEC_SOURCES,
    steps: [
      {
        number: "01", label: "CORE", title: "Inherit the cash-conversion book",
        description:
          "Eighty percent of the portfolio is the cash-conversion breadth-20 strategy, unchanged. Its rules, its costs, and its failures are carried over rather than retuned, so that anything this strategy adds can be attributed to the sleeve alone.",
        inputs: ["The complete control weight vector"],
        formulaKey: "blend",
        note: "Retuning the core inside this experiment would make the sleeve's contribution unmeasurable.",
      },
      {
        number: "02", label: "DECOMPOSE", title: "Strip out market and sector",
        description:
          "A stock that rose 20% because its whole sector rose 20% tells you nothing about the company. The sleeve estimates how much of each stock's move is explained by the market and by its sector, and keeps only the leftover.",
        inputs: ["Stock returns", "Market index returns", "Sector index returns"],
        formulaKey: "residualSplit",
        note: "The betas are estimated on lagged windows only. Using the full sample to estimate beta is a classic lookahead error and was found in this project before.",
        example: {
          caption: "Worked example",
          rows: [
            { label: "Stock return, 13 weeks", value: "+18.0%" },
            { label: "Market return × beta 1.1", value: "+8.8%" },
            { label: "Sector return × beta 0.7", value: "+6.3%" },
            { label: "Residual", value: "18.0 − 8.8 − 6.3 = +2.9%" },
          ],
          outcome: "Only the +2.9% is treated as information about the company. A stock up 18% on a sector that rose more would score negative here.",
        },
      },
      {
        number: "03", label: "BETA", title: "Estimate the sensitivities honestly",
        description:
          "Beta is covariance over variance, computed on a rolling window that ends before the decision date. A minimum history is required before a stock is eligible, so newly listed names cannot enter on a two-week estimate.",
        inputs: ["52-week lagged return windows", "26-week minimum history"],
        formulaKey: "betaEstimate",
        note: "Residual momentum is available for 82.1% of issuer-decision rows. The rest are excluded rather than filled in.",
      },
      {
        number: "04", label: "RANK", title: "Score residual strength and select",
        description:
          "Companies are ranked on their accumulated residual return, and the top names are taken subject to issuer and sector limits so the sleeve cannot become a single-sector bet on its own.",
        inputs: ["Residual returns per company", "Issuer and sector caps"],
        formulaKey: "issuerCap",
        note: "Measured information coefficient for residual momentum is 0.0571, positive in 67% of quarters, and outside a 2,000-shuffle permutation null at p below 0.0001.",
      },
      {
        number: "05", label: "BLEND", title: "Hold the fixed 80 / 20 mix",
        description:
          "The complete core portfolio gets 80% and the complete sleeve gets 20%. Both are full weight vectors, so overlapping names simply add up — which is exactly how the two books turned out to share 25 of the sleeve's 29 names.",
        inputs: ["Control weights", "Sleeve weights", "a = 0.20"],
        formulaKey: "blend",
        note: "The 20% was chosen after observing this sample. That is why this strategy carries a frozen forward clock rather than a promotion.",
        example: {
          caption: "What the blend actually does to a shared name",
          rows: [
            { label: "Weight in the core", value: "5.0%" },
            { label: "Weight in the sleeve", value: "5.0%" },
            { label: "Combined", value: "0.80 × 5.0% + 0.20 × 5.0% = 5.0%" },
          ],
          outcome: "Because both books hold the same name, blending them does not diversify it away. Measured weight overlap between the two is 75.8%.",
        },
      },
      {
        number: "06", label: "EXPOSURE", title: "Apply 1.25x and pay for it",
        description:
          "The blended book is scaled to 125% gross. The extra 25% is borrowed, and financing is charged on it. The pure-cash version of this same strategy is the default view in this dashboard; the financed version is offered as an explicit option.",
        inputs: ["Blended weekly return", "L = 1.25", "financing rate f"],
        formulaKey: "leverage",
        note: "Financing multiplies losses by the same 1.25 that it multiplies gains. Pure cash returns 112.60% trailing; at 1.25x and 5% financing it returns 150.86%.",
        example: {
          caption: "One week, both ways",
          rows: [
            { label: "Pure-cash week", value: "−2.00%" },
            { label: "Scaled 1.25x", value: "−2.50%" },
            { label: "Financing on 0.25 at 5%", value: "−0.024%" },
            { label: "Financed week", value: "−2.524%" },
          ],
          outcome: "The uplift and the damage are the same multiple. A 26% cash drawdown becomes roughly 33% financed.",
        },
      },
      executeStep("07"),
      costStep("08"),
      validateStep(
        "09",
        "Passes drawdown, cost, decay and Monte Carlo. Fails worst-rolling-year at −16.17% and concentration at 90% single position, which after ETF look-through is an 81.6% technology book. Forward record 0 of 52. The 80/20 weight was selected on this same sample.",
      ),
    ],
  },

  "sec-sector-aware-signal-ensemble-v1": {
    summary:
      "Combine several filing-based signals into one score, enforce sector balance so the book cannot become a single-sector bet, and size positions against realised volatility. No leverage.",
    cadence: "Quarterly ensemble · weekly risk scaling · 50 bps",
    universe: "Point-in-time SEC filers with validated prices, plus sector ETFs",
    dataSources: SEC_SOURCES,
    steps: [
      {
        number: "01", label: "DATA", title: "Same point-in-time foundation",
        description: "The universe, prices and sector labels are the same causal foundation used by every SEC strategy here: only what had been filed and priced by the decision date.",
        inputs: ["Filer roster", "Adjusted prices", "SIC sectors"],
        formulaKey: "pointInTime",
        note: "Sharing the foundation is what makes strategies comparable — and also what makes them correlated.",
      },
      {
        number: "02", label: "SIGNALS", title: "Compute several features, not one",
        description:
          "Rather than betting everything on one ratio, the ensemble computes trend quality, quality momentum, and cash-conversion strength for each company, each standardised inside its sector.",
        inputs: ["Trend quality", "Quality momentum", "Cash conversion"],
        formulaKey: "zScore",
        note: "Measured ICs: trend quality 0.0665, quality momentum 0.0285. Both clear a permutation null. The event-score feature was measured at 0.0005 and is noise.",
      },
      {
        number: "03", label: "COMBINE", title: "Weighted sum into one score",
        description:
          "The standardised components are combined into a single score per company with fixed weights. Fixed weights matter: refitting the blend on the same data you evaluate it on is how a backtest teaches itself the answer.",
        inputs: ["Standardised component scores", "Fixed component weights"],
        formulaKey: "compositeRank",
        note: "Weights are frozen before evaluation and are part of the sealed configuration.",
        example: {
          caption: "Worked example",
          rows: [
            { label: "Trend quality z", value: "+1.20 × 0.4 = +0.48" },
            { label: "Quality momentum z", value: "+0.30 × 0.3 = +0.09" },
            { label: "Cash conversion z", value: "−0.50 × 0.3 = −0.15" },
            { label: "Composite", value: "+0.42" },
          ],
          outcome: "One weak component does not disqualify a company, but it does pull the score down.",
        },
      },
      {
        number: "04", label: "SECTOR", title: "Force sector balance",
        description:
          "Selection is constrained so no sector can dominate. Without this, a score built from momentum-like features reliably piles into whatever sector has been winning, which is a sector bet wearing a stock-selection costume.",
        inputs: ["Composite scores", "Sector labels", "Sector caps"],
        formulaKey: "issuerCap",
        note: "This control operates on directly held names. Fund holdings need the look-through step to be measured correctly.",
      },
      {
        number: "05", label: "LOOK THROUGH", title: "Push fund weights into sectors",
        description:
          "A sector ETF is not one position, it is a basket. To know real sector exposure, each fund's weight is expanded into the sectors it actually holds and added to the directly held names.",
        inputs: ["Fund weights", "Fund sector composition"],
        formulaKey: "lookThrough",
        note: "Over half of this book's weight sits in funds. Without look-through, its measured sector concentration is understated by a wide margin.",
        example: {
          caption: "Why the naive number is wrong",
          rows: [
            { label: "Direct technology names", value: "22%" },
            { label: "XLK weight", value: "48%, of which technology 100%" },
            { label: "Naive sector reading", value: "22%" },
            { label: "After look-through", value: "22% + 48% = 70%" },
          ],
          outcome: "The same portfolio looks diversified before look-through and concentrated after it.",
        },
      },
      {
        number: "06", label: "RISK", title: "Scale toward a volatility target",
        description:
          "Exposure is scaled by the ratio of a target volatility to recently realised volatility, capped at one so the rule can only ever reduce risk, never add leverage.",
        inputs: ["Realised volatility, lagged", "Volatility target"],
        formulaKey: "volTarget",
        note: "Capping at one is deliberate. A scaler allowed above one becomes leverage by another name.",
      },
      executeStep("07"),
      costStep("08"),
      validateStep(
        "09",
        "Passes drawdown, cost, decay and Monte Carlo, with the best realised drawdown of the six at −8.71%. Fails worst-rolling-year at −14.06% and concentration at 90%. Forward record 0 of 52.",
      ),
    ],
  },

  "sec-sector-ensemble-fragile-1.35x-v1": {
    summary:
      "The sector ensemble run at 1.35x exposure. It posts the highest headline return of the six and also failed its own robustness gates — it is kept visible as a return ceiling, not as a candidate.",
    cadence: "Quarterly ensemble · weekly risk scaling · 1.35x exposure",
    universe: "The sector-aware ensemble universe",
    dataSources: SEC_SOURCES,
    steps: [
      {
        number: "01", label: "BASE", title: "Start from the sector ensemble",
        description: "Every selection and sizing rule is inherited unchanged from the sector-aware ensemble. The only difference is how much exposure is applied on top.",
        inputs: ["The complete ensemble weight vector"],
        formulaKey: "blend",
        note: "Because the base is shared, this strategy is not an independent bet from the ensemble.",
      },
      {
        number: "02", label: "EXPOSURE", title: "Scale to 135%",
        description:
          "The book is levered to 1.35x with financing charged on the borrowed 35%. This is the single change that produces the headline number, and it is also what makes the strategy fragile.",
        inputs: ["Ensemble weekly return", "L = 1.35", "financing rate"],
        formulaKey: "leverage",
        note: "Pure cash it returns 114.12% trailing. At 1.35x it returns 168.68%. The 54.56 point difference is borrowed money, not skill.",
        example: {
          caption: "The concentration this creates",
          rows: [
            { label: "Largest fund weight at 1.00x", value: "90.0%" },
            { label: "Same position at 1.35x", value: "121.5%" },
          ],
          outcome: "A single fund position larger than the entire account. This is why the concentration gate fails hardest here.",
        },
      },
      {
        number: "03", label: "FALSIFY", title: "The gates it actually failed",
        description:
          "Leave-one-issuer-out and bootstrap testing were run on this strategy and it did not survive them. It is displayed to mark the upper bound of what this signal family produced, so that the ceiling is visible rather than imagined.",
        inputs: ["Weekly returns", "Per-issuer contribution"],
        formulaKey: "informationCoefficient",
        note: "Five-issuer and bootstrap gates failed. The badge on this strategy says FAILED ROBUSTNESS for that reason.",
      },
      executeStep("04"),
      costStep("05"),
      validateStep(
        "06",
        "Worst 5th-percentile simulated year of the four top scorers at −3.54%, and the highest chance of a greater-than-30% drawdown at 5.86%. Fails worst-rolling-year at −20.88% and concentration at 121.5%. Forward record 0 of 52.",
      ),
    ],
  },

  "sec-growth-survivorship-aware-v1": {
    summary:
      "A concentrated quarterly growth sleeve of five names, sized against the ETF incumbent using lagged relative momentum. It posts the highest pure-cash return of the six and is also the most concentrated bet in the set.",
    cadence: "Quarterly selection · weekly risk review",
    universe: "Point-in-time SEC filers, top five by growth score",
    dataSources: SEC_SOURCES,
    steps: [
      {
        number: "01", label: "DATA", title: "Survivorship-aware universe",
        description:
          "The name of this strategy is the point: the universe is rebuilt from the historical filer roster at each date, so companies that later failed are still present in the past where they belong.",
        inputs: ["Historical filer roster", "Adjusted prices by CIK"],
        formulaKey: "pointInTime",
        note: "Getting this wrong is the fastest way to manufacture a great backtest.",
      },
      {
        number: "02", label: "SCORE", title: "Rank on growth quality",
        description: "Companies are scored on filing-derived growth measures, standardised within sector so the comparison is against peers.",
        inputs: ["Growth measures from filings", "Sector labels"],
        formulaKey: "zScore",
        note: "Fundamental growth is measured from filed statements, never from analyst estimates, which are not point-in-time here.",
      },
      {
        number: "03", label: "SELECT", title: "Take only five names",
        description:
          "The top five are held at 20% each. Five is a deliberate concentration choice and it is the strategy's defining risk: with twenty names, one company cannot decide the year; with five, it can and did.",
        inputs: ["Top five scores"],
        formulaKey: "equalWeight",
        note: "Micron supplied 67.63% of this strategy's positive return. That single fact is the whole risk profile.",
        example: {
          caption: "What five names means",
          rows: [
            { label: "Weight per name", value: "1 ÷ 5 = 20%" },
            { label: "Micron share of positive return", value: "67.63%" },
            { label: "Monte Carlo profit probability", value: "81.14%" },
            { label: "5th-percentile simulated year", value: "−19.21%" },
          ],
          outcome: "The highest pure-cash return of the six, and the weakest downside of the six. Both come from the same choice.",
        },
      },
      {
        number: "04", label: "GATE", title: "Size against the incumbent",
        description:
          "The sleeve's allocation is raised or lowered based on lagged relative momentum against the ETF incumbent, plus breadth and volatility checks. When the growth sleeve is not outperforming, exposure falls.",
        inputs: ["26-week growth return", "26-week incumbent return, both lagged"],
        formulaKey: "breadthGate",
        note: "The comparison is lagged on both sides. The rule cannot see which one is about to win.",
      },
      executeStep("05"),
      costStep("06"),
      validateStep(
        "07",
        "Scores 55 of 100. Fails full-history drawdown at −36.5%, worst rolling year at −18.47%, and concentration. A 21.91% chance of a greater-than-30% drawdown, the highest of the six. Forward record 0 of 52.",
      ),
    ],
  },

  "candidate-return-first-60-40-forward-v1": {
    summary:
      "A frozen ETF-only blend: 60% a pre-selected technology core, 40% a rank-consensus allocator across liquid funds. It is the longest history in the book, running back to 2005, and the only one that has seen 2008 and 2020.",
    cadence: "Frozen weekly decision record",
    universe: "Liquid sector and broad-market ETFs plus a short-treasury cash equivalent",
    dataSources: ETF_SOURCES,
    steps: [
      {
        number: "01", label: "DATA", title: "Read causal ETF prices",
        description:
          "Each weekly decision uses only prices available by that date. Momentum and volatility windows are shifted so that the return being predicted never appears in the features that predict it.",
        inputs: ["Adjusted weekly ETF closes"],
        formulaKey: "pointInTime",
        note: "1,127 weekly decisions from January 2005 to August 2026.",
      },
      {
        number: "02", label: "RETURNS", title: "Compute multi-horizon momentum",
        description:
          "For each fund, trailing returns are computed over 4, 13, 26 and 52 weeks. Using several horizons rather than one is a guard against picking whichever single lookback happened to work in the sample.",
        inputs: ["Fund price history"],
        formulaKey: "totalReturn",
        note: "Four horizons, all ending at or before the decision date.",
        example: {
          caption: "Worked example, one fund",
          rows: [
            { label: "Price 13 weeks ago", value: "$152.40" },
            { label: "Price today", value: "$175.35" },
            { label: "13-week return", value: "175.35 ÷ 152.40 − 1 = +15.06%" },
          ],
        },
      },
      {
        number: "03", label: "RANK", title: "Average the cross-sectional ranks",
        description:
          "Within each horizon every fund is ranked against the others, and the four ranks are averaged. Ranking rather than using raw returns keeps one extreme horizon from dominating the score.",
        inputs: ["Trailing returns at 4, 13, 26, 52 weeks"],
        formulaKey: "compositeRank",
        note: "A fund must be positive on the consensus to be eligible; otherwise the allocation moves to the cash equivalent.",
      },
      {
        number: "04", label: "CORE", title: "Hold the locked 60% technology core",
        description:
          "Sixty percent follows a source fixed before the holdout period: a technology-weighted core plus an embargoed allocator component. It is frozen precisely so that the dashboard cannot tune it after seeing results.",
        inputs: ["Locked core definition"],
        formulaKey: "blend",
        note: "The core was selected before the holdout window and has not been changed since.",
      },
      {
        number: "05", label: "COMBINE", title: "Blend the two sources without discretion",
        description: "The two complete weight vectors are combined at fixed 60/40 proportions. No manual overrides are applied anywhere in the dashboard.",
        inputs: ["Core weights", "Rank-consensus weights"],
        formulaKey: "blend",
        note: "If the rank source finds nothing positive, its 40% sits in the cash equivalent rather than being forced into a fund.",
      },
      executeStep("06"),
      costStep("07"),
      validateStep(
        "08",
        "Scores 40 of 100 and is the weakest of the six on this battery — but it is the only strategy with history through 2008 and 2020, and its −44.1% full-history drawdown is a real regime being measured rather than a regime never tested. Fails drawdown, rolling year, signal decay and concentration. Forward record 0 of 52.",
      ),
    ],
  },
};
