import unittest

from kcm.decide import Judge, decide, needs_llm
from kcm.llm import LLMJudge, has_ad_hint
from kcm.rules import evidence


class Tiers(unittest.TestCase):
    def test_rule_and_model_agree(self):
        d = decide('야 이 개새끼야', 0.8)
        self.assertEqual((d.tier, d.category), ('auto', 'targeted_curse'))

    def test_model_rejects_rule_hit(self):
        self.assertEqual(decide('야 이 개새끼야', 0.1).tier, 'review')

    def test_curse_at_a_mob(self):
        self.assertEqual(decide('좀비 이 개새끼야', 0.9).tier, 'review')
        self.assertEqual(decide('너 좀비 같은 개새끼야', 0.9).tier, 'auto')     # aimed at "너"

    def test_model_alone(self):
        d = decide('그래서 말귀를 못 알아듣는구나', 0.95)
        self.assertEqual((d.tier, d.category), ('review', 'context'))
        self.assertEqual(decide('그래서 말귀를 못 알아듣는구나', 0.5).tier, 'pass')

    def test_no_model(self):
        self.assertEqual(decide('야 이 개새끼야', None).tier, 'review')
        self.assertEqual(decide('철 64개 줄게', None).tier, 'pass')

    def test_needs_llm(self):
        t = '철 64개 줄게'
        self.assertTrue(needs_llm(decide(t, 0.25), 0.25, evidence(t)))
        self.assertFalse(needs_llm(decide(t, 0.1), 0.1, evidence(t)))
        t = '너 사귀는 사람 있어?'
        self.assertTrue(needs_llm(decide(t, 0.05), 0.05, evidence(t)))


class FakeModel:
    def __init__(self, p):
        self.p = p

    def score1(self, prev, msg):
        return self.p


class FakeLLM:
    def __init__(self, punish):
        self.punish, self.calls = punish, 0

    def judge(self, prev, msg):
        self.calls += 1
        return {'punish': self.punish, 'category': 'family_insult' if self.punish else None,
                'reason': 'fake', 'seconds': 0.0}


class Pipeline(unittest.TestCase):
    def test_auto_skips_llm(self):
        llm = FakeLLM(False)
        r = Judge(FakeModel(0.8), llm)(['Player1: 왜'], 'Player2: 야 이 개새끼야')
        self.assertEqual((r['tier'], r['punish'], llm.calls), ('auto', True, 0))

    def test_uncertain_line_goes_to_llm(self):
        r = Judge(FakeModel(0.5), FakeLLM(True))([], 'Player2: 그래서 말귀를 못 알아듣는구나')
        self.assertEqual((r['tier'], r['punish'], r['category']), ('llm', True, 'family_insult'))
        r = Judge(FakeModel(0.5), FakeLLM(False))([], 'Player2: 그래서 말귀를 못 알아듣는구나')
        self.assertEqual((r['tier'], r['punish']), ('llm_pass', False))

    def test_rules_only(self):
        r = Judge()([], 'P: 야 이 개새끼야')
        self.assertEqual((r['tier'], r['punish'], r['p']), ('review', False, None))


class Advertising(unittest.TestCase):
    def test_hint(self):
        self.assertTrue(has_ad_hint('mc.example.com 들어와'))
        self.assertTrue(has_ad_hint('10.0.0.1:25565 ㄱㄱ'))
        self.assertFalse(has_ad_hint('다이아 몇개 있음?'))

    def test_allowed_server_never_asks_the_llm(self):
        llm = LLMJudge('http://127.0.0.1:9/unused', allowed_servers=['practice.example'])
        self.assertFalse(llm.advertising([], 'P: practice.example 가서 연습하자'))


if __name__ == '__main__':
    unittest.main()
