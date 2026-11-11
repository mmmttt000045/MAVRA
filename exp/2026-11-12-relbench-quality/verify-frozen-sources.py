"""Read-only verification of source and executable bytes during the study."""
import hashlib
import json
from pathlib import Path

roots = [Path('/root/agentdb-quality-20261112/results/quality-20261112-v1'),
         Path('/root/agentdb-quality-portfolio-20261112/results/quality-20261112-v2'),
         Path('/root/agentdb-quality-directed-20261112/results/quality-20261112-v3b'),
         Path('/root/agentdb-quality-cached-safe-20261112/results/quality-20261112-v4b'),
         Path('/root/agentdb-quality-signal-20261112/results/quality-20261112-v5')]
report = {}
for output in roots:
    manifest = json.loads((output/'source-sha256.json').read_text())
    source = output.parent.parent
    checked = {}
    for relative, expected in manifest.items():
        current = source / ('target/release/agentdb-mid' if relative == 'binary' else relative)
        digest = hashlib.sha256(current.read_bytes()).hexdigest()
        checked[relative] = digest == expected
        if relative != 'binary':
            frozen = hashlib.sha256((output/'frozen-source'/relative).read_bytes()).hexdigest()
            checked[relative] = checked[relative] and frozen == expected
    report[output.name] = {'passed':all(checked.values()),'files':checked}
print(json.dumps(report,indent=2))
if not all(r['passed'] for r in report.values()):
    raise SystemExit('A frozen study input changed; do not accept its result.')
