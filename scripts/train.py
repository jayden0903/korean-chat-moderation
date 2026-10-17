"""Fine-tune KcELECTRA on (previous chat lines, judged line) pairs.

  python scripts/train.py --out models/ctx                          # synthetic data only
  python scripts/train.py --out models/ctx --negatives my-chat.txt  # + your own ordinary chat as negatives
  python scripts/train.py --dry-run                                 # build and count the examples, no training

Training data (all AI-written, see data/README.md): data/train/*.json. The test sets in data/test/ are never read.

--negatives: real chat from your own server is the best source of "normal" examples (the original model used
12,500 lines). It is optional and never shipped. Two formats:
  .txt    one line per row, 'name: text', oldest first; the 5 rows before a line are its context;
          an empty row starts a new conversation
  .jsonl  one object per row: {"prev": ["name: text", ...], "msg": "name: text"}
Lines the rules flag are skipped, because unlabelled chat may contain real abuse.

Recipe (round 3 of the original model): 2 epochs, batch 32, lr 3e-5 with linear warm-up/decay, weight decay 0.01,
class weights 1:3, label smoothing 0.05, max 160 tokens with the context truncated from the left.
With 12,500 real negatives this was 20,234 examples and 49 minutes on 44 CPU threads; synthetic-only is smaller.
"""
import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kcm.context_model import MAXLEN, MAXPREV, encode  # noqa: E402
from kcm.normalize import KEY, jamo  # noqa: E402
from kcm.rules import rule  # noqa: E402

BASE = 'beomi/KcELECTRA-base-v2022'
TRAIN = os.path.join(ROOT, 'data', 'train')


def load(name):
    return json.load(open(os.path.join(TRAIN, name + '.json'), encoding='utf-8'))


def text_of(line):
    return line.split(': ', 1)[-1]


def read_negatives(path, limit, rnd):
    out = []
    if path.endswith('.jsonl'):
        for row in open(path, encoding='utf-8'):
            if row.strip():
                d = json.loads(row)
                out.append((list(d.get('prev', []))[-MAXPREV:], d['msg']))
    else:
        window = []
        for row in open(path, encoding='utf-8'):
            row = row.rstrip('\n')
            if not row.strip():
                window = []
                continue
            if ': ' not in row:
                row = 'P: ' + row
            out.append((list(window), row))
            window = (window + [row])[-MAXPREV:]
    out = [(p, m) for p, m in out if len(text_of(m).strip()) > 1 and not rule(text_of(m))]
    rnd.shuffle(out)
    return out[:limit]


def build(negatives=None, neg_limit=12500, seed=11):
    rnd = random.Random(seed)
    X, Y = [], []

    def add(prev, msg, y):
        X.append((list(prev), msg))
        Y.append(y)

    sev, mild = [], []
    for f in ('train-a', 'train-b', 'train-c', 'blind-test'):
        d = load(f)
        sev += d['severe']
        mild += d['normal']
    conv = {f: load(f) for f in ('ctx-train-1', 'ctx-train-2', 'ctx-train-3', 'blind-ctx', 'mild-train')}
    flips = {f: load(f) for f in ('flip-train-a', 'flip-train-b')}
    neg = read_negatives(negatives, neg_limit, rnd) if negatives else []

    # harmless contexts to drop single lines into: synthetic normal conversations (+ your negatives)
    contexts = [it['prev'] for d in conv.values() for it in d['normal']]
    contexts += [it['normal_prev'] for d in flips.values() for it in d.get('pairs', [])]
    contexts += [p for p, _ in neg]
    contexts = [[x for x in c if not rule(text_of(x))] for c in contexts]
    harmless = [(it['prev'], it['msg']) for d in conv.values() for it in d['normal'] if not rule(text_of(it['msg']))]
    harmless += neg

    def placed(text):
        """a single line dropped into a harmless conversation (30%: no context)."""
        prev = [] if rnd.random() < 0.3 else rnd.choice(contexts)
        names = [x.split(': ')[0] for x in prev]
        spk = rnd.choice(names + ['Player%d' % rnd.randint(1, 99)]) if prev else 'Player1'
        return prev, '%s: %s' % (spk, text)

    sev_u = sorted(set(sev))
    for t in sev_u:
        add(*placed(t), 1)
        add([], 'P: ' + t, 1)
    for t in sorted(set(mild) - set(sev)):
        add(*placed(t), 0)
    for f in ('ctx-train-1', 'ctx-train-2', 'ctx-train-3'):
        for lab, y in (('severe', 1), ('normal', 0)):
            for it in conv[f][lab]:
                add(it['prev'], it['msg'], y)
                if y == 0 and rnd.random() < 0.3:
                    add([], it['msg'], 0)
    for p, m in neg:
        add(p, m, 0)
    # the same line in two contexts, and innocent lines right after someone else's abuse
    for d in flips.values():
        for it in d.get('pairs', []):
            add(it['severe_prev'], '%s: %s' % (it['severe_speaker'], it['msg']), 1)
            add(it['normal_prev'], '%s: %s' % (it['normal_speaker'], it['msg']), 0)
        for it in d.get('after_abuse', []):
            add(it['prev'], it['msg'], 0)
    for f in ('blind-ctx', 'mild-train'):
        for lab, y in (('severe', 1), ('normal', 0)):
            for it in conv[f][lab]:
                add(it['prev'], it['msg'], y)
    # a harmless line with a severe line by someone else inserted just before it
    for _ in range(1500):
        prev, msg = rnd.choice(harmless)
        prev = list(prev)[-3:]
        me = msg.split(': ')[0]
        others = [x.split(': ')[0] for x in prev if x.split(': ')[0] != me] or ['Player%d' % rnd.randint(1, 99)]
        prev.insert(rnd.randint(max(0, len(prev) - 1), len(prev)), '%s: %s' % (rnd.choice(others), rnd.choice(sev_u)))
        add(prev, msg, 0)
    # Korean typed with the keyboard in English mode
    inv = {v: k for k, v in KEY.items()}

    def tokeys(t):
        return ''.join(inv.get(c, c) for c in jamo(t))

    for _ in range(250):
        prev, msg = rnd.choice(harmless)
        k = tokeys(text_of(msg))
        add(prev, '%s: %s' % (msg.split(': ')[0], k if rnd.random() < 0.5 else k.upper()), 0)
        add(*placed(''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rnd.randint(2, 9)))), 0)
    for t in rnd.sample(sev_u, min(250, len(sev_u))):
        add(*placed(tokeys(t)), 1)
    return X, Y


