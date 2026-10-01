"""Every shipped setting regex is fully anchored and matches in linear time.

The server validates a setting value with ``re.search`` (Configurator, Database.is_valid_setting,
the UI's check_variables), so:

- a regex with no end anchor accepts any suffix: ``^\\d+`` took ``100; include /etc/passwd`` for
  BROTLI_MIN_LENGTH, which lands verbatim in ``brotli_min_length ...;``;
- a regex that backtracks catastrophically lets one value pin the validating process: the
  ``( *X *)*`` list shape and the ``(,? ?X)*`` optional-separator shape are exponential on a near
  miss (CORS_EXPOSE_HEADERS took about 110 s on 30 characters).

``REWRITES`` maps each regex that was rewritten to its replacement. The equivalence test proves,
on a generated corpus, that ``re.fullmatch`` gives the same verdict with both, except where a
rewrite deliberately refuses (or accepts) a value, each kind with its reason and a predicate that
recognises it.
"""

import json
import multiprocessing
import random
import re
import time
from pathlib import Path
from re import _constants as C, _parser as P  # type: ignore[attr-defined]

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _shipped() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for path in [ROOT / "src" / "common" / "settings.json", *sorted((ROOT / "src" / "common" / "core").glob("*/plugin.json"))]:
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, setting in (data if path.name == "settings.json" else data.get("settings", {})).items():
            if not isinstance(setting, dict) or not setting.get("regex"):
                continue
            entry = found.setdefault(setting["regex"], {"settings": [], "values": set(), "flags": 0})
            entry["settings"].append(name)
            entry["values"].update(v for v in (setting.get("default"), *setting.get("select", ())) if isinstance(v, str))
            if setting.get("type") == "file":  # the server matches file settings with DOTALL
                entry["flags"] = re.DOTALL
    return found


SHIPPED = _shipped()

# --------------------------------------------------------------------------------------------
# The rewrites. `kind` names the only verdict change the corpus may show (see _EXPLAINED).

_IP = (
    r"(((\b25[0-5]|\b2[0-4]\d|\b[01]?\d\d?)(\.(25[0-5]|2[0-4]\d|[01]?\d\d?)){3})(\/([1-2][0-9]?|3[0-2]?|[04-9]))?|(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"
    r"|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}"
    r"(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:"
    r"((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]Z{0,4}){0,4}%[0-9a-zA-Z]+|::(ffff(:0{1,4})?:)?((25[0-5]|(2[0-4]|1?\d)?\d)\.){3}"
    r"(25[0-5]|(2[0-4]|1?\d)?\d)|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1?\d)?\d)\.){3}(25[0-5]|(2[0-4]|1?\d)?\d))(\/(12[0-8]|1[01][0-9]|[0-9][0-9]?))?)"
)
_PORT = r"(\b((6553[0-5])|(655[0-2][0-9])|(65[0-4][0-9]{2})|(6[0-4][0-9]{3})|([1-5][0-9]{4})|([0-5]{0,5})|([0-9]{1,4}))\b)"
_URL_OLD = r"[\-\w@:%.+~#=]+[\-\w\(\)!@:%+.~#?&\/=$]*"
# The first class is a subset of the second, so `A+B*` is `AB*` without the quadratic split.
_URL_NEW = r"[\-\w@:%.+~#=][\-\w\(\)!@:%+.~#?&\/=$]*"
_COOKIE_FLAG = r"(([Ee]xpires)=[^\s;]+|([Dd]omain)=[^\s;]+|([Pp]ath)=[^\s;]+|[Hh]ttp[Oo]nly|[Ss]ame[Ss]ite(=([Ll]ax|[Ss]trict|[Nn]one))?|[Ss]ecure)"
_HEADER_ITEM = r"[\w\-]+\s+[^;\s{}#][^;{}#\r\n]*"
_SET_ITEM = r"\$[a-z_\-]+\s+[^;\s{}#][^;{}#\r\n]*"


def _star_list(item: str) -> str:
    """`^( *ITEM *)*$`, linear: items need a space between them, no all-space value."""
    return rf"^(?! +$) *(?:{item}(?: +|$))*$"


def _plus_list(item: str) -> str:
    """`^( *ITEM *)+$`, linear."""
    return rf"^ *(?:{item}(?: +|$))+$"


