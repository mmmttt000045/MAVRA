"""Fig. 6: answers after data changes, five methods on two schemas (exp/2026-11-01-change-study; TeCoD from
results/change-study-20261106-tecod, added 2026-11-06).

(a, b) correct answers above zero and wrong answers below it, per change group and schema; requests for
clarification are outlined segments on top of the correct answers. (c, d) cost per question, pooled over
both schemas: tokens (memory updates included) and session time.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/figures"))
from matplotlib import colors
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import mplstyle
import style

NAME = "change-study"
W, H = style.TEXTWIDTH, 39.0
ARMS = ["ace", "awm", "gmemory", "tecod", "mavra"]
GROUPS = ["holdout", "non_breaking", "covered_breaks", "outside_conditions"]
SCHEMAS = ["synthetic", "tpch"]
HATCHES = dict(zip(ARMS, ["////", r"\\", "xx", "++", "...."]))
LABEL = {"ace": "ACE", "awm": "AWM", "gmemory": "G-Memory", "tecod": "TeCoD", "mavra": "MAVRA"}
for key, color in zip(ARMS, ["mACE", "mAWM", "mGMem", "mTeCoD", "mCond"]):
    style.METHODS[key] = (LABEL[key], LABEL[key], color)
TAG = {"ace": "Ace", "awm": "Awm", "gmemory": "Gmem", "tecod": "Tecod", "mavra": "Mavra"}
GTAG = {"holdout": "Hold", "non_breaking": "Benign", "covered_breaks": "Break", "outside_conditions": "Outside"}
STAG = {"synthetic": "Syn", "tpch": "Tpch"}
TEXT = {
    "en": {"groups": ["Held-\nout", "Non-\nbreaking", "Covered\nbreaks", "Premise\nchanges"],
           "panels": ["(a) Answers, synthetic retail", "(b) Answers, TPC-H SF1", "(c) Tokens, both schemas",
                      "(d) Time, both schemas"],
           "up": "Correct", "down": "Wrong", "y": ["Answers (%)", "Tokens per question (k)", "Seconds per question"],
           "flag": "Asked for clarification"},
    "zh": {"groups": ["留出", "正常\n更新", "覆盖\n破坏", "前提\n变化"],
           "panels": ["(a) 作答，合成零售", "(b) 作答，TPC-H SF1", "(c) token，两种模式", "(d) 耗时，两种模式"],
           "up": "正确", "down": "错误", "y": ["作答（%）", "每题 token（千）", "每题耗时（秒）"], "flag": "请求澄清"},
}


def load():
    data = json.loads((ROOT / "exp/2026-11-01-change-study/study-stats.json").read_text(encoding="utf-8"))
    assert data["complete_runs"] and not data["problems"]
    printed = style.macros("change-study")
    for g in GROUPS:
        for ds in SCHEMAS:
            for arm in ARMS:
                row = data["groups"][g][ds][arm]
                assert len(row["per_run"]) == len(data.get("arm_runs", {}).get(arm, data["complete_runs"]))
                key = f"Cs{GTAG[g]}{STAG[ds]}{TAG[arm]}"
                style.agree(key, f"{row['accuracy']:.1f}", printed[key])
                style.agree(key + "Wrong", f"{row['wrong_pct']:.1f}", printed[key + "Wrong"])
        for arm in ARMS:
            row = data["groups"][g]["both"][arm]
            key = f"Cs{GTAG[g]}{TAG[arm]}"
            style.agree(key + "TokK", f"{row['tokens'] / 1000:.1f}", printed[key + "TokK"])
            style.agree(key + "S", f"{row['seconds']:.0f}", printed[key + "S"])
    return data


def darker(arm):
    rgb = colors.to_rgb(mplstyle.color(arm))
    return tuple(.62 * c + .08 for c in rgb)


def answers(ax, data, ds, t):
    width = .8 / len(ARMS)
    for mi, arm in enumerate(ARMS):
        rows = [data["groups"][g][ds][arm] for g in GROUPS]
        xs = [i + (mi - (len(ARMS) - 1) / 2) * width for i in range(len(GROUPS))]
        good = [r["accuracy"] for r in rows]
        bad = [r["wrong_pct"] for r in rows]
        ax.bar(xs, good, width=width, **mplstyle.bar_style(arm, HATCHES[arm]), zorder=2)
        # requests for clarification: neither correct nor wrong, outlined on top of the correct answers
        ax.bar(xs, [r["clarify_pct"] for r in rows], width=width, bottom=good, facecolor="white",
               edgecolor="black", lw=.4, ls=(0, (1.5, 1)), zorder=2)
        ax.bar(xs, [-b for b in bad], width=width, facecolor=darker(arm), edgecolor="black", lw=.5,
               hatch=HATCHES[arm], zorder=2)
        ax.errorbar(xs, good, yerr=[[v - r["min"] for v, r in zip(good, rows)], [r["max"] - v for v, r in zip(good, rows)]],
                    fmt="none", ecolor="black", elinewidth=.4, capsize=.7, capthick=.4, zorder=3)
        ax.errorbar(xs, [-b for b in bad], yerr=[[r["wrong_max"] - b for b, r in zip(bad, rows)],
                                                [b - r["wrong_min"] for b, r in zip(bad, rows)]],
                    fmt="none", ecolor="black", elinewidth=.4, capsize=.7, capthick=.4, zorder=3)
        for x, b in zip(xs, bad):
            if b == 0:
                ax.text(x, -1.5, "0", ha="center", va="top", fontsize=5.6, zorder=4)
    ax.axhline(0, color="black", lw=.6, zorder=3)
    ax.set(ylim=(-88, 106), yticks=[-75, -50, -25, 0, 25, 50, 75, 100])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{abs(v):.0f}"))


def cost(ax, data, field):
    width = .8 / len(ARMS)
    top = 0
    for mi, arm in enumerate(ARMS):
        rows = [data["groups"][g]["both"][arm] for g in GROUPS]
        xs = [i + (mi - (len(ARMS) - 1) / 2) * width for i in range(len(GROUPS))]
        if field == "tokens":
            values = [r["tokens"] / 1000 for r in rows]
        else:
            values = [r["seconds"] for r in rows]
            lo = [min(r["seconds_per_run"]) for r in rows]
            hi = [max(r["seconds_per_run"]) for r in rows]
            ax.errorbar(xs, values, yerr=[[v - a for v, a in zip(values, lo)], [b - v for v, b in zip(values, hi)]],
                        fmt="none", ecolor="black", elinewidth=.4, capsize=.7, capthick=.4, zorder=3)
            top = max(top, *hi)
        ax.bar(xs, values, width=width, **mplstyle.bar_style(arm, HATCHES[arm]), zorder=2)
        top = max(top, *values)
    ax.set_ylim(0, top * 1.1)


def figure(lang):
    t, data = TEXT[lang], load()
    fig = mplstyle.figure(W, H)
    axes = fig.subplots(1, 4, gridspec_kw=dict(left=.05, right=.995, top=.862, bottom=.24, wspace=.26))
    handles = [Patch(**mplstyle.bar_style(arm, HATCHES[arm]), label=LABEL[arm]) for arm in ARMS]
    handles.append(Patch(facecolor="white", edgecolor="black", lw=.4, ls=(0, (1.5, 1)), label=t["flag"]))
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.52, 1.0), ncol=6, handlelength=1.4,
               columnspacing=1.2, fontsize=7)
    for k, ax in enumerate(axes):
        if k < 2:
            answers(ax, data, SCHEMAS[k], t)
        else:
            cost(ax, data, "tokens" if k == 2 else "seconds")
        ax.set_xlim(-.55, len(GROUPS) - .45)
        ax.set_xticks(range(len(GROUPS)), t["groups"])
        ax.tick_params(axis="x", length=0, labelsize=6.3)
        ax.tick_params(axis="y", labelsize=6.3)
        ax.yaxis.grid(True)
        if k == 0:
            # split label: correct answers above the zero line, wrong answers below it
            zero = 88 / (88 + 106)
            for y, label in [((1 + zero) / 2, t["up"]), (zero / 2, t["down"])]:
                ax.text(-.2, y, label, transform=ax.transAxes, rotation=90, ha="center", va="center", fontsize=7)
        elif k > 1:
            ax.set_ylabel(t["y"][k - 1], fontsize=7)
        box = ax.get_position()
        fig.text((box.x0 + box.x1) / 2, .005, t["panels"][k], ha="center", va="bottom", fontsize=7.2)
    return fig


if __name__ == "__main__":
    for path in style.build(sys.modules[__name__]):
        print(path)
