"""Slugging and the on-disk subject store."""

import json

import pytest

from hyprmuse import config, library
from tests.conftest import make_subject


@pytest.mark.parametrize("raw,slug", [
    ("Element of Crime", "element-of-crime"),
    ("de:Ingeborg Bachmann", "de-ingeborg-bachmann"),
    ("Émile Zola", "emile-zola"),
    ("  spaced  out  ", "spaced-out"),
    ("!!!", "unnamed"),
])
def test_slugify(raw, slug):
    assert library.slugify(raw) == slug


def test_save_then_load_roundtrip():
    subject = make_subject(name="Round Trip", n_items=2, n_lines=4)
    library.save(subject)
    loaded = library.load_all()
    assert len(loaded) == 1
    assert loaded[0].name == "Round Trip"
    assert len(loaded[0].items) == 2
    assert loaded[0].items[0].lines == subject.items[0].lines
    assert loaded[0].items[0].work == "Work 0"


def test_save_preserves_atomic_flag_and_attribution():
    subject = make_subject(atomic=True)
    subject.attribution = {"license": "CC BY-SA 4.0"}
    library.save(subject)
    loaded = library.load_all()[0]
    assert loaded.items[0].atomic is True
    assert loaded.attribution["license"] == "CC BY-SA 4.0"


