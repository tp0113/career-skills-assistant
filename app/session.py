"""The server-side identity. Tools read the employee id from here, never from the model."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    employee_id: str
