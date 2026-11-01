"""Fig. 4: agent tool calls per reuse session (RelBench official-API cohort, cutoffs 2-3).

Same data, categories, colours and hatching as exp/2026-10-29-fig45-official/build-figures.py
(figure-data.json, six reuse sessions per method and database, failures included); the two
databases are drawn side by side to fit one column at a lower height.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/figures"))
from matplotlib.patches import Patch
import mplstyle
import style

NAME = "reuse-work"
W, H = style.COLUMN, 37.8
METHODS = [("none", "No memory", "无记忆"), ("ace", "ACE", "ACE"), ("awm", "AWM", "AWM"),
           ("gmemory", "G-Memory", "G-Memory"), ("mavra", "MAVRA", "MAVRA")]
KINDS = [("schema", "Schema", "结构检查", "#B8CDE5", ""),
         ("probe", "SQL probes", "SQL 探查", "#E1B78D", "//"),
         ("validate", "Validation", "验证", "#8FBCA0", ".."),
         ("memory", "Memory tools", "记忆工具", "#B3A7C9", "xx"),
         ("submit", "Submission", "提交", "#D4D4D4", "\\\\")]
TEXT = {"en": {"y": "Agent tool calls per session", "panels": ["(a) rel-stack", "(b) rel-trial"]},
        "zh": {"y": "每个复用会话的工具调用数", "panels": ["(a) rel-stack", "(b) rel-trial"]}}


def figure(lang):
    work = json.loads((ROOT / "exp/2026-10-29-fig45-official/figure-data.json").read_text(encoding="utf-8"))["work"]
    fig = mplstyle.figure(W, H)
    axes = fig.subplots(1, 2, gridspec_kw=dict(left=.11, right=.99, top=.783, bottom=.230, wspace=.22))
    for ax, ds, title in zip(axes, ["rel-stack", "rel-trial"], TEXT[lang]["panels"]):
        bottom = [0.0] * len(METHODS)
        for key, en, zh, color, hatch in KINDS:
            ys = [work[ds][m[0]][key] for m in METHODS]
            ax.bar(range(len(METHODS)), ys, bottom=bottom, color=color, edgecolor="black", hatch=hatch, linewidth=.4, width=.66)
            bottom = [a + b for a, b in zip(bottom, ys)]
        ax.set_xticks(range(len(METHODS)), [m[1] if lang == "en" else m[2] for m in METHODS], rotation=35, ha="right",
                      rotation_mode="anchor", fontsize=6.2)
        ax.set_ylim(0, max(bottom) * 1.16)
        ax.tick_params(axis="y", labelsize=6.3)
        ax.yaxis.grid(True)
        ax.set_title(title, fontsize=7, pad=2)
        for i, v in enumerate(bottom):
            ax.text(i, v + max(bottom) * .015, f"{v:.1f}", ha="center", va="bottom", fontsize=6,
                    fontweight="bold" if METHODS[i][0] == "mavra" else "normal")
    axes[0].set_ylabel(TEXT[lang]["y"], fontsize=6.8)
    fig.legend(handles=[Patch(facecolor=c, edgecolor="black", hatch=h, linewidth=.4, label=en if lang == "en" else zh)
                        for _, en, zh, c, h in KINDS], loc="upper center", ncol=5, bbox_to_anchor=(.54, 1.0), fontsize=6.2,
               handlelength=1.3, columnspacing=.7)
    return fig


if __name__ == "__main__":
    for path in style.build(sys.modules[__name__]):
        print(path)