def test_save_writes_schema_and_timestamp():
    library.save(make_subject())
    path = next(config.SUBJECTS_DIR.glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == library.SCHEMA
    assert data["fetched_at"].endswith("+00:00")


def test_save_is_atomic_leaving_no_temp_files():
    library.save(make_subject())
    assert list(config.SUBJECTS_DIR.glob("*.tmp")) == []


def test_save_overwrites_same_subject_rather_than_duplicating():
    library.save(make_subject(n_items=2))
    library.save(make_subject(n_items=5))
    assert len(library.load_all()) == 1
    assert len(library.load_all()[0].items) == 5


def test_load_all_skips_corrupt_files():
    library.save(make_subject())
    (config.SUBJECTS_DIR / "broken.json").write_text("{not json", encoding="utf-8")
    assert len(library.load_all()) == 1


def test_load_all_on_missing_directory_is_empty():
    assert library.load_all() == []


def test_find_by_source_key_and_by_name():
    library.save(make_subject(source="genius", source_id="42", name="Some Band"))
    assert library.find("genius:42")[0].name == "Some Band"
    assert library.find("some band")[0].source_id == "42"
    assert library.find("nothing here") == []


def test_remove_deletes_the_file():
    subject = make_subject()
    library.save(subject)
    assert library.remove(subject) is True
    assert library.load_all() == []
    assert library.remove(subject) is False


def test_subject_key_format():
    assert make_subject(source="wikiquote", source_id="de:X").key == "wikiquote:de:X"


def test_find_prefers_a_key_over_a_name_containing_it():
    library.save(make_subject(source_id="2", name="Keyed"))
    library.save(make_subject(source_id="3", name="Tribute to genius:2"))
    assert [s.name for s in library.find("genius:2")] == ["Keyed"]


def test_find_with_an_empty_token_finds_nothing():
    library.save(make_subject())
    assert library.find("") == []


def wikiquote(source_id, name):
    return make_subject(source="wikiquote", source_id=source_id, name=name, domain="quotations")


def test_ids_that_slugify_the_same_are_stored_apart():
    """Regression (#9): non-Latin titles slugify to nothing and shared one file."""
    library.save(wikiquote("ru:Лев Толстой", "Лев Толстой"))
    library.save(wikiquote("ru:Фёдор Достоевский", "Фёдор Достоевский"))
    assert sorted(s.name for s in library.load_all()) == ["Лев Толстой", "Фёдор Достоевский"]


def store_under_old_name(subject):
    """Save ``subject`` as hyprmuse up to 0.3.2 did: <source>--<slug>.json."""
    path = library.save(subject)
    old = config.SUBJECTS_DIR / f"{subject.source}--{library.slugify(subject.source_id)}.json"
    path.rename(old)
    return old


def test_a_subject_stored_under_its_old_name_still_loads():
    store_under_old_name(make_subject(name="Old Timer"))
    assert [s.name for s in library.load_all()] == ["Old Timer"]


def test_saving_a_subject_stored_under_its_old_name_leaves_one_file():
    old = store_under_old_name(make_subject(n_items=2))
    library.save(make_subject(n_items=5))
    assert not old.exists()
    assert [len(s.items) for s in library.load_all()] == [5]


def test_removing_a_subject_stored_under_its_old_name_deletes_it():
    subject = make_subject()
    store_under_old_name(subject)
    assert library.remove(subject) is True
    assert library.load_all() == []


def test_an_old_name_file_holding_another_subject_is_left_alone():
    # Up to 0.3.2 both ids below mapped to wikiquote--ru.json.
    old = store_under_old_name(wikiquote("ru:Лев Толстой", "Лев Толстой"))
    dostoevsky = wikiquote("ru:Фёдор Достоевский", "Фёдор Достоевский")
    library.save(dostoevsky)
    assert library.remove(dostoevsky) is True
    assert library.remove(dostoevsky) is False
    assert old.exists()
    assert [s.name for s in library.load_all()] == ["Лев Толстой"]


def test_saving_a_subject_under_its_old_name_never_shows_it_twice(monkeypatch):
    """After each rename save makes, load_all finds the subject exactly once."""
    store_under_old_name(make_subject(name="Old Timer"))
    seen = []
    real_replace = library.os.replace

    def replace(src, dst):
        real_replace(src, dst)
        seen.append([s.name for s in library.load_all()])

    monkeypatch.setattr(library.os, "replace", replace)
    library.save(make_subject(name="Old Timer"))
    assert seen and all(names == ["Old Timer"] for names in seen)


def test_an_old_name_file_that_cannot_be_deleted_fails_remove(monkeypatch):
    subject = make_subject()
    old = store_under_old_name(subject)
    real_unlink = library.Path.unlink

    def unlink(self, *args, **kwargs):
        if self == old:
            raise PermissionError(self)
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(library.Path, "unlink", unlink)
    with pytest.raises(PermissionError):
        library.remove(subject)


@pytest.mark.parametrize("item", [
    {"lines": [1, 2]}, {"lines": None}, {"lines": ["a"], "work": 5},
    {"lines": ["a"], "atomic": "yes"}, "oops",
])
def test_load_all_skips_and_names_a_file_with_an_item_of_the_wrong_shape(capsys, item):
    library.save(make_subject())
    broken = config.SUBJECTS_DIR / "broken.json"
    broken.write_text(json.dumps({"source": "genius", "source_id": "2", "name": "B",
                                  "items": [item]}), encoding="utf-8")
    assert [s.source_id for s in library.load_all()] == ["1"]
    assert str(broken) in capsys.readouterr().err


@pytest.mark.parametrize("stored", [[], {"source": "genius", "source_id": "2", "name": 5},
                                    {"source": "genius", "name": "B"}])
def test_load_all_skips_a_file_that_is_not_a_subject(stored):
    library.save(make_subject())
    (config.SUBJECTS_DIR / "broken.json").write_text(json.dumps(stored), encoding="utf-8")
    assert [s.source_id for s in library.load_all()] == ["1"]


def test_load_all_gives_missing_optional_fields_their_defaults():
    (config.SUBJECTS_DIR).mkdir(parents=True)
    (config.SUBJECTS_DIR / "minimal.json").write_text(json.dumps(
        {"source": "genius", "source_id": "2", "name": "B", "items": [{"lines": ["a"]}]}),
        encoding="utf-8")
    (subject,) = library.load_all()
    assert (subject.domain, subject.lang, subject.url, subject.attribution) == ("unknown", "en", "", {})
    assert (subject.items[0].work, subject.items[0].atomic, subject.items[0].note) == ("", False, "")
