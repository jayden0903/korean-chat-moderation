import unittest

from kcm.context_model import encode, split_line


class Encode(unittest.TestCase):
    def test_speakers_become_letters(self):
        ctx, target = encode(['Player01: 안녕', 'Player02: ㅎㅇ Player01'], 'Player01: qudtlsdk')
        self.assertEqual(ctx, 'A: 안녕 / B: ㅎㅇ a')     # names in text -> the speaker's letter (lower-cased by light())
        self.assertEqual(target, 'A: 병신아')

    def test_name_inside_a_longer_word_is_kept(self):
        self.assertEqual(encode(['Bob: hi'], 'Amy: Bobby 왔어'), ('A: hi', 'B: bobby 왔어'))

    def test_only_last_five_lines(self):
        ctx, target = encode(['U%d: line %d' % (i, i) for i in range(8)], 'Q: ok')
        self.assertEqual(ctx, 'A: line 3 / B: line 4 / C: line 5 / D: line 6 / E: line 7')
        self.assertEqual(target, 'F: ok')

    def test_no_context(self):
        self.assertEqual(encode([], 'P: 철 64개 줄게'), ('', 'A: 철 64개 줄게'))

    def test_split_line(self):
        self.assertEqual(split_line('no speaker'), ('?', 'no speaker'))
        self.assertEqual(split_line('Player1: a: b'), ('Player1', 'a: b'))


if __name__ == '__main__':
    unittest.main()
