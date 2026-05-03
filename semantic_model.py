import json
import os
import re
from collections import Counter
import numpy as np

MODEL_PATH = os.path.join('output', 'semantic_model.json')

# 文本分词：提取中文词组和字母/数字/符号组合
TOKEN_RE = re.compile(r'[\u4e00-\u9fff]+|[A-Za-z0-9\+\#]+' )


def tokenize(text):
    if not text:
        return []
    text = text.lower()
    return TOKEN_RE.findall(text)


def build_vocab(texts, max_size=2000):
    counter = Counter()
    for text in texts:
        counter.update(tokenize(text))
    most_common = [token for token, _ in counter.most_common(max_size)]
    return most_common


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


def fit_regression(X, y):
    # 线性回归：最小二乘法
    X_aug = np.hstack([X, np.ones((X.shape[0], 1), dtype=float)])
    w, residuals, rank, s = np.linalg.lstsq(X_aug, y, rcond=None)
    return w[:-1], float(w[-1])


def train_model():
    # 训练样本由工程经历描述和六个评分维度构成
    texts = [
        '精通C++和Python，5年开发经验，熟练掌握数据结构和算法，数据库设计优化',
        '自学新技术，持续学习人工智能，主动学习算法与系统设计',
        '带领团队开发大型项目，跨部门协作，项目协调和沟通能力强',
        '高压力环境下按时交付，解决复杂问题，生产环境部署与维护',
        '创新设计优化方案，改进流程，提高性能和用户体验',
        '从零搭建系统架构，部署上线并持续优化，解决高并发问题',
        '指导新人并培训同事，推动团队合作，项目协调顺利完成',
        '主动学习新知识，掌握新技术，研究优化方法，提高效率',
        '负责架构设计和系统开发，数据库和算法性能优化',
        '在压力下坚持执行任务，责任心强，按时交付结果并做好复盘'
    ]

    labels = [
        [9.0, 3.0, 4.0, 1.0, 1.0, 1.0],
        [2.0, 9.0, 2.0, 1.0, 1.0, 2.0],
        [3.0, 2.0, 8.0, 9.0, 3.0, 3.0],
        [3.0, 2.0, 4.0, 1.0, 9.0, 4.0],
        [2.0, 3.0, 2.0, 2.0, 2.0, 9.0],
        [4.0, 2.0, 9.0, 5.0, 5.0, 5.0],
        [2.0, 2.0, 7.0, 8.0, 3.0, 3.0],
        [1.0, 8.0, 2.0, 2.0, 1.0, 2.0],
        [7.0, 3.0, 4.0, 1.0, 2.0, 2.0],
        [1.0, 1.0, 2.0, 1.0, 8.0, 3.0]
    ]

    vocab = build_vocab(texts)
    X = np.vstack([vectorize(text, vocab) for text in texts])
    Y = np.array(labels, dtype=float)

    weights = []
    biases = []
    for dim in range(Y.shape[1]):
        w, b = fit_regression(X, Y[:, dim])
        weights.append(w.tolist())
        biases.append(b)

    model = {
        'vocab': vocab,
        'weights': weights,
        'biases': biases,
    }

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, 'w', encoding='utf-8') as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
    print('Model saved to', MODEL_PATH)


def load_model():
    if not os.path.exists(MODEL_PATH):
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
    parser = argparse.ArgumentParser(description='Semantic scoring model trainer and predictor.')
    parser.add_argument('--train', action='store_true', help='Train and save the model.')
    parser.add_argument('text', nargs='?', default='')
    args = parser.parse_args()

    if args.train or not os.path.exists(MODEL_PATH):
        train_model()

    if args.text:
        model = load_model()
        scores = predict(args.text, model)
        print(' '.join(f'{x:.1f}' for x in scores))