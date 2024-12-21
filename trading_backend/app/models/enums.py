"""Enums used throughout the application."""
from enum import Enum

class TradingDirection(str, Enum):
    LONG = "long"
    SHORT = "short"

class MarginType(str, Enum):
    ISOLATED = "isolated"
    CROSS = "cross"

class AccountStage(str, Enum):
    INITIAL = "INITIAL"        # 100U - 1000U
    GROWTH = "GROWTH"         # 1000U - 10000U
    ADVANCED = "ADVANCED"     # 10000U - 100000U
    PROFESSIONAL = "PROFESSIONAL"  # 100000U - 1000000U
    EXPERT = "EXPERT"         # 1000000U+ (1亿U target)

    def __lt__(self, other):
        stages = [
            AccountStage.INITIAL,
            AccountStage.GROWTH,
            AccountStage.ADVANCED,
            AccountStage.PROFESSIONAL,
            AccountStage.EXPERT
        ]
        return stages.index(self) < stages.index(other)

    def __gt__(self, other):
        stages = [
            AccountStage.INITIAL,
            AccountStage.GROWTH,
            AccountStage.ADVANCED,
            AccountStage.PROFESSIONAL,
            AccountStage.EXPERT
        ]
        return stages.index(self) > stages.index(other)

class AccountStageTransition(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
