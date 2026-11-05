"""Shared types and HTTP helpers for quote sources."""

import time
from dataclasses import dataclass, field
from typing import Protocol

import requests

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT = 20


class SourceError(RuntimeError):
    """A source could not fulfil a search or fetch."""


@dataclass
class Candidate:
    """A search hit: a subject a source could harvest, shown to the user to pick.

    Only ``source`` and ``source_id`` matter once one is chosen; the rest is for
    display, since ``Source.fetch`` needs nothing but the id.
    """

    source: str
    source_id: str
    name: str
    domain: str
    hint: str = ""  # shown to the user when disambiguating

    @property
    def key(self) -> str:
        """The ``Subject.key`` the subject will have once fetched."""
        return _key(self.source, self.source_id)


@dataclass
class Item:
    """One harvested unit: a song, a poem, a quotation, a passage.

    ``atomic`` items are quoted whole (a Wikiquote line, a prose passage).
    Non-atomic items are sliceable: a random window of lines is taken.
    """

    lines: list[str]
    work: str = ""
    url: str = ""
    atomic: bool = False
    note: str = ""  # source citation, e.g. the book a quote came from


@dataclass
class Subject:
    """A harvested subject plus everything needed to attribute it."""

    source: str
    source_id: str
    name: str
    domain: str
    lang: str = "en"
    url: str = ""
    items: list[Item] = field(default_factory=list)
    attribution: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """``source:source_id``, which names this subject to the user.

        `hyprmuse list` shows it, a token on the command line can be it, and
        config.toml's ``[subjects."<key>"]`` tables are keyed by it.
        """
        return _key(self.source, self.source_id)


def _key(source: str, source_id: str) -> str:
    """The format of ``Subject.key`` and ``Candidate.key``, kept in one place."""
    return f"{source}:{source_id}"


class Source(Protocol):
    """A provider of quotable subjects, registered in ``sources.REGISTRY``.

    ``name`` is the registry key and the ``source`` of everything it returns;
    ``domain`` is the kind of text it yields; ``produces_atomic`` says whether
    its items are quoted whole or sliced.
    """

    name: str
    domain: str
    produces_atomic: bool

    def search(self, query: str, lang: str) -> list[Candidate]:
        """Subjects matching ``query``, best first; [] when nothing matches.

        ``lang`` is a language edition code, honoured only by sources that
        have editions. Raises SourceError when the provider is unreachable.
        """
        ...

    def fetch(self, source_id: str, progress=None) -> Subject:
        """Harvest the subject ``source_id`` names, from scratch.

        ``source_id`` is a ``Candidate.source_id`` from this source, or the
        ``source_id`` of a Subject it harvested earlier: the same id always
        re-harvests the same subject with the same name and attribution.
        ``progress``, if given, is called with one-line status messages.
        Raises SourceError when the provider fails or yields nothing usable.
        """
        ...


_LAST_CALL: dict[str, float] = {}


def get(url: str, *, params: dict | None = None, throttle: float = 0.0,
        key: str = "default", headers: dict | None = None) -> requests.Response:
    """GET with a browser UA, a timeout, and optional per-host throttling."""
    if throttle:
        elapsed = time.monotonic() - _LAST_CALL.get(key, 0.0)
        if elapsed < throttle:
            time.sleep(throttle - elapsed)
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    try:
        resp = requests.get(url, params=params, headers=hdrs, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise SourceError(f"request to {url} failed: {exc}") from exc
    finally:
        _LAST_CALL[key] = time.monotonic()
    if resp.status_code != 200:
        raise SourceError(f"{url} returned HTTP {resp.status_code}")
    return resp
