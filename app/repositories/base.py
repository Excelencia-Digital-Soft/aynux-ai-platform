from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T], ABC):
    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    def create(self, entity: T) -> T:
        pass

    @abstractmethod
    def get_by_id(self, id: str) -> Optional[T]:
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        pass
