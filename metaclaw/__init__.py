"""
MetaClaw — Conversation RL with Tinker LoRA + OpenClaw-style data collection.

Integrates:
  - OpenClaw online dialogue RL data collection (FastAPI proxy)
  - Tinker cloud LoRA training (replaces SLIME/Megatron)
  - SkillRL skill bank retrieval and skill evolution
"""

from .config import MetaClawConfig
from .data_formatter import ConversationSample, batch_to_datums, compute_advantages
from .api_server import MetaClawAPIServer
from .rollout import AsyncRolloutWorker
from .prm_scorer import PRMScorer
from .skill_manager import SkillManager
from .skill_evolver import SkillEvolver
from .trainer import MetaClawTrainer

__all__ = [
    "MetaClawConfig",
    "ConversationSample",
    "batch_to_datums",
    "compute_advantages",
    "MetaClawAPIServer",
    "AsyncRolloutWorker",
    "PRMScorer",
    "SkillManager",
    "SkillEvolver",
    "MetaClawTrainer",
]
