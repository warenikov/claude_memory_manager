import re
from typing import Dict, Tuple

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n?', re.DOTALL)


def parse(content: str) -> Tuple[Dict[str, str], str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content
    meta: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            meta[key.strip()] = val.strip()
    return meta, content[match.end():]


def render(meta: Dict[str, str], body: str) -> str:
    lines = ['---']
    for k, v in meta.items():
        lines.append(f'{k}: {v}')
    lines.extend(['---', ''])
    return '\n'.join(lines) + body
