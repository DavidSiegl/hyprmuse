"""The source registry contract every adapter must satisfy."""

import pytest

from hyprmuse.sources import AUTO_ORDER, REGISTRY, get_source
from hyprmuse.sources.base import SourceError


def test_every_source_is_in_the_auto_order():
    assert set(AUTO_ORDER) == set(REGISTRY)


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_adapter_exposes_the_protocol(name):
    src = REGISTRY[name]
    assert src.name == name
    assert isinstance(src.domain, str) and src.domain
    assert isinstance(src.produces_atomic, bool)
    assert callable(src.search) and callable(src.fetch)


def test_domains_are_distinct():
    domains = [s.domain for s in REGISTRY.values()]
    assert len(domains) == len(set(domains))


def test_get_source_resolves_and_rejects():
    assert get_source("genius").name == "genius"
    with pytest.raises(SourceError, match="unknown source"):
        get_source("nope")


@pytest.mark.parametrize(("name", "source_id"), [
    ("genius", "342499"), ("wikiquote", "en:Arno Schmidt")])
def test_split_key_reads_back_the_key_a_candidate_has(name, source_id):
    """Review 24, F2: split_key parses the format base._key writes."""
    from hyprmuse.sources import split_key
    from hyprmuse.sources.base import Candidate
    key = Candidate(name, source_id, "Name", "domain").key
    assert split_key(key) == (name, source_id)
