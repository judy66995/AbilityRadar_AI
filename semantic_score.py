import json
import os
import re
import sys
import numpy as np

MODEL_PATH = os.path.join('output', 'semantic_model.json')
TOKEN_RE = re.compile(r'[\u4e00-\u9fff]+|[A-Za-z0-9\+\#]+')


def tokenize(text):
    if not text:
        return []
    text = text.lower()
    return TOKEN_RE.findall(text)


def vectorize(text, vocab):
    tokens = tokenize(text)
    vec = np.zeros(len(vocab), dtype=float)
    if not tokens:
        return vec
    vocab_index = {token: i for i, token in enumerate(vocab)}
    for token in tokens:
        if token in vocab_index:
            vec[vocab_index[token]] += 1.0
    total = vec.sum()
    if total > 0:
        vec /= total
    return vec


def load_model():
    if not os.path.exists(MODEL_PATH):
        from semantic_model import train_model
        train_model()
    with open(MODEL_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def predict(text, model):
    vocab = model['vocab']
    weights = np.array(model['weights'], dtype=float)
    biases = np.array(model['biases'], dtype=float)
    x = vectorize(text, vocab)
    y = weights.dot(x) + biases
    y = np.clip(y, 0.0, 10.0)
    return y.tolist()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Semantic scoring model predictor.')
    parser.add_argument('--file', type=str, help='Path to UTF-8 input text file.')
    parser.add_argument('text', nargs='?', default='')
    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read().strip()
    else:
        text = args.text

    if not text:
        print('0 0 0 0 0 0')
        sys.exit(1)

    model = load_model()
    scores = predict(text, model)
    print(' '.join(f'{x:.1f}' for x in scores))