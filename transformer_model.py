"""
AbilityRadar AI — 基于 Transformer 的深度学习语义评分模型
==========================================================

这个模块实现了一个 **Transformer 编码器**，用于将用户的工程经历文本
映射到 6 个能力维度的分数（0–10 分）。

=== 与旧版线性回归模型的区别 ===
旧版：词袋向量 → 线性加权求和 → 6 个分数
新版：字符序列 → Transformer 编码器 → 池化 → 全连接头 → 6 个分数

Transformer 能捕捉词语之间的**上下文关系**，比如“精通C++”和
“用过C++”虽然包含同一个词“C++”，但含义完全不同——Transformer
可以通过自注意力机制区分这种差异。

=== 模型架构（从输入到输出） ===
输入文本
  │
  ▼
字符级分词 ──→ Token IDs
  │
  ▼
Embedding 层 (每个字符 → 64 维向量)
  │
  ▼
位置编码 (加入位置信息，让模型知道字符顺序)
  │
  ▼
Transformer 编码器 × 2 层
  │  每层包含：
  │  ├── 多头自注意力 (4 个头)
  │  ├── 残差连接 + LayerNorm
  │  ├── 前馈网络 (64 → 256 → 64)
  │  └── 残差连接 + LayerNorm
  │
  ▼
平均池化 (把所有字符向量合并成一个句子向量)
  │
  ▼
全连接头 (64 → 64 → 6)
  │
  ▼
输出：6 个分数 [专业能力, 学习能力, 项目实践, 团队协作, 抗压执行, 创新思维]
"""

import json
import os
import re
import math
import random
import sys
from collections import Counter

import numpy as np

# 确保 Windows 控制台能正确输出中文
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ============================================================
# 第一部分：检查 PyTorch 是否可用
# ============================================================
_HAS_TORCH = False
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    _HAS_TORCH = True
except ImportError:
    pass  # 会在需要用到 torch 的地方给出友好提示

# ============================================================
# 第二部分：配置参数（可按需调整）
# ============================================================
MODEL_DIR = 'output'
MODEL_PATH = os.path.join(MODEL_DIR, 'transformer_model.pt')
VOCAB_PATH = os.path.join(MODEL_DIR, 'transformer_vocab.json')

# 文本处理
MAX_SEQ_LEN = 256       # 最大序列长度（字符数），超出的截断
VOCAB_SIZE = 5000       # 词表最大大小

# 模型结构
EMBED_DIM = 64          # 嵌入维度（每个字符用 64 个数表示）
NUM_HEADS = 4           # 多头注意力的“头”数
NUM_LAYERS = 2          # Transformer 编码器层数
FFN_DIM = 256           # 前馈网络隐藏层大小
DROPOUT = 0.3           # Dropout 比例（防止过拟合）

# 训练
BATCH_SIZE = 32         # 每批样本数
EPOCHS = 80             # 训练轮数
LR = 1e-3               # 学习率
SYNTHETIC_SAMPLES = 800 # 生成的合成训练样本数

# 6 个能力维度的中文名
DIMENSION_NAMES = [
    '专业能力',   # 0: 技术硬实力
    '学习能力',   # 1: 学习与成长
    '项目实践',   # 2: 项目经验
    '团队协作',   # 3: 沟通合作
    '抗压执行',   # 4: 抗压与执行力
    '创新思维',   # 5: 创新与优化
]


# ============================================================
# 第三部分：文本预处理（字符级分词）
# ============================================================
def tokenize(text):
    """
    把文本拆成字符列表（字符级分词）。
    对中文来说，每个汉字单独作为一个 token；
    英文字母/数字按单个字符处理，但连续的英文单词中
    每个字母也独立成 token。

    例子：
        "精通C++" → ['精', '通', 'c', '+', '+']
    """
    if not text:
        return []
    return list(text.lower())


def build_vocab(texts, max_size=VOCAB_SIZE):
    """
    从所有训练文本中统计字符频率，构建字符→编号的映射表。
    保留两个特殊 token：
      <PAD> (id=0): 填充符号，补到统一长度
      <UNK> (id=1): 未知字符，词表中不存在的字符都用它
    """
    counter = Counter()
    for text in texts:
        counter.update(tokenize(text))
    chars = ['<PAD>', '<UNK>'] + [c for c, _ in counter.most_common(max_size)]
    char2idx = {c: i for i, c in enumerate(chars)}
    return chars, char2idx


