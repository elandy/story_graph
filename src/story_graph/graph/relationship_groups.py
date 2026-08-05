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
        "friend", "acquaintance", "classmate", "colleague", "teammate", "roommate",
        "neighbor", "ally", "rival",
        "enemy", "nemesis", "betrayer", "victim",
    },
    "romantic": {
        "romantic_interest", "lover", "fiance", "ex_lover", "unrequited_love",
    },
    "family": {
        "parent", "child", "grandparent", "grandchild", "sibling",
        "aunt", "uncle", "niece", "nephew", "cousin",
        "step_parent", "step_child",
        "spouse", "ex_spouse", "guardian", "ward",
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

# Color palette by relationship group, tuned to the Story Graph Studio
# "Threadbound" theme (ink page, gold thread, wax-seal accents) and picked
# so each group stays distinguishable against the dark network background.
RELATIONSHIP_GROUP_COLORS = {
    "social": "#a3792f",                # gold thread — the everyday ties
    "romantic": "#b1496a",              # wine rose
    "family": "#4f8f68",                # verdigris green
    "professional_authority": "#5b74b0",  # slate indigo
    "professional_employment": "#8863ab",  # plum
    "professional_education": "#4fa3a3",   # teal
    "professional_service": "#a9754a",     # umber
    "professional_covert": "#a1402e",      # wax-seal vermillion
}

DEFAULT_RELATION_COLOR = "#9a8f7d"  # muted taupe for unknown/uncategorized


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