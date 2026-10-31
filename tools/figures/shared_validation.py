"""Fig. 5: validation work after one update as more agents use the same 16 definitions."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/figures"))
import mplstyle
import style

NAME = "shared-validation"
W, H = style.COLUMN, 46.0
POLICIES = [("per-agent", "mPrivate", "v", "--"), ("full-recheck", "mDef", "s", ":"), ("mavra", "mCond", "o", "-")]
TEXT = {
    "en": {"names": {"per-agent": "Per-agent validation", "full-recheck": "Shared, full recheck", "mavra": "MAVRA"},
           "panels": ["(a) Staggered arrivals", "(b) Simultaneous arrivals"], "x": "Agents after the update",
           "y": "Validation DB time (s)"},
    "zh": {"names": {"per-agent": "各智能体分别验证", "full-recheck": "共享，整定义重查", "mavra": "MAVRA"},
           "panels": ["(a) 交错到达", "(b) 同时到达"], "x": "更新后使用定义的智能体数", "y": "验证数据库耗时（秒）"},
}


def load():
    data = json.loads((ROOT / "exp/2026-11-01-shared-validation/stats.json").read_text())
    printed = style.macros("shared-validation")
    top = max(data["agents"])
    for arrival, tag in [("staggered", "Stag"), ("simultaneous", "Sim")]:
        for policy, ptag in [("per-agent", "Private"), ("full-recheck", "Full"), ("mavra", "Mavra")]:
            x = next(g for g in data["groups"] if g["policy"] == policy and g["arrival"] == arrival and g["agents"] == top)
            style.agree(f"Sv{tag}{ptag}DbS", f"{x['db_s']['median']:.1f}", printed[f"Sv{tag}{ptag}DbS"])
    return data


def figure(lang):
    t, data = TEXT[lang], load()
    fig = mplstyle.figure(W, H)
    axes = fig.subplots(1, 2, sharey=True)
    fig.subplots_adjust(left=.14, right=.98, top=.78, bottom=.25, wspace=.12)
    for col, arrival in enumerate(["staggered", "simultaneous"]):
        ax = axes[col]
        for policy, color, marker, line in POLICIES:
            pts = sorted((g for g in data["groups"] if g["policy"] == policy and g["arrival"] == arrival), key=lambda g: g["agents"])
            xs = [g["agents"] for g in pts]
            ys = [g["db_s"]["median"] for g in pts]
            err = [[y - g["db_s"]["min"] for y, g in zip(ys, pts)], [g["db_s"]["max"] - y for y, g in zip(ys, pts)]]
            ax.errorbar(xs, ys, yerr=err, color=style.PAPER_COLORS[color], marker=marker, ls=line, mfc="white", mew=.6,
                        ms=3.2, lw=.9, capsize=1.4, elinewidth=.5, label=t["names"][policy])
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks(data["agents"], [str(n) for n in data["agents"]])
        ax.minorticks_off()
        ax.tick_params(labelsize=6.5)
        ax.grid(axis="y", which="major")
        ax.set_title(t["panels"][col], fontsize=6.5)
        ax.set_xlabel(t["x"], fontsize=6.5)
    axes[0].set_ylabel(t["y"], fontsize=7)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.55, 1.0), ncol=3,
               handlelength=1.8, fontsize=6.5, columnspacing=.8)
    return fig


if __name__ == "__main__":
    for path in style.build(sys.modules[__name__]):
        print(path)
