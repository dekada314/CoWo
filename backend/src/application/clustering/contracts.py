from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

CommunityName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
CommunitySummary = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class CommunityDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: CommunityName
    summary: CommunitySummary
