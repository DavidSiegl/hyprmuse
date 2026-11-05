"""Wikitext stripping and quote parsing, across Wikiquote language editions."""

import pytest

from hyprmuse.sources import wikiquote as wq


@pytest.mark.parametrize("raw,expected", [
    ("[[Freedom]] is worth having", "Freedom is worth having"),
    ("[[w:Some Page|Displayed text]] follows", "Displayed text follows"),
    ("''italic'' and '''bold''' text", "italic and bold text"),
    ("A quote<ref>Book, 1920, p. 4</ref> ends", "A quote ends"),
    ("Before<!-- hidden note -->after", "Beforeafter"),
    ("Text {{template|arg}} more", "Text more"),
    ("See [http://example.org the source] here", "See the source here"),
    ("Bare [http://example.org] link", "Bare link"),
    ("Spaced&nbsp;out &amp; escaped", "Spaced out & escaped"),
    ("<span class='x'>tagged</span>", "tagged"),
    ("collapse    excess\n\nwhitespace", "collapse excess whitespace"),
])
def test_strip_markup(raw, expected):
    assert wq.strip_markup(raw) == expected


def test_strip_markup_handles_nested_templates():
    assert wq.strip_markup("a {{outer {{inner}} }} b").strip() == "a b"


@pytest.mark.parametrize("raw,quote,note", [
    ('"Ein Zitat" - Quelle 1978', "Ein Zitat", "Quelle 1978"),
    ('"Nur das Zitat"', "Nur das Zitat", ""),
    ("Plain quote with no quoting", "Plain quote with no quoting", ""),
    ('„Deutsche Zitatzeichen“ - Werk', "Deutsche Zitatzeichen", "Werk"),
    ("«Una cita en español».", "Una cita en español", ""),
    ("«Él dijo «sí» y se fue» – Fuente", "Él dijo «sí» y se fue", "Fuente"),
    ("«Dijo «sí» y «no» al fin» – F", "Dijo «sí» y «no» al fin", "F"),
    ("„Polski cytat”", "Polski cytat", ""),
])
def test_split_quote_and_note(raw, quote, note):
    assert wq._split_quote_and_note(raw) == (quote, note)


WIKITEXT = """
== Zitate mit Quellenangabe ==
* "Ein hinreichend langes Zitat mit Quelle" - ''Ein Werk, 1959''
* "Ein zweites Zitat das lang genug ist"
* kurz

== Zitate über die Person ==
* "Dieses Zitat stammt von jemand anderem und zaehlt nicht"

== Weblinks ==
* [http://example.org Eine Seite]
"""


def test_parse_wikitext_extracts_quotes_and_notes():
    items = wq.parse_wikitext(WIKITEXT, "Jemand")
    assert [i.lines[0] for i in items] == [
        "Ein hinreichend langes Zitat mit Quelle",
        "Ein zweites Zitat das lang genug ist",
    ]
    assert items[0].note == "Ein Werk, 1959"
    assert items[1].note == ""


def test_parse_wikitext_skips_about_and_link_sections():
    texts = [i.lines[0] for i in wq.parse_wikitext(WIKITEXT, "Jemand")]
    assert not any("jemand anderem" in t for t in texts)
    assert not any("Eine Seite" in t for t in texts)


def test_parse_wikitext_marks_items_atomic():
    assert all(i.atomic for i in wq.parse_wikitext(WIKITEXT, "Jemand"))


def test_parse_wikitext_drops_too_short_and_too_long():
    text = "== Quotes ==\n* tiny\n* " + "x" * 500 + "\n* " + "y" * 50
    items = wq.parse_wikitext(text, "Jemand")
    assert len(items) == 1
    assert items[0].lines[0] == "y" * 50


def test_sub_bullet_becomes_note_of_preceding_quote():
    text = ("== Quotes ==\n"
            "* A quote long enough to survive the filter\n"
            "** ''The Book'', 1925\n")
    items = wq.parse_wikitext(text, "Jemand")
    assert items[0].note == "The Book, 1925"


