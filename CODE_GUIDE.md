# AbilityRadar AI — 代码阅读指南

> **目标**：快速理解整个项目的代码结构，重点掌握「Transformer 评分」的完整调用链路。
>
> **适合**：需要维护、调试或二次开发本项目的开发者。

---

## 目录

- [一、项目全景地图](#一项目全景地图)
- [二、主流程速览（main.cpp）](#二主流程速览maincpp)
- [三、评分核心——Transformer 调用全链路](#三评分核心transformer-调用全链路)
  - [3.1 C++ 入口 score.cpp](#31-c-入口-scorecpp)
  - [3.2 Python 桥接 semantic_score.py](#32-python-桥接-semantic_scorepy)
  - [3.3 Transformer 模型 transformer_model.py](#33-transformer-模型-transformer_modelpy)
  - [3.4 回退机制：规则评分](#34-回退机制规则评分)
- [四、其他模块速览](#四其他模块速览)
  - [4.1 用户输入 input.cpp](#41-用户输入-inputcpp)
  - [4.2 雷达图 radar.cpp + plot.py](#42-雷达图-radarcpp--plotpy)
  - [4.3 AI 分析 ai.cpp](#43-ai-分析-aicpp)
  - [4.4 报告保存 file_utils.cpp](#44-报告保存-file_utilscpp)
- [五、数据结构一览](#五数据结构一览)
- [六、如何修改 Transformer 评分逻辑](#六如何修改-transformer-评分逻辑)
- [七、调试技巧](#七调试技巧)

---

## 一、项目全景地图

```
main.cpp                          ← 程序入口，编排所有步骤
  │
  ├── input.cpp / input.h         ← 控制台交互，收集用户信息
  │     └── 定义: struct UserInfo
  │
  ├── score.cpp / score.h         ← ★ 评分引擎 ★
  │     ├── runPythonSemanticModel()  → semantic_score.py → transformer_model.py  [主力]
  │     ├── calculateDimensionScore() → 关键词规则匹配                         [回退]
  │     └── 定义: struct AbilityScore, struct ScoreExplanation
  │
  ├── radar.cpp / radar.h         ← 调用 plot.py 生成雷达图
  │     └── 中转文件: output/radar_args.txt
  │
  ├── file_utils.cpp / file_utils.h ← 保存评分报告到 output/report.txt
  │
  └── ai.cpp / ai.h               ← 调用 DeepSeek API 生成分析建议
        └──中转文件: output/request.json, output/temp_response.json

Python 脚本:
  transformer_model.py            ← ★ Transformer 模型定义 + 训练 + 预测
  semantic_score.py               ← ★ C++ ↔ Python 桥接（推理入口）
  plot.py                         ← Matplotlib 雷达图绘制
  semantic_model.py               ← [已废弃] 旧版线性回归模型
```

### 文件依赖关系

```
         main.cpp
        /    |    \
       /     |     \
  score.cpp radar.cpp ai.cpp
    │          │        │
    │_popen    │system  │system+curl
    ▼          ▼        ▼
semantic_score.py  plot.py   DeepSeek API
    │
    │import
    ▼
transformer_model.py
```

---

## 二、主流程速览（main.cpp）

[main.cpp](main.cpp) 是整个程序的编排中心，不超过 35 行：

```cpp
int main() {
    system("chcp 65001 > nul");              // ① 设 UTF-8 编码

    UserInfo user = inputUserInfo();         // ② 收集用户输入（8 个字段）
    AbilityScore score = calculateScore(user);// ③ ★ 评分（核心步骤）
    printScore(score);                       // ④ 打印 6 个分数
    printDetailedScore(score);               // ⑤ 打印详细解释

    generateRadar(user, score);              // ⑥ 生成雷达图 png
    saveReport(score);                       // ⑦ 保存评分报告 txt

    AIResult aiRes = getAIAnalysis(user,score);// ⑧ 调用 DeepSeek AI
    printAIResult(aiRes);                    // ⑨ 打印 AI 分析
    saveAIResult(aiRes);                     // ⑩ 保存 AI 报告

    return 0;
}
```

**执行顺序**：①②③④⑤⑥⑦⑧⑨⑩，严格串行。

---

## 三、评分核心——Transformer 调用全链路

这是本文档的重点。从 C++ 到 Python 再到 Transformer 模型，完整链路如下：

```
calculateScore()                         [score.cpp:208]
  │
  │  拼接文本: skills + " " + project + " " + challenge
  │
  ├── runPythonSemanticModel(all, s)     [score.cpp:43]  ← 优先尝试
  │     │
  │     │  ① 写文件: output/semantic_input.txt
  │     │  ② _popen("python semantic_score.py --file output/semantic_input.txt")
  │     │  ③ 读 stdout: "10.0 5.0 6.7 6.4 7.0 5.4"
  │     │  ④ 解析 6 个 float → 四舍五入 int → 赋值给 s
  │     │  ⑤ s.explanations.clear()
  │     │
  │     └── 成功? → return s  ← 到此结束，不走下面
  │
  └── 失败? → calculateDimensionScore()  [score.cpp:217]  ← 兜底回退
        │
        └── 关键词匹配打分（professional / learning / project / ...）
```

### 3.1 C++ 入口 score.cpp

#### 核心函数 `runPythonSemanticModel`（第 43-94 行）

逐段注释版：

```cpp
static bool runPythonSemanticModel(const string& text, AbilityScore& s) {
    // ── 第 1 步：空文本检查 ──
    if (text.empty()) return false;

    // ── 第 2 步：把文本写入临时文件 ──
    // 为什么用文件而不是命令行传参？
    // → 文本可能包含空格、引号、特殊字符，直接放命令行极易转义出错
    CreateDirectoryA("output", nullptr);
    ofstream outFile("output/semantic_input.txt");
    outFile << text;          // UTF-8 编码写入
    outFile.close();

    // ── 第 3 步：构建命令并执行 ──
    // 命令: python semantic_score.py --file output/semantic_input.txt
    string cmd = "python semantic_score.py --file output/semantic_input.txt";
    // utf8_to_ansi: Windows 的 _popen 需要 ANSI 编码的命令行
    string ansiCmd = utf8_to_ansi(cmd);
    FILE* pipe = _popen(ansiCmd.c_str(), "r");  // 打开管道，读取 Python 的 stdout
    if (!pipe) return false;

    // ── 第 4 步：逐行读取 Python 的输出 ──
    char buffer[512];
    string output;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr)
        output += buffer;
    _pclose(pipe);

    // ── 第 5 步：解析 6 个浮点数 ──
    // Python 输出格式: "7.5 2.1 3.0 1.2 1.0 1.5\n"
    istringstream iss(output);
    vector<float> values;
    float v;
    while (iss >> v) values.push_back(v);

    if (values.size() != 6) return false;  // 必须是恰好 6 个

    // ── 第 6 步：赋值到结构体（float → int，四舍五入）──
    s.professional = (int)(values[0] + 0.5f);  // 专业能力
    s.learning     = (int)(values[1] + 0.5f);  // 学习能力
    s.project      = (int)(values[2] + 0.5f);  // 项目实践
    s.teamwork     = (int)(values[3] + 0.5f);  // 团队协作
    s.pressure     = (int)(values[4] + 0.5f);  // 抗压执行
    s.innovation   = (int)(values[5] + 0.5f);  // 创新思维

    // ── 第 7 步：清空关键词解释 ──
    // 这是区分“Transformer 评分”和“规则评分”的关键标记：
    // Transformer 没有关键词级别的解释，所以 explanations 为空
    s.explanations.clear();

    return true;  // 成功！
}
```

#### 调用入口 `calculateScore`（第 208-233 行）

```cpp
AbilityScore calculateScore(const UserInfo& u) {
    // 拼接三段文本作为模型输入
    string all = u.skills + " " + u.project + " " + u.challenge;

    AbilityScore s{};

    // ★ 优先：尝试 Transformer 评分
    if (runPythonSemanticModel(all, s)) {
        return s;  // 成功！直接返回，不走规则评分
    }

    // ★ 回退：只有 Transformer 失败时才走到这里
    auto profExp  = calculateDimensionScore(all, "professional");
    auto learnExp = calculateDimensionScore(all, "learning");
    // ...（省略其他维度）...
    // 此时 s.explanations 会包含关键词匹配详情
    return s;
}
```

**一句话总结**：`calculateScore` 先尝试 Python→Transformer，失败才走 C++ 关键词匹配。

---

### 3.2 Python 桥接 semantic_score.py

[semantic_score.py](semantic_score.py) 只有 85 行，是整个调用链的 **中间层**。

#### 职责

```
C++ _popen 调用 → semantic_score.py → transformer_model.py → stdout 输出分数
```

#### 关键代码路径

```python
def main():
    # ── Step 1: 解析命令行参数 ──
    # C++ 传入: --file output/semantic_input.txt
    parser.add_argument('--file', ...)
    parser.add_argument('text', ...)     # 也支持命令行直接传文本
    args = parser.parse_args()

    # ── Step 2: 读取输入文本 ──
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read().strip()
    else:
        text = args.text

    # ── Step 3: 空文本 → 全零输出 → C++ 端会回退 ──
    if not text:
        print('0 0 0 0 0 0')
        sys.exit(1)

    # ── Step 4: 导入并加载 Transformer 模型 ──
    from transformer_model import load_model, predict
    model, chars, char2idx = load_model()  # 首次自动训练

    # ── Step 5: 推理 ──
    scores = predict(text, model, char2idx)  # → [7.5, 2.1, 3.0, ...]

    # ── Step 6: 输出到 stdout（C++ 通过 _popen 管道读取）──
    print(' '.join(f'{x:.1f}' for x in scores))
    # 输出: "7.5 2.1 3.0 1.2 1.0 1.5"
```

#### 异常处理

| 异常类型 | 行为 | C++ 端现象 |
|---------|------|-----------|
| 文本为空 | `print('0 0 0 0 0 0')` | `runPythonSemanticModel` 返回 false，回退规则评分 |
| PyTorch 未安装 | `print(错误信息, stderr)` | stderr 不回传给 C++，pipe 读到空输出 |
| 模型文件不存在 | `load_model()` 自动训练 | 首次调用会慢，之后缓存 |
| 推理异常 | `print(错误信息, stderr); sys.exit(1)` | pipe 读到空输出，回退 |

---

### 3.3 Transformer 模型 transformer_model.py

[transformer_model.py](transformer_model.py) 是评分能力的核心，约 860 行。

#### 文件结构（按阅读顺序）

| 部分 | 行号范围 | 内容 |
|------|---------|------|
| 模块文档 | 1-44 | 架构总览 ASCII 图 |
| 第一部分 | 65-75 | 检查 PyTorch 是否安装，兼容无 torch 环境 |
| 第二部分 | 77-99 | 超参数配置（`EMBED_DIM=64`, `NUM_LAYERS=2` 等） |
| 第三部分 | 103-120 | 文本预处理：`tokenize()`, `build_vocab()`, `encode()`, `create_mask()` |
| 第四部分 | 123-345 | 合成训练数据生成：`PHRASE_POOL` 短语库 + `generate_one_sample()` |
| 第五部分 | 347-475 | **Transformer 模型组件**（核心） |
| 第六部分 | 480-500 | PyTorch Dataset 封装 |
| 第七部分 | 575-730 | `train_model()` 完整训练流程 |
| 第八部分 | 740-790 | `load_model()` + `predict()` — 推理入口 |
| 第九部分 | 795-850 | 命令行入口 `__main__` |
| else 分支 | 840+ | 无 PyTorch 时的占位函数 |

#### 模型组件详解

```
TextRegressionTransformer                     ← 顶层容器
  ├── Embedding (vocab_size → 64)            ← 字符 → 向量
  ├── PositionalEncoding (sin/cos)           ← 加入位置信息
  ├── Dropout(0.3)
  ├── TransformerEncoderLayer × 2            ← 每层:
  │     ├── MultiHeadAttention (4 heads)     ←   Q·K^T/√dk → softmax → ×V
  │     ├── LayerNorm + Residual             ←   加回去，防丢失
  │     ├── FeedForward (64→256→64)          ←   Linear→ReLU→Linear
  │     └── LayerNorm + Residual
  └── Head: Linear(64→64) + ReLU + Linear(64→6)  ← 输出 6 个分数
```

#### 关键函数速查

```python
# ── 推理相关 ──
tokenize(text)                         # "精通C++" → ['精','通','c','+','+']
encode(text, char2idx)                 # token列表 → 固定长度 ID 序列 [123, 45, 67, ...]
load_model()                           # 加载 output/transformer_model.pt
predict(text, model, char2idx)         # 单条文本 → [7.5, 2.1, ...]
create_mask(token_ids)                 # 创建 padding mask

# ── 训练相关 ──
generate_training_data(n)              # 生成 n 条合成训练样本
build_vocab(texts)                     # 构建字符词表
train_model(n_samples=None)            # 完整训练流程
```

#### 从文本到分数的完整数据流

```
"精通C++和Python，5年开发经验"
  │
  │ tokenize()
  ▼
['精','通','c','+','+','和','p','y','t','h','o','n','，','5','年','开','发','经','验']
  │
  │ encode()  ← 查 char2idx 映射表，补/截到 MAX_SEQ_LEN=256
  ▼
[234, 89, 12, 5, 5, 67, 45, 101, 103, 110, 108, 102, 3, 18, 56, 78, 90, 34, 67, 0, 0, ...(236个0)]
  │
  │ torch.tensor → (1, 256)  ← batch_size=1, seq_len=256
  ▼
Embedding:    (1, 256) → (1, 256, 64)   每个字符展开成 64 维向量
  │
  ▼
PositionalEncoding: 加上位置指纹
  │
  ▼
TransformerEncoderLayer × 2:
  ├── MultiHeadAttention: 256 个字符互相“看”，计算注意力
  └── FeedForward: 每个位置独立过两层全连接
  │
  ▼
Mean Pooling: (1, 256, 64) → (1, 64)    所有字符向量求平均
  │
  ▼
Head: (1, 64) → (1, 6)                  全连接输出
  │
  │ clamp(0, 10)
  ▼
[7.5, 2.1, 3.0, 1.2, 1.0, 1.5]          6 个分数
```

---

### 3.4 回退机制：规则评分

当以下任一情况发生时，退回到 C++ 关键词匹配：

| 回退触发条件 | 对应代码 |
|-------------|---------|
| 拼接后的文本为空 | `score.cpp:44` — `if (text.empty()) return false` |
| Python 脚本运行失败 | `score.cpp:64` — `if (!pipe) return false` |
| 输出无法解析为 6 个 float | `score.cpp:82` — `if (values.size() != 6) return false` |
| PyTorch 未安装 | `semantic_score.py:71-74` — 输出错误到 stderr |
| 模型文件损坏 | `semantic_score.py:75-77` — 异常退出 |

规则评分原理（[score.cpp](score.cpp) 第 96-206 行）：

```cpp
// 每个维度预定义了关键词 + 权重
static map<string, vector<KeywordWeight>> dimensionKeywords = {
    {"professional", {
        {"精通", 3.0}, {"C++", 2.5}, {"Python", 2.5}, ...
    }},
    {"learning", {
        {"自学", 2.5}, {"主动学习", 2.5}, ...
    }},
    // ... 共 6 个维度
};

// 计算规则：匹配到的关键词权重总和 / 全部关键词权重总和 × 10
// 结果四舍五入到 0-10 整数
```

---

## 四、其他模块速览

### 4.1 用户输入 input.cpp

- [input.h](input.h) 定义 `UserInfo` 结构体（8 个 string 字段）
- [input.cpp](input.cpp) 实现 `inputUserInfo()`，逐行 `getline(cin, ...)` 读取
- 设置了 `SetConsoleCP(CP_UTF8)` 确保中文输入正常

### 4.2 雷达图 radar.cpp + plot.py

调用链：

```
radar.cpp::generateRadar()
  ├── 写 output/radar_args.txt（姓名 + 6 个分数）
  └── system("python plot.py")
        │
        plot.py:
        ├── 读取 output/radar_args.txt
        ├── Matplotlib 极坐标雷达图
        └── 保存 output/radar.png (200dpi)
```

### 4.3 AI 分析 ai.cpp

调用链：

```
ai.cpp::getAIAnalysis()
  ├── makePrompt()           ← 把用户信息 + 分数拼成提示词
  ├── 写 output/request.json  ← {"model":"deepseek-chat", "messages":[...]}
  ├── system("curl ... deepseek API ...")  ← HTTP POST
  ├── 读 output/temp_response.json
  ├── extractAIResponse()     ← 手工解析 JSON，提取 content 字段
  └── 返回 AIResult.fullText
```

**注意**：AI 分析是独立的——它不知道评分用的是 Transformer 还是规则，它只看最终的 6 个 int 分数。

### 4.4 报告保存 file_utils.cpp

- 把 6 个分数写入 `output/report.txt`
- 纯文本格式，无复杂逻辑

---

## 五、数据结构一览

```cpp
// ── 定义在 input.h ──
struct UserInfo {
    string name;       // 姓名
    string gender;     // 性别
    string age;        // 年龄
    string major;      // 专业/职业
    string education;  // 学历
    string skills;     // 技能描述   ← 参与评分
    string project;    // 项目经历   ← 参与评分
    string challenge;  // 挑战经历   ← 参与评分
};

// ── 定义在 score.h ──
struct AbilityScore {
    int professional;   // 专业能力  [0-10]
    int learning;       // 学习能力  [0-10]
    int project;        // 项目实践  [0-10]
    int teamwork;       // 团队协作  [0-10]
    int pressure;       // 抗压执行  [0-10]
    int innovation;     // 创新思维  [0-10]
    vector<ScoreExplanation> explanations;  // 详细解释（Transformer 路径下为空）
};

struct ScoreExplanation {
    string dimension;            // 维度名
    int score;                   // 分数
    double confidence;           // 置信度 0.0~1.0
    vector<string> matchedKeywords;  // 匹配到的关键词
    vector<string> reasoning;        // 评分依据
};

// ── 定义在 ai.h ──
struct AIResult {
    string summary;    // 综合评价
    string trend;      // 发展趋势
    string advice;     // 提升建议
    string fullText;   // 完整回答（实际上只有这个字段在使用）
};
```

---

## 六、如何修改 Transformer 评分逻辑

### 场景 1：调整模型超参数

编辑 [transformer_model.py](transformer_model.py) 第二部分：

```python
EMBED_DIM = 64      # 加大 → 模型更强但更慢
NUM_HEADS = 4       # 必须是 EMBED_DIM 的约数
NUM_LAYERS = 2      # 加深 → 更强，但数据太少会过拟合
DROPOUT = 0.3       # 加大 → 防过拟合，但训练更慢
EPOCHS = 80         # 训练轮数
SYNTHETIC_SAMPLES = 800  # 合成数据量
```

改完删掉旧模型重新训练：
```bash
rm output/transformer_model.pt
python transformer_model.py --train
```

### 场景 2：添加更多短语提升模型质量

编辑 `PHRASE_POOL`（第 128 行起），按照现有格式添加：

```python
'professional': [
    # 格式: ("短语文本", [专业, 学习, 项目, 协作, 抗压, 创新])
    ("你新加的短语描述",           [3.0, 0.5, 1.0, 0.0, 0.0, 0.5]),
],
```

每个数值表示这条短语对该维度的贡献分（0-10）。

### 场景 3：修改评分维度（6 维 → N 维）

涉及多处修改：

| 文件 | 修改内容 |
|------|---------|
| `score.h` | `AbilityScore` 结构体增删字段 |
| `score.cpp` | `runPythonSemanticModel` 中解析 N 个 float |
| `score.cpp` | `printScore` 中打印 N 个维度 |
| `score.cpp` | `dimensionKeywords` 增删维度条目 |
| `transformer_model.py` | `DIMENSION_NAMES` 列表长度改为 N |
| `transformer_model.py` | `PHRASE_POOL` 增删维度 |
| `transformer_model.py` | `predict()` 输出 N 维（自动适配） |
| `radar.cpp` | `generateRadar` 写入 N 个分数 |
| `plot.py` | `labels` 列表改为 N 个 |
| `ai.cpp` | `makePrompt` 提示词模板更新 |

### 场景 4：切换回旧版线性回归模型

如果暂时不想用 Transformer：

```cpp
// score.cpp calculateScore() 中，注释掉这两行：
// if (runPythonSemanticModel(all, s)) return s;
```

这样会直接走 `calculateDimensionScore` 规则评分。

---

## 七、调试技巧

### 验证是否使用了 Transformer

运行后检查输出——如果**详细评分分析**中没有任何关键词匹配信息，说明走了 Transformer 路径；如果有“匹配关键词”列表，说明回退到了规则评分。

### 单独测试 Python 端

```bash
# 1. 直接测 Transformer 模型
python transformer_model.py "精通C++和Python，5年开发经验"

# 2. 测桥接脚本（模拟 C++ 调用方式）
echo "精通Python和算法，独立完成多个项目" > output/semantic_input.txt
python semantic_score.py --file output/semantic_input.txt

# 3. 查看模型文件是否存在
ls -la output/transformer_model.pt
ls -la output/transformer_vocab.json
```

### 排查 C++ → Python 通信

```cpp
// 在 runPythonSemanticModel 中加调试输出：
cout << "[DEBUG] cmd: " << cmd << endl;
cout << "[DEBUG] python output: [" << output << "]" << endl;
cout << "[DEBUG] parsed values: " << values.size() << endl;
```

### 强制使用规则评分（不用 Transformer）

把 `output/semantic_input.txt` 内容清空或不生成它，程序会自动回退。

### 查看完整评分过程

```bash
# 重新训练并观察训练过程
python transformer_model.py --train

# 用更多短语训练
python transformer_model.py --train --samples 1200
```

### 模型推理性能

在 Python 中测试推理速度：
```python
import time
from transformer_model import load_model, predict
model, chars, char2idx = load_model()
text = "精通C++和Python，5年开发经验" * 10  # 模拟长文本

start = time.time()
for _ in range(100):
    predict(text, model, char2idx)
elapsed = time.time() - start
print(f"100次推理耗时: {elapsed:.3f}s, 平均: {elapsed/100*1000:.1f}ms")
```

---

> 最后更新：2026/06/06
>
> 如需更详细的模型原理解释，请阅读 [ABILITYRADAR_AI.md](ABILITYRADAR_AI.md)（面向 AI 初学者）。
