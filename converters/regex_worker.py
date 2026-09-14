"""Isolated, bounded regular-expression extraction worker (stdlib only)."""
import re
import sys
from pathlib import Path


def main():
    pattern = sys.stdin.buffer.read(801).decode('utf-8')
    if len(pattern) > 200:
        raise ValueError('pattern limit')
    source, output = map(Path, sys.argv[1:3])
    if source.stat().st_size > 15 * 1024 * 1024:
        raise ValueError('input limit')
    matches = set()
    size = 0
    for match in re.finditer(pattern, source.read_text(encoding='utf-8'), re.I | re.UNICODE):
        value = match.group(0)
        if value and value not in matches:
            matches.add(value)
            size += len(value.encode('utf-8')) + 1
        if len(matches) > 100_000 or size > 15 * 1024 * 1024:
            raise ValueError('output limit')
    output.write_text('\n'.join(sorted(matches)) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
