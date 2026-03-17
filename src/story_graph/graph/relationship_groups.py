"""
Exclusion groups for relationship types.

Relations in the same group are mutually exclusive at a given story time
(e.g. friend vs enemy: only the "current" one is shown).
Relations in different groups can coexist (e.g. enemy and lover at the same time).
"""

# Group id -> set of relationship type values (strings) that exclude each other.
# Employer and leader are in different groups so both can show (e.g. Dumbledore
# as employer and as leader of Snape at chunk 0). Teacher/mentor in one group
# so only one "teaching" role per pair at a time (Snape vs Lucius as teacher).
RELATIONSHIP_EXCLUSION_GROUPS = {
    "social": {
        "friend", "acquaintance", "colleague", "neighbor", "ally", "rival",
        "enemy", "nemesis", "betrayer", "victim",
    },
    "romantic": {
        "romantic_interest", "lover", "ex_lover", "unrequited_love",
    },
    "family": {
        "parent", "child", "sibling", "spouse", "ex_spouse", "guardian", "ward",
    },
    "professional_authority": {
        "leader", "subordinate", "commander", "soldier",
    },
    "professional_employment": {
        "employer", "employee",
    },
    "professional_education": {
        "mentor", "student", "teacher",
    },
    "professional_service": {
        "protector", "bodyguard", "servant", "advisor", "patron", "client",
    },
    "professional_covert": {
        "spy", "handler", "informant", "conspirator", "blackmailer",
    },
}

# Color palette by relationship group (used for visualization)
RELATIONSHIP_GROUP_COLORS = {
    "social": "#2ca02c",  # green
    "romantic": "#e377c2",  # pink
    "family": "#ff7f0e",  # orange
    "professional_authority": "#1f77b4",  # blue
    "professional_employment": "#9467bd",  # purple
    "professional_education": "#17becf",  # cyan
    "professional_service": "#8c564b",  # brown
    "professional_covert": "#d62728",  # red
}

DEFAULT_RELATION_COLOR = "#7f7f7f"  # gray for unknown/uncategorized


def get_relation_group(relation_value: str) -> str:
    """Return the exclusion group id for a relationship type value.

    If the type is not in any group, return the relation value itself
    so it forms its own single-type group (does not exclude others).
    """
    for group_id, members in RELATIONSHIP_EXCLUSION_GROUPS.items():
        if relation_value in members:
            return group_id
    return relation_value


def get_relation_color(relation_value: str) -> str:
    """Return a hex color for a relationship type by mapping it to a group."""
    group = get_relation_group(relation_value)
    return RELATIONSHIP_GROUP_COLORS.get(group, DEFAULT_RELATION_COLOR)
