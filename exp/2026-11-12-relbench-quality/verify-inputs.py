"""Recheck frozen data bytes and every candidate's data link, without decoding labels."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path


ROOTS = (
    '/root/agentdb-quality-20261112',
    '/root/agentdb-quality-portfolio-20261112',
    '/root/agentdb-quality-directed-20261112',
    '/root/agentdb-quality-cached-safe-20261112',
    '/root/agentdb-quality-signal-20261112',
    '/root/agentdb-quality-refine-20261112',
    '/root/agentdb-quality-early-20261112',
    '/root/agentdb-quality-delta-20261112',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.expected.read_bytes()
    expected = json.loads(raw)
    data = Path('/root/agentdb-mid/results/relbench-data').resolve(strict=True)
    mismatches = []
    files = 0
    for records in expected['datasets'].values():
        for relative, recorded in records.items():
            path = data / relative
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if path.stat().st_size != recorded['bytes'] or digest.hexdigest() != recorded['sha256']:
                mismatches.append(relative)
            files += 1
    links = {}
    for root in ROOTS:
        target = Path(root) / 'results/relbench-data'
        links[root] = {'resolved': str(target.resolve(strict=True)),
                       'matches_original': target.resolve(strict=True) == data}
    passed = not mismatches and all(row['matches_original'] for row in links.values())
    report = {
        'at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'purpose': 'input integrity only; no model selection or scoring',
        'held_out_labels_decoded': False,
        'expected_manifest_sha256': hashlib.sha256(raw).hexdigest(),
        'verified_files': files,
        'mismatches': mismatches,
        'candidate_data_links': links,
        'passed': passed,
    }
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': passed, 'files': files, 'candidate_links': len(links),
                      'mismatches': mismatches}))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
