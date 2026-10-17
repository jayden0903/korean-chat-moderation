"""Normalisation for Korean game chat.

Players hide abuse with cheap tricks: separators between letters ("병.신"), digits ("병1신"), full-width
characters, filler syllables ("씨이발"), bare consonants ("ㅂㅅ"), and Korean typed with the keyboard left in
English mode ("qudtlsdk" is what you get when you type 병신아 on a 2-set keyboard in English mode).

The rules match on *jamo* strings (every syllable split into its consonant and vowel letters), so one pattern
covers all spellings that share the same letters. Compound vowels and double final consonants are split as well
("ㅘ" -> "ㅗㅏ", "ㅄ" -> "ㅂㅅ"), because people type them either way.
"""
import re
import unicodedata

CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG = [''] + list('ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ')

# compound vowels / double final consonants -> their parts
SPLIT = {'ㅘ': 'ㅗㅏ', 'ㅙ': 'ㅗㅐ', 'ㅚ': 'ㅗㅣ', 'ㅝ': 'ㅜㅓ', 'ㅞ': 'ㅜㅔ', 'ㅟ': 'ㅜㅣ', 'ㅢ': 'ㅡㅣ',
         'ㄳ': 'ㄱㅅ', 'ㄵ': 'ㄴㅈ', 'ㄶ': 'ㄴㅎ', 'ㄺ': 'ㄹㄱ', 'ㄻ': 'ㄹㅁ', 'ㄼ': 'ㄹㅂ', 'ㄽ': 'ㄹㅅ',
         'ㄾ': 'ㄹㅌ', 'ㄿ': 'ㄹㅍ', 'ㅀ': 'ㄹㅎ', 'ㅄ': 'ㅂㅅ'}
# the reverse, for rebuilding syllables from keyboard input
JOIN_VOWEL = {'ㅗㅏ': 'ㅘ', 'ㅗㅐ': 'ㅙ', 'ㅗㅣ': 'ㅚ', 'ㅜㅓ': 'ㅝ', 'ㅜㅔ': 'ㅞ', 'ㅜㅣ': 'ㅟ', 'ㅡㅣ': 'ㅢ'}
JOIN_FINAL = {'ㄱㅅ': 'ㄳ', 'ㄴㅈ': 'ㄵ', 'ㄴㅎ': 'ㄶ', 'ㄹㄱ': 'ㄺ', 'ㄹㅁ': 'ㄻ', 'ㄹㅂ': 'ㄼ', 'ㄹㅅ': 'ㄽ',
              'ㄹㅌ': 'ㄾ', 'ㄹㅍ': 'ㄿ', 'ㄹㅎ': 'ㅀ', 'ㅂㅅ': 'ㅄ'}

# Korean 2-set (Dubeolsik) layout: the letter a key produces when the keyboard is in Korean mode
KEY = dict(zip('qwertyuiopasdfghjklzxcvbnmQWERTOP',
               'ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔㅁㄴㅇㄹㅎㅗㅓㅏㅣㅋㅌㅊㅍㅠㅜㅡㅃㅉㄸㄲㅆㅒㅖ'))


def decompose(s):
    """Hangul syllables -> jamo (compound letters kept): '병신' -> 'ㅂㅕㅇㅅㅣㄴ'."""
    out = []
    for ch in s:
        c = ord(ch) - 0xAC00
        if 0 <= c < 11172:
            out += [CHO[c // 588], JUNG[c % 588 // 28], JONG[c % 28]]
        else:
            out.append(ch)
    return ''.join(out)


def jamo(s):
    """Hangul -> jamo with compound vowels and double finals split: '뷁' -> 'ㅂㅜㅔㄹㄱ'."""
    return ''.join(SPLIT.get(c, c) for c in decompose(s))


def clean(m):
    """NFKC (full-width -> ASCII), lower case, runs of 3+ equal characters cut to 2, at most 200 characters.
    Compatibility jamo (ㄱ..ㅣ) are kept as they are, because NFKC would turn them into conjoining jamo."""
    m = ''.join(ch if 'ㄱ' <= ch <= 'ㅣ' else unicodedata.normalize('NFKC', ch) for ch in m).lower()
    m = re.sub(r'(.)\1{2,}', r'\1\1', m)
    return m.strip()[:200]


def squeeze(m):
    """Letters only, no spaces, no digits: '병1신 새.끼' -> '병신새끼'."""
    return re.sub(r'[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣ]', '', clean(m)).translate(str.maketrans('', '', '0123456789'))


def words(m):
    """Like squeeze() but keeps single spaces, because some rules need the start of a word."""
    return re.sub(r' +', ' ', re.sub(r'[^a-z가-힣ㄱ-ㅎㅏ-ㅣ ]', '', clean(m))).strip()


def hangul_only(m):
    """Hangul syllables, bare jamo and spaces only; used for bare-consonant abbreviations (ㅅㅂ, ㄴㄱㅁ)."""
    return re.sub(r'[^가-힣ㄱ-ㅎ ]', '', clean(m))


def engkey(m):
    """Read every pure-letter token of 4+ characters as Korean typed in English mode and return its jamo.
    Other tokens become a space. 'qudtlsdk' -> 'ㅂㅕㅇㅅㅣㄴㅇㅏ' (병신아)."""
    out = []
    for tok in m.split():
        if re.fullmatch(r'[A-Za-z]{4,}', tok):
            out.append(''.join(SPLIT.get(KEY.get(c, KEY.get(c.lower(), c)), KEY.get(c, KEY.get(c.lower(), c)))
                               for c in tok))
        else:
            out.append(' ')
    return ' '.join(out)


def eng2han(tok):
    """Rebuild Hangul syllables from a token typed in English mode: 'qudtlsdk' -> '병신아'.
    The token is returned unchanged unless every key forms a complete, common (KS X 1001) syllable,
    so ordinary English words and usernames are left alone."""
    if not re.fullmatch(r'[a-zQWERTOP]{4,}', tok) or tok.isupper():
        return tok
    k = [KEY.get(c, KEY.get(c.lower())) for c in tok]
    if None in k:
        return tok
    out = []
    i, n = 0, len(k)
    while i < n:
        if k[i] not in CHO or i + 1 >= n or k[i + 1] not in JUNG:
            return tok
        c, v = k[i], k[i + 1]
        i += 2
        if i < n and v + k[i] in JOIN_VOWEL:
            v = JOIN_VOWEL[v + k[i]]
            i += 1
        jg = ''
        if i < n and k[i] in JONG and not (i + 1 < n and k[i + 1] in JUNG):
            jg = k[i]
            i += 1
            if i < n and jg + k[i] in JOIN_FINAL and not (i + 1 < n and k[i + 1] in JUNG):
                jg = JOIN_FINAL[jg + k[i]]
                i += 1
        out.append(chr(0xAC00 + CHO.index(c) * 588 + JUNG.index(v) * 28 + JONG.index(jg)))
    r = ''.join(out)
    try:
        r.encode('euc-kr')          # rare syllables are almost always a false reading
    except UnicodeEncodeError:
        return tok
    return r


def light(m):
    """The normalisation the context model sees: keyboard-typed words rebuilt, clean(), and up to two
    separator characters between Hangul letters removed ('병.신' -> '병신'). Spaces and meaning are kept."""
    m = ' '.join(eng2han(t) for t in m.split(' '))
    m = clean(m)
    return re.sub(r'(?<=[가-힣ㄱ-ㅣ])[\.\,@\*~_\-\^\d!]{1,2}(?=[가-힣ㄱ-ㅣ])', '', m)
