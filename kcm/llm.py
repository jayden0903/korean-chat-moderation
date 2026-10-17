"""Second look by a local LLM (any llama.cpp-compatible server; measured with Gemma-4 26B-A4B IQ4_XS on CPU).

Only lines the rules or the context model are unsure about get here (about 0.15% of real chat).
Two steps, because generating a reason costs most of the time on a CPU:
  screen()   one output letter, constrained by a grammar (F/C/S/H = punish as family_insult / targeted_curse /
             slur / sexual_harassment, N = pass). About 3 s.
  confirm()  only when screen() says punish: the same question again, answered as JSON with a target and a
             one-sentence reason. Punish only when both agree. About 10 s more.
advertising() and title() are single-letter checks for other-server promotion and for user-chosen titles.

The prompts are in Korean on purpose: the model reads Korean slang better when the policy is written in Korean.
Nothing here calls an external service; the URL is a local llama.cpp server (llama-server --jinja).
"""
import json
import re
import time
import urllib.request

SYSTEM = '''너는 한국 마인크래프트 생존 서버의 채팅 감시 담당이다. 유저는 대부분 10대이고 초성·오타·은어·영타(qudtlsdk=병신아)·글자 사이 기호로 욕을 숨기기도 한다.
마지막 줄 하나만 판정한다. 앞 줄들은 상황 파악용이다. 앞 줄에 다른 사람이 한 욕은 마지막 줄의 책임이 아니다.

처벌(아래 넷 중 하나이고, 채팅의 다른 플레이어를 향한 것):
- 패드립: 상대의 부모·가족을 모욕하거나 조롱(돌아가신 가족 조롱, 엄마가 몸 판다는 암시, 부모가 버렸다는 조롱 등). 욕 단어가 없어도 뜻이 그러면 처벌.
- 심한 쌍욕: 상대에게 퍼붓는 병신아, 씨발놈아, 개새끼야, 미친년아 수준.
- 비하: 장애·인종·국적·종교·출신으로 상대를 깎아내림(장애인 새끼, 짱깨, 테러리스트 취급 등).
- 성희롱: 상대의 몸·성에 대한 말, 사진 요구, 성적 제안.
통과:
- 몹·동물·주민·렉·물건·자기 자신에게 한 욕, 혼잣말 욕(아 ㅅㅂ, 크리퍼 개새끼).
- 가벼운 놀림과 무례함(바보, 허접, 쫄보, 잼민이, 초딩, 꺼져, 닥쳐, 지랄 ㅋㅋ, 노답), 게임 속 위협(죽인다, 목 딴다).
- 욕을 신고하거나 인용하는 말, 욕하지 말라는 말, 평범한 대화.
돌려 말한 모욕도 속뜻으로 판단한다. 예:
- (앞: "우리 아빠 택시 해") "밤에 손님 태우는 게 아빠만은 아니겠지 ㅋㅋ 엄마도?" → 처벌, 패드립(엄마가 몸 판다는 암시)
- (앞: "할아버지 입원하셨어") "빨리 가시라고 해 ㅋㅋ" → 처벌, 패드립(가족 죽음 조롱)
- (앞: "나 청각장애 있어") "그래서 말귀를 못 알아먹는구나 ㅋㅋ" → 처벌, 비하
- (앞: "엔더맨이 블록 훔쳐감") "저 병신 또 들고 튀네" → 통과(몹)
- (앞: "너 왜 내 템 먹음") "먼저 주운 사람이 임자지 쫄보야" → 통과(가벼운 놀림)
욕 단어가 없어도 위처럼 속뜻이 분명하면 처벌하고, 정말 애매하면 통과.'''

KINDS = {'패드립': 'family_insult', '쌍욕': 'targeted_curse', '비하': 'slur', '성희롱': 'sexual_harassment'}
LETTER = {'F': 'family_insult', 'C': 'targeted_curse', 'S': 'slur', 'H': 'sexual_harassment', 'N': None}

CONFIRM_SCHEMA = {'type': 'object', 'properties': {
    '대상': {'type': 'string', 'enum': ['다른 플레이어', '몹·사물·렉', '자기 자신', '없음']},
    '이유': {'type': 'string'},
    '판정': {'type': 'string', 'enum': ['처벌', '통과']},
    '종류': {'type': 'string', 'enum': ['패드립', '쌍욕', '비하', '성희롱', '없음']}},
    'required': ['대상', '이유', '판정', '종류']}

AD_HINT = re.compile(r'(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:kr|com|net|xyz|me|gg|io|org|kro|pe)\b'
                     r'|\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b|discord\.gg|디코|디스코드|주소|아이피|섭 ?주|서버 ?주')

TITLE_SYSTEM = ('너는 마인크래프트 서버의 서포터 칭호(모든 이용자에게 보이는 짧은 문자열)를 검사한다. 욕설·비속어(초성·영타·기호 끼워넣기 포함), '
                '성적 표현, 혐오·차별, 특정인 비하, 현실 위협, 광고·다른 서버 홍보, 개인정보, 운영진(관리자·운영자·스태프·GM·공식) 사칭이 '
                '하나라도 있으면 R, 전혀 없으면 Y. 평범한 단어·게임 용어·별명·가벼운 장난은 Y.')


def _user(prev, msg, tail):
    return '앞 줄:\n' + ('\n'.join(prev) if prev else '(없음)') + '\n\n판정할 마지막 줄:\n' + msg + tail


