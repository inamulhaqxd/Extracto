import uuid

from sqlalchemy import JSON, TypeDecorator


class GUID(TypeDecorator):
    """Portable UUID column — stored as string on SQLite, native UUID on PG."""
    impl = JSON
    cache_ok = True

    def __init__(self, **kwargs):
        super().__init__()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return uuid.UUID(value)
        return value


PortableJSON = JSON
PortableUUID = GUID
