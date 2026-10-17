"""Command line: judge one line.

  python -m kcm.judge "line to judge" --prev "A: earlier line" --prev "B: later line"
                      [--speaker B] [--model DIR] [--llm-url URL] [--ad] [--json]

Without --model only the rules run (a rule hit is shown as 'review'). With --model the two-tier decision runs.
With --llm-url the uncertain lines also get the local LLM's second look.
"""
import argparse
import json
import sys

from .decide import Judge
from .rules import CATEGORIES


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m kcm.judge', description='Judge one Korean game-chat line.')
    ap.add_argument('text', help='the line to judge (without speaker name)')
    ap.add_argument('--prev', action='append', default=[], metavar='"NAME: TEXT"',
                    help='a previous chat line, oldest first; repeat up to 5 times')
    ap.add_argument('--speaker', default='P', help='speaker of the judged line (match a --prev name to link them)')
    ap.add_argument('--model', help='directory of a context model trained with scripts/train.py')
    ap.add_argument('--threads', type=int, default=4, help='CPU threads for the context model (default 4)')
    ap.add_argument('--llm-url', help='llama.cpp chat endpoint, e.g. http://127.0.0.1:8080/v1/chat/completions')
    ap.add_argument('--home', help='name or address of this server, for the advertising question')
    ap.add_argument('--allow-server', action='append', default=[], help='server players may invite to (repeatable)')
    ap.add_argument('--ad', action='store_true', help='always ask the advertising question (needs --llm-url)')
    ap.add_argument('--json', action='store_true', help='print the full result as JSON')
    a = ap.parse_args(argv)

    model = llm = None
    if a.model:
        from .context_model import ContextModel
        model = ContextModel(a.model, threads=a.threads)
    if a.llm_url:
        from .llm import LLMJudge
        llm = LLMJudge(a.llm_url, home=a.home, allowed_servers=a.allow_server)
    r = Judge(model, llm)(a.prev, '%s: %s' % (a.speaker, a.text), ad=True if a.ad else None)

    if a.json:
        json.dump(r, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    cat = r['category']
    label = '%s (%s)' % (cat, CATEGORIES[cat]) if cat in CATEGORIES else (cat or '-')
    print('verdict  : %s' % ('PUNISH' if r['punish'] else 'no action'))
    print('tier     : %s' % r['tier'])
    print('category : %s' % label)
    if r['p'] is not None:
        print('model P  : %.3f' % r['p'])
    if r['reason']:
        print('reason   : %s' % r['reason'])
    clues = {k: v for k, v in r['evidence'].items() if k not in ('rule', 'reason')}
    if clues:
        print('evidence : %s' % ', '.join(k if v is True else '%s=%s' % (k, v) for k, v in clues.items()))
    if 'llm' in r:
        print('llm      : %.1f s' % r['llm']['seconds'])
    if 'advertising' in r:
        print('advert.  : %s' % ('yes' if r['advertising'] else 'no'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
