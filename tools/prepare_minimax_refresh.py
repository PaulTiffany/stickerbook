"""Inventory and back up manifest-owned sprites; never modify runtime assets."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
SOURCE = ROOT / 'web/static/assets/manifest.json'
STYLE = ('Create a 2x2 sheet of four separate sticker illustrations, one per cell, '
         'with generous clear margins and no overlap or text. Cohesive colorful '
         'child-friendly polished storybook style, clean silhouettes readable at '
         'small sizes. Plain removable white background. Preserve each subject '
         'and its specified pose; people must retain recognizable likenesses.')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backup(path):
    destination = ASSETS / '_backup_pre_minimax_refresh' / path.relative_to(ROOT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if digest(destination) != digest(path):
            raise RuntimeError(f'Refusing to overwrite differing backup: {destination}')
    else:
        shutil.copy2(path, destination)
    return destination.relative_to(ROOT).as_posix()


def main():
    manifest_path = ASSETS / 'minimax_refresh_manifest.json'
    if manifest_path.exists():
        raise SystemExit('Refresh manifest already exists; preserve recorded progress.')
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    families = {}
    for identifier, definition in source['stickers'].items():
        category = definition.get('category', 'other')
        family = {'plants': 'nature', 'weather': 'nature',
                  'vehicles': 'objects'}.get(category, category)
        families.setdefault(family, []).append(identifier)
    entries, sheets = [], []
    for family, identifiers in families.items():
        for group_index in range(0, len(identifiers), 4):
            group = identifiers[group_index:group_index + 4]
            # Separate sheets per pose ordinal retain every existing clip frame.
            frame_count = max(len(source['stickers'][i]['sprites']) for i in group)
            for pose_index in range(frame_count):
                sheet_id = f'{family}_{group_index // 4 + 1:02d}_pose_{pose_index + 1:02d}'
                cells = []
                for cell, identifier in enumerate(group):
                    definition = source['stickers'][identifier]
                    sprites = list(definition['sprites'].items())
                    if pose_index >= len(sprites):
                        continue
                    pose, relative = sprites[pose_index]
                    path = ROOT / 'web' / relative
                    cells.append({'cell': cell, 'asset': identifier, 'pose': pose,
                                  'name': definition['name']})
                    entries.append({
                        'asset': identifier, 'pose': pose, 'family': family,
                        'original_path': path.relative_to(ROOT).as_posix(),
                        'backup_path': backup(path), 'original_sha256': digest(path),
                        'generated_sheet_path': f'assets/_generated_minimax_refresh/sheets/{sheet_id}.png',
                        'cropped_output_path': f'assets/_generated_minimax_refresh/cropped/{identifier}/{pose}.png',
                        'sheet_id': sheet_id, 'cell': cell,
                        'generation_settings': {'provider': 'sponsored MiniMax (unverified image lane)',
                                                'model': None, 'endpoint': None,
                                                'layout': '2x2', 'background': 'removable white'},
                        'replacement_succeeded': False, 'status': 'awaiting-provider-configuration',
                        'notes': 'Original remains active; preserve clip frame identity and rendering bounds.'})
                prompt = STYLE + ' Subjects, in top-left, top-right, bottom-left, bottom-right order: ' + '; '.join(
                    f"{c['name']} ({c['asset']}), pose: {c['pose']}" for c in cells)
                if len(cells) < 4:
                    prompt += '; leave unused cells blank.'
                sheets.append({'id': sheet_id, 'family': family, 'cells': cells, 'prompt': prompt})
                for entry in entries:
                    if entry['sheet_id'] == sheet_id:
                        entry['prompt'] = prompt
    for directory in ['sheets', 'cropped']:
        (ASSETS / '_generated_minimax_refresh' / directory).mkdir(parents=True, exist_ok=True)
    result = {'version': 1, 'source_manifest': SOURCE.relative_to(ROOT).as_posix(),
              'source_manifest_backup': backup(SOURCE),
              'status': 'prepared-not-generated',
              'stickers': len(source['stickers']), 'sprite_files': len(entries),
              'backgrounds': {'status': 'excluded', 'pages': source['pages'], 'cover': source['cover']},
              'sheets': sheets, 'assets': entries}
    manifest_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'stickers': result['stickers'], 'sprites_backed_up': len(entries),
                      'planned_sheets': len(sheets), 'active_assets_changed': 0}))


if __name__ == '__main__':
    main()
