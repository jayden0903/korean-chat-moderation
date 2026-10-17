"""LLM client against a stub llama.cpp server on 127.0.0.1 (no model needed)."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from kcm.decide import Judge
from kcm.llm import LLMJudge


class Stub(BaseHTTPRequestHandler):
    answers = {}          # grammar (or 'json') -> content
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        Stub.seen.append(body)
        key = body.get('grammar') or 'json'
        out = {'choices': [{'message': {'content': Stub.answers[key]}}], 'usage': {'prompt_tokens': 700}}
        b = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b)


class FakeModel:
    def score1(self, prev, msg):
        return 0.5


class LLMClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = 'http://127.0.0.1:%d/v1/chat/completions' % cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Stub.seen.clear()

    def test_screen_then_confirm(self):
        Stub.answers = {'root ::= [FCSHN]': 'F',
                        'json': json.dumps({'대상': '다른 플레이어', '이유': '가족 조롱', '판정': '처벌', '종류': '패드립'})}
        v = LLMJudge(self.url).judge(['Player1: 할아버지 입원하셨어'], 'Player2: 빨리 가시라고 해 ㅋㅋ')
        self.assertEqual((v['punish'], v['category']), (True, 'family_insult'))
        screen, confirm = Stub.seen
        self.assertEqual(screen['max_tokens'], 2)
        self.assertEqual(confirm['response_format']['type'], 'json_schema')
        self.assertEqual(screen['chat_template_kwargs'], {'enable_thinking': False})

    def test_screen_pass_skips_confirm(self):
        Stub.answers = {'root ::= [FCSHN]': 'N'}
        v = LLMJudge(self.url).judge([], 'Player2: 크리퍼 개새끼')
        self.assertFalse(v['punish'])
        self.assertEqual(len(Stub.seen), 1)

    def test_confirm_disagrees(self):
        Stub.answers = {'root ::= [FCSHN]': 'C',
                        'json': json.dumps({'대상': '몹·사물·렉', '이유': '몹', '판정': '통과', '종류': '없음'})}
        self.assertFalse(LLMJudge(self.url).judge([], 'P: 저 병신 또 들고 튀네')['punish'])

    def test_unparsable_confirm_passes(self):
        Stub.answers = {'root ::= [FCSHN]': 'S', 'json': 'not json'}
        self.assertFalse(LLMJudge(self.url).judge([], 'P: x')['punish'])

    def test_pipeline_and_advertising(self):
        Stub.answers = {'root ::= [FCSHN]': 'N', 'root ::= [AN]': 'A'}
        r = Judge(FakeModel(), LLMJudge(self.url, home='play.example.com'))([], 'Player2: mc.example.net 으로 다 넘어와')
        self.assertEqual((r['tier'], r['punish'], r['advertising']), ('llm_pass', False, True))
        self.assertIn('play.example.com', Stub.seen[-1]['messages'][0]['content'])

    def test_title(self):
        Stub.answers = {'root ::= [YR]': 'R'}
        self.assertEqual(LLMJudge(self.url).title('관리자')[0], False)


if __name__ == '__main__':
    unittest.main()
