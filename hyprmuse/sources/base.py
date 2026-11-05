"""Shared types and the HTTP client for quote sources."""

import random
import time
from dataclasses import dataclass, field
from importlib import metadata
from typing import Protocol

import requests

# What the scraped sites see by default: some refuse clients that are not a browser.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT = 20


def hyprmuse_user_agent() -> str:
    """A User-Agent naming hyprmuse, its version and where to reach its maintainer.

    For providers that ask automated clients to identify themselves, such as
    Wikimedia (https://meta.wikimedia.org/wiki/User-Agent_policy). The version
    comes from the installed package's metadata and is left out where there is
    none, as in the PyInstaller binary.
    """
    try:
        product = f"hyprmuse/{metadata.version('hyprmuse')}"
    except metadata.PackageNotFoundError:
        product = "hyprmuse"
    return f"{product} (https://github.com/DavidSiegl/hyprmuse)"


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


class Client:
    """Makes a source's HTTP GETs, spaced so its provider is never hit too often.

    Each source holds one Client for all its requests, so the spacing covers
    every request the source makes. A request starts at least ``gap`` seconds,
    plus a random extra of up to ``jitter`` seconds, after the previous one
    ended; the first request does not wait. Requests send ``user_agent`` and
    time out after ``TIMEOUT`` seconds.
    """

    def __init__(self, gap: float = 0.0, jitter: float = 0.0,
                 user_agent: str = BROWSER_USER_AGENT):
        self._gap = gap
        self._jitter = jitter
        self._user_agent = user_agent
        # time.monotonic() when the previous request ended; None before the first.
        self._last_end: float | None = None

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        """GET ``url`` with ``params`` as its query string, after waiting out the gap.

        Returns the response when the status is 200. Raises SourceError when
        the request fails (connection, timeout) or the status is anything else.
        """
        if self._last_end is not None:
            jitter = random.uniform(0.0, self._jitter)  # noqa: S311 - spacing, not secrecy
            wait = self._gap + jitter - (time.monotonic() - self._last_end)
            if wait > 0:
                time.sleep(wait)
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": self._user_agent},
                                timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise SourceError(f"request to {url} failed: {exc}") from exc
        finally:
            self._last_end = time.monotonic()
        if resp.status_code != 200:
            raise SourceError(f"{url} returned HTTP {resp.status_code}")
        return resp