def test_english_about_heading_is_skipped():
    text = ("== Quotes about him ==\n"
            "* Something said by another person entirely\n")
    assert wq.parse_wikitext(text, "Jemand") == []


def quotes(wikitext, title):
    return [(i.lines[0], i.note) for i in wq.parse_wikitext(wikitext, title)]


def test_subsections_of_an_about_section_are_skipped_too():
    """Each author quoted about the subject gets a subsection of their own."""
    text = ("== Quotes ==\n* A quote by the subject, long enough\n"
            "== Quotes about Ada ==\n=== Charles Babbage ===\n"
            "* Something Babbage said about her, long enough\n"
            "== Later ==\n* Another quote by the subject herself\n")
    assert [q for q, _ in quotes(text, "Ada Lovelace")] == [
        "A quote by the subject, long enough", "Another quote by the subject herself"]


@pytest.mark.parametrize("heading", [
    "Misattributed", "See also", "External links", "References",
])
def test_english_sections_not_by_the_subject_are_skipped(heading):
    text = f"== {heading} ==\n* Words this subject never said at all\n"
    assert quotes(text, "Ada Lovelace") == []


FRENCH = """
== Citations ==
=== ''Œuvres choisies'' ===
{{Citation|Si l’on poursuit une onde lumineuse à la vitesse de la lumière,
on se trouve face à un champ [[onde|d’ondes]] indépendant du temps.}}
{{Réf Livre|titre=Science, éthique, philosophie|auteur=Albert Einstein|page=14}}

{{citation|citation=Une autre citation, avec un modèle {{w|imbriqué}} dedans.}}
== Citations rapportées ==
{{Citation|Une citation rapportée par un témoin de l’époque.}}
== Citations sur Albert Einstein ==
{{Citation|Une phrase de quelqu’un d’autre au sujet d’Einstein.}}
== Citations le concernant ==
=== Gustave Flaubert ===
{{citation|citation=Flaubert parle de lui, pas l’inverse.}}
== Voir aussi ==
* [[w:Albert Einstein|Article Wikipédia]] sur le physicien
"""


def test_french_citation_templates_and_headings():
    assert [q for q, _ in quotes(FRENCH, "Albert Einstein")] == [
        ("Si l’on poursuit une onde lumineuse à la vitesse de la lumière, "
         "on se trouve face à un champ d’ondes indépendant du temps."),
        "Une autre citation, avec un modèle dedans.",
        "Une citation rapportée par un témoin de l’époque.",
    ]


RUSSIAN = """
== Цитаты ==
{{Q|[[Математика]] — наиболее совершенный способ водить самого себя за нос.|Оригинал=Mathematik ist…|Автор=«Геометрия и опыт», 1921}}
=== О себе ===
{{Q|Я не обладаю особым талантом, я лишь страстно любопытен.}}
=== О [[наука|науке]] и учёных ===
{{Q|Наука без религии хрома, религия без науки слепа.|Автор=речь, 1941}}
== Об Эйнштейне ==
{{Q|Это сказал о нём кто-то совсем другой.}}
== Примечания ==
{{примечания}}
"""


def test_russian_q_templates_keep_topics_and_skip_sections_about_him():
    assert quotes(RUSSIAN, "Альберт Эйнштейн") == [
        ("Математика — наиболее совершенный способ водить самого себя за нос.",
         "«Геометрия и опыт», 1921"),
        ("Я не обладаю особым талантом, я лишь страстно любопытен.", ""),
        ("Наука без религии хрома, религия без науки слепа.", "речь, 1941"),
    ]


def test_russian_section_about_him_matches_an_inflected_name():
    text = ("== Цитаты ==\n{{Q|Всё счастливые семьи похожи друг на друга.}}\n"
            "== О Льве Толстом ==\n{{Q|Это сказал о Толстом кто-то другой.}}\n")
    assert [q for q, _ in quotes(text, "Лев Николаевич Толстой")] == [
        "Всё счастливые семьи похожи друг на друга."]


