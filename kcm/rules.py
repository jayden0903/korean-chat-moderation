"""Rules with evidence.

Policy (what is punished): only severe abuse aimed at another player.
  family_insult      패드립   insulting or mocking someone's parents or family
  targeted_curse     쌍욕     heavy swearing thrown at a person (병신아, 씨발놈아, 개새끼야 ...)
  slur               비하     degrading someone for disability, race, nationality or origin
  sexual_harassment  성희롱   sexual remarks about a person, requests for photos, sexual offers
Ordinary swearing, swearing at mobs, lag or oneself, light teasing, slang and in-game threats ("죽인다") pass.

evidence(text) does not just answer yes/no. It collects clues and says why:
  TERM    a strong term in one of the categories, found on the jamo string, the jamo string without spaces,
          the keyboard-typed reading, or a bare-consonant abbreviation
  TARGET  the line is aimed at someone (2nd-person words, a vocative ending, a username, 닥쳐/꺼져 ...)
  SELF    the line is about the speaker ("나 ...", "내가 ...")
  QUOTE   the line talks *about* abuse (reporting it, quoting it, asking someone to stop)
  GAME    a mob, lag, the server or terrain is mentioned
and then lets the context cancel a hit (self-talk, quoting, the year 병신년 (2016), game phrases like 땅따먹기).
The lexicons below are the point of a moderation tool and are kept in full.
"""
import re
from dataclasses import dataclass, field

from .normalize import clean, engkey, hangul_only, jamo, squeeze, words

CATEGORIES = {'family_insult': '패드립', 'targeted_curse': '쌍욕', 'slur': '비하', 'sexual_harassment': '성희롱'}

# filler syllables people insert between letters: 씨이발, 병으응신
F = '(?:ㅇㅡㅇ?|ㅇㅣ|ㅡ)*'


def L(*ws):
    """jamo regex for a set of words; filler syllables allowed between syllables."""
    return '(?:' + '|'.join(F.join(re.escape(jamo(ch)) for ch in w) for w in ws) + ')'


B = '(?:^| )'      # start of a word (only checked on the spaced view)
FAMILY = ('(?:' + L('엄마', '어매', '애미', '에미', '앰이', '느금', '니애미', '느그매', '어미', '어머니', '할매', '할머니',
                    '할배', '아빠', '애비', '아버지', '부모', '가족', '누나', '여동생') + '|ㄴㄱㅁ)')
YOURS = L('니', '너', '느그', '니네', '너네', '너희', '네')
BAD = L('창녀', '창년', '뒤진', '뒤졌', '뒤짐', '뒤지', '걸레', '몸판', '몸팔', '화장했', '장례', '도망', '버렸', '버린',
        '없지', '없냐', '없잖', '죽었', '죽은', '바람')
CURSE = L('씨발', '시발', '씨바', '씨벌', '시벌', '씌발', '쓰발', '씹', '좆', '존나') + '|ㅆㅂ|ㅅㅂ'
HEAD = L('새끼', '새기', '새키', '쉐끼', '색기', '련', '년', '놈', '자식')
SLUR = L('외노자', '흑곤', '깜둥', '깜씨', '짱깨', '짱개', '쪽바리', '쪽발', '장애인', '장애', '정신병자', '저능아', '애자',
         '찐따', '동남아', '조선족', '틀딱', '거지', '고아', '호로', '엠창', '니거', '다운증후군', '자폐', '정박아', '병자')

