"""Fig. 6: accuracy after data changes, four memory methods on two schemas (exp/2026-11-01-change-study)."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/figures"))
from matplotlib.patches import Patch
import mplstyle
import style

NAME = "change-study"
W, H = style.TEXTWIDTH, 50.0
ARMS = ["ace", "awm", "gmemory", "mavra"]
GROUPS = ["non_breaking", "covered_breaks", "outside_conditions", "all"]
SCHEMAS = ["synthetic", "tpch"]
HATCHES = dict(zip(ARMS, ["////", r"\\", "xx", "...."]))
LABEL = {"ace": "ACE", "awm": "AWM", "gmemory": "G-Memory", "mavra": "MAVRA"}
for key, color in zip(ARMS, ["mACE", "mAWM", "mGMem", "mCond"]):
    style.METHODS[key] = (LABEL[key], LABEL[key], color)
TAG = {"ace": "Ace", "awm": "Awm", "gmemory": "Gmem", "mavra": "Mavra"}
GTAG = {"non_breaking": "Benign", "covered_breaks": "Break", "outside_conditions": "Outside", "all": "All"}
STAG = {"synthetic": "Syn", "tpch": "Tpch"}
TEXT = {
    "en": {"groups": ["Non-\nbreaking", "Covered\nbreaks", "Outside\nconditions", "All\nsettings"],
           "panels": ["(a) Accuracy, synthetic retail", "(b) Accuracy, TPC-H SF1", "(c) Tokens, synthetic retail",
                      "(d) Tokens, TPC-H SF1"],
           "y": ["Correct (%)", "Tokens per question (k)"], "flag": "Asked for clarification"},
    "zh": {"groups": ["正常\n更新", "覆盖\n变化", "条件\n之外", "全部\n情形"],
           "panels": ["(a) 正确率，合成零售", "(b) 正确率，TPC-H SF1", "(c) token，合成零售", "(d) token，TPC-H SF1"],
           "y": ["正确（%）", "每题 token（千）"], "flag": "请求澄清"},
}


def load():
    data = json.loads((ROOT / "exp/2026-11-01-change-study/study-stats.json").read_text(encoding="utf-8"))
    assert data["complete_runs"] and not data["problems"]
    printed = style.macros("change-study")
    for g in GROUPS:
        for ds in SCHEMAS:
            for arm in ARMS:
                row = data["groups"][g][ds][arm]
                assert len(row["per_run"]) == len(data["complete_runs"])
                style.agree(f"Cs{GTAG[g]}{STAG[ds]}{TAG[arm]}", f"{row['accuracy']:.1f}", printed[f"Cs{GTAG[g]}{STAG[ds]}{TAG[arm]}"])
    return data


def figure(lang):
    t, data = TEXT[lang], load()
    fig = mplstyle.figure(W, H)
    axes = fig.subplots(1, 4, gridspec_kw=dict(left=.055, right=.995, top=.84, bottom=.27, wspace=.30))
    handles = [Patch(**mplstyle.bar_style(arm, HATCHES[arm]), label=LABEL[arm]) for arm in ARMS]
    handles.append(Patch(facecolor="white", edgecolor="black", lw=.4, ls=(0, (1.5, 1)), label=t["flag"]))
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.52, 1.0), ncol=5, handlelength=1.4,
               columnspacing=1.2, fontsize=7)
    runs = len(data["complete_runs"])
    width = .8 / len(ARMS)
    for k, ax in enumerate(axes):
        ds, cost = SCHEMAS[k % 2], k >= 2
        top = 0
        for mi, arm in enumerate(ARMS):
            rows = [data["groups"][g][ds][arm] for g in GROUPS]
            xs = [i + (mi - (len(ARMS) - 1) / 2) * width for i in range(len(GROUPS))]
            if cost:
                values = [r["tokens"] / 1000 for r in rows]
                ax.bar(xs, values, width=width, **mplstyle.bar_style(arm, HATCHES[arm]), zorder=2)
                top = max(top, *values)
                continue
            values = [r["accuracy"] for r in rows]
            ax.bar(xs, values, width=width, **mplstyle.bar_style(arm, HATCHES[arm]), zorder=2)
            # requests for clarification, stacked as an outlined segment: flagged rather than answered wrongly
            ax.bar(xs, [r["clarify_pct"] for r in rows], width=width, bottom=values, facecolor="white",
                   edgecolor="black", lw=.4, ls=(0, (1.5, 1)), zorder=2)
            for x, value in zip(xs, values):
                if value == 0:
                    ax.text(x, 1.5, "0", ha="center", va="bottom", fontsize=6, zorder=4)
            if runs > 1:
                ax.errorbar(xs, values, yerr=[[v - r["min"] for v, r in zip(values, rows)],
                                              [r["max"] - v for v, r in zip(values, rows)]],
                            fmt="none", ecolor="black", elinewidth=.4, capsize=.7, capthick=.4, zorder=3)
        if cost:
            ax.set_ylim(0, top * 1.12)
        else:
            ax.set(ylim=(0, 105), yticks=[0, 25, 50, 75, 100])
        ax.set_xlim(-.55, len(GROUPS) - .45)
        ax.set_xticks(range(len(GROUPS)), t["groups"])
        ax.tick_params(axis="x", length=0, labelsize=6.3)
        ax.yaxis.grid(True)
        if k in (0, 2):
            ax.set_ylabel(t["y"][k // 2], fontsize=7)
        box = ax.get_position()
        fig.text((box.x0 + box.x1) / 2, .02, t["panels"][k], ha="center", va="bottom", fontsize=7.2)
    return fig


if __name__ == "__main__":
    for path in style.build(sys.modules[__name__]):
        print(path)
