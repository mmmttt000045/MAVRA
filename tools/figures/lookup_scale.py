"""Empirical lookup scaling (26 to 1,000 definitions) and selective risk-coverage (Section 6.3, P1-1).

Two side-by-side panels (single column, 84.6 mm wide):
  (a) Set-exact accuracy across nested catalogs |M| in {26, 100, 500, 1,000} over 390 multi-style requests
      (96 human original + 174 unseen GLM rewrites + 120 multi-domain scale queries).
  (b) Selective wrong-match risk vs. autonomous (zero-LLM) coverage at |M| = 1,000, sweeping uncertainty thresholds.
Data: revision v3 (exp/2026-11-17-lookup-scale/analyse_v3.py -> scale-summary-v3.json, risk-coverage-v3.json).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/figures"))
import mplstyle  # noqa: E402
import style  # noqa: E402

NAME = "lookup-scale"
W, H = style.COLUMN, 43.0
SCALES = ["26", "100", "500", "1000"]
X_POS = [0, 1, 2, 3]


def load():
    summ = json.loads((ROOT / "exp/2026-11-17-lookup-scale/scale-summary-v3.json").read_text(encoding="utf-8"))
    rc = json.loads((ROOT / "exp/2026-11-17-lookup-scale/risk-coverage-v3.json").read_text(encoding="utf-8"))
    printed = style.macros("lookup-scale")
    # Verify key endpoints against overleaf/gen/lookup-scale.tex
    style.agree(
        "LsMavRefFinalKAll",
        f"{100.0 * summ['mavra_confirmed']['mavra_refreshed']['1000']['all_390']['final_exact_rate']:.1f}",
        printed["LsMavRefFinalKAll"],
    )
    style.agree(
        "LsMavZeroFinalKAll",
        f"{100.0 * summ['mavra_confirmed']['mavra_zero']['1000']['all_390']['final_exact_rate']:.1f}",
        printed["LsMavZeroFinalKAll"],
    )
    style.agree(
        "LsTopLlmKAll",
        f"{100.0 * summ['top8_llm_judge']['1000']['all_390']['exact_rate']:.1f}",
        printed["LsTopLlmKAll"],
    )
    return summ, rc


def figure(lang):
    summ, rc = load()
    fig = mplstyle.figure(W, H)
    ax_a, ax_b = fig.subplots(1, 2, gridspec_kw=dict(left=0.115, right=0.99, top=0.77, bottom=0.22, wspace=0.32))

    c_mavra = style.PAPER_COLORS["mCond"]
    c_zero = "#2B6CB0"
    c_llm = "#333333"
    c_sce = "#D55E00"
    c_emb = style.PAPER_COLORS["mTraj"]
    c_tecod = style.PAPER_COLORS["mTeCoD"]

    # Panel (a): Accuracy vs Catalog Size |M| on all_390
    qset = "all_390"
    rec8 = [100.0 * summ["recall_bge_m3"][s][qset]["recall@8_all"] for s in SCALES]
    rec8t = [100.0 * summ["recall_tuned_v3"][s][qset]["recall@8_all"] for s in SCALES]
    mav_ref = [100.0 * summ["mavra_confirmed"]["mavra_refreshed"][s][qset]["final_exact_rate"] for s in SCALES]
    mav_zero = [100.0 * summ["mavra_confirmed"]["mavra_zero"][s][qset]["final_exact_rate"] for s in SCALES]
    top_llm = [100.0 * summ["top8_llm_judge"][s][qset]["exact_rate"] for s in SCALES]
    sce_key = "single_ce_refreshed"
    sce = [100.0 * summ[sce_key][s][qset]["no_abstain_exact_rate"] for s in SCALES] if sce_key in summ else None
    emb = [100.0 * summ["emb_top1"][s][qset]["oracle_exact_rate"] for s in SCALES]
    tecod = [100.0 * summ["tecod_nli_gpu"][s][qset]["exact_rate"] for s in SCALES]

    ax_a.plot(X_POS, rec8t, ls=":", lw=0.9, color="#4A4A4A", label="Recall@8 (tuned)")
    ax_a.plot(X_POS, rec8, ls=":", lw=0.8, color="#A0A0A0", label="Recall@8 (raw)")
    ax_a.plot(X_POS, mav_ref, marker="o", lw=1.2, ms=3.5, color=c_mavra, label="MAVRA (refreshed)")
    ax_a.plot(X_POS, mav_zero, marker="s", ls="--", lw=1.0, ms=3.0, color=c_zero, label="MAVRA (0-retrain)")
    ax_a.plot(X_POS, top_llm, marker="^", ls="-.", lw=0.95, ms=3.2, color=c_llm, label="Top-8 + LLM")
    if sce:
        ax_a.plot(X_POS, sce, marker="D", ls="-", lw=0.95, ms=2.9, color=c_sce, label="CE w/o diffs")
    ax_a.plot(X_POS, emb, marker="v", ls="--", lw=0.9, ms=3.0, color=c_emb, label="Embed. top-1")
    ax_a.plot(X_POS, tecod, marker="x", ls=":", lw=0.95, ms=3.4, color=c_tecod, label="TeCoD NLI")

    ax_a.set_xticks(X_POS, ["26", "100", "500", "1k"])
    ax_a.set_xlim(-0.2, 3.2)
    ax_a.set_ylim(15, 104)
    ax_a.set_yticks([20, 40, 60, 80, 100])
    ax_a.set_ylabel("Exact match (%)", fontsize=7.0)
    ax_a.set_xlabel("(a) Catalog size $|\\mathcal{M}|$", fontsize=7.0, labelpad=2.5)
    ax_a.tick_params(labelsize=6.5)
    ax_a.yaxis.grid(True)

    # Panel (b): Selective Wrong-Match Risk vs Autonomous Coverage at |M| = 1,000
    rc_k = rc["1000"]

    def plot_rc(fam_key, color, ls, marker, label, mark_default=False):
        if fam_key not in rc_k:
            return
        pts = rc_k[fam_key][qset]
        # Keep non-decreasing coverage envelope for clean visual curve
        xs = [100.0 * p["coverage"] for p in pts]
        ys = [100.0 * p["selective_risk"] for p in pts]
        step_idx = [0, 5, 10, 15, len(pts) - 1] if len(pts) >= 20 else list(range(0, len(pts), max(1, len(pts) // 5)))
        ax_b.plot(xs, ys, ls=ls, lw=1.05 if "mavra" in fam_key else 0.9, color=color)
        ax_b.plot([xs[i] for i in step_idx], [ys[i] for i in step_idx], ls="none", marker=marker, ms=3.0, color=color)
        if mark_default and len(pts) >= 11:
            ax_b.scatter([xs[10]], [ys[10]], marker="*", s=34, color=color, edgecolor="black", linewidth=0.35, zorder=5)

    plot_rc("mavra_refreshed", c_mavra, "-", "o", "MAVRA (refreshed)", mark_default=True)
    plot_rc("mavra_zero", c_zero, "--", "s", "MAVRA (0-retrain)", mark_default=True)
    plot_rc(sce_key, c_sce, "-", "D", "Single CE (no diff)")
    plot_rc("emb_top1", c_emb, "--", "v", "Embed. top-1")
    plot_rc("tecod_nli", c_tecod, ":", "x", "TeCoD NLI")

    ax_b.set_xlim(20, 103)
    ax_b.set_ylim(-2, 86)
    ax_b.set_xticks([25, 50, 75, 100])
    ax_b.set_yticks([0, 20, 40, 60, 80])
    ax_b.set_ylabel("Wrong-match risk (%)", fontsize=7.0, labelpad=1.5)
    ax_b.set_xlabel("(b) Direct coverage (%, $|\\mathcal{M}|{=}1\\text{k}$)", fontsize=7.0, labelpad=2.5)
    ax_b.tick_params(labelsize=6.5)
    ax_b.yaxis.grid(True)

    handles, labels = ax_a.get_legend_handles_labels()
    fig.legend(
        handles=handles,
        labels=labels,
        loc="upper center",
        bbox_to_anchor=(0.51, 1.0),
        ncol=4,
        fontsize=6.1,
        handlelength=1.45,
        columnspacing=0.75,
        handletextpad=0.35,
    )
    return fig


if __name__ == "__main__":
    for path in style.build(sys.modules[__name__]):
        print(path)