DUTCH = """
{{Citaat
| tekst = Over het geheel is schrijven voor publiek iets indecents.
| bron = {{aut|Eduard Douwes Dekker}}, ''Brief aan Mimi'', 29 juli 1863.
| opmerking =
}}
== Citaten over Multatuli ==
{{Citaat
| tekst = Iemand anders schreef dit over hem.
}}
"""


def test_dutch_citaat_template_gives_text_and_source():
    assert quotes(DUTCH, "Multatuli") == [
        ("Over het geheel is schrijven voor publiek iets indecents.",
         "Brief aan Mimi, 29 juli 1863."),
    ]


@pytest.mark.parametrize("wikitext,title", [
    (("== Citas ==\n* «Una cita propia que es suficientemente larga».<ref>Libro</ref>\n"
      "== Citas sobre Einstein ==\n* «Algo que otro dijo de Einstein»\n"
      "== Véase también ==\n* [[Física]] y otras ciencias\n"), "Albert Einstein"),
    (("== Citazioni di Dante Alighieri ==\n*Una citazione propria abbastanza lunga.\n"
      "== Citazioni su Dante Alighieri ==\n=== Giosuè Carducci ===\n"
      "*Carducci su Dante, non Dante.\n"
      "== Bibliografia ==\n*Un libro con un titolo lungo\n"), "Dante Alighieri"),
    (("== Outros ==\n* \"Uma citação própria e longa o bastante.\"\n"
      "== Sobre ==\n* \"Alguém falando sobre o poeta.\"\n"
      "== Mal atribuídas ==\n* \"Uma frase que ele nunca disse.\"\n"), "Fernando Pessoa"),
    (("== A ==\n* Własny cytat, wystarczająco długi.\n** Źródło: książka\n"
      "== Cytaty błędnie przypisywane Einsteinowi ==\n* Tego nigdy nie powiedział.\n"
      "== O Albercie Einsteinie ==\n* Ktoś inny o nim mówi.\n"
      "== Zobacz też ==\n* [[fizyka]] i inne nauki\n"), "Albert Einstein"),
])
def test_bullet_editions_keep_only_the_subjects_own_quotes(wikitext, title):
    assert len(quotes(wikitext, title)) == 1


def test_quotes_of_exactly_15_and_400_characters_are_kept():
    text = "== Quotes ==\n* " + "a" * 14 + "\n* " + "b" * 15 + "\n* " + "c" * 400 + "\n* " + "d" * 401
    assert [len(q) for q, _ in quotes(text, "X")] == [15, 400]


def test_an_unclosed_quote_template_ends_the_page():
    text = "== Цитаты ==\n{{Q|Цитата, у которой нет конца шаблона\n* not read as a bullet\n"
    assert quotes(text, "X") == [("Цитата, у которой нет конца шаблона * not read as a bullet", "")]


def test_fetch_raises_on_api_error(monkeypatch, fake_response):
    from hyprmuse.sources.base import SourceError
    monkeypatch.setattr(wq, "get", lambda *a, **k: fake_response(
        {"error": {"info": "page not found"}}))
    with pytest.raises(SourceError, match="page not found"):
        wq.SOURCE.fetch("en:Nobody")


def test_fetch_builds_subject_with_licence(monkeypatch, fake_response):
    monkeypatch.setattr(wq, "get", lambda *a, **k: fake_response(
        {"parse": {"wikitext": {"*": WIKITEXT}}}))
    subject = wq.SOURCE.fetch("de:Jemand")
    assert subject.name == "Jemand"
    assert subject.lang == "de"
    assert subject.url == "https://de.wikiquote.org/wiki/Jemand"
    assert len(subject.items) == 2
    assert subject.attribution["license"] == "CC BY-SA 4.0"
