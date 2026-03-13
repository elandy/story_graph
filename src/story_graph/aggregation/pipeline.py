from story_graph.aggregation.character_registry import CharacterRegistry
from story_graph.aggregation.relationships import aggregate_relationships
from story_graph.aggregation.sentiments import aggregate_sentiments


def aggregate(results):

    registry = CharacterRegistry()

    for result in results:
        for c in result.characters:
            registry.add(c.name)

    relationships = aggregate_relationships(results)
    sentiments = aggregate_sentiments(results)

    return registry, relationships, sentiments