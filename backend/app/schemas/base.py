from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Serialised with camelCase keys (matches frontend/src/types/index.ts)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class SnakeModel(BaseModel):
    """Serialised with snake_case keys (health + upload/validation envelopes, as the frontend expects)."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
