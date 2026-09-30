"""Check submission links, artwork, frozen evidence hashes and source status.

Standard library only. Does not regenerate evidence, call a provider, start
Docker, or claim that byte separation establishes perceptual discriminability.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper/cross_modal_witnesses'


def main():
    files = [ROOT / 'README.md', ROOT / 'SECURITY.md',
             *sorted((ROOT / 'docs').glob('*.md')),
             *sorted((ROOT / 'paper').rglob('*.md')),
             ROOT / 'web/README.md', ROOT / 'runtime/README.md']
    count = 0
    for path in files:
        text = path.read_text(encoding='utf-8')
        targets = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text)
        targets += re.findall(r'<img[^>]+src="([^"]+)"', text)
        for target in targets:
            if target.startswith(('http:', 'https:', '#', 'mailto:')):
                continue
            target = target.split('#')[0].strip('<>')
            if target:
                assert (path.parent / target).exists(), f'{path}: missing {target}'
                count += 1
    tex = (PAPER / 'main.tex').read_text(encoding='utf-8')
    assert r'\date{September 30, 2026}' in tex and 'This draft' not in tex
    assert 'upstream OpenShell/WSL deployment issue remains unresolved' in tex
    assert 'made with support from' in tex and 'https://bgicommons.org/teams/62' in tex
    assert (PAPER / 'main.pdf').read_bytes().startswith(b'%PDF-')

    verified = 0
    experiment = PAPER / 'experiment'
    for manifest in [experiment / 'stimulus_manifest.json',
                     experiment / 'runtime_evidence/manifest.json']:
        records = json.loads(manifest.read_text(encoding='utf-8'))['items']
        for item in records:
            for kind in ['visual', 'sonic', 'trace']:
                field = kind + '_file'
                if field not in item:
                    continue
                path = experiment / item[field].replace('\\', '/')
                assert hashlib.sha256(path.read_bytes()).hexdigest() == item[kind + '_sha256'], path
                verified += 1
            if 'fixture_sha256' in item:
                path = experiment / 'fixtures' / (item['trace_id'] + '.json')
                assert hashlib.sha256(path.read_bytes()).hexdigest() == item['fixture_sha256'], path
                verified += 1
    for validator in ['validate_fixtures.py', 'validate_runtime_evidence.py']:
        subprocess.run([sys.executable, str(experiment / validator)], check=True)
    help_data = json.loads((ROOT / 'web/static/help.json').read_text(encoding='utf-8'))
    assert any(t['id'] == 'grown-up' for t in help_data['child']['topics'])
    assert any(s['id'] == 'supervision' for s in help_data['adult']['sections'])
    print(f'Checked {len(files)} documents, {count} local links/images, {verified} frozen evidence hashes, and submission disclosures.')


if __name__ == '__main__':
    main()
