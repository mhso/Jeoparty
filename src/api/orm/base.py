from typing import Any
from enum import Enum

from sqlalchemy.orm import DeclarativeBase, RelationshipDirection, reconstructor
from sqlalchemy.inspection import inspect

class Base(DeclarativeBase):
    def __init__(self, **kw: Any):
        self.registry.constructor(self, **kw)
        self.json = self._to_json()

    @reconstructor
    def init_on_load(self):
        self.json = self._to_json()

    @property
    def extra_fields(self):
        return {}

    def _serialize_value(self, value):
        if isinstance(value, Enum):
            return value.value

        return value

    def _to_json(self):
        json_data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        json_data.update(self.extra_fields)

        relationships = inspect(self.__class__).relationships
        for relationship in relationships:
            name = relationship.key
            if name in json_data:
                continue

            value = getattr(self, name)
            if relationship.direction in (RelationshipDirection.ONETOMANY, RelationshipDirection.MANYTOMANY):
                json_data[name] = [entry._to_json() for entry in value]

        return json_data
