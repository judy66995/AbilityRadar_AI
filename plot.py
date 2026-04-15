import sys
import matplotlib.pyplot as plt
import numpy as np
import locale

# 【核心修复】强制设置UTF-8编码，解决Windows中文乱码
sys.stdout.reconfigure(encoding='utf-8')
locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')

# 读取参数（处理中文空格/特殊字符）
username = sys.argv[1]
scores = list(map(int, sys.argv[2:8]))

labels = [
    '专业能力', '学习能力', '项目实践',
    '团队协作', '抗压执行', '创新思维'
]

# 极坐标设置
angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
scores += scores[:1]
angles += angles[:1]

# 【彻底修复】中文乱码：多字体兜底，强制渲染
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