RULES = [
    ('family_insult', FAMILY + '.{0,12}' + L('창녀', '창년', '뒤진', '뒤졌', '뒤짐', '걸레', '몸판', '몸팔', '화장했')),
    ('family_insult', L('창녀', '창년', '뒤진', '뒤졌', '걸레') + '.{0,6}' + FAMILY),
    ('family_insult', YOURS + ' ?' + FAMILY + '.{0,14}' + BAD),
    ('family_insult', FAMILY + ' ?' + L('없는', '죽은', '버린') + ' ?' + L('새끼', '놈', '년', '티', '주제', '애', '게')),
    ('family_insult', L('느금', '니애미', '니앰', '니엄')),
    ('family_insult', B + L('고아', '호로', '엠창', '느금마') + ' ?' + L('새끼', '년', '놈')),
    ('family_insult', L('느그', '니네') + ' ?' + L('어매', '애미', '에미', '애비')),
    ('targeted_curse', '(?:' + CURSE + ').{0,14}' + L('새끼야', '새기야', '놈아', '년아', '련아')),
    ('targeted_curse', '(?:' + CURSE + ').{0,3}(?:' + L('새끼', '련', '년', '놈아', '놈의') + ')'),
    ('targeted_curse', L('병신', '빙신', '븅신', '벙신', '병싄', '등신') + '(?:' + L('아', '새끼', '련', '년', '놈', '들아') + ')'),
    ('targeted_curse', '(?:' + L('야', '이', '니', '너') + ' ?' + L('개새') + '|'
     + L('개새끼야', '개새야', '개자식', '미친새끼야', '미친년아', '미친놈아', '씹새끼', '좆같은새끼', '개년', '개같은년',
         '개같은놈', '개같은새끼야') + ')'),
    ('targeted_curse', YOURS + '.{0,10}' + L('병신같은게', '병신이냐', '병신이지', '병신임', '병신새끼')),
    ('slur', SLUR + '.{0,3}(?:' + HEAD + '|' + L('야닥쳐', '닥쳐', '주제') + ')'),
    ('slur', L('닥쳐') + '.{0,3}' + L('찐따')),
    ('targeted_curse', L('걸레년', '창녀년', '창년', '걸레같은년', '씨발년', '미친년', '보지년')
     + '(?:' + L('아', '이지', '이네', '이냐', '들') + ')'),
    ('slur', YOURS + '.{0,6}' + L('장애인이지', '장애인이냐', '장애인임', '장애있', '정신병자', '저능아')),
    ('sexual_harassment', B + L('섹스', '쎅스', '쎅쓰', '섹쓰', '색스', '쎾쓰', '강간', '성폭행')),
    ('sexual_harassment', L('섹스') + '.{0,6}' + L('하자', '할래', '해줘', '하고싶', '머신')),
    ('sexual_harassment', L('따먹') + '(?:' + L('고싶', '는다', '자', '어버', '을게', '힌', '히고') + ')'),
    ('sexual_harassment', '(?:' + YOURS + '|' + FAMILY + ').{0,8}' + L('따먹')),
    ('sexual_harassment', B + L('보지', '자지', '봊이', '잦이') + '(?:' + L('가', '를', '에', '년', '털') + '(?: |$)| ?'
     + L('사진', '빨', '같은', '크', '작', '보여', '만지') + ')'),
    ('sexual_harassment', B + YOURS + ' ?' + L('보지', '자지', '젖', '가슴', '엉덩이', '빨통', '꼭지')
     + '(?! ?' + L('마', '말', '못', '않', '도') + ')'),
    ('sexual_harassment', L('가슴', '젖', '엉덩이', '알몸', '벗은', 'ㄱㅅ') + ' ?' + L('사진', '만지', '빨', '보여줘', '보내', '까봐')),
    ('sexual_harassment', L('빨아줘', '빨아라', '빨아봐', '박아줄', '박고싶', '뚫어줄', '신음소리', '벗어봐', '꼴린다', '꼴리네')),
]
RX = [(name, re.compile(p)) for name, p in RULES]

# bare-consonant abbreviations, checked first
CHOSUNG = [
    ('family_insult', re.compile('ㄴㄱㅁ|ㄴㅇㅁ|ㄴㄱㅇㅁ|ㅇㅁㅊㄴ')),
    ('targeted_curse', re.compile('(?:ㅆㅂ|ㅅㅂ)(?:ㄴ|ㄹ|ㅅㄲ)(?:아|ㅇ|$)|ㅆㅂㅅㄲ|ㅅㅂㅅㄲ|ㄱㅅㄲ|ㅁㅊ(?:ㄴ|ㄹ)(?:아|ㅇ)'
                                  '|(?:ㅂㅅ|ㅄ)(?:아|새끼|ㅅㄲ|들아|련|년)|ㅈㅇㅇ(?:새끼|ㅅㄲ|아)')),
    ('sexual_harassment', re.compile('ㅅㅅ ?(?:하자|할래|해봤|ㄱ|하고)|ㅂㅈ ?(?:사진|보여|ㄱ)|(?:너|니) ?ㄱㅅ')),
]