def _token(item: str) -> str:
    r"""One space-free token that ITEM matches whole. For an ITEM that can match the same token
    several ways (`[01]?\d\d?` reads "16" twice, the IPv6 branches overlap), the lookahead is
    tried once per token instead of the parses multiplying across the list."""
    return rf"(?={item}(?: |$))[^ \n]+"


# old regex -> (new regex, kind, item regex for the "glued" kind)
REWRITES: dict[str, tuple[str, str, str | None]] = {
    # No end anchor: `re.search` accepted any suffix.
    r"^[\w\-]+": (r"^[^:]+$", "rfc7617", None),
    r"^.+": (r"^.+$", "same", None),
    r"^[1-9][0-9]*": (r"^[1-9][0-9]*$", "same", None),
    r"^\d+": (r"^[0-9]+$", "ascii-digits", None),
    r"^.*": (r"^.*$", "same", None),
    # `( *ITEM *)*`: two optional space runs per item split every gap two ways.
    r"^( *(ASN?)?\d+ *)*$": (_star_list(r"(ASN?)?\d+"), "glued", r"(ASN?)?\d+"),
    r"^( *[A-Za-z]{2} *)*$": (_star_list(r"[A-Za-z]{2}"), "glued", r"[A-Za-z]{2}"),
    r"^( *([A-Z]{2}|@[A-Z0-9_]+) *)*$": (_star_list(r"([A-Z]{2}|@[A-Z0-9_]+)"), "glued", r"[A-Z]{2}|@[A-Z0-9_]+"),
    r"^( *([1-5]\d{2}) *)*$": (_star_list(r"([1-5]\d{2})"), "glued", r"[1-5]\d{2}"),
    r"^( *[1-5]\d{2} *)+$": (_plus_list(r"[1-5]\d{2}"), "glued", r"[1-5]\d{2}"),
    r"^( *[\-\w.]+/[\-\w.+]+ *)+$": (_plus_list(r"[\-\w.]+/[\-\w.+]+"), "glued", r"[\-\w.]+/[\-\w.+]+"),
    r"^( *[\w\-]+ *)*$": (_star_list(r"[\w\-]+"), "same", None),
    r"^( *([1-5]\d{2})=[^ ]+ *)*$": (_star_list(r"([1-5]\d{2})=[^ ]+"), "same", None),
    r"^(( *[\w\-]+ *)+|\*)?$": (r"^( *(?:[\w\-]+(?: +|$))+|\*)?$", "same", None),
    r"^( *(.*) *)*$": (r"^.*$", "same", None),
    rf"^( *((https?:\/\/|file:\/\/\/){_URL_OLD}) *)*$": (_star_list(rf"(https?:\/\/|file:\/\/\/){_URL_NEW}"), "same", None),
    rf"^( *{_IP} *)*$": (_star_list(_token(_IP)), "glued", _IP),
    rf"^(?! )( *{_IP} *)*$": (rf"^(?:{_token(_IP)}(?: +|$))*$", "glued", _IP),
    # Same, and the duplicate check's backreference follows the IP group from \2 to \1.
    rf"^(?! )( *{_IP}(?!.*\D\2([^\d\/]|$)) *)*$": (rf"^(?:{_token(_IP)}(?!.*\D\1([^\d\/]|$))(?: +|$))*$", "glued", _IP),
    rf"^( *({_PORT}) *)+$": (_plus_list(_token(_PORT)), "glued", _PORT),
    # `(sep? ITEM)*` with an optional separator: glued items split every way. Where two glued
    # items are themselves one item (every case below), requiring the separator changes nothing.
    r"^(?!\|)(\|?[a-z0-9]+)+$": (r"^[a-z0-9]+(\|[a-z0-9]+)*$", "same", None),
    r"^(?!\|)(\|?[A-Z][A-Z_-]{2,})+$": (r"^[A-Z][A-Z_-]{2,}(\|[A-Z][A-Z_-]{2,})*$", "same", None),
    r"^(?!:)(:?[A-Za-z0-9-]+)*$": (r"^([A-Za-z0-9-]+(:[A-Za-z0-9-]+)*)?$", "same", None),
    r"^(?! )( ?[A-Z]{3,})+$": (r"^[A-Z]{3,}( [A-Z]{3,})*$", "same", None),
    r"^(\*|(?![, ])(,? ?[A-Z]{3,})*)?$": (r"^(\*|[A-Z]{3,}((, ?| )[A-Z]{3,})*)?$", "same", None),
    r"^(\*|(?![, ])(,? ?([\w\-]+))*)?$": (r"^(\*|[\w\-]+((, ?| )[\w\-]+)*)?$", "same", None),
    r"^(\*|(?![, ]+)(,? ?([\w\-]+))*)?$": (r"^(\*|[\w\-]+((, ?| )[\w\-]+)*)?$", "same", None),
    r"^(?! )(( ?(?!proxy_protocol)[\w\-]+)*|proxy_protocol)$": (
        r"^((?!proxy_protocol)[\w\-]+( (?!proxy_protocol)[\w\-]+)*|proxy_protocol)?$",
        "same",
        None,
    ),
    # Glued header items: a value runs up to `;`/newline, so without a `;` two items on one line
    # are one item; only `;` or a newline really separates them. The one shape this drops is an
    # item glued onto the previous value whose name and value are split by a newline.
    r"^(?![;\s])(;?\s*([\w\-]+)\s+[^;\s{}#\r\n][^;{}#\r\n]*)*$": (
        rf"^(?:{_HEADER_ITEM}(?:(?:;\s*|[\r\n]\s*){_HEADER_ITEM})*)?$",
        "embedded-newline",
        None,
    ),
    r"^(?![;\s])(;?\s*(\$[a-z_\-]+)\s+[^;\s{}#\r\n][^;{}#\r\n]*)*$": (
        rf"^(?:{_SET_ITEM}(?:(?:;\s*|[\r\n]\s*){_SET_ITEM})*)?$",
        "embedded-newline",
        None,
    ),
    rf"^(\*|[^\s;]+)?(\s*{_COOKIE_FLAG})*$": (rf"^(\*|[^\s;]+)?(\s+{_COOKIE_FLAG})*$", "glued-after-head", _COOKIE_FLAG),
    # The token must be whole (`(?![^ ])`) so it is not re-split; \2 captured its leading spaces
    # and \1 still does.
    r"^(?! )(( *[^ ]+)(?!.*\2))*$": (r"^(?! )(?:( *[^ ]+)(?![^ ])(?!.*\1))*$", "same", None),
    # `A+B*` with A a subset of B: quadratic on a near miss.
    rf"^(https?:\/\/{_URL_OLD})?$": (rf"^(https?:\/\/{_URL_NEW})?$", "same", None),
    rf"^https?:\/\/{_URL_OLD}$": (rf"^https?:\/\/{_URL_NEW}$", "same", None),
    r"^((https?|\$[a-zA-Z0-9_]+):\/\/[\-\w@:%.+~#=$]+[\-\w\(\)!@:%+.~#?&\/=$]*)?$": (
        r"^((https?|\$[a-zA-Z0-9_]+):\/\/[\-\w@:%.+~#=$][\-\w\(\)!@:%+.~#?&\/=$]*)?$",
        "same",
        None,
    ),
    r"^((https?|\$[a-zA-Z0-9_]+):\/\/[#\-\w@:%.+~#=$]+[#\-\w\(\)!@:%+.~#?&\/=$]*)?$": (
        r"^((https?|\$[a-zA-Z0-9_]+):\/\/[#\-\w@:%.+~#=$][#\-\w\(\)!@:%+.~#?&\/=$]*)?$",
        "same",
        None,
    ),
    rf"^(?![ ])(,? ?([a-z0-9\-]+)=(\*|\(( ?(self|\u0022https?:\/\/{_URL_OLD}\u0022)(?=[ \)]))*\)))*$": (
        rf"^(?![ ])(,? ?([a-z0-9\-]+)=(\*|\(( ?(self|\u0022https?:\/\/{_URL_NEW}\u0022)(?=[ \)]))*\)))*$",
        "same",
        None,
    ),
    # The domain's first dot decides the split instead of every dot.
    r"^([^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+)?$": (r"^([^@ \t\r\n]+@[^@ \t\r\n][^@ \t\r\n.]*\.[^@ \t\r\n]+)?$", "same", None),
}

