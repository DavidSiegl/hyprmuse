"""Registry of quote sources."""

from . import genius, gutenberg, poetrydb, wikiquote
from .base import Candidate, Item, Source, SourceError, Subject

REGISTRY: dict[str, Source] = {
    s.SOURCE.name: s.SOURCE for s in (genius, wikiquote, poetrydb, gutenberg)
}

# Order tried when the user does not name a source explicitly. Wikiquote first:
# it has the broadest subject coverage across every domain.
AUTO_ORDER = ["wikiquote", "genius", "poetrydb", "gutenberg"]


def get_source(name: str) -> Source:
    try:
        return REGISTRY[name]
    except KeyError:
        raise SourceError(
            f"unknown source '{name}' (have: {', '.join(sorted(REGISTRY))})"
        ) from None


def split_key(token: str) -> tuple[str, str] | None:
    """The source name and source_id of the ``Subject.key`` a token is.

    None when the text before the token's first colon is not a key of REGISTRY,
    or nothing follows the colon: the token is then not a key but, say, a
    title such as "Mr. T: The Book". Ids may hold colons themselves
    ("wikiquote:en:Arno Schmidt" is wikiquote's "en:Arno Schmidt").
    """
    source, colon, source_id = token.partition(":")
    if not colon or not source_id or source not in REGISTRY:
        return None
    return source, source_id


__all__ = ["AUTO_ORDER", "REGISTRY", "Candidate", "Item", "Source", "SourceError",
           "Subject", "get_source", "split_key"]
