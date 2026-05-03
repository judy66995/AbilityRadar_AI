from pathlib import Path
text = '精通C++和Python，5年开发经验，熟练掌握数据结构和算法，数据库设计优化'
Path('output/semantic_input.txt').write_text(text, 'utf-8')
print('ok')