def train(X, Y, out, base=BASE, epochs=2, bs=32, lr=3e-5, threads=None, seed=11, limit=None):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    if threads:
        torch.set_num_threads(threads)
    rnd = random.Random(seed)
    torch.manual_seed(seed)
    if limit:
        keep = rnd.sample(range(len(X)), min(limit, len(X)))
        X, Y = [X[i] for i in keep], [Y[i] for i in keep]
    tok = AutoTokenizer.from_pretrained(base)
    tok.truncation_side = 'left'
    model = AutoModelForSequenceClassification.from_pretrained(base, num_labels=2)
    enc = [encode(p, m) for p, m in X]
    steps = max(1, epochs * (len(X) // bs))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sch = get_linear_schedule_with_warmup(opt, steps // 15, steps)
    lossf = torch.nn.CrossEntropyLoss(weight=torch.tensor([1.0, 3.0]), label_smoothing=0.05)
    t0, n = time.time(), 0
    for ep in range(epochs):
        order = list(range(len(X)))
        rnd.shuffle(order)
        model.train()
        for s in range(0, len(order) - bs + 1, bs):
            idx = order[s:s + bs]
            b = tok([enc[i][0] for i in idx], [enc[i][1] for i in idx], padding=True, truncation='only_first',
                    max_length=MAXLEN, return_tensors='pt')
            loss = lossf(model(**b).logits, torch.tensor([Y[i] for i in idx]))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sch.step()
            opt.zero_grad()
            n += 1
            if n % 25 == 0 or n == steps:
                print('epoch %d step %d/%d loss %.4f %.1f min' % (ep, n, steps, loss.item(), (time.time() - t0) / 60),
                      flush=True)
        model.save_pretrained(out)
        tok.save_pretrained(out)
    print('saved', out, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='models/ctx')
    ap.add_argument('--base', default=BASE)
    ap.add_argument('--negatives', help='your own ordinary chat (.txt or .jsonl), optional')
    ap.add_argument('--negatives-limit', type=int, default=12500)
    ap.add_argument('--epochs', type=int, default=2)
    ap.add_argument('--batch-size', type=int, default=32)
    ap.add_argument('--threads', type=int)
    ap.add_argument('--seed', type=int, default=11)
    ap.add_argument('--limit', type=int, help='train on a random subset (smoke test)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    X, Y = build(a.negatives, a.negatives_limit, a.seed)
    print('examples %d, positive %d, with context %d' % (len(X), sum(Y), sum(1 for p, _ in X if p)), flush=True)
    if not a.dry_run:
        train(X, Y, a.out, a.base, a.epochs, a.batch_size, threads=a.threads, seed=a.seed, limit=a.limit)


if __name__ == '__main__':
    main()
