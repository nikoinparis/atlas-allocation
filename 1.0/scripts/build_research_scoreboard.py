"""Build a living research scoreboard from known project branches."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "research"
DATA = ROOT / "data"
OUT_CSV = DATA / "research" / "research_scoreboard.csv"
OUT_MD = DOCS / "research_scoreboard.md"


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def doc_exists(name: str) -> str:
    path = DOCS / name
    return rel(path) if path.exists() else f"{rel(path)} (not found)"


def md_table(df: pd.DataFrame, columns: List[str], n: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df[[c for c in columns if c in df.columns]].head(n).copy()
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def row(
    phase_or_branch: str,
    candidate_or_idea: str,
    layer: str,
    category: str,
    status: str,
    main_question: str,
    what_worked: str,
    what_failed: str,
    best_metric_change: str,
    holdout_result: str,
    state_impact: str,
    turnover_or_cost_impact: str,
    hidden_beta_or_cash_issue: str,
    final_decision: str,
    reason_for_decision: str,
    reuse_later: str,
    next_action: str,
    source_doc: str,
) -> Dict[str, str]:
    return {
        "phase_or_branch": phase_or_branch,
        "candidate_or_idea": candidate_or_idea,
        "layer": layer,
        "category": category,
        "status": status,
        "main_question": main_question,
        "what_worked": what_worked,
        "what_failed": what_failed,
        "best_metric_change": best_metric_change,
        "holdout_result": holdout_result,
        "state_impact": state_impact,
        "turnover_or_cost_impact": turnover_or_cost_impact,
        "hidden_beta_or_cash_issue": hidden_beta_or_cash_issue,
        "final_decision": final_decision,
        "reason_for_decision": reason_for_decision,
        "reuse_later": reuse_later,
        "next_action": next_action,
        "source_doc": source_doc,
    }


def build_rows() -> List[Dict[str, str]]:
    return [
        row(
            "Phase 2B",
            "improved_phase2b_regime_confidence_boost / combo_abc",
            "Layer 3",
            "production baseline / shadow",
            "active reference",
            "Can regime confidence improve the base allocator?",
            "Became pinned production reference in registry; combo_abc remains important comparator.",
            "Later GGG dashboard candidate appears stronger on headline metrics.",
            "Phase2B Sharpe around 0.88 in exact comparator context.",
            "Useful but no longer best dashboard candidate.",
            "Production fallback behavior remains important in stressed states.",
            "Controlled turnover profile.",
            "No current hidden beta issue identified; compare against GGG mismatch explicitly.",
            "Keep as pinned comparator",
            "Registry still pins Phase2B while dashboard uses GGG candidate.",
            "Yes",
            "Always compare frontier candidates against Phase2B and GGG.",
            doc_exists("phase2b_dual_track_summary.md"),
        ),
        row(
            "GGG / Phaseggg",
            "improved_phaseggg_confirmed_only_robust_offense",
            "Layer 3",
            "dashboard candidate",
            "current research benchmark",
            "Can confirmed robust offense improve return without breaking defense?",
            "Exact reconstruction succeeded with net-return max error near 2.1e-16 and correlation 1.0000.",
            "Still below long-term 10% annual-return aspiration.",
            "Annual return about 7.14%, Sharpe about 0.94, max DD about -11.77%.",
            "Exact saved path validates the benchmark.",
            "Stressed_panic defense is the preservation constraint.",
            "One-way turnover/cost convention must be reused.",
            "Future improvements must not be hidden offense/beta increases.",
            "Use as official research baseline",
            "Exact-plumbing fidelity is now locked.",
            "Yes",
            "Use no-write wrapper for all deployment tests.",
            doc_exists("path1_rebuild_report.md"),
        ),
        row(
            "R1-R4",
            "Renaissance signal discovery foundation",
            "Layer 1",
            "signal research",
            "completed",
            "Can broader signal discovery find orthogonal candidates?",
            "Signal decay, state IC, R2 signal validation, and ETF pairs lab were completed.",
            "ETF pairs mostly failed weekly cointegration/half-life gates.",
            "Only r2_dollar_strength passed strict unconditional new-signal gate.",
            "Mixed; strong conditional macro but weak unconditional pass rate.",
            "Macro/VIX/credit useful in calm_trend but dangerous in stressed_panic.",
            "Not a turnover solution.",
            "No deployment yet.",
            "Research-only memory",
            "Signal discovery alone is not the bottleneck.",
            "Yes",
            "Use validated signals only through stabilized deployment harness.",
            doc_exists("renaissance_r1_r4_overnight_summary.md"),
        ),
        row(
            "Dollar Strength",
            "r2_dollar_strength / bm_dollar_strength_4w / blended",
            "Layer 1",
            "macro/cross-asset signal",
            "promising",
            "Does dollar pressure predict ETF allocation conditions?",
            "Only strict R2 pass; 4w and blended variants remained useful diagnostics.",
            "Needs deployment discipline; not a standalone production rule.",
            "Best as filter/pressure signal, not alpha claim.",
            "Useful enough for B6/B7/B8 and confidence inputs.",
            "Can help detect pressure for EM/commodity/offense exposure.",
            "Low turnover as filter.",
            "Must avoid simply reducing risk too often.",
            "Reuse as confidence input",
            "Works best as bounded filter in deployment architecture.",
            "Yes",
            "Keep in confidence and deterioration feature sets.",
            doc_exists("dollar_strength_deep_dive_report.md"),
        ),
        row(
            "Breadth + Macro",
            "ETF/sector breadth and state-gated macro",
            "Layer 1 / deployment diagnostics",
            "breadth / macro",
            "promising diagnostics",
            "Can breadth and macro improve calm_trend participation without harming stress?",
            "ETF breadth, sector breadth, risk-on participation, and gated macro showed real information.",
            "Naive pass-through did not beat GGG.",
            "Breadth looked promising at signal level but lost edge in naive portfolio plumbing.",
            "Mixed; not enough for deployment.",
            "Calm_trend useful, stressed_panic danger requires gating.",
            "Turnover not the bottleneck.",
            "Risk of lower-BIL/higher-offense illusion if deployed naively.",
            "Reuse through wrapper only",
            "Deployment location matters more than raw signal existence.",
            "Yes",
            "Test with allocator-native insertion points only.",
            doc_exists("breadth_macro_sprint_summary.md"),
        ),
        row(
            "B6",
            "Unified signal validation",
            "Layer 1 validation",
            "robustness validation",
            "completed",
            "Which breadth/macro/dollar candidates deserve pass-through?",
            "Separated candidates into pass-through, gate/filter, and reject buckets.",
            "Many candidates were conditional or redundant.",
            "Identified top breadth and dollar candidates for controlled tests.",
            "Not a portfolio proof.",
            "Helped classify stressed_panic dangers.",
            "No production turnover changes.",
            "No direct beta deployment.",
            "Research-only gating memory",
            "Narrowed candidate set before portfolio tests.",
            "Yes",
            "Use B6 table for future rule inputs.",
            doc_exists("b6_sprint_summary.md"),
        ),
        row(
            "B7/B8",
            "Controlled pass-through and bounded refinement",
            "Layer 3 sandbox",
            "deployment test",
            "negative result",
            "Do breadth/macro filters improve portfolio outcomes?",
            "Showed breadth/macro information is real but naive deployment fails.",
            "B7/B8 plumbing used wrong return/turnover convention versus exact GGG.",
            "Best B7 sector breadth gate still worsened Sharpe vs GGG.",
            "Failed to beat benchmark.",
            "Stressed_panic preservation was not enough to offset return drag.",
            "Sandbox cost/turnover convention mismatch polluted comparisons.",
            "Some variants risked cash/offense artifacts.",
            "Closed as naive-pass-through branch",
            "Deployment architecture, not raw signal discovery, became the bottleneck.",
            "Yes, as a warning",
            "Do not repeat post-hoc scaling without exact wrapper.",
            doc_exists("b8_sprint_summary.md"),
        ),
        row(
            "Path 1/3 + Native Confidence",
            "exact plumbing and confidence-aware deployment",
            "Layer 3 research architecture",
            "plumbing / confidence",
            "near miss",
            "Can exact GGG plumbing and confidence insertion improve deployment?",
            "Exact GGG reconstruction succeeded; confidence modifier nearly improved exact GGG.",
            "Native insertion did not pass strict improvement gate.",
            "Best confidence sandbox Sharpe around 0.9395 vs exact GGG around 0.9366; native variants near-missed.",
            "Promising but not enough.",
            "Stressed_panic roughly preserved.",
            "Correct one-way turnover convention locked.",
            "Must avoid hidden offense increase.",
            "Keep as architecture direction",
            "Correct insertion point is necessary but not sufficient.",
            "Yes",
            "Use stabilized wrapper for transition-quality frontier.",
            doc_exists("c7_native_confidence_sprint_summary.md"),
        ),
        row(
            "Stabilization",
            "no-write checkpoint wrapper and rule harness",
            "research infrastructure",
            "architecture",
            "completed",
            "Can future deployment tests be run cleanly and reproducibly?",
            "Wrapper reproduced exact GGG; rule harness ran standardized checks.",
            "Early checkpoint modifications are still final-weight proxies until deeper allocator hook exists.",
            "No-modifier max net-return error around 2.1e-16.",
            "Stable baseline.",
            "Architecture-valid rules preserved stressed_panic within gate.",
            "Turnover controlled in harness.",
            "Designed to expose hidden beta/cash checks.",
            "Use as mandatory framework",
            "Prevents B7/B8-style plumbing mistakes.",
            "Yes",
            "Run frontier tests only through wrapper/harness.",
            doc_exists("deployment_architecture_stabilization_summary.md"),
        ),
        row(
            "W1 / Structural Defense",
            "structural defense / W1 sizing family",
            "Layer 3",
            "defense architecture",
            "historical branch",
            "Can structural defense sizing improve drawdowns and state behavior?",
            "W/AA branches appear in project history and candidate files.",
            "Details require deeper parse of dated phase reports.",
            "Not automatically parsed in this starter scoreboard.",
            "Unknown in this pass.",
            "Likely stress-defense focused.",
            "Needs source-specific review.",
            "Potential lower-return/cash-drag risk.",
            "Diagnostic until reviewed",
            "Included to avoid research-memory loss.",
            "Maybe",
            "Parse W/AA reports in a future memory-cleanup sprint.",
            doc_exists("2026-04-25_phase_y_conditional_w1_sizing_report.md"),
        ),
        row(
            "Q-V / Trust / ML Allocator",
            "trust-aware and abstention meta-allocators",
            "ML / meta-allocation",
            "trust model",
            "plateaued",
            "Can ML/trust layers decide when to trust production vs ML experts?",
            "Q/R/S reports found useful trust concepts and bucket structure.",
            "Repeated holdout residuals and plateau; Phase S recommended stopping narrow trust refinement.",
            "Some holdout Sharpe improvements vs ML references, not enough for production.",
            "Mixed; branch plateaued.",
            "Trust buckets helped stressed_panic production fallback.",
            "Some turnover improvements, but not final gate.",
            "Complexity risk high.",
            "Do not revive without new hypothesis",
            "Three-sprint failure mode suggests pivot.",
            "Limited",
            "Use lessons, not the old branch itself.",
            doc_exists("2026-04-24_phase_s_targeted_trust_fix_report.md"),
        ),
        row(
            "ML Lab",
            "rankers, attention, decision-focused, RL, triple barrier",
            "ML research",
            "frontier ML",
            "defer",
            "Can advanced ML find allocation edge?",
            "Generated study artifacts and possible future frameworks.",
            "High overfitting risk before deployment architecture is fully mature.",
            "No production proof.",
            "Not ready.",
            "Unknown.",
            "Potentially high turnover/complexity.",
            "Major hidden complexity risk.",
            "Research-only",
            "Governance says frontier ML comes after simpler deployment architecture.",
            "Maybe later",
            "Only revisit after transition-quality wrapper tests.",
            doc_exists("ml_lab/phase_mlx_machine_learning_in_finance_study_guide.md"),
        ),
        row(
            "Pre-frontier Validation",
            "statistical validation, governance, scoreboard",
            "research infrastructure",
            "discipline layer",
            "new",
            "Can the project defend against overfitting and research-memory mistakes?",
            "Adds PSR/DSR proxy, purged CV utilities, PBO proxy, governance, and scoreboard.",
            "Approximations depend on available logged trials.",
            "No performance target; infrastructure only.",
            "N/A.",
            "N/A.",
            "N/A.",
            "Designed to flag hidden beta/cash issues.",
            "Mandatory for frontier phase",
            "Raises evidence standard before bigger ideas.",
            "Yes",
            "Use in every frontier sprint summary.",
            doc_exists("statistical_validation_layer.md"),
        ),
    ]


def write_report(df: pd.DataFrame) -> None:
    successes = df[df["final_decision"].str.contains("Use|Keep|Mandatory", case=False, na=False)]
    negative = df[df["status"].str.contains("negative|plateaued|defer", case=False, na=False)]
    open_rows = df[df["reuse_later"].str.contains("Yes|Maybe", case=False, na=False)]
    avoid = df[df["next_action"].str.contains("Do not|Delay|Only revisit|avoid|not repeat", case=False, na=False)]
    lines = [
        "# Research Scoreboard",
        "",
        "Living starter scoreboard for major research branches. Some rows are manually curated from known reports because project history is spread across many dated documents.",
        "",
        "## Top Successful Ideas",
        "",
        md_table(successes, ["phase_or_branch", "candidate_or_idea", "what_worked", "final_decision", "source_doc"], 12),
        "",
        "## Useful Negative Results",
        "",
        md_table(negative, ["phase_or_branch", "candidate_or_idea", "what_failed", "reason_for_decision", "next_action", "source_doc"], 12),
        "",
        "## Open Branches",
        "",
        md_table(open_rows, ["phase_or_branch", "candidate_or_idea", "status", "reuse_later", "next_action"], 20),
        "",
        "## Ideas To Avoid Repeating Blindly",
        "",
        md_table(avoid, ["phase_or_branch", "candidate_or_idea", "reason_for_decision", "next_action"], 20),
        "",
        "## Notes",
        "",
        "- This is a curated starter scoreboard, not a perfect automatic parser.",
        "- Future sprints should append or regenerate rows when a branch is closed.",
        "- The goal is research memory: what worked, what failed, and why.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(build_rows())
    df.to_csv(OUT_CSV, index=False)
    write_report(df)
    print(f"Wrote {rel(OUT_CSV)} rows={len(df)}")
    print(f"Wrote {rel(OUT_MD)}")


if __name__ == "__main__":
    main()
