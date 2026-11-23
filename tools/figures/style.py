"""Shared look, method names, and data checks for the paper's figures.

Figures that plot experiment data read the archived JSON in exp/ and compare
every plotted endpoint against generated macros in results/gen/ (falling back
to reference_macros.json when results/gen/<name>.tex has not been generated yet);
a mismatch stops the build.
"""
import json
import re
from pathlib import Path

from vecfig import Sheet

ROOT = Path(__file__).resolve().parents[2]
GEN_DIR = ROOT / 'results' / 'gen'
OUT = ROOT / 'results' / 'figures'
REF_MACROS = Path(__file__).with_name('reference_macros.json')

COLUMN, TEXTWIDTH = 84.6, 178.0        # acmart sigconf widths, mm

PAPER_COLORS = {
    'mCond': '#2F4F9F',
    'mDef': '#B8B8B8',
    'mRevoke': '#1F8FB0',
    'mSchema': '#E3643A',
    'mUnguarded': '#E87BA4',
    'mNoShare': '#9C5A26',
    'mScope': '#A9740A',
    'mCache': '#3A3A3A',
    'mTraj': '#00A087',
    'mTrajVerify': '#66C2AE',
    'mCondGold': '#9DB3E4',
    'mCondCur': '#5F86D6',
    'mTable': '#8E5BB0',
    'mPrivate': '#E6A01E',
    'mACE': '#E6A01E',
    'mGMem': '#00A087',
    'mAWM': '#E87BA4',
    'mTeCoD': '#8E5BB0',
    'mFeatPilot': '#A9740A',
    'inkmuted': '#52514E',
    'gridline': '#DDDCD8',
}

# Drawing inks shared by all figures.
INK, MUTED, RULE = '#2B2A28', '#6B6A66', '#D3D0CA'
EDGE, FACE, SIDE, TOP = '#8E8B85', '#F6F5F2', '#DCD9D3', '#ECEAE5'
# Schematic figures (1, 2) keep their own MAVRA blue; experiment figures use the method colors above.
ACC, ACC_DK, ACC_PALE, FIELD = '#2A78D6', '#1D5BA6', '#E3EEFB', '#F1F6FC'
SLATE, AMBER, AMBER_PALE = '#5E6E82', '#C98600', '#FBEFD3'
RED, WHITE = '#C2412E', '#FFFFFF'
ORANGE, ORANGE_PALE = '#EB6834', '#FCE8DF'
GRID = PAPER_COLORS['gridline']

# Experiment figures (3-7), besides the method colors: one dark red for wrong answers and stale definitions, one light
# navy tint behind MAVRA's row and emphasized setting groups, and neutral grays for the other outcomes.
WRONG, FOCUS = '#B2182B', '#EBEEF6'
OUT_CORRECT, OUT_NEEDED, OUT_UNNEEDED = '#4A4A4A', '#A6A6A6', '#D9D9D9'

# Experiment method key -> (English, Chinese, color name), as in Table 2.
METHODS = {
    'middle': ('No memory', 'No memory', 'mNoShare'),
    'middle-alone': ('No memory', 'No memory', 'mNoShare'),
    'traj-global': ('Example retrieval', 'Example retrieval', 'mTraj'),
    'traj-verify': ('Example retrieval + self-verification', 'Example retrieval + self-verification', 'mTrajVerify'),
    'metric-global-noguard': ('Never revalidated', 'Never revalidated', 'mUnguarded'),
    'metric-global-schema': ('Invalidate on schema change', 'Invalidate on schema change', 'mSchema'),
    'metric-global-revoke': ('Invalidate on every write', 'Invalidate on every write', 'mRevoke'),
    'metric-global-def': ('Full recheck per definition', 'Full recheck per definition', 'mDef'),
    'metric-global-snap': ('MAVRA (ours)', 'MAVRA (ours)', 'mCond'),
    'metric-private': ('Single-agent memory', 'Single-agent memory', 'mPrivate'),
    'mem-awm': ('AWM', 'AWM', 'mPrivate'),
    'mem-ace': ('ACE', 'ACE', 'mPrivate'),
    'mem-mem0': ('Mem0', 'Mem0', 'mPrivate'),
    'mem-reasoningbank': ('ReasoningBank', 'ReasoningBank', 'mPrivate'),
    'mem-apc': ('APC', 'APC', 'mPrivate'),
    'mem-ace-shared': ('ACE, shared', 'ACE, shared', 'mTraj'),
    'mem-apc-shared': ('APC, shared', 'APC, shared', 'mTraj'),
    'metric-global-exref': ('MAVRA, regression on current data', 'MAVRA, regression on current data', 'mCondCur'),
    'metric-global': ('MAVRA, gold-SQL reference', 'MAVRA, gold-SQL reference', 'mCondGold'),
    'tabletest': ('dbt-style table tests', 'dbt-style table tests', 'mTable'),
    'definition': ('Full recheck per definition', 'Full recheck per definition', 'mDef'),
    'definition-cache': ('Full recheck + query cache', 'Full recheck + query cache', 'mCache'),
    'condition-scope': ('Recheck changed tables only', 'Recheck changed tables only', 'mScope'),
    'condition': ('MAVRA (ours)', 'MAVRA (ours)', 'mCond'),
    'condition-current': ('MAVRA, regression on current data', 'MAVRA, regression on current data', 'mCondCur'),
}


def method(key, lang):
    en, zh, color = METHODS[key]
    return (en if lang == 'en' else zh), PAPER_COLORS[color]


def macros(name):
    """\\newcommand / \\renewcommand values of results/gen/<name>.tex (or reference_macros.json) as strings."""
    tex_path = GEN_DIR / f'{name}.tex'
    if tex_path.exists():
        text = tex_path.read_text(encoding='utf-8')
        return dict(re.findall(r'\\(?:re)?newcommand\{\\(\w+)\}\{((?:[^{}]|\{[^{}]*\})*)\}', text))
    ref = json.loads(REF_MACROS.read_text(encoding='utf-8'))
    if name not in ref:
        raise KeyError(f'No generated {tex_path} and no entry {name!r} in {REF_MACROS}')
    return dict(ref[name])


def agree(what, shown, printed):
    """Stop when a plotted value, formatted as the text prints it, differs."""
    if shown != printed:
        raise SystemExit(f'{what}: figure data gives {shown}, expected {printed}')


def build(figure, out=OUT):
    """Write <name>.pdf for a figure module into `out`."""
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for lang, suffix in (('en', ''),):
        if lang not in getattr(figure, 'LANGS', ('en',)):
            continue
        path = out_dir / f'{figure.NAME}{suffix}.pdf'
        if hasattr(figure, 'figure'):
            import mplstyle
            mplstyle.setup(lang)
            mplstyle.save(figure.figure(lang), path)
        else:
            sheet = Sheet(path, figure.W, figure.H)
            figure.draw(sheet, lang)
            sheet.save()
        paths.append(path)
    return paths
