"""Evaluate on the held-out AI-written test sets.

  python scripts/evaluate.py                                   # rules only (no model needed)
  python scripts/evaluate.py --model models/ctx               # + context model, two-tier decision
  python scripts/evaluate.py --model models/ctx --llm-cache results/llm-hard-subset.json
                                                               # + replay the recorded Gemma answers
  python scripts/evaluate.py --model models/ctx --llm-url http://127.0.0.1:8080/v1/chat/completions
                                                               # + ask a running llama.cpp server (slow on CPU)

Test sets (never used for training or for writing rules, but see the caveats in data/README.md):
  data/test/blind-ctx-2.json   100 severe + 200 normal conversations, each tagged with a type
  data/test/blind-test-2.json  120 severe + 200 normal single lines
--exclude-train-overlap drops test items whose judged line also appears word for word in the training data.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kcm.decide import decide, needs_llm  # noqa: E402
from kcm.rules import evidence  # noqa: E402


def norm(s):
    return re.sub(r'\s+', '', s.split(': ', 1)[-1] if re.match(r'^\S+: ', s) else s).lower()


def train_messages():
    seen = set()
    for f in glob.glob(os.path.join(ROOT, 'data', 'train', '*.json')):
        for v in json.load(open(f, encoding='utf-8')).values():
            for it in v:
                seen.add(norm(it if isinstance(it, str) else it['msg']))
    return seen


def load_sets(exclude):
    ctx = json.load(open(os.path.join(ROOT, 'data', 'test', 'blind-ctx-2.json'), encoding='utf-8'))
    one = json.load(open(os.path.join(ROOT, 'data', 'test', 'blind-test-2.json'), encoding='utf-8'))
    skip = train_messages() if exclude else set()
    items = []      # (set, label, type, index, prev, msg)
    for lab in ('severe', 'normal'):
        for i, x in enumerate(ctx[lab]):
            if norm(x['msg']) not in skip:
                items.append(('blind-ctx-2', lab, x['type'], i, x['prev'], x['msg']))
        for i, t in enumerate(one[lab]):
            if norm(t) not in skip:
                items.append(('blind-test-2', lab, 'single line', i, [], 'P: ' + t))
    return items


def table(rows, cols):
    w = [max(len(str(r[i])) for r in rows + [cols]) for i in range(len(cols))]
    out = ['| ' + ' | '.join(str(c).ljust(w[i]) for i, c in enumerate(cols)) + ' |',
           '|' + '|'.join('-' * (x + 2) for x in w) + '|']
    out += ['| ' + ' | '.join(str(c).ljust(w[i]) for i, c in enumerate(r)) + ' |' for r in rows]
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', help='context model directory (scripts/train.py output)')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--llm-cache', help='recorded LLM answers (results/llm-hard-subset.json)')
    ap.add_argument('--llm-url', help='live llama.cpp endpoint; asks only the lines the pipeline would send')
    ap.add_argument('--exclude-train-overlap', action='store_true')
    ap.add_argument('--out', help='write per-item results as JSON')
    a = ap.parse_args()

    items = load_sets(a.exclude_train_overlap)
    texts = [m.split(': ', 1)[-1] for *_, m in items]
    ev = [evidence(t) for t in texts]
    P = [None] * len(items)
    if a.model:
        from kcm.context_model import ContextModel
        t0 = time.time()
        P = ContextModel(a.model, threads=a.threads).score([(pv, m) for *_, pv, m in items])
        print('scored %d items in %.0f s (%.0f ms per item, %d threads)\n'
              % (len(items), time.time() - t0, (time.time() - t0) * 1000 / len(items), a.threads))
    D = [decide(t, p, e) for t, p, e in zip(texts, P, ev)]

    groups = collections.OrderedDict()
    for n, (s, lab, ty, *_rest) in enumerate(items):
        groups.setdefault((s, lab, ty), []).append(n)
    rows = []
    for (s, lab, ty), ns in groups.items():
        r = [s, lab, ty, len(ns), sum(1 for n in ns if ev[n].rule)]
        if a.model:
            r += [sum(1 for n in ns if P[n] >= 0.5), sum(1 for n in ns if P[n] >= 0.9),
                  sum(1 for n in ns if D[n].tier == 'auto'), sum(1 for n in ns if D[n].tier == 'review')]
        rows.append(r)
    for s in ('blind-ctx-2', 'blind-test-2'):
        for lab in ('severe', 'normal'):
            sub = [r for r in rows if r[0] == s and r[1] == lab]
            if len(sub) > 1:
                rows.append([s, lab, 'all'] + [sum(r[i] for r in sub) for i in range(3, len(sub[0]))])
    cols = ['set', 'label', 'type', 'n', 'rule hit']
    if a.model:
        cols += ['P>=0.5', 'P>=0.9', 'auto', 'review']
    rows.sort(key=lambda r: (r[0], r[1] != 'severe', r[2] == 'all'))
    print(table(rows, cols))
    print('\nsevere rows: higher is better. normal rows: every count is a false alarm (auto) or extra review work.')

    result = {'items': [{'set': s, 'label': lab, 'type': ty, 'index': i, 'p': None if p is None else round(p, 4),
                         'rule': e.rule, 'tier': d.tier, 'reason': d.reason}
                        for (s, lab, ty, i, _, _), p, e, d in zip(items, P, ev, D)]}

    if a.model and (a.llm_cache or a.llm_url):
        cache = {}
        if a.llm_cache:
            doc = json.load(open(a.llm_cache, encoding='utf-8'))
            cache = {(x['label'], x['index']): x for x in doc['items']}
        llm = None
        if a.llm_url:
            from kcm.llm import LLMJudge
            llm = LLMJudge(a.llm_url)
        sub = [n for n, it in enumerate(items) if it[0] == 'blind-ctx-2' and (it[1], it[3]) in cache] if cache else \
              [n for n, it in enumerate(items) if it[0] == 'blind-ctx-2']
        stats = collections.Counter()
        for n in sub:
            s, lab, ty, i, pv, m = items[n]
            stats[(lab, 'n')] += 1
            if D[n].tier == 'auto':
                stats[(lab, 'auto')] += 1
                continue
            if not needs_llm(D[n], P[n], ev[n]):
                continue
            stats[(lab, 'sent')] += 1
            if llm:
                v = llm.judge(pv, m)
                stats[(lab, 'llm two-step')] += v['punish']
                continue
            x = cache[(lab, i)]
            stats[(lab, 'llm confirm only')] += x['confirm'] != 'pass'
            if x['screen'] is None:
                stats[(lab, 'screen missing')] += 1
            else:
                stats[(lab, 'llm two-step')] += x['screen'] != 'N' and x['confirm'] != 'pass'
        keys = ['n', 'auto', 'sent', 'llm confirm only', 'llm two-step', 'screen missing'] if cache else \
               ['n', 'auto', 'sent', 'llm two-step']
        print('\nblind-ctx-2 %s: context model + LLM second look' % ('hard subset (215)' if cache else 'all'))
        print(table([[lab] + [stats[(lab, k)] for k in keys] for lab in ('severe', 'normal')], ['label'] + keys))
        print('punished = auto + llm. "sent" = lines the pipeline hands to the LLM (review, P>=0.2 or a weak clue).')
        result['llm'] = {'%s %s' % k: v for k, v in stats.items()}

    if a.out:
        json.dump(result, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
