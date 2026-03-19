import re


_RANGE_RE = r"[-0-9x,]+"

_BRACE_SEQUENCE_RE = re.compile(rf"^(?P<base>.*\{{.+\}}.*?)(?:=(?P<range>{_RANGE_RE}))?$")
_SHAKE_SEQUENCE_RE = re.compile(
    rf"^(?P<head>.+\.)(?P<pad>[#@]+)(?P<tail>\..+?)(?:=(?P<range>{_RANGE_RE}))?$"
)
_PREFIX_BRACE_SEQUENCE_RE = re.compile(
    rf"^(?P<head>.*\.)(?P<range>{_RANGE_RE})(?P<pattern>\{{.+\}}.*)$"
)
_PREFIX_SHAKE_SEQUENCE_RE = re.compile(
    rf"^(?P<head>.+\.)(?P<range>{_RANGE_RE})(?P<pad>[#@]+)(?P<tail>\..+)$"
)
_PERCENT_SEQUENCE_RE = re.compile(
    rf"^(?P<head>.*?)(?P<percent>%0(?P<width>\d+)d)(?P<tail>\..+?)(?:=(?P<range>{_RANGE_RE}))?$"
)
def _brace_padding(pad: str) -> str:
    if not pad:
        return ""
    width = 4 if pad == "#" else len(pad)
    return f"{{:0{width}d}}"


def normalize_sequence_load_path(path: str) -> str | None:
    if not path:
        return None

    match = _PREFIX_BRACE_SEQUENCE_RE.match(path)
    if match:
        return f"{match.group('head')}{match.group('pattern')}={match.group('range')}"

    match = _PREFIX_SHAKE_SEQUENCE_RE.match(path)
    if match:
        return (
            f"{match.group('head')}{_brace_padding(match.group('pad'))}"
            f"{match.group('tail')}={match.group('range')}"
        )

    match = _SHAKE_SEQUENCE_RE.match(path)
    if match:
        result = (
            f"{match.group('head')}{_brace_padding(match.group('pad'))}"
            f"{match.group('tail')}"
        )
        if match.group("range"):
            result += f"={match.group('range')}"
        return result

    match = _PERCENT_SEQUENCE_RE.match(path)
    if match:
        result = f"{match.group('head')}{{:0{match.group('width')}d}}{match.group('tail')}"
        if match.group("range"):
            result += f"={match.group('range')}"
        return result

    if _BRACE_SEQUENCE_RE.match(path):
        return path

    return None


def looks_like_sequence_path(path: str) -> bool:
    if not path:
        return False

    return bool(
        _BRACE_SEQUENCE_RE.match(path) or
        _SHAKE_SEQUENCE_RE.match(path) or
        _PREFIX_BRACE_SEQUENCE_RE.match(path) or
        _PREFIX_SHAKE_SEQUENCE_RE.match(path) or
        _PERCENT_SEQUENCE_RE.match(path)
    )
