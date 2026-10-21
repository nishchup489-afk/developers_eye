"""Network-free robots matching: merged groups, longest rules, * and $."""

from dataclasses import dataclass
from string import ascii_letters, digits, hexdigits
from urllib.parse import urlsplit

_UNRESERVED = frozenset(ascii_letters + digits + '-._~')


def _octets(value: str, *, pattern: bool = False) -> str:
    output = []
    cursor = 0
    while cursor < len(value):
        character = value[cursor]
        if character == '%' and cursor + 2 < len(value) and all(c in hexdigits for c in value[cursor + 1:cursor + 3]):
            byte = int(value[cursor + 1:cursor + 3], 16)
            output.append(chr(byte) if chr(byte) in _UNRESERVED else f'%{byte:02X}')
            cursor += 3
            continue
        if ord(character) > 127 or (not pattern and character in '*$'):
            output.extend(f'%{byte:02X}' for byte in character.encode('utf-8'))
        else:
            output.append(character)
        cursor += 1
    return ''.join(output)


def _matches(pattern: str, target: str) -> bool:
    # Splitting avoids regex backtracking on a site's untrusted wildcard rules.
    anchored = pattern.endswith('$')
    pattern = pattern[:-1] if anchored else pattern
    parts = pattern.split('*')
    if not target.startswith(parts[0]):
        return False
    if len(parts) == 1:
        return target == pattern if anchored else True
    cursor = len(parts[0])
    for part in parts[1:-1] if anchored else parts[1:]:
        position = target.find(part, cursor)
        if position < 0:
            return False
        cursor = position + len(part)
    return (target.endswith(parts[-1]) and len(target) - len(parts[-1]) >= cursor) if anchored else True


@dataclass(frozen=True, slots=True)
class RobotsRules:
    groups: tuple[tuple[tuple[str, ...], tuple[tuple[str, bool], ...]], ...]

    def can_fetch(self, user_agent: str, url: str) -> bool:
        product = user_agent.split('/', 1)[0].casefold()
        matches = [(len(agent), rules) for agents, rules in self.groups
                   for agent in agents if agent != '*' and agent in product]
        if matches:
            length = max(size for size, _ in matches)
            rules = [rule for size, group in matches if size == length for rule in group]
        else:
            rules = [rule for agents, group in self.groups if '*' in agents for rule in group]
        parts = urlsplit(url)
        if parts.path == '/robots.txt':
            return True
        target = _octets((parts.path or '/') + ('?' + parts.query if parts.query else ''))
        applicable = [(len(pattern), allowed) for pattern, allowed in rules if _matches(pattern, target)]
        # True wins equal-length ties between Allow and Disallow.
        return max(applicable)[1] if applicable else True


def parse_rules(raw: str) -> RobotsRules:
    if not isinstance(raw, str):
        raise TypeError('raw_content must be text')
    groups = []
    agents = []
    rules = []
    has_rules = False
    for line in raw.lstrip('\ufeff').splitlines():
        field, separator, value = line.partition('#')[0].partition(':')
        if not separator:
            continue
        field, value = field.strip().casefold(), value.strip()
        if field == 'user-agent':
            if has_rules:
                groups.append((tuple(agents), tuple(rules)))
                agents, rules, has_rules = [], [], False
            if value:
                agents.append(value.casefold())
        elif field in {'allow', 'disallow'} and agents:
            has_rules = True
            if value.startswith('/') and not any(c.isspace() or ord(c) < 32 for c in value):
                rules.append((_octets(value, pattern=True), field == 'allow'))
    if agents:
        groups.append((tuple(agents), tuple(rules)))
    return RobotsRules(tuple(groups))
