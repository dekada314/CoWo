from pydantic import BaseModel, ConfigDict, Field


class GraphCommunityView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    summary: str


class GraphDomainView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    summary: str
    community_id: str


class GraphConceptView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    summary: str
    domain_id: str
    card_count: int = Field(ge=1)


class GraphEdgeView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    weight: float = Field(ge=0)


class KnowledgeGraphView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    communities: list[GraphCommunityView]
    domains: list[GraphDomainView]
    concepts: list[GraphConceptView]
    edges: list[GraphEdgeView]


class GraphConceptNotFound(Exception):
    pass


class GraphUnavailable(Exception):
    pass
