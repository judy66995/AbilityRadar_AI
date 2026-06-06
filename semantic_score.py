"""
AbilityRadar AI — 语义评分入口（供 C++ 主程序调用）

这个脚本是 C++ 与 Python 之间的桥梁。
C++ 程序通过 _popen 调用本脚本，传入用户填写的工程经历文本，
本脚本加载 Transformer 模型进行推理，输出 6 个维度分数。

用法：
    python semantic_score.py "用户的工程经历文本..."
    python semantic_score.py --file output/semantic_input.txt

输出格式（stdout）：
    7.5 2.1 3.0 1.2 1.0 1.5
    （6 个空格分隔的浮点数，对应 6 个能力维度）

=== 与旧版（线性回归）的区别 ===
旧版使用 semantic_model.py 中的线性回归模型（JSON 格式保存），
新版使用 transformer_model.py 中的 Transformer 深度学习模型（.pt 格式保存）。
接口完全兼容，C++ 端无需任何改动。
"""

import sys
import os


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='AbilityRadar AI - 语义评分（Transformer 模型）'
    )
    parser.add_argument(
        '--file', type=str,
        help='UTF-8 文本文件路径（包含要评分的文本）'
    )
    parser.add_argument(
        'text', nargs='?', default='',
        help='要评分的文本（命令行直接传入）'
    )
    args = parser.parse_args()

    # ── 读取输入文本 ──
    if args.file:
        if not os.path.exists(args.file):
            print(f"错误：文件不存在 {args.file}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
        except Exception as e:
            print(f"错误：读取文件失败 {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = args.text

    if not text:
        # 无输入时返回全零（C++ 端会回退到规则评分）
        print('0 0 0 0 0 0')
        sys.exit(1)

    # ── 加载模型并预测 ──
    try:
        from transformer_model import load_model, predict, DIMENSION_NAMES
    except ImportError as e:
        print(f"错误：无法导入 transformer_model 模块\n{e}", file=sys.stderr)
        print("请确保 transformer_model.py 在同一目录下", file=sys.stderr)
        sys.exit(1)

    try:
        model, chars, char2idx = load_model()
        scores = predict(text, model, char2idx)
    except ImportError as e:
        # PyTorch 未安装
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误：模型推理失败 — {e}", file=sys.stderr)
        sys.exit(1)

    # ── 输出分数（与旧版格式完全一致）──
    print(' '.join(f'{x:.1f}' for x in scores))


if __name__ == '__main__':
    main()
