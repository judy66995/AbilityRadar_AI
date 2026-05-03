# test.py
import sys
import matplotlib.pyplot as plt

# 接收 C++ 传过来的参数
name = sys.argv[1]
score = sys.argv[2]

# 输出测试（会在 C++ 控制台显示）
print(f"Python 收到：姓名={name}, 分数={score}")

# 生成一张简单图片
plt.figure()
plt.text(0.5, 0.5, f"Hello {name}\nScore: {score}", 
         fontsize=16, ha="center")
plt.savefig("test_output.png")
plt.close()

print("Python 已生成图片：test_output.png")