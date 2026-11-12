"""Build the paper's vector figures into overleaf/figures/.

    python3 tools/figures/build.py                     # all paper figures
    python3 tools/figures/build.py population          # only named figures
    python3 tools/figures/build.py --out /tmp/preview  # custom output folder
"""
import argparse
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style  # noqa: E402

FIGURES = {
    'metric-record': 'metric_record',
    'architecture': 'architecture',
    'extraction': 'extraction',
    'lookup': 'lookup',
    'maintenance': 'maintenance',
    'relbench-cumulative': 'relbench_cumulative',
    'reuse-work': 'reuse_work',
    'population': 'population',
    'change-study': 'change_study',
    'shared-validation': 'shared_validation',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('names', nargs='*', metavar='name',
                        help=f'figures to build: {", ".join(FIGURES)} (default: all)')
    parser.add_argument('--out', type=Path, default=style.OUT)
    args = parser.parse_args()
    unknown = set(args.names) - set(FIGURES)
    if unknown:
        parser.error(f'unknown figure: {", ".join(sorted(unknown))}')
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.names or FIGURES:
        for path in style.build(importlib.import_module(FIGURES[name]), args.out):
            print(path)


if __name__ == '__main__':
    main()
