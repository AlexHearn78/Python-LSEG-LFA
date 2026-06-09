from pathlib import Path
import re

exp_path = Path('/Users/alexanderhearn/Downloads/files/universe_expansion.txt')
base_path = Path('universe_full.txt')
text = exp_path.read_text(encoding='utf-8')
lines = [line.strip() for line in text.splitlines() if line.strip()]
pattern = re.compile(r'^[A-Z0-9.%@+\-]+ (US|LN|GB|GR|DE|FP|FR|NA|NL|SM|IM|IT|SW|CH|HK|JP|AU|CN|CA|ES|KR|IN|ID|PL|SE|NO|DK|FI)$')
start = next((i for i, line in enumerate(lines) if pattern.match(line)), None)
if start is None:
    raise SystemExit('Could not find first instrument line')
blocks = lines[start:]
if len(blocks) % 4 != 0:
    raise SystemExit(f'Lines from start not multiple of 4: {len(blocks)}')
with base_path.open('a', encoding='utf-8') as f:
    for i in range(0, len(blocks), 4):
        f.write('\n' + '\n'.join(blocks[i:i+4]) + '\n')
all_lines = [line for line in base_path.read_text(encoding='utf-8').splitlines() if line.strip()]
print('After append lines:', len(all_lines))
print('Approx instruments (lines/4):', len(all_lines)//4)
