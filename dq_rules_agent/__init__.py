"""DQ Rules Agent: profile a dataset, then generate data quality rules from the profile."""
from .profiler import profile_dataframe
from .rules import suggest_rules, Rule
from .validator import validate

__all__ = ["profile_dataframe", "suggest_rules", "Rule", "validate"]
__version__ = "0.1.0"
