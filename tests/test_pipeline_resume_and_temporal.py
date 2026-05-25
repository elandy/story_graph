import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from story_graph.aggregation.character_registry import CharacterRegistry
from story_graph.aggregation.relationships import aggregate_relationships
from story_graph.aggregation.sentiments import aggregate_sentiments
from story_graph.chunking.splitter import chunk_paragraphs, estimate_text_tokens
from story_graph.extraction.checkpoint import load_checkpoint, write_checkpoint
from story_graph.extraction.models import ExtractionResult, Relationship, RelationshipType, Sentiment, SentimentType
from story_graph.extraction.pipeline import annotate_temporal_positions, process_chunks
from story_graph.graph.relationship_groups import get_relation_group


class TemporalNormalizationTests(unittest.TestCase):
    def test_relationship_type_supports_specific_family_roles(self):
        relationship = Relationship(
            source="Vernon Dursley",
            target="Harry Potter",
            relation=RelationshipType.uncle,
            evidence="Uncle Vernon",
        )

        self.assertEqual(relationship.relation, RelationshipType.uncle)
        self.assertEqual(get_relation_group(relationship.relation.value), "family")

    def test_relationship_groups_include_new_social_and_family_types(self):
        self.assertEqual(get_relation_group(RelationshipType.classmate.value), "social")
        self.assertEqual(get_relation_group(RelationshipType.teammate.value), "social")
        self.assertEqual(get_relation_group(RelationshipType.roommate.value), "social")
        self.assertEqual(get_relation_group(RelationshipType.aunt.value), "family")
        self.assertEqual(get_relation_group(RelationshipType.nephew.value), "family")
        self.assertEqual(get_relation_group(RelationshipType.cousin.value), "family")
        self.assertEqual(get_relation_group(RelationshipType.fiance.value), "romantic")

    def test_annotate_temporal_positions_uses_exclusive_end_positions(self):
        chunk = {
            "text": "Opening line.\n\nThe friendship ends here.",
            "start_index": 10,
        }
        result = ExtractionResult(
            characters=[],
            relationships=[
                Relationship(
                    source="Alice",
                    target="Bob",
                    relation=RelationshipType.friend,
                    evidence="The friendship ends here.",
                    ends_here=True,
                )
            ],
            sentiments=[
                Sentiment(
                    source="Alice",
                    target="Bob",
                    sentiment=SentimentType.trust,
                    evidence="Opening line.",
                    ends_here=True,
                )
            ],
        )

        normalized = annotate_temporal_positions(result, chunk)

        self.assertEqual(normalized.relationships[0].position, 11)
        self.assertEqual(normalized.relationships[0].end_position, 12)
        self.assertEqual(normalized.sentiments[0].position, 10)
        self.assertEqual(normalized.sentiments[0].end_position, 11)


