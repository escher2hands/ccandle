# The single source of truth for the inline link markers baked into plain_text.
# Nothing else in ccandle should hand-build or hand-regex these.
#
# [[link to: KEY:PID]]        resolved: target page is in the corpus, PID is its id
# [[ulink to: KEY:Some Title]] unresolved: target page isn't tracked, we only know its title
#
# KEY is the target's space key, or "?" when it couldn't be determined.
#
# Grammar notes:
# - Backslash escapes keep the grammar unambiguous for awkward input. Inside KEY, `\\`, `\]`, `\:` and `\ `
#   are escaped (personal-space keys can contain ":", e.g. ~712020:abc). Inside the target, `\\` and `\]`.
# - Titles are whitespace-normalized on render, so a marker never spans lines.
# - The first unescaped ":" after "to: " ends the key, so a title like "FAQ: Billing" is safe.
import re
from typing import Iterator, NamedTuple

RESOLVED_TAG = "link"
UNRESOLVED_TAG = "ulink"
UNKNOWN_SPACE = "?"

MARKER_PATTERN = re.compile(
    r"\[\[(?P<kind>u?link) to: "
    r"(?P<space>(?:[^:\]\s\\]|\\.)+):"
    r"(?P<target>(?:[^\]\\]|\\.)*)\]\]"
)


class Marker(NamedTuple):
    kind: str          # "link" or "ulink"
    space_key: str     # unescaped
    target: str        # unescaped: a pid if resolved, a title if not

    @property
    def resolved(self) -> bool:
        return self.kind == RESOLVED_TAG

    @property
    def entry(self) -> str:
        """The 'KEY:target' form stored in links_list."""
        return f"{self.space_key}:{self.target}"


def _escape(value: str, extra_specials: str = "") -> str:
    out = []
    for ch in value:
        if ch in ("\\", "]") or ch in extra_specials:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def render_marker(space_key, target, resolved: bool) -> str:
    tag = RESOLVED_TAG if resolved else UNRESOLVED_TAG
    key = str(space_key).strip() if space_key else UNKNOWN_SPACE
    target = " ".join(str(target).split())
    return f"[[{tag} to: {_escape(key, ': ')}:{_escape(target)}]]"


def iter_markers(text: str) -> Iterator[Marker]:
    for m in MARKER_PATTERN.finditer(text or ""):
        yield Marker(m["kind"], _unescape(m["space"]), _unescape(m["target"]))


def strip_markers(text: str) -> str:
    return MARKER_PATTERN.sub("", text or "")