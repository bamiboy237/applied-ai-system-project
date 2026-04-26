"""base Tool class - defines the interface all tools must implement."""

from abc import ABC, abstractmethod
from typing import ClassVar

from codereview.tools.schema import ToolSchema


class Tool(ABC):
    schema: ClassVar[ToolSchema]

    @abstractmethod
    def execute(self, **kwargs: object) -> str:
        """Execute the tool and return a text response."""
        ...