_NON_ASCII_DIGIT = re.compile(r"[^\x00-\x7f]")


def _glued(item: str, value: str, skip_head: bool = False) -> bool:
    fields = [field for field in re.split(r"\s+" if skip_head else " ", value) if field]
    if skip_head and value[:1] and not value[:1].isspace():
        fields = fields[1:]  # the cookie name, any non-space token
    return any(not re.fullmatch(item, field) for field in fields)


# kind -> (reason, predicate(old_accepts, new_accepts, value, item))
_EXPLAINED = {
    "same": ("no verdict may change", lambda old, new, value, item: False),
    "rfc7617": (
        "AUTH_BASIC_USER: an RFC 7617 user-id is anything without a colon; `^[\\w\\-]+` was searched, so 'john.doe' was already accepted",
        lambda old, new, value, item: new and not old and ":" not in value,
    ),
    "ascii-digits": (
        "BROTLI_MIN_LENGTH/BAD_BEHAVIOR_COUNT_TIME: nginx and Lua tonumber() only read ASCII digits",
        lambda old, new, value, item: old and not new and bool(_NON_ASCII_DIGIT.search(value)),
    ),
    "glued": (
        "two list items with no space between them ('404500', 'FRDE') were one field the list consumers never split",
        lambda old, new, value, item: old and not new and _glued(item, value),
    ),
    "embedded-newline": (
        "GRPC/REVERSE_PROXY_HEADERS and *_AUTH_REQUEST_SET: a value with a newline inside it, which the Configurator refuses anyway",
        lambda old, new, value, item: old and not new and bool(re.search(r"[\r\n].", value, re.DOTALL)),
    ),
    "glued-after-head": (
        "COOKIE_FLAGS: two flags with no whitespace between them ('HttpOnlySecure') after the cookie name",
        lambda old, new, value, item: old and not new and _glued(item, value, skip_head=True),
    ),
}


