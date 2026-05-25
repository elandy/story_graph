import re

import spacy


INTERACTION_VERBS = {
    "ask", "call", "confront", "discuss", "embrace", "fight", "greet", "help",
    "hug", "ignore", "kiss", "look", "love", "marry", "meet", "reply", "rescue",
    "save", "see", "speak", "talk", "tease", "thank", "tell", "trust", "visit",
    "warn", "watch",
}
SPEECH_VERBS = {"say", "tell", "ask", "reply", "shout", "whisper"}
KINSHIP_HINTS = {
    "aunt", "uncle", "brother", "sister", "mother", "father", "parent", "guardian",
    "cousin", "nephew", "niece", "grandmother", "grandfather",
}
TITLE_PATTERN = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Professor|Captain|Colonel|Sir|Lady)\.?\s+[A-Z][a-z]+"
)


_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def count_character_mentions(text: str) -> int:
    return analyze_character_interaction(text)["character_mentions"]


def analyze_character_interaction(text: str) -> dict:
    doc = _get_nlp()(text)

    characters = set()
    named_people = set()
    speech_verbs = 0
    interaction_verbs = 0
    pronouns = 0

    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG"}:
            value = ent.text.strip().lower()
            characters.add(value)
            if ent.label_ == "PERSON":
                named_people.add(value)

    for token in doc:
        lemma = token.lemma_.lower()
        if token.pos_ == "PROPN":
            characters.add(token.text.lower())
        if lemma in SPEECH_VERBS:
            speech_verbs += 1
        if lemma in INTERACTION_VERBS:
            interaction_verbs += 1
        if token.lower_ in {"he", "she", "they", "him", "her", "them"}:
            pronouns += 1

    lowered = text.lower()
    title_mentions = len(TITLE_PATTERN.findall(text))
    dialogue_markers = text.count('"') // 2 + lowered.count("“") + lowered.count("”")
    kinship_hints = sum(lowered.count(hint) for hint in KINSHIP_HINTS)

    return {
        "character_mentions": len(characters),
        "named_people": len(named_people),
        "dialogue_markers": dialogue_markers,
        "speech_verbs": speech_verbs,
        "interaction_verbs": interaction_verbs,
        "pronouns": pronouns,
        "kinship_hints": kinship_hints,
        "title_mentions": title_mentions,
    }


def has_character_interaction(text: str, min_characters: int = 2) -> bool:
    stats = analyze_character_interaction(text)

    if stats["character_mentions"] >= min_characters and (
        stats["interaction_verbs"] > 0
        or stats["speech_verbs"] > 0
        or stats["kinship_hints"] > 0
    ):
        return True

    if (
        stats["named_people"] >= min_characters
        and stats["dialogue_markers"] > 0
        and (stats["speech_verbs"] > 0 or stats["pronouns"] >= 2)
    ):
        return True

    if stats["title_mentions"] >= min_characters and stats["speech_verbs"] > 0:
        return True

    return False
