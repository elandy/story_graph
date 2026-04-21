import spacy


_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def count_character_mentions(text: str) -> int:
    doc = _get_nlp()(text)

    characters = set()

    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG"}:
            characters.add(ent.text.lower())

    for token in doc:
        if token.pos_ == "PROPN":
            characters.add(token.text.lower())

    return len(characters)

def has_character_interaction(text: str, min_characters: int = 2) -> bool:
    if '"' in text or "“" in text:
        return True

    return count_character_mentions(text) >= min_characters
