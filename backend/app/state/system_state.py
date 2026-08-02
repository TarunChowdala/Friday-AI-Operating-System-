"""Host system status snapshot."""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SystemState:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    online: bool = True
    extras: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "online": self.online,
            **self.extras,
        }
