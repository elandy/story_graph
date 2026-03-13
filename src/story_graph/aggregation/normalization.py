import re

PRONOUN_MAP = {
    "i": "narrator",
    "me": "narrator",
    "my": "narrator",
}

def normalize_name(name: str) -> str:
    name = name.lower()

    # remove articles
    name = re.sub(r"^(the|a|an)\s+", "", name)

    # remove punctuation
    name = re.sub(r"[^\w\s]", "", name)

    name = name.strip()

    if name in PRONOUN_MAP:
        return PRONOUN_MAP[name]

    return name