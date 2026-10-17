import unittest

from kcm.normalize import clean, decompose, eng2han, engkey, hangul_only, jamo, light, squeeze, words


class Jamo(unittest.TestCase):
    def test_syllables_split(self):
        self.assertEqual(jamo('병신'), 'ㅂㅕㅇㅅㅣㄴ')

    def test_compound_letters_split(self):
        self.assertEqual(decompose('뷁'), 'ㅂㅞㄺ')
        self.assertEqual(jamo('뷁'), 'ㅂㅜㅔㄹㄱ')
        self.assertEqual(jamo('ㅄ'), 'ㅂㅅ')

    def test_non_hangul_kept(self):
        self.assertEqual(jamo('a1!'), 'a1!')


class Clean(unittest.TestCase):
    def test_fullwidth_and_case(self):
        self.assertEqual(clean('ＡＢＣ'), 'abc')

    def test_runs_cut_to_two(self):
        self.assertEqual(clean('ㅋㅋㅋㅋㅋ'), 'ㅋㅋ')

    def test_compatibility_jamo_survive_nfkc(self):
        self.assertEqual(clean('ㅅㅂ'), 'ㅅㅂ')

    def test_squeeze_drops_digits_symbols_spaces(self):
        self.assertEqual(squeeze('병1신 새.끼'), '병신새끼')

    def test_words_keeps_single_spaces(self):
        self.assertEqual(words('병~신~아  꺼져!!'), '병신아 꺼져')

    def test_hangul_only(self):
        self.assertEqual(hangul_only('ㅅ.ㅂ!!'), 'ㅅㅂ')


class Keyboard(unittest.TestCase):
    def test_english_mode_rebuilt(self):
        self.assertEqual(eng2han('qudtlsdk'), '병신아')
        self.assertEqual(eng2han('dkssud'), '안녕')

    def test_english_words_untouched(self):
        for w in ('hello', 'tpaccept', 'QUDTLSDK', 'abc'):
            self.assertEqual(eng2han(w), w)

    def test_engkey_gives_jamo(self):
        self.assertEqual(engkey('qudtlsdk').strip(), jamo('병신아'))
        self.assertEqual(engkey('ab 12').strip(), '')

    def test_light(self):
        self.assertEqual(light('병.신 qudtlsdk'), '병신 병신아')
        self.assertEqual(light('철 64개 줄게'), '철 64개 줄게')


if __name__ == '__main__':
    unittest.main()