class LLMJudge:
    """url: an OpenAI-compatible chat endpoint of llama.cpp, e.g. http://127.0.0.1:8080/v1/chat/completions.
    home: how players should refer to this server in the advertising check (name or address), optional.
    allowed_servers: servers players may invite others to without it counting as advertising
    (e.g. public PvP practice servers); matched case-insensitively before the LLM is asked."""

    def __init__(self, url, timeout=120, home=None, allowed_servers=()):
        self.url = url
        self.timeout = timeout
        self.home = home
        self.allowed = [a for a in allowed_servers if a]
        self.allowed_rx = (re.compile('|'.join(re.escape(a).replace(r'\ ', r'\s*') for a in self.allowed), re.I)
                           if self.allowed else None)

    def _post(self, body):
        body.setdefault('temperature', 0)
        body.setdefault('cache_prompt', True)           # the long system prompt stays in the KV cache
        body.setdefault('chat_template_kwargs', {'enable_thinking': False})
        req = urllib.request.Request(self.url, json.dumps(body).encode(), {'Content-Type': 'application/json'})
        t = time.time()
        r = json.load(urllib.request.urlopen(req, timeout=self.timeout))
        return r['choices'][0]['message']['content'].strip(), round(time.time() - t, 1), r.get('usage', {})

    def screen(self, prev, msg):
        """-> (category or None, seconds). One output token."""
        tail = '\n\n답은 글자 하나: F=패드립 처벌, C=쌍욕 처벌, S=비하 처벌, H=성희롱 처벌, N=통과'
        c, s, _ = self._post({'messages': [{'role': 'system', 'content': SYSTEM},
                                           {'role': 'user', 'content': _user(prev, msg, tail)}],
                              'max_tokens': 2, 'grammar': 'root ::= [FCSHN]'})
        return LETTER.get(c[:1]), s

    def confirm(self, prev, msg):
        """-> dict(punish, category, target, reason, seconds, usage). A one-sentence reason in Korean."""
        c, s, usage = self._post({'messages': [{'role': 'system', 'content': SYSTEM},
                                               {'role': 'user', 'content': _user(prev, msg, '\n\n이유는 한 문장으로 짧게.')}],
                                  'max_tokens': 160,
                                  'response_format': {'type': 'json_schema',
                                                      'json_schema': {'name': 'v', 'schema': CONFIRM_SCHEMA}}})
        try:
            v = json.loads(c)
        except ValueError:
            v = {'판정': '통과', '종류': '없음', '대상': '없음', '이유': 'unparsable answer: ' + c[:80]}
        punish = v.get('판정') == '처벌'
        return {'punish': punish, 'category': KINDS.get(v.get('종류')) if punish else None,
                'target': v.get('대상'), 'reason': v.get('이유', ''), 'seconds': s, 'usage': usage}

    def judge(self, prev, msg):
        """screen, then confirm only if the screen says punish. -> dict(punish, category, reason, seconds)."""
        cat, s1 = self.screen(prev, msg)
        if not cat:
            return {'punish': False, 'category': None, 'reason': 'screen: pass', 'seconds': s1}
        v = self.confirm(prev, msg)
        v['seconds'] = round(s1 + v['seconds'], 1)
        if not v['punish']:
            v['reason'] = 'screen said %s, confirm passed: %s' % (cat, v['reason'])
        return v

    def advertising(self, prev, msg):
        """Is the last line promoting another server? Allowed servers never count."""
        text = msg.split(': ', 1)[-1]
        if self.allowed_rx and self.allowed_rx.search(text):
            return False
        home = ('이 서버(%s) 주소 안내' % self.home) if self.home else '이 서버 주소 안내'
        allowed = ('허용된 서버 이야기(%s, 오라고 해도 통과), ' % ', '.join(self.allowed)) if self.allowed else ''
        system = SYSTEM.split('\n처벌(')[0] + (
            '\n지금은 타 서버 홍보만 판정한다. 처벌: 이 서버가 아닌 다른 마인크래프트 서버의 주소·IP·디스코드를 알리거나, '
            '다른 서버로 오라·가자·옮기자고 권유하거나, 다른 서버 인원을 모집함(서버 이름이 가려지거나 은어여도 같음).\n'
            '통과: 다른 서버를 권유 없이 언급·비교·회상·질문, ' + home + ', ' + allowed
            + '광고 신고·인용, 서버와 무관한 링크.')
        c, _, _ = self._post({'messages': [{'role': 'system', 'content': system},
                                           {'role': 'user', 'content': _user(prev, msg, '\n\n답은 글자 하나: A=타 서버 홍보 처벌, N=통과')}],
                              'max_tokens': 2, 'grammar': 'root ::= [AN]'})
        return c[:1] == 'A'

    def title(self, text):
        """-> (approve, reason) for a short user-chosen title shown to everyone."""
        c, _, _ = self._post({'messages': [{'role': 'system', 'content': TITLE_SYSTEM},
                                           {'role': 'user', 'content': '칭호: 「' + text[:60] + '」\n답은 글자 하나: Y=허용, R=거절'}],
                              'max_tokens': 2, 'grammar': 'root ::= [YR]'})
        ok = c[:1] == 'Y'
        return ok, '' if ok else 'not clearly acceptable'


def has_ad_hint(text):
    """Cheap gate: only lines with an address, IP, invite or 'server address' wording get the advertising question."""
    return bool(AD_HINT.search(text))