SELF = re.compile('^(?:' + L('나', '내가', '난', '나는', '제가', '저는') + ')')
QUOTE = re.compile(L('하지마', '하지말', '치지마', '그만', '욕하면', '욕은', '신고', '패드립', '부모욕', '라고', '이라는',
                     '래요', '랬', '욕함', '욕하'))
YEAR = re.compile(r'(\d{2,4}|올해|내년|작년|무슨|갑자)\s*년?.{0,6}병신년|병신년\s*(이었|이래|이라|에|은|도)')
GAME_PHRASE = re.compile('땅 ?따먹|사과|열매|과일|베리|당근|감자|수박|점령|유니섹스')
GAME_OBJECT = re.compile('크리퍼|좀비|스켈|엔더|위더|몹|거미|팬텀|용암|렉|서버|지형|주민|돼지|소 |닭|가디언|워든|드래곤|블레이즈')
TARGET = re.compile(r'(?:^|\s)(?:너|니|넌|널|니가|네가|느그|니네|너네|님|야)(?:\s|$|[가는를도])|[가-힣ㄱ-ㅎ](?:아|야)(?:\s|$)'
                    r'|[A-Za-z][A-Za-z0-9_]{3,15}|닥쳐|꺼져|해봐|보내|말해')
# words that are only a clue when aimed at someone (body, family, disability ...); they never punish on their own
CLUE = re.compile('가슴|젖|엉덩이|벗|사귀|처녀|야한|ㅅㅅ|ㅂㅈ|엄마|애미|아빠|부모|할머니|장애|고아|거지')
BENIGN = re.compile(r'^(엄마야|아빠야|니 ?거(야|임|지|다)?|니 ?꺼(야|임|지|다)?|네 ?거(야|임)?)[ㅋㅎ!?. ]*$')


@dataclass
class Evidence:
    rule: str = None           # punishable category, or None
    reason: str = None         # which view matched, or why a match was cancelled
    target: bool = False
    self_talk: bool = False
    game: bool = False
    quote: bool = False
    weak: str = None           # a cancelled category or 'clue': not punishable, but worth a second look
    benign: bool = False
    extra: dict = field(default_factory=dict)

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items() if k != 'extra' and v not in (None, False)}


def evidence(m):
    c = clean(m)
    sq = squeeze(m)
    w = words(m)
    j = jamo(w)
    j2 = j.replace(' ', '')
    e = Evidence(target=bool(TARGET.search(m)), self_talk=bool(SELF.match(j2)),
                 game=bool(GAME_OBJECT.search(c)), quote=bool(QUOTE.search(j2)))
    for name, rx in CHOSUNG:
        if rx.search(hangul_only(m)) or rx.search(sq):
            e.rule, e.reason = name, 'chosung ' + name
            break
    if not e.rule:
        views = [('', j), ('nospace ', j2), ('engkey ', jamo(engkey(m)))]
        for name, rx in RX:
            for tag, v in views:
                if tag == 'nospace ' and '(?:^| )' in rx.pattern:
                    continue        # word-start rules only make sense with spaces
                if v and rx.search(v):
                    e.rule, e.reason = name, tag + name
                    break
            if e.rule:
                break
    if e.rule:
        if e.self_talk and e.rule in ('targeted_curse', 'slur'):
            e.weak, e.rule, e.reason = e.rule, None, 'about oneself'
        elif e.quote and not e.target:
            e.weak, e.rule, e.reason = e.rule, None, 'talks about abuse'
        elif YEAR.search(c):
            e.rule, e.reason = None, 'the year 병신년'
        elif e.rule == 'sexual_harassment' and GAME_PHRASE.search(c):
            e.rule, e.reason = None, 'game phrase'
    elif CLUE.search(c) and e.target and not e.game:
        e.weak = 'clue'
    if BENIGN.match(c):
        e.weak, e.benign = None, True
    return e


def rule(m):
    """The punishable category the rules find in a line, or None."""
    return evidence(m).rule
