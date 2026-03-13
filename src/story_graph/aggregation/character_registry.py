from collections import defaultdict
from story_graph.aggregation.normalization import normalize_name


class CharacterRegistry:

    def __init__(self):
        self.characters = {}
        self.aliases = defaultdict(set)

    def add(self, name: str):

        key = normalize_name(name)

        if key not in self.characters:
            self.characters[key] = name

        self.aliases[key].add(name)

        return key