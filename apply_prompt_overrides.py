import csv
import json
from pathlib import Path

PROMPT_JSON = Path('prompt_ric_override_input.json')
OVERRIDE_CSV = Path('ric_overrides.csv')
UNRESOLVED_CSV = Path('prompt_ric_unresolved.csv')

VALID_STATUSES = {
    'verified',
    'trusted_unverified',
    'best_guess',
    'unverified_rule',
}

NOTE_TEMPLATE = {
    'verified': 'verified prompt',
    'trusted_unverified': 'trusted unverified prompt override',
    'best_guess': 'best guess prompt override',
    'unverified_rule': 'unverified rule prompt override',
}


def load_existing_overrides(path):
    overrides = {}
    if not path.exists():
        return overrides
    with path.open('r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for parts in reader:
            if not parts or len(parts) < 2:
                continue
            key = parts[0].strip()
            override_ric = parts[1].strip()
            note = parts[2].strip() if len(parts) > 2 else ''
            if key and override_ric:
                overrides[key] = (override_ric, note)
    return overrides


def load_prompt_records(path):
    with path.open('r', encoding='utf-8') as f:
        payload = json.load(f)
    return payload.get('records', [])


def build_override_rows(records, existing_overrides):
    overrides = dict(existing_overrides)
    unresolved = []
    added = 0
    updated = 0

    for record in records:
        key = record.get('input')
        status = record.get('status')
        ric = record.get('ric')
        if not key:
            continue

        if status in VALID_STATUSES and ric:
            note_parts = [NOTE_TEMPLATE.get(status, status)]
            if record.get('reason'):
                note_parts.append(record['reason'])
            if record.get('name'):
                note_parts.append(record['name'])
            note = ' | '.join(note_parts)
            if key in overrides:
                if overrides[key][0] != ric:
                    overrides[key] = (ric, note)
                    updated += 1
            else:
                overrides[key] = (ric, note)
                added += 1
        elif status == 'unresolved':
            unresolved.append({
                'input': key,
                'status': status,
                'reason': record.get('reason', ''),
                'ticker': record.get('ticker', ''),
                'country': record.get('country', ''),
                'name': record.get('name', ''),
            })

    return overrides, unresolved, added, updated


def write_overrides(path, overrides):
    rows = [
        {'bbg_name': key, 'override_ric': value[0], 'note': value[1]}
        for key, value in sorted(overrides.items())
    ]
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['bbg_name', 'override_ric', 'note'])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_unresolved(path, unresolved_rows):
    if not unresolved_rows:
        return
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['input', 'status', 'ticker', 'country', 'reason', 'name'])
        writer.writeheader()
        for row in unresolved_rows:
            writer.writerow(row)


def main():
    if not PROMPT_JSON.exists():
        raise FileNotFoundError(f'Prompt input JSON not found: {PROMPT_JSON}')

    existing_overrides = load_existing_overrides(OVERRIDE_CSV)
    records = load_prompt_records(PROMPT_JSON)
    overrides, unresolved, added, updated = build_override_rows(records, existing_overrides)

    write_overrides(OVERRIDE_CSV, overrides)
    write_unresolved(UNRESOLVED_CSV, unresolved)

    print(f'Existing overrides: {len(existing_overrides)}')
    print(f'Added overrides: {added}')
    print(f'Updated overrides: {updated}')
    print(f'Total overrides now: {len(overrides)}')
    if unresolved:
        print(f'Unresolved records written to: {UNRESOLVED_CSV}')
    else:
        print('No unresolved records to write.')


if __name__ == '__main__':
    main()