def encode(text, char2idx, max_len=MAX_SEQ_LEN):
    """
    把文本编码成固定长度的 token ID 序列。
    - 比 max_len 短 → 末尾补 <PAD> (id=0)
    - 比 max_len 长 → 截断
    """
    tokens = tokenize(text)
    ids = [char2idx.get(t, 1) for t in tokens]   # 1 = <UNK>
    if len(ids) < max_len:
        ids += [0] * (max_len - len(ids))         # 0 = <PAD>
    else:
        ids = ids[:max_len]
    return ids


def create_mask(token_ids, pad_idx=0):
    """创建 padding mask：标记哪些位置是真实字符，哪些是填充"""
    return (token_ids != pad_idx).unsqueeze(1).unsqueeze(2)  # (B, 1, 1, L)


# ============================================================
# 第四部分：合成训练数据生成
# ============================================================

# 短语库：每个短语附带它对 6 个维度的贡献分
# 格式：(短语文本, [专业能力, 学习能力, 项目实践, 团队协作, 抗压执行, 创新思维])

PHRASE_POOL = {
    # ──── 专业能力相关短语 ────
    'professional': [
        ("精通C++与Python，代码功底扎实",            [4.0, 0.5, 1.0, 0.0, 0.5, 0.0]),
        ("熟练掌握数据结构与算法",                   [3.0, 1.0, 0.5, 0.0, 0.0, 0.0]),
        ("Java开发经验丰富，熟悉Spring框架",         [3.5, 0.0, 1.0, 0.0, 0.0, 0.0]),
        ("深入理解操作系统原理与计算机网络",          [2.5, 1.0, 0.0, 0.0, 0.0, 0.0]),
        ("精通数据库设计与SQL优化",                  [3.0, 0.0, 1.0, 0.0, 0.0, 0.5]),
        ("熟悉Linux系统管理与Shell脚本",             [2.5, 0.5, 0.5, 0.0, 0.0, 0.0]),
        ("掌握多种编程语言，包括Go和Rust",           [3.0, 1.0, 0.5, 0.0, 0.0, 0.0]),
        ("精通前端技术栈React和TypeScript",          [3.0, 0.5, 1.0, 0.0, 0.0, 0.0]),
        ("具备扎实的计算机基础理论功底",              [2.5, 0.5, 0.0, 0.0, 0.0, 0.0]),
        ("深耕后端开发多年，熟悉分布式系统",          [4.0, 0.0, 2.0, 0.5, 0.0, 0.0]),
        ("熟练运用设计模式，代码可维护性高",          [3.0, 0.0, 0.5, 0.5, 0.0, 1.0]),
        ("掌握微服务架构与容器化技术",                [3.0, 0.5, 1.5, 0.0, 0.0, 0.5]),
        ("具备全栈开发能力，独立完成项目",            [3.5, 0.0, 2.0, 0.0, 1.0, 0.5]),
        ("对底层原理有深入研究，能写出高性能代码",     [4.0, 1.0, 0.5, 0.0, 0.5, 1.0]),
        ("技术栈广泛，能快速切换不同技术领域",         [3.0, 1.5, 0.5, 0.0, 0.0, 0.5]),
        ("有扎实的测试驱动开发经验",                  [2.0, 0.5, 1.0, 0.5, 0.0, 0.0]),
        ("精通移动端开发，iOS和Android双平台",        [3.5, 0.5, 1.0, 0.0, 0.0, 0.0]),
        ("熟悉AI/ML框架，有模型部署经验",             [3.5, 1.0, 1.0, 0.0, 0.0, 0.5]),
        ("擅长性能调优与系统瓶颈分析",                [3.5, 0.0, 1.0, 0.0, 0.5, 1.0]),
        ("掌握云计算平台AWS和Azure的深度使用",        [3.0, 0.5, 1.0, 0.0, 0.0, 0.0]),
        ("熟练编写高质量技术文档",                    [2.0, 0.0, 0.0, 0.5, 0.0, 0.0]),
        ("有5年以上的软件开发经验",                   [3.5, 0.0, 1.5, 0.0, 0.5, 0.0]),
        ("基本功扎实，编码速度快且bug率低",            [3.0, 0.0, 0.5, 0.0, 1.0, 0.0]),
        ("熟悉敏捷开发流程，有Scrum Master经验",      [2.5, 0.0, 1.5, 1.0, 0.5, 0.0]),
    ],

    # ──── 学习能力相关短语 ────
    'learning': [
        ("自学能力极强，能快速掌握新技术栈",           [1.0, 4.0, 0.5, 0.0, 0.5, 0.0]),
        ("持续关注前沿技术动态，保持学习热情",          [0.5, 3.5, 0.0, 0.0, 0.0, 1.0]),
        ("每周坚持阅读技术博客和论文",                 [0.5, 3.0, 0.0, 0.0, 0.5, 0.5]),
        ("善于通过在线课程和书籍系统学习",              [0.5, 3.0, 0.0, 0.0, 0.5, 0.0]),
        ("主动参加技术社区和开源项目贡献",              [1.0, 3.0, 1.0, 1.0, 0.0, 0.5]),
        ("能够独立研究并解决从未遇过的技术难题",        [1.5, 3.5, 0.5, 0.0, 1.0, 0.5]),
        ("学习新语言或框架只需一两周即可上手开发",      [1.5, 4.0, 0.5, 0.0, 0.5, 0.0]),
        ("乐于接受新挑战，视困难为成长机会",            [0.0, 3.0, 0.0, 0.0, 1.0, 0.5]),
        ("定期总结复盘学习心得，形成知识体系",           [0.5, 3.0, 0.0, 0.5, 0.0, 0.5]),
        ("拥有多个技术认证，不断提升专业水平",           [1.5, 2.5, 0.0, 0.0, 0.5, 0.0]),
        ("善于从失败中总结经验教训",                   [0.5, 2.5, 0.0, 0.0, 0.5, 0.5]),
        ("有强烈的求知欲，不满足于完成表面任务",         [0.5, 3.5, 0.0, 0.0, 0.5, 1.0]),
        ("习惯深入源码理解框架底层原理",                [2.0, 3.0, 0.0, 0.0, 0.5, 0.0]),
        ("主动寻求导师指导和同行反馈",                  [0.0, 2.5, 0.0, 1.0, 0.0, 0.0]),
        ("能在短时间内从零掌握一门全新领域知识",         [1.0, 4.0, 0.5, 0.0, 1.0, 0.0]),
    ],

    # ──── 项目实践相关短语 ────
    'project': [
        ("曾独立从零搭建一套完整的电商系统并上线运营",    [2.5, 0.0, 4.0, 0.0, 1.0, 1.0]),
        ("主导过大型分布式项目的架构设计与核心开发",      [3.0, 0.0, 4.0, 1.0, 0.5, 1.0]),
        ("带领团队完成了公司核心产品的重构升级",          [2.5, 0.0, 3.5, 1.5, 1.0, 1.0]),
        ("负责关键业务模块的需求分析与技术方案设计",      [2.0, 0.0, 3.0, 1.0, 0.0, 0.5]),
        ("成功交付过多个百万级用户量的商业项目",          [2.5, 0.0, 3.5, 0.5, 1.0, 0.0]),
        ("深度参与项目全生命周期，从规划到运维",          [1.5, 0.0, 3.0, 1.0, 1.0, 0.0]),
        ("负责过跨部门大型项目的技术协调与推进",          [1.5, 0.0, 3.0, 2.0, 1.0, 0.0]),
        ("有丰富的敏捷项目管理经验，按时交付率高",         [1.0, 0.0, 2.5, 1.0, 2.0, 0.0]),
        ("主导技术选型和架构评审，积累了丰富的实战经验",    [2.5, 0.0, 3.0, 1.0, 0.0, 0.5]),
        ("负责过日活百万级产品的性能优化与稳定性保障",     [3.0, 0.0, 3.5, 0.5, 1.5, 1.0]),
        ("推动项目按时上线，获得客户高度评价",             [1.0, 0.0, 2.5, 1.0, 1.5, 0.0]),
        ("管理过10人以上的开发团队完成复杂项目",           [2.0, 0.0, 3.0, 2.5, 1.0, 0.0]),
        ("多次在紧急情况下接手并救回濒临失败的项目",       [2.5, 0.5, 3.0, 0.5, 3.0, 0.5]),
        ("有从0到1的产品孵化经验",                        [1.5, 0.5, 3.5, 0.5, 1.0, 1.5]),
        ("负责制定项目技术规范和代码审查标准",             [2.0, 0.0, 2.0, 1.0, 0.5, 0.5]),
    ],

    # ──── 团队协作相关短语 ────
    'teamwork': [
        ("具备出色的跨部门沟通和协调能力",               [0.0, 0.0, 0.5, 4.0, 0.0, 0.0]),
        ("善于带领团队攻克技术难关，凝聚力强",            [1.0, 0.0, 1.0, 3.5, 1.0, 0.0]),
        ("曾指导多名新人快速上手，团队整体效率提升显著",   [1.0, 0.5, 0.5, 3.5, 0.0, 0.0]),
        ("具备良好的表达能力和文档习惯，信息传递清晰",     [0.5, 0.0, 0.0, 3.0, 0.0, 0.0]),
        ("能有效调解团队中的技术分歧，推动达成共识",       [1.0, 0.0, 0.5, 3.5, 0.5, 0.0]),
        ("作为技术团队的桥梁，高效连接产品与研发",         [0.5, 0.0, 0.5, 3.5, 0.5, 0.0]),
        ("乐于分享知识，定期组织团队技术分享会",           [0.5, 0.5, 0.0, 3.0, 0.0, 0.5]),
        ("擅长与产品、设计、测试等多个角色高效协作",       [0.0, 0.0, 0.5, 3.5, 0.0, 0.0]),
        ("有优秀的领导力，能激励团队成员发挥最大潜能",     [0.5, 0.0, 0.5, 4.0, 0.5, 0.0]),
        ("在跨国团队中工作，有良好的跨文化沟通能力",       [0.5, 0.5, 0.0, 3.5, 0.0, 0.0]),
        ("善于倾听他人意见，能换位思考解决问题",           [0.0, 0.0, 0.0, 3.0, 0.5, 0.0]),
    ],

    # ──── 抗压执行相关短语 ────
    'pressure': [
        ("能在高压力环境下保持冷静并高效完成任务",        [0.5, 0.0, 0.5, 0.5, 4.0, 0.0]),
        ("面对紧急线上故障，曾彻夜排查并成功修复",         [2.0, 0.0, 0.5, 0.0, 4.0, 0.0]),
        ("有极强的责任心和执行力，决不轻言放弃",           [0.0, 0.0, 0.0, 0.0, 3.5, 0.0]),
        ("习惯在Deadline驱动下高效产出，质量不打折",      [0.5, 0.0, 0.5, 0.0, 3.5, 0.0]),
        ("曾在资源极度有限的情况下保障项目顺利交付",       [1.0, 0.0, 1.0, 0.5, 4.0, 0.5]),
        ("具备良好的情绪管理能力和抗挫折心态",             [0.0, 0.0, 0.0, 0.5, 3.0, 0.0]),
        ("能同时管理多个并行任务，不遗漏不延期",           [1.0, 0.0, 1.0, 0.5, 3.5, 0.0]),
        ("在生产事故面前快速响应、精准定位、果断决策",     [2.0, 0.0, 0.5, 0.0, 4.0, 0.0]),
        ("对工作质量要求苛刻，从不将就过关",               [1.0, 0.0, 0.0, 0.0, 2.5, 0.5]),
        ("经历多次大促高峰考验，稳定性屡获认可",           [1.5, 0.0, 1.0, 0.0, 3.5, 0.0]),
    ],

    # ──── 创新思维相关短语 ────
    'innovation': [
        ("擅长从日常工作中发现优化机会并主动推动改进",     [0.5, 0.5, 0.5, 0.5, 0.5, 3.5]),
        ("曾提出一套全新的自动化方案，大幅提升团队效率",   [1.0, 0.0, 1.0, 0.5, 0.5, 4.0]),
        ("对现有系统进行了大胆重构，性能提升了3倍以上",    [2.5, 0.0, 1.5, 0.0, 0.5, 3.5]),
        ("不满足于现有方案，总是尝试寻找更优解",           [0.5, 0.5, 0.0, 0.0, 0.5, 3.0]),
        ("主导技术创新，获得过多项技术专利",               [2.0, 0.5, 1.0, 0.0, 0.0, 4.0]),
        ("善于将跨领域的思路引入本行业，带来突破性改变",    [1.0, 1.0, 0.5, 0.5, 0.0, 3.5]),
        ("有敏锐的产品嗅觉，能提出创新性的功能设计",        [0.5, 0.0, 0.5, 0.5, 0.0, 3.5]),
        ("发起的技术改进项目为公司节省了大量成本",          [1.5, 0.0, 1.0, 0.5, 0.5, 3.0]),
        ("鼓励团队成员一起脑力激荡，营造创新氛围",          [0.0, 0.0, 0.0, 1.5, 0.0, 3.0]),
        ("多次在技术大会上分享创新的解决方案和经验",        [1.0, 0.5, 0.5, 1.0, 0.0, 3.5]),
    ],
}