class ProcessChunksResumeTests(unittest.IsolatedAsyncioTestCase):
    def test_chunk_paragraphs_respects_the_token_budget(self):
        paragraphs = [
            "Alice enters the station.",
            "Bob watches the monitors.",
            "They argue about the mission timeline.",
        ]
        max_tokens = (
            estimate_text_tokens(paragraphs[0]) +
            estimate_text_tokens(paragraphs[1]) + 1
        )

        chunks = chunk_paragraphs(
            paragraphs,
            max_tokens=max_tokens,
            max_paragraphs=0,
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["start_index"], 0)
        self.assertEqual(chunks[0]["end_index"], 2)
        self.assertEqual(chunks[1]["start_index"], 2)
        self.assertLessEqual(chunks[0]["token_estimate"], max_tokens)

    async def test_process_chunks_reuses_checkpointed_results(self):
        chunks = [
            {"text": "Alpha paragraph.", "start_index": 0},
            {"text": "Beta paragraph.", "start_index": 1},
        ]
        first_result = annotate_temporal_positions(
            ExtractionResult(
                characters=[],
                relationships=[
                    Relationship(
                        source="Alice",
                        target="Bob",
                        relation=RelationshipType.friend,
                        evidence="Alpha paragraph.",
                    )
                ],
                sentiments=[],
            ),
            chunks[0],
        )
        second_result = ExtractionResult(
            characters=[],
            relationships=[
                Relationship(
                    source="Alice",
                    target="Bob",
                    relation=RelationshipType.friend,
                    evidence="Beta paragraph.",
                    ends_here=True,
                )
            ],
            sentiments=[],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_path = Path(temp_dir) / "checkpoint.json"
            write_checkpoint(checkpoint_path, chunks, [first_result])

            with patch(
                "story_graph.extraction.pipeline.extract_relationships",
                new=AsyncMock(return_value=second_result),
            ) as mock_extract, patch("builtins.input", return_value="y"):
                results = await process_chunks(chunks, checkpoint_path=checkpoint_path)

            self.assertEqual(len(results), 2)
            mock_extract.assert_awaited_once_with(text="Beta paragraph.")

            saved_results = load_checkpoint(checkpoint_path, chunks)
            self.assertEqual(len(saved_results), 2)
            self.assertEqual(saved_results[0].relationships[0].position, 0)
            self.assertEqual(saved_results[1].relationships[0].position, 1)
            self.assertEqual(saved_results[1].relationships[0].end_position, 2)

    async def test_process_chunks_retries_transient_extraction_errors(self):
        chunks = [{"text": "Alpha paragraph.", "start_index": 0}]
        result = ExtractionResult(
            characters=[],
            relationships=[
                Relationship(
                    source="Alice",
                    target="Bob",
                    relation=RelationshipType.friend,
                    evidence="Alpha paragraph.",
                )
            ],
            sentiments=[],
        )
        attempts = 0
        sleep_calls = []

        async def fake_extract(*, text: str):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary outage")
            return result

        async def fake_sleep(delay: float):
            sleep_calls.append(delay)

        results = await process_chunks(
            chunks,
            confirm_continue=lambda _remaining: True,
            rate_limit_every=0,
            max_retries=2,
            retry_backoff_base_seconds=1.5,
            retry_backoff_max_seconds=10.0,
            extractor=fake_extract,
            sleep_fn=fake_sleep,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(attempts, 2)
        self.assertEqual(sleep_calls, [1.5])

    async def test_process_chunks_batches_multiple_chunks_into_one_request(self):
        chunks = [
            {"text": "Alpha paragraph.", "start_index": 0},
            {"text": "Beta paragraph.", "start_index": 1},
        ]
        batch_calls = []

        async def fake_batch_extract(texts: list[str]):
            batch_calls.append(list(texts))
            return [
                ExtractionResult(
                    characters=[],
                    relationships=[
                        Relationship(
                            source="Alice",
                            target="Bob",
                            relation=RelationshipType.friend,
                            evidence=text,
                        )
                    ],
                    sentiments=[],
                )
                for text in texts
            ]

        async def fail_single_extract(*, text: str):
            raise AssertionError(f"single-chunk extractor should not be used for batched chunks: {text}")

        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_path = Path(temp_dir) / "checkpoint.json"
            results = await process_chunks(
                chunks,
                checkpoint_path=checkpoint_path,
                confirm_continue=lambda _remaining: True,
                rate_limit_every=0,
                batch_size=2,
                extractor=fail_single_extract,
                batch_extractor=fake_batch_extract,
            )

            saved_results = load_checkpoint(checkpoint_path, chunks)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(saved_results), 2)
        self.assertEqual(batch_calls, [["Alpha paragraph.", "Beta paragraph."]])
        self.assertEqual(saved_results[0].relationships[0].position, 0)
        self.assertEqual(saved_results[1].relationships[0].position, 1)

    async def test_process_chunks_spreads_requests_across_the_rate_window(self):
        chunks = [
            {"text": "Alpha paragraph.", "start_index": 0},
            {"text": "Beta paragraph.", "start_index": 1},
        ]
        clock = {"now": 0.0}
        sleep_calls = []

        async def fake_extract(*, text: str):
            return ExtractionResult(
                characters=[],
                relationships=[
                    Relationship(
                        source="Alice",
                        target="Bob",
                        relation=RelationshipType.friend,
                        evidence=text,
                    )
                ],
                sentiments=[],
            )

        async def fake_sleep(delay: float):
            sleep_calls.append(delay)
            clock["now"] += delay

        await process_chunks(
            chunks,
            confirm_continue=lambda _remaining: True,
            rate_limit_every=5,
            rate_limit_seconds=60.0,
            batch_size=1,
            extractor=fake_extract,
            now_fn=lambda: clock["now"],
            sleep_fn=fake_sleep,
        )

        self.assertEqual(sleep_calls, [12.0])


class AggregationTemporalTests(unittest.TestCase):
    def test_aggregate_relationships_repairs_same_chunk_end_positions(self):
        registry = CharacterRegistry()
        registry.add("Alice")
        registry.add("Bob")

        result = ExtractionResult(
            characters=[],
            relationships=[
                Relationship(
                    source="Alice",
                    target="Bob",
                    relation=RelationshipType.friend,
                    evidence="They split up.",
                    position=5,
                    end_position=5,
                )
            ],
            sentiments=[],
        )

        aggregated = aggregate_relationships([result], registry)
        self.assertEqual(aggregated[0]["end_position"], 6)

    def test_aggregate_sentiments_repairs_same_chunk_end_positions(self):
        registry = CharacterRegistry()
        registry.add("Alice")
        registry.add("Bob")

        result = ExtractionResult(
            characters=[],
            relationships=[],
            sentiments=[
                Sentiment(
                    source="Alice",
                    target="Bob",
                    sentiment=SentimentType.trust,
                    evidence="The trust died there.",
                    position=7,
                    end_position=7,
                )
            ],
        )

        aggregated = aggregate_sentiments([result], registry)
        self.assertEqual(aggregated[0]["end_position"], 8)
