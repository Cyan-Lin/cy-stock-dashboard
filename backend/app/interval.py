from enum import Enum


class Interval(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