# 连接词和过渡句
CONNECTORS = [
    "。", "；", "，此外，", "。同时，", "。另外，", "，而且，",
    "。值得一提的是，", "。总结来说，", "。在过往经历中，",
    "。从技术角度看，", "。在实际工作中，", "。尤其值得强调的是，",
]

# 开头模板
OPENERS = [
    "本人{sample}。",
    "作为一名资深技术人员，{sample}。",
    "在多年的职业生涯中，{sample}。",
    "我的技术背景和经历如下：{sample}。",
    "总结个人核心能力：{sample}。",
    "以下是我的能力概述：{sample}。",
    "从技术能力来看，{sample}。",
    "综合来看，{sample}。",
]


def generate_one_sample():
    """
    随机生成一条训练样本。

    做法：
    1. 从 6 个维度中各随机选 1~3 条短语
    2. 用连接词拼接成自然的段落
    3. 将所有短语的维度分数求和 → 得到 6 个标签分
    4. 用 clip 限制在 [0, 10] 范围内
    """
    all_phrases = []
    scores = np.zeros(6, dtype=float)

    # 每个维度随机选1~3条短语
    for dim_name, phrases in PHRASE_POOL.items():
        n = random.randint(1, 3)
        chosen = random.sample(phrases, min(n, len(phrases)))
        for text, contrib in chosen:
            all_phrases.append(text)
            for i in range(6):
                scores[i] += contrib[i]

    # 随机打乱短语顺序（让文本更自然多样）
    random.shuffle(all_phrases)

    # 用连接词拼接
    sample = ""
    for i, phrase in enumerate(all_phrases):
        if i == 0:
            sample = phrase
        else:
            connector = random.choice(CONNECTORS)
            sample += connector + phrase

    # 随机选一个开头模板
    opener = random.choice(OPENERS)
    text = opener.format(sample=sample)

    # Clip 分数到 [0, 10]
    scores = np.clip(scores, 0.0, 10.0)

    return text, scores.tolist()


