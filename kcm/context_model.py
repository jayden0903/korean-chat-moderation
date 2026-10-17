"""Context model: a fine-tuned KcELECTRA cross-encoder that reads (previous chat lines, judged line).

Input format (shared by training and inference, see encode()):
  segment 1  up to 5 previous lines, 'A: text / B: text / ...'
  segment 2  the judged line, 'B: text'
Speakers are renamed A, B, C ... in order of appearance, and usernames of 3+ characters that appear inside the
text are replaced by the same letter. The model therefore learns *who talks to whom*, never *who* it is.
When the pair is too long, the context is cut from the left (oldest words first); the judged line is never cut.

torch and transformers are imported lazily, so the rest of the package works without them.
"""
import re

from .normalize import light

MAXPREV = 5
MAXLEN = 160
LETTERS = 'ABCDEFGH'


def split_line(line):
    """'name: text' -> (name, text); a line without a speaker gets '?'."""
    n, sep, t = line.partition(': ')
    return (n, t) if sep else ('?', line)


def encode(prev, msg):
    """prev: list of 'name: text' (oldest first), msg: 'name: text' -> (context, target) strings."""
    pairs = [split_line(x) for x in list(prev)[-MAXPREV:]]
    tn, tt = split_line(msg)
    names = {}
    for n, _ in pairs + [(tn, tt)]:
        names.setdefault(n, LETTERS[min(len(names), len(LETTERS) - 1)])

    def sub(t):
        for n, a in names.items():
            if len(n) >= 3:
                t = re.sub(r'(?<![A-Za-z0-9_])' + re.escape(n) + r'(?![A-Za-z0-9_])', a, t, flags=re.I)
        return light(t)

    context = ' / '.join('%s: %s' % (names[n], sub(t)) for n, t in pairs)
    return context, '%s: %s' % (names[tn], sub(tt))


class ContextModel:
    """P(severe) for (prev, msg) pairs. path = a directory saved by scripts/train.py (save_pretrained)."""

    def __init__(self, path, threads=None, device='cpu'):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        if threads:
            torch.set_num_threads(threads)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.tok.truncation_side = 'left'
        self.model = AutoModelForSequenceClassification.from_pretrained(path).eval().to(device)
        self.device = device

    def score(self, pairs, batch_size=32):
        """pairs: [(prev, msg)] -> list of P(severe) in [0, 1]."""
        out = []
        with self.torch.inference_mode():
            for i in range(0, len(pairs), batch_size):
                enc = [encode(p, m) for p, m in pairs[i:i + batch_size]]
                b = self.tok([x[0] for x in enc], [x[1] for x in enc], padding=True, truncation='only_first',
                             max_length=MAXLEN, return_tensors='pt').to(self.device)
                out += self.torch.softmax(self.model(**b).logits, -1)[:, 1].tolist()
        return out

    def score1(self, prev, msg):
        return self.score([(prev, msg)])[0]