# --------------------------------------------------------------------------------------------
# A small generator over the regex parse tree: strings the regex (mostly) accepts, with one
# chosen unbounded repeat pumped k times. Lookarounds are skipped, so some outputs miss.

_PRINTABLE = [chr(c) for c in range(32, 127)] + ["é", "١", "\t", "\n"]


def _in_class(char: str, items) -> bool:
    negate, hit = False, False
    for op, av in items:
        if op is C.NEGATE:
            negate = True
        elif op is C.LITERAL:
            hit |= ord(char) == av
        elif op is C.RANGE:
            hit |= av[0] <= ord(char) <= av[1]
        elif op is C.CATEGORY:
            word = char.isalnum() or char == "_"
            hit |= {
                C.CATEGORY_DIGIT: char.isdigit(),
                C.CATEGORY_NOT_DIGIT: not char.isdigit(),
                C.CATEGORY_WORD: word,
                C.CATEGORY_NOT_WORD: not word,
                C.CATEGORY_SPACE: char.isspace(),
                C.CATEGORY_NOT_SPACE: not char.isspace(),
            }.get(av, False)
    return hit != negate


def _children(op, av):
    if op in (C.MAX_REPEAT, C.MIN_REPEAT, C.POSSESSIVE_REPEAT):
        return [av[2]]
    if op is C.SUBPATTERN:
        return [av[3]]
    if op is C.BRANCH:
        return list(av[1])
    if op is C.ATOMIC_GROUP:
        return [av]
    return []


def _contains(pattern, target: int) -> bool:
    return id(pattern) == target or any(_contains(child, target) for op, av in pattern for child in _children(op, av))


def _unbounded_repeats(pattern, found: list) -> list:
    for op, av in pattern:
        if op in (C.MAX_REPEAT, C.MIN_REPEAT, C.POSSESSIVE_REPEAT) and (av[1] == C.MAXREPEAT or av[1] >= 16):
            found.append(av[2])
        for child in _children(op, av):
            _unbounded_repeats(child, found)
    return found


