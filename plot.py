# sys = 快递员：帮你接收 C++ 传过来的 “姓名 + 分数” 包裹；
# locale = 翻译官：确保 Python 能看懂并显示中文；
# numpy = 计算师：把分数转换成画图需要的 “坐标数据”；
# matplotlib.pyplot = 画师：用计算好的数据画出雷达图。
import sys 
import os
import matplotlib.pyplot as plt
import numpy as np
import locale

# 设置编码和区域，确保中文显示正常
sys.stdout.reconfigure(encoding='utf-8') # sys.stdout.reconfigure → 解决 Python 控制台打印中文乱码；
locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8') # locale.setlocale → 解决 matplotlib 显示中文乱码；

# 读取参数（处理中文空格/特殊字符）
# 从文件读取参数以避免命令行处理问题
try:
    # 尝试从临时文件读取参数
    if os.path.exists('output/radar_args.txt'):
        with open('output/radar_args.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        username = lines[0].strip()
        scores_str = lines[1].strip().split()
        scores = [int(s) for s in scores_str]
    else:
        # 降级：从命令行读取
        username = sys.argv[1] if len(sys.argv) > 1 else "未知用户"
        raw_scores = sys.argv[2:8] if len(sys.argv) >= 8 else []
        
        if len(raw_scores) < 6:
            print(f"❌ 错误：接收到 {len(raw_scores)} 个分数参数，需要6个", file=sys.stderr)
            sys.exit(1)
        
        scores = []
        for i, score_str in enumerate(raw_scores):
            try:
                score = int(score_str)
                scores.append(max(0, min(10, score)))
            except ValueError:
                print(f"❌ 第 {i+1} 个分数无法转换为整数: '{score_str}'", file=sys.stderr)
                sys.exit(1)
    
except Exception as e:
    print(f"❌ 参数解析异常: {e}", file=sys.stderr)
    sys.exit(1)

labels = [
    '专业能力', '学习能力', '项目实践',
    '团队协作', '抗压执行', '创新思维'
]

# 极坐标设置
angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
scores += scores[:1]
angles += angles[:1]

# 设置 matplotlib 参数，确保中文显示和负号显示正常
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Zen Hei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.family'] = 'sans-serif'

# 绘图
fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
ax.plot(angles, scores, 'o-', linewidth=2.5, color='#4285F4', zorder=3)
ax.fill(angles, scores, alpha=0.3, color='#4285F4', zorder=2)

# 设置标签和刻度
ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels, fontsize=12, fontweight='medium')
ax.set_yticks([2, 4, 6, 8, 10])
ax.set_yticklabels(['2', '4', '6', '8', '10'], fontsize=10)
ax.set_ylim(0, 10)
ax.set_title(f'{username} 的能力雷达图', fontsize=16, pad=25, fontweight='bold')

# 美化网格
ax.grid(color='gray', linestyle='-', linewidth=0.5, alpha=0.7, zorder=1)

plt.tight_layout()
plt.savefig('output/radar.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close()

print(f"✅ {username} 的雷达图已成功保存到 output/radar.png")