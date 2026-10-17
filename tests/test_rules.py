"""Synthetic examples written for these tests (not taken from any chat log)."""
import unittest

from kcm.rules import evidence, rule

SEVERE = {
    'family_insult': ['니애미 뒤졌냐', '느1금1마', 'ㄴㄱㅁ', '애미 없는 놈', '니네 엄마 도망갔다며'],
    'targeted_curse': ['병~신~아 꺼져', '야 이 개새끼야', '씨이발 새끼야 닥쳐', 'ㅄ아 조용히 해', 'qudtlsdk',
                       'tlqkfshadk', '미친년아 조용히 해', '너 진짜 병신이냐'],
    'slur': ['장애인 새끼가 왜 겜함', '짱깨새끼 꺼져', '너 장애인이냐'],
    'sexual_harassment': ['섹스하자', '가슴 사진 보내봐'],
}
PASS = ['아 ㅅㅂ 용암', '크리퍼 개새끼', '엄마가 밥 먹으래', '땅따먹기 하자', '보지마 스포임', '자지 말고 빨리 와',
        '시발점이 어디야', '죽어라 좀비', '고아원 만들자 주민', '씨발 또 렉', '철 64개 줄게']


class Severe(unittest.TestCase):
    def test_categories(self):
        for cat, lines in SEVERE.items():
            for line in lines:
                with self.subTest(line=line):
                    self.assertEqual(rule(line), cat)

    def test_reason_names_the_view(self):
        self.assertTrue(evidence('ㄴㄱㅁ').reason.startswith('chosung'))
        self.assertTrue(evidence('qudtlsdk').reason.startswith('engkey'))


class Pass(unittest.TestCase):
    def test_ordinary_swearing_and_lookalikes(self):
        for line in PASS:
            with self.subTest(line=line):
                self.assertIsNone(rule(line))


class Cancelled(unittest.TestCase):
    def test_about_oneself(self):
        e = evidence('나 병신새끼인듯 또 죽음')
        self.assertIsNone(e.rule)
        self.assertEqual((e.reason, e.weak), ('about oneself', 'targeted_curse'))

    def test_talking_about_abuse(self):
        e = evidence('욕하지 마 병신아라고 하면 신고함')
        self.assertIsNone(e.rule)
        self.assertEqual(e.reason, 'talks about abuse')
        self.assertEqual(e.weak, 'targeted_curse')     # still worth a second look

    def test_year(self):
        self.assertEqual(evidence('2016년은 병신년이었지').reason, 'the year 병신년')

    def test_game_phrase(self):
        self.assertEqual(evidence('사과 따먹자').reason, 'game phrase')

    def test_benign_exclamation(self):
        self.assertTrue(evidence('엄마야 ㅋㅋ').benign)

    def test_weak_clue_only(self):
        e = evidence('너 사귀는 사람 있어?')
        self.assertIsNone(e.rule)
        self.assertEqual(e.weak, 'clue')


class KnownLimits(unittest.TestCase):
    """Rules are deliberately broad; these hits are why a rule alone never punishes (see decide.py)."""

    def test_quote_with_vocative_still_hits(self):
        self.assertEqual(rule('걔가 나한테 병신아 라고 했어요 신고합니다'), 'targeted_curse')

    def test_your_mom_without_spaces(self):
        self.assertEqual(rule('니 엄마 요리 잘하시네'), 'family_insult')


if __name__ == '__main__':
    unittest.main()
