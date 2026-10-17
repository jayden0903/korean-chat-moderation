"""kcm: Korean chat moderation. Rules with evidence -> context model -> local LLM for the uncertain lines."""
from .decide import Judge, decide
from .rules import CATEGORIES, evidence, rule

__version__ = '0.5.0'
__all__ = ['Judge', 'decide', 'evidence', 'rule', 'CATEGORIES']
