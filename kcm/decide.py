"""Two-tier decision.

  auto    the rules found a severe term AND the context model agrees (P >= 0.3), and it is not a curse at a
          mob or an object. Safe to act on without a person or an LLM.
  review  only one side is sure: the model alone (P >= 0.9) with no rule, a rule hit the model rejects
          (P < 0.3, e.g. quoting or a game context), or a curse that names a mob or object.
  pass    everything else.

With an LLM configured, every review line and every line with P >= 0.2 or a weak clue gets the two-step second
look (llm.LLMJudge.judge); its tiers are 'llm' (punish) and 'llm_pass'. Without a context model the rules still
run, but a rule hit can only reach 'review' (the model is what makes 'auto' safe).
"""
import re
from dataclasses import dataclass

from .llm import has_ad_hint
from .rules import evidence

AUTO_MIN = 0.3     # rule hit + model at least this -> auto
REVIEW_MIN = 0.9   # model alone at least this -> review
LLM_MIN = 0.2      # model at least this -> worth an LLM look

THING = re.compile('크리퍼|좀비|스켈|엔더|위더|몹|거미|팬텀|주민|돼지|닭|가디언|워든|드래곤|블레이즈|마녀|여우|늑대|고양이|파괴수|약탈자'
                   '|피글린|가스트|슬라임|렉|서버|인터넷|통신사|와이파이|컴퓨터|마우스|키보드')
YOU = re.compile(r'(?:^|\s)(?:너|니|넌|널|니가|네가|느그|니네|너네)(?:\s|$|[가는를도])')


@dataclass
class Decision:
    category: str      # suspected category ('context' = model only), or None
    tier: str          # 'auto' | 'review' | 'pass'
    reason: str


def decide(text, p, ev=None):
    """text: the judged line without speaker; p: context-model P(severe) or None when no model is loaded."""
    ev = ev or evidence(text)
    if ev.rule:
        if p is None:
            return Decision(ev.rule, 'review', 'rule %s (no context model loaded)' % ev.reason)
        if p < AUTO_MIN:
            return Decision(ev.rule, 'review', 'rule %s, but context model %.2f (context may excuse it)' % (ev.reason, p))
        if ev.rule == 'targeted_curse' and THING.search(text) and not YOU.search(text):
            return Decision(ev.rule, 'review', 'rule %s, may be aimed at a mob or object (%.2f)' % (ev.reason, p))
        return Decision(ev.rule, 'auto', 'rule %s + context model %.2f' % (ev.reason, p))
    if p is not None and p >= REVIEW_MIN:
        return Decision('context', 'review', 'context model %.2f (wording no rule lists)' % p)
    return Decision(None, 'pass', '')


def needs_llm(d, p, ev):
    if d.tier == 'auto':
        return False
    return d.tier == 'review' or (p is not None and p >= LLM_MIN) or bool(ev.weak)


class Judge:
    """rules -> optional context model -> optional local LLM for the uncertain lines."""

    def __init__(self, model=None, llm=None):
        self.model = model
        self.llm = llm

    def __call__(self, prev, msg, ad=None):
        """prev: up to 5 previous lines 'name: text'; msg: 'name: text'. -> dict.
        ad: None = ask the advertising question only when the line has an address/invite hint, True = always."""
        prev = list(prev)[-5:]
        text = msg.split(': ', 1)[-1]
        ev = evidence(text)
        p = self.model.score1(prev, msg) if self.model else None
        d = decide(text, p, ev)
        out = {'punish': d.tier == 'auto', 'category': d.category if d.tier != 'pass' else None, 'tier': d.tier,
               'reason': d.reason, 'p': None if p is None else round(p, 3), 'evidence': ev.as_dict()}
        if self.llm and needs_llm(d, p, ev):
            v = self.llm.judge(prev, msg)
            out['llm'] = v
            out.update(tier='llm' if v['punish'] else 'llm_pass', punish=v['punish'],
                       category=v['category'] if v['punish'] else out['category'], reason=v['reason'] or out['reason'])
        if self.llm and (ad or (ad is None and has_ad_hint(text))):
            out['advertising'] = self.llm.advertising(prev, msg)
        return out