def _generate(pattern, rng: random.Random, target: int = 0, pump: int = 1, bodies: dict | None = None, spread: int = 1) -> str:
    bodies = {} if bodies is None else bodies
    out = []
    for op, av in pattern:
        if op is C.LITERAL:
            out.append(chr(av))
        elif op is C.NOT_LITERAL:
            out.append(rng.choice([c for c in _PRINTABLE if ord(c) != av]))
        elif op is C.ANY:
            out.append(rng.choice(_PRINTABLE[:95]))
        elif op is C.IN:
            pool = [c for c in _PRINTABLE if _in_class(c, av)]
            out.append(rng.choice(pool) if pool else "")
        elif op is C.BRANCH:
            on_path = [branch for branch in av[1] if _contains(branch, target)]
            out.append(_generate(rng.choice(on_path or av[1]), rng, target, pump, bodies, spread))
        elif op in (C.SUBPATTERN, C.ATOMIC_GROUP):
            out.append(_generate(av[3] if op is C.SUBPATTERN else av, rng, target, pump, bodies, spread))
        elif op in (C.MAX_REPEAT, C.MIN_REPEAT, C.POSSESSIVE_REPEAT):
            low, high, sub = av
            if id(sub) == target:
                if id(sub) not in bodies:
                    bodies[id(sub)] = _generate(sub, rng, target, 1, bodies, spread) or " "
                out.append(bodies[id(sub)] * max(pump, low))
            else:
                count = low + rng.randint(0, spread)
                count = min(count, high) if high != C.MAXREPEAT else count
                if not count and _contains(sub, target):
                    count = 1
                out.append("".join(_generate(sub, rng, target, pump, bodies, spread) for _ in range(count)))
    return "".join(out)


# --------------------------------------------------------------------------------------------
# Anchoring guard


# regex -> reason it may stay unanchored. Empty: every shipped regex is anchored at both ends.
UNANCHORED_ALLOWED: dict[str, str] = {}


def _edge_anchored(sequence, first: bool) -> bool:
    if not sequence:
        return False
    op, av = sequence[0] if first else sequence[-1]
    if op is C.AT:
        return av in ((C.AT_BEGINNING, C.AT_BEGINNING_STRING) if first else (C.AT_END, C.AT_END_STRING))
    if op is C.BRANCH:
        return all(_edge_anchored(list(branch), first) for branch in av[1])
    if op is C.SUBPATTERN:
        return _edge_anchored(list(av[3]), first)
    return False


def _fully_anchored(regex: str) -> bool:
    tree = list(P.parse(regex))
    return _edge_anchored(tree, True) and _edge_anchored(tree, False)


def test_every_shipped_regex_is_anchored_at_both_ends():
    unanchored = {regex: entry["settings"] for regex, entry in SHIPPED.items() if not _fully_anchored(regex)}
    assert {regex: names for regex, names in unanchored.items() if regex not in UNANCHORED_ALLOWED} == {}
    assert set(UNANCHORED_ALLOWED) <= set(unanchored), "an allowlisted regex is anchored now: drop it"


@pytest.mark.parametrize(
    ("regex", "anchored"),
    [(r"^\d+$", True), (r"^$|^a+$", True), (r"^(a|b)$", True), (r"^\d+", False), (r"^a$|b$", False), (r"^a|^b$", False), (r"\d+$", False)],
)
def test_the_anchoring_check(regex, anchored):
    assert _fully_anchored(regex) is anchored


# --------------------------------------------------------------------------------------------
# Timing guard

NEAR_MISS_LENGTH = 512  # characters
BUDGET_MS = 50  # per re.search of one near miss; a linear regex takes well under 1 ms here
_BREAKERS = ["!", " ", "\x01", "{", ",", "é", "\nx"]


def _search_ms(compiled: re.Pattern, candidate: str) -> float:
    start = time.perf_counter()
    compiled.search(candidate)
    return (time.perf_counter() - start) * 1000


