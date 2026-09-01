"""Helpers for building OSDU search query strings.

OSDU Search accepts Lucene query-string syntax, in which a value's own
punctuation can change the meaning of a query. Every caller-supplied term must
pass through one of these helpers so that a value can only ever be matched, not
interpreted.
"""

# Characters Lucene's query parser treats specially outside of quotes. The `&`
# and `|` cover the && and || operators, which are special only when doubled.
_SPECIAL_CHARACTERS = '+-=&|><!(){}[]^"~*?:\\/'

#: An unversioned OSDU record id is `partition:entity-type:unique-id`.
_RECORD_ID_SEGMENTS = 3


def normalize_record_id(record_id: str) -> str:
    """Strip the version segment from an OSDU record id.

    Records reference each other in the version-qualified form
    `partition:entity-type:unique-id:version`, and OSDU leaves the version empty
    when it is unpinned - so a reference read off another record usually arrives
    with a bare trailing colon. The search index stores the unversioned id, and
    matching `id` against the qualified form returns nothing, silently.

    Only a trailing segment that is empty or all digits is removed, so an id that
    merely ends in a colon-bearing unique id is left intact.
    """
    segments = record_id.split(":")
    if len(segments) == _RECORD_ID_SEGMENTS + 1 and (
        segments[-1] == "" or segments[-1].isdigit()
    ):
        return ":".join(segments[:_RECORD_ID_SEGMENTS])
    return record_id


def is_record_id(value: str) -> bool:
    """Report whether a caller-supplied value is already an OSDU record id.

    Used to let a tool that normally takes a human-readable name accept the id
    it would have resolved to. The version-qualified form counts, so that an id
    read off another record is recognised as readily as one typed by hand.
    """
    return len(normalize_record_id(value).split(":")) == _RECORD_ID_SEGMENTS


def quoted(value: str) -> str:
    """Render a term as a quoted Lucene phrase.

    Inside quotes only the backslash and the closing quote retain any meaning,
    so nothing else needs escaping. Use this for exact values - IDs, sources,
    and other terms that should match literally.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def wildcard_contains(value: str) -> str:
    """Render an unquoted substring match: `*term*`.

    The term cannot be quoted, because a quoted value is a phrase in which `*`
    is a literal asterisk rather than a wildcard. Every Lucene special character
    is therefore escaped individually - including any `*` or `?` in the caller's
    own input, so that the only wildcards in the result are the two added here.

    Whitespace is escaped as well: unquoted, it would otherwise split the value
    into separate terms and match far more than the caller asked for.
    """
    escaped = "".join(
        f"\\{character}"
        if character in _SPECIAL_CHARACTERS or character.isspace()
        else character
        for character in value
    )
    return f"*{escaped}*"