def generate_training_data(n_samples=SYNTHETIC_SAMPLES):
    """
    生成 n 条合成训练数据。
    返回两个列表：texts（文本）和 labels（6维分数列表）
    """
    texts = []
    labels = []
    for _ in range(n_samples):
        text, label = generate_one_sample()
        texts.append(text)
        labels.append(label)
    return texts, labels


# ============================================================
# 第五部分：Transformer 模型组件（仅当 PyTorch 可用时定义）
# ============================================================

if _HAS_TORCH:

    class PositionalEncoding(nn.Module):
        """
        位置编码层。

        Transformer 本身不包含位置信息——它同时看到所有字符，
        不知道谁在前谁在后。位置编码就是给每个位置的字符向量
        加上一个独特的“位置指纹”，让模型知道字符的顺序。

        这里使用正弦/余弦编码（经典方案）：
        - 偶数维度用 sin
        - 奇数维度用 cos
        - 不同频率对应不同位置粒度
        """
        def __init__(self, d_model, max_len=MAX_SEQ_LEN):
            super().__init__()
            pe = torch.zeros(max_len, d_model)
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            div_term = torch.exp(
                torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
            )
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            pe = pe.unsqueeze(0)  # shape: (1, max_len, d_model)
            self.register_buffer('pe', pe)

        def forward(self, x):
            # x: (batch, seq_len, d_model)
            return x + self.pe[:, :x.size(1)]


    class MultiHeadAttention(nn.Module):
        """
        多头自注意力层。

        这是 Transformer 的核心。它让每个字符都能“看到”
        句子中所有其他字符，并计算出每个字符对当前字符的
        “重要程度”（注意力权重）。

        “多头”意味着同时进行多组独立的注意力计算，
        就像多个专家同时从不同角度分析同一段文字，
        最后综合所有专家的意见。

        计算过程：
        1. 输入 X 分别经过三个线性变换 → Q(查询), K(键), V(值)
        2. 计算注意力分数：softmax(Q·K^T / √d_k)
        3. 用注意力分数加权 V → 输出
        """
        def __init__(self, d_model, num_heads, dropout=0.1):
            super().__init__()
            assert d_model % num_heads == 0, "d_model 必须能被 num_heads 整除"
            self.d_model = d_model
            self.num_heads = num_heads
            self.d_k = d_model // num_heads

            self.W_q = nn.Linear(d_model, d_model)
            self.W_k = nn.Linear(d_model, d_model)
            self.W_v = nn.Linear(d_model, d_model)
            self.W_o = nn.Linear(d_model, d_model)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x, mask=None):
            B, L, _ = x.size()
            # 线性变换 + 拆成多头
            Q = self.W_q(x).view(B, L, self.num_heads, self.d_k).transpose(1, 2)
            K = self.W_k(x).view(B, L, self.num_heads, self.d_k).transpose(1, 2)
            V = self.W_v(x).view(B, L, self.num_heads, self.d_k).transpose(1, 2)

            # 缩放点积注意力
            scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)
            if mask is not None:
                scores = scores.masked_fill(mask == 0, -1e9)
            attn = F.softmax(scores, dim=-1)
            attn = self.dropout(attn)

            # 加权求和
            out = torch.matmul(attn, V)
            # 合并多头
            out = out.transpose(1, 2).contiguous().view(B, L, self.d_model)
            return self.W_o(out)


    class FeedForward(nn.Module):
        """
        前馈网络层。

        每个位置的字符向量独立经过一个两层全连接网络。
        它的作用是：在注意力层收集了上下文信息后，
        对每个字符的表示做进一步的非线性变换。

        结构：Linear → ReLU → Dropout → Linear
        中间维度（256）比输入维度（64）大，提供更强的表达能力。
        """
        def __init__(self, d_model, d_ff, dropout=0.1):
            super().__init__()
            self.linear1 = nn.Linear(d_model, d_ff)
            self.linear2 = nn.Linear(d_ff, d_model)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x):
            return self.linear2(self.dropout(F.relu(self.linear1(x))))


    class TransformerEncoderLayer(nn.Module):
        """
        一个完整的 Transformer 编码器层。

        结构（Pre-Norm 风格）：
        x → LayerNorm → MultiHeadAttention → Dropout → (+)残差
          → LayerNorm → FeedForward → Dropout → (+)残差

        “残差连接”（+号）就是直接把输入加到输出上，
        相当于告诉模型：“如果你学不会新东西，至少把原来的传过去”。
        这解决了深层网络难以训练的问题。
        """
        def __init__(self, d_model, num_heads, d_ff, dropout=0.1):
            super().__init__()
            self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
            self.ffn = FeedForward(d_model, d_ff, dropout)
            self.norm1 = nn.LayerNorm(d_model)
            self.norm2 = nn.LayerNorm(d_model)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x, mask=None):
            # 自注意力 + 残差
            attn_out = self.self_attn(x, mask)
            x = x + self.dropout(attn_out)
            x = self.norm1(x)
            # 前馈 + 残差
            ffn_out = self.ffn(x)
            x = x + self.dropout(ffn_out)
            x = self.norm2(x)
            return x


    class TextRegressionTransformer(nn.Module):
        """
        完整的文本→分数回归模型。

        流程：
        1. Embedding:     字符ID → 64维向量
        2. PositionalEncoding: 加入位置信息
        3. Dropout:       随机丢弃（正则化）
        4. TransformerEncoder × 2: 上下文建模
        5. Mean Pooling:  所有字符向量求平均 → 得到句子级别的向量
        6. Linear Head:   64 → 64 → 6（输出6个分数）
        7. Clamp:         限制在 [0, 10]
        """
        def __init__(self, vocab_size, d_model=EMBED_DIM, num_heads=NUM_HEADS,
                     num_layers=NUM_LAYERS, d_ff=FFN_DIM, dropout=DROPOUT,
                     max_len=MAX_SEQ_LEN, num_outputs=6):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
            self.pos_encoding = PositionalEncoding(d_model, max_len)
            self.encoder_dropout = nn.Dropout(dropout)
            self.layers = nn.ModuleList([
                TransformerEncoderLayer(d_model, num_heads, d_ff, dropout)
                for _ in range(num_layers)
            ])
            self.head = nn.Sequential(
                nn.Linear(d_model, d_model),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(d_model, num_outputs),
            )

        def forward(self, token_ids, mask=None):
            # token_ids: (batch, seq_len)
            x = self.embedding(token_ids)           # → (batch, seq_len, d_model)
            x = self.pos_encoding(x)
            x = self.encoder_dropout(x)

            for layer in self.layers:
                x = layer(x, mask)

            # 平均池化（只对非填充位置求平均）
            if mask is not None:
                mask_float = mask.squeeze(1).squeeze(1).float().unsqueeze(-1)  # (B, L, 1)
                x = x * mask_float
                pooled = x.sum(dim=1) / mask_float.sum(dim=1).clamp(min=1)
            else:
                pooled = x.mean(dim=1)              # → (batch, d_model)

            scores = self.head(pooled)              # → (batch, 6)
            scores = torch.clamp(scores, 0.0, 10.0)
            return scores


    # ============================================================
    # 第六部分：PyTorch 数据集类
    # ============================================================

    class AbilityDataset(Dataset):
        """把文本和标签包装成 PyTorch 可迭代的数据集"""
        def __init__(self, texts, labels, char2idx):
            self.texts = texts
            self.labels = labels
            self.char2idx = char2idx

        def __len__(self):
            return len(self.texts)

        def __getitem__(self, idx):
            token_ids = encode(self.texts[idx], self.char2idx, MAX_SEQ_LEN)
            label = self.labels[idx]
            return (
                torch.tensor(token_ids, dtype=torch.long),
                torch.tensor(label, dtype=torch.float),
            )


    # ============================================================
    # 第七部分：训练函数
    # ============================================================

    def train_model(n_samples=None):
        """
        完整训练流程：
        1. 生成合成训练数据
        2. 构建字符词表
        3. 创建 DataLoader
        4. 初始化 Transformer 模型
        5. 训练循环（MSE loss + Adam 优化器）
        6. 保存模型和词表到 output/ 目录
        """
        if n_samples is None:
            n_samples = SYNTHETIC_SAMPLES

        print("=" * 60)
        print("  AbilityRadar AI — Transformer 模型训练")
        print("=" * 60)

        # Step 1: 生成训练数据
        print(f"\n[1/6] 生成 {n_samples} 条合成训练数据...")
        train_texts, train_labels = generate_training_data(n_samples)
        print(f"  [OK] 已生成 {len(train_texts)} 条样本")

        # 打印几条样例
        print("\n  ── 样例数据（前3条）──")
        for i in range(3):
            print(f"  样本 {i+1}: {train_texts[i][:80]}...")
            scores_str = " ".join(f"{s:.1f}" for s in train_labels[i])
            dims_str = " | ".join(
                f"{DIMENSION_NAMES[j]}={train_labels[i][j]:.1f}"
                for j in range(6)
            )
            print(f"  标签:   {dims_str}")
            print()

        # Step 2: 构建词表
        print("[2/6] 构建字符词表...")
        all_texts = train_texts
        chars, char2idx = build_vocab(all_texts)
        print(f"  [OK] 词表大小: {len(chars)} 个字符")

        # Step 3: 划分训练/验证集 (90/10)
        print("[3/6] 划分训练集和验证集...")
        split_idx = int(len(train_texts) * 0.9)
        train_dataset = AbilityDataset(
            train_texts[:split_idx], train_labels[:split_idx], char2idx
        )
        val_dataset = AbilityDataset(
            train_texts[split_idx:], train_labels[split_idx:], char2idx
        )
        train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
        print(f"  [OK] 训练集: {len(train_dataset)} 条, 验证集: {len(val_dataset)} 条")

        # Step 4: 初始化模型
        print("[4/6] 初始化 Transformer 模型...")
        model = TextRegressionTransformer(
            vocab_size=len(chars),
            d_model=EMBED_DIM,
            num_heads=NUM_HEADS,
            num_layers=NUM_LAYERS,
            d_ff=FFN_DIM,
            dropout=DROPOUT,
        )
        total_params = sum(p.numel() for p in model.parameters())
        print(f"  [OK] 模型参数量: {total_params:,}")
        print(f"  [OK] 嵌入维度: {EMBED_DIM}")
        print(f"  [OK] 注意力头数: {NUM_HEADS}")
        print(f"  [OK] 编码器层数: {NUM_LAYERS}")
        print(f"  [OK] 前馈维度: {FFN_DIM}")

        # Step 5: 训练
        print(f"\n[5/6] 开始训练 ({EPOCHS} 轮)...")
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=LR)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

        best_val_loss = float('inf')

        for epoch in range(EPOCHS):
            # ── 训练阶段 ──
            model.train()
            train_loss = 0.0
            for token_ids, labels in train_loader:
                mask = create_mask(token_ids)  # (B, 1, 1, L)
                optimizer.zero_grad()
                preds = model(token_ids, mask)
                loss = criterion(preds, labels)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)

            # ── 验证阶段 ──
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for token_ids, labels in val_loader:
                    mask = create_mask(token_ids)
                    preds = model(token_ids, mask)
                    loss = criterion(preds, labels)
                    val_loss += loss.item()
            val_loss /= len(val_loader)

            scheduler.step()

            # 保存最佳模型
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

            # 每 10 轮打印一次
            if (epoch + 1) % 10 == 0:
                print(
                    f"  Epoch {epoch+1:3d}/{EPOCHS} | "
                    f"训练Loss: {train_loss:.4f} | "
                    f"验证Loss: {val_loss:.4f} | "
                    f"LR: {scheduler.get_last_lr()[0]:.6f}"
                )

        print(f"  [OK] 训练完成！最佳验证 Loss: {best_val_loss:.4f}")

        # Step 6: 保存模型
        print("[6/6] 保存模型和词表...")
        os.makedirs(MODEL_DIR, exist_ok=True)

        # 加载最佳参数
        model.load_state_dict(best_state)

        # 保存 PyTorch 模型
        torch.save(model.state_dict(), MODEL_PATH)
        print(f"  [OK] 模型已保存到: {MODEL_PATH}")

        # 保存词表和配置（JSON 格式，方便查看）
        config = {
            'chars': chars,
            'char2idx': char2idx,
            'vocab_size': len(chars),
            'embed_dim': EMBED_DIM,
            'num_heads': NUM_HEADS,
            'num_layers': NUM_LAYERS,
            'ffn_dim': FFN_DIM,
            'max_seq_len': MAX_SEQ_LEN,
            'dropout': DROPOUT,
            'dimension_names': DIMENSION_NAMES,
        }
        with open(VOCAB_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 词表已保存到: {VOCAB_PATH}")

        print("\n" + "=" * 60)
        print("  [DONE] 训练全部完成！")
        print("=" * 60)

        return model, chars, char2idx


    # ============================================================
    # 第八部分：加载和预测
    # ============================================================

    def load_model():
        """
        加载已训练的模型。
        如果模型文件不存在，自动调用 train_model() 训练一个新模型。
        """
        if not _HAS_TORCH:
            raise ImportError(
                "PyTorch 未安装，无法使用 Transformer 模型。\n"
                "请运行: pip install torch"
            )

        if not os.path.exists(MODEL_PATH) or not os.path.exists(VOCAB_PATH):
            print("[WARN] 未找到已训练的模型，开始自动训练...\n")
            return train_model()

        # 加载配置
        with open(VOCAB_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

        chars = config['chars']
        char2idx = config['char2idx']

        # 重建模型结构
        model = TextRegressionTransformer(
            vocab_size=len(chars),
            d_model=config.get('embed_dim', EMBED_DIM),
            num_heads=config.get('num_heads', NUM_HEADS),
            num_layers=config.get('num_layers', NUM_LAYERS),
            d_ff=config.get('ffn_dim', FFN_DIM),
            dropout=config.get('dropout', DROPOUT),
            max_len=config.get('max_seq_len', MAX_SEQ_LEN),
        )

        # 加载权重
        model.load_state_dict(torch.load(MODEL_PATH, map_location='cpu'))
        model.eval()

        return model, chars, char2idx


    def predict(text, model, char2idx):
        """
        对单条文本进行评分预测。

        参数：
            text: 输入的中文文本
            model: 已加载的 Transformer 模型
            char2idx: 字符到 ID 的映射

        返回：
            6 个浮点数 [专业能力, 学习能力, 项目实践, 团队协作, 抗压执行, 创新思维]
        """
        model.eval()
        token_ids = torch.tensor(
            [encode(text, char2idx, MAX_SEQ_LEN)], dtype=torch.long
        )
        mask = create_mask(token_ids)

        with torch.no_grad():
            scores = model(token_ids, mask)

        return scores.squeeze(0).tolist()


    # ============================================================
    # 第九部分：命令行入口
    # ============================================================

    if __name__ == '__main__':
        import argparse
        parser = argparse.ArgumentParser(
            description='AbilityRadar AI - Transformer 语义评分模型'
        )
        parser.add_argument(
            '--train', action='store_true',
            help='（重新）训练模型并保存'
        )
        parser.add_argument(
            '--samples', type=int, default=SYNTHETIC_SAMPLES,
            help=f'合成训练样本数（默认 {SYNTHETIC_SAMPLES}）'
        )
        parser.add_argument(
            'text', nargs='?', default='',
            help='要评分的文本（不传则只训练）'
        )
        args = parser.parse_args()

        # 训练或加载（传递命令行指定的样本数）
        if args.train or not os.path.exists(MODEL_PATH):
            model, chars, char2idx = train_model(n_samples=args.samples)
        else:
            model, chars, char2idx = load_model()

        # 预测
        if args.text:
            scores = predict(args.text, model, char2idx)
            # 输出 6 个空格分隔的分数（与旧版接口兼容）
            print(' '.join(f'{x:.1f}' for x in scores))

            # 附加可读的输出
            print()
            for name, score in zip(DIMENSION_NAMES, scores):
                bar = '█' * int(score) + '░' * (10 - int(score))
                print(f"  {name:6s} [{bar}] {score:.1f}/10")

else:
    # PyTorch 不可用时的占位函数
    def train_model(n_samples=None):
        raise ImportError(
            "PyTorch 未安装，无法训练 Transformer 模型。\n"
            "请运行: pip install torch\n"
            "详细安装说明见 ABILITYRADAR_AI.md"
        )

    def load_model():
        raise ImportError(
            "PyTorch 未安装，无法加载 Transformer 模型。\n"
            "请运行: pip install torch"
        )

    def predict(text, model, char2idx):
        raise ImportError(
            "PyTorch 未安装，无法进行预测。\n"
            "请运行: pip install torch"
        )
