from collections import defaultdict
from story_graph.aggregation.normalization import normalize_name


class CharacterRegistry:

    def __init__(self):
        self.characters = {}
        self.aliases = defaultdict(set)
        self._normalized_to_key = {}

    def add(self, name: str, aliases: list[str] | None = None):
        if aliases is None:
            aliases = []
        all_forms = {normalize_name(name)} | {normalize_name(a) for a in aliases}

        existing_key = None
        for form in all_forms:
            if form in self._normalized_to_key:
                existing_key = self._normalized_to_key[form]
                break

        if existing_key is not None:
            canonical_key = existing_key
            self.aliases[canonical_key].add(name)
            for a in aliases:
                self.aliases[canonical_key].add(a)
            for form in all_forms:
                self._normalized_to_key[form] = canonical_key
            return canonical_key

        canonical_key = normalize_name(name)
        self.characters[canonical_key] = name
        self.aliases[canonical_key].add(name)
        for a in aliases:
            self.aliases[canonical_key].add(a)
        for form in all_forms:
            self._normalized_to_key[form] = canonical_key
        return canonical_key

    def resolve(self, name: str) -> str:
        normalized = normalize_name(name)
        return self._normalized_to_key.get(normalized, normalized)