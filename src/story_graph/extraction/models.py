from enum import Enum

from pydantic import BaseModel, Field
from typing import List, Optional


class Character(BaseModel):
    name: str
    aliases: List[str]

class RelationshipType(str, Enum):
    unknown = "unknown"

    # social
    friend = "friend"
    acquaintance = "acquaintance"
    colleague = "colleague"
    neighbor = "neighbor"
    ally = "ally"
    rival = "rival"

    # antagonistic
    enemy = "enemy"
    nemesis = "nemesis"
    betrayer = "betrayer"
    victim = "victim"

    # family
    parent = "parent"
    child = "child"
    sibling = "sibling"
    spouse = "spouse"
    ex_spouse = "ex_spouse"
    guardian = "guardian"
    ward = "ward"

    # romance
    romantic_interest = "romantic_interest"
    lover = "lover"
    ex_lover = "ex_lover"
    unrequited_love = "unrequited_love"

    # mentorship / education
    mentor = "mentor"
    student = "student"
    teacher = "teacher"

    # hierarchy / work
    leader = "leader"
    subordinate = "subordinate"
    employer = "employer"
    employee = "employee"
    commander = "commander"
    soldier = "soldier"

    # protection / service
    protector = "protector"
    bodyguard = "bodyguard"
    servant = "servant"

    # political / strategic
    advisor = "advisor"
    patron = "patron"
    client = "client"

    # covert / intrigue
    spy = "spy"
    handler = "handler"
    informant = "informant"
    conspirator = "conspirator"
    blackmailer = "blackmailer"

class SentimentType(str, Enum):
    # positive attachment
    love = "love"
    affection = "affection"
    fondness = "fondness"

    # admiration / status
    admiration = "admiration"
    respect = "respect"

    # loyalty / alignment
    loyalty = "loyalty"
    devotion = "devotion"
    trust = "trust"

    # attraction
    attraction = "attraction"
    desire = "desire"

    # competitive emotions
    jealousy = "jealousy"
    envy = "envy"

    # negative interpersonal
    dislike = "dislike"
    resentment = "resentment"
    contempt = "contempt"
    hatred = "hatred"

    # threat perception
    fear = "fear"
    intimidation = "intimidation"
    suspicion = "suspicion"

    # moral emotions
    guilt = "guilt"
    pity = "pity"
    shame = "shame"

    # ambivalent / neutral
    indifference = "indifference"
    curiosity = "curiosity"

class Relationship(BaseModel):
    source: str
    target: str
    relation: RelationshipType
    evidence: str = Field(description="Exact text that implies the relationship")
    chapter: Optional[int] = None
    scene: Optional[int] = None
    position: Optional[int] = None
    end_position: Optional[int] = None

    def __str__(self):
        return f"{self.source} -> {self.target}: Relation: {self.relation.value}. Evidence: {self.evidence}. Position: {self.position}. End: {self.end_position}"


class Sentiment(BaseModel):
    source: str
    target: str
    sentiment: SentimentType
    evidence: str = Field(description="Exact text that implies the sentiment")
    chapter: Optional[int] = None
    scene: Optional[int] = None
    position: Optional[int] = None
    end_position: Optional[int] = None

    def __str__(self):
        return f"{self.source} -> {self.target}: Sentiment: {self.sentiment.value}. Evidence: {self.evidence}. Position: {self.position}. End: {self.end_position}"


class ExtractionResult(BaseModel):
    characters: List[Character]
    relationships: List[Relationship]
    sentiments: List[Sentiment]