def _slowest_near_miss(regex: str, flags: int) -> tuple[float, str]:
    """Pump every unbounded repeat, break the match at the end, time `re.search` as the server
    runs it. Lengths grow by about a quarter at a time so an exponential regex is caught just
    past the budget instead of hanging on a long input."""
    compiled, tree = re.compile(regex, flags), P.parse(regex, flags)
    slowest = (0.0, "")
    for target in _unbounded_repeats(tree, []):
        for seed, spread in [(seed, spread) for seed in range(4) for spread in (0, 1)]:
            bodies: dict = {}
            for breaker in _BREAKERS:
                for strip in (False, True):
                    pump, previous = 2, -1
                    while True:
                        base = _generate(tree, random.Random(seed), id(target), pump, bodies, spread)
                        candidate = (base.lstrip(" ,;:|") if strip else base) + breaker
                        if len(candidate) > NEAR_MISS_LENGTH or len(candidate) <= previous:
                            break
                        elapsed = _search_ms(compiled, candidate)
                        if elapsed > BUDGET_MS:  # a loaded machine stalls one run; three do not lie
                            elapsed = min(elapsed, *(_search_ms(compiled, candidate) for _ in range(2)))
                        if elapsed > slowest[0]:
                            slowest = (elapsed, candidate)
                        if elapsed > BUDGET_MS:
                            return slowest
                        previous, pump = len(candidate), pump + max(1, pump // 4)
    return slowest


def _timed(args):
    regex, flags = args
    return regex, _slowest_near_miss(regex, flags)


def test_every_shipped_regex_rejects_a_near_miss_in_linear_time():
    """One process per regex, killed with the pool: a catastrophic one must fail, not hang."""
    over, pending = {}, {}
    with multiprocessing.get_context("fork").Pool() as pool:
        for regex, entry in SHIPPED.items():
            pending[regex] = pool.apply_async(_timed, ((regex, entry["flags"]),))
        deadline = time.monotonic() + 240
        for regex, result in pending.items():
            try:
                _, (elapsed, candidate) = result.get(timeout=max(1, deadline - time.monotonic()))
            except multiprocessing.TimeoutError:
                over[regex] = (SHIPPED[regex]["settings"], "did not finish", "")
                continue
            if elapsed > BUDGET_MS:
                over[regex] = (SHIPPED[regex]["settings"], f"{elapsed:.0f} ms", candidate[:60])
        pool.terminate()
    assert over == {}


# --------------------------------------------------------------------------------------------
# Equivalence of the rewrites

_MUTANTS = [" ", "  ", ",", ", ", "|", ":", ";", "-", "_", ".", "/", "*", "@", "#", "=", "a", "A", "Z", "0", "9", "١", "é", "\t", "\n", '"', "(", ")"]
_FIXED = ["", " ", "  ", "*", "a", "abc", "0", "404", "404500", "404 500", "FR", "FRDE", "FR DE", "@EU", "AS1234", "1.2.3.4", "::1", "10.0.0.0/8"]


def _corpus(old: str, new: str, values) -> set[str]:
    corpus = set(_FIXED) | {value for value in values if len(value) <= 64}
    seeds = set()
    for regex in (old, new):
        tree = P.parse(regex)
        for seed in range(150):
            seeds.add(_generate(tree, random.Random(seed), spread=2))
    seeds |= {value[:16] for value in values}
    for sample in seeds:
        corpus.add(sample[:48])
        short = sample[:14]
        middle = len(short) // 2
        for mutant in _MUTANTS:
            corpus.update((short + mutant, mutant + short, short[:middle] + mutant + short[middle:], short[:middle] + mutant + short[middle + 1 :]))
    return corpus


def test_the_rewritten_regexes_are_the_shipped_ones():
    assert sorted(old for old in REWRITES if old in SHIPPED) == []
    assert sorted(new for new, _, _ in REWRITES.values() if new not in SHIPPED) == []


@pytest.mark.parametrize("old", sorted(REWRITES), ids=lambda old: old[:40])
def test_a_rewrite_keeps_the_verdict_of_the_old_regex(old):
    new, kind, item = REWRITES[old]
    _, explains = _EXPLAINED[kind]
    values = SHIPPED.get(new, {}).get("values", set())
    corpus = _corpus(old, new, values)
    unexplained, accepted = [], 0
    for value in sorted(corpus):
        before, after = bool(re.fullmatch(old, value)), bool(re.fullmatch(new, value))
        accepted += before
        if before != after and not explains(before, after, value, item):
            unexplained.append((value, before, after))
    assert unexplained == []
    assert accepted, "the corpus never exercised an accepted value"
    # every shipped default and select value keeps its verdict
    assert [value for value in values if bool(re.fullmatch(old, value)) != bool(re.fullmatch(new, value))] == []
