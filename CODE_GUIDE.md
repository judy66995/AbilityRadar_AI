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
- [四、简历解析模块](#四简历解析模块)
  - [4.1 C++ 入口 resume_parser.cpp](#41-c-入口-resume_parsercpp)
  - [4.2 Python 解析引擎 resume_parser.py](#42-python-解析引擎-resume_parserpy)
  - [4.3 字段提取逻辑](#43-字段提取逻辑)
- [五、其他模块速览](#五其他模块速览)
  - [5.1 用户输入 input.cpp](#51-用户输入-inputcpp)
  - [5.2 雷达图 radar.cpp + plot.py](#52-雷达图-radarcpp--plotpy)
  - [5.3 AI 分析 ai.cpp](#53-ai-分析-aicpp)
  - [5.4 报告保存 file_utils.cpp](#54-报告保存-file_utilscpp)
- [六、数据结构一览](#六数据结构一览)
- [七、如何修改 Transformer 评分逻辑](#七如何修改-transformer-评分逻辑)
- [八、调试技巧](#八调试技巧)

---

## 一、项目全景地图

```
main.cpp                          ← 程序入口，编排所有步骤
  │
  ├── input.cpp / input.h         ← 控制台交互（菜单 + 手动输入 + 简历转换）
  │     ├── 定义: struct UserInfo（含 raw_text）
  │     ├── inputModeMenu()       ← 选择 [1]手动 / [2]简历 / [0]退出
  │     └── resumeToUserInfo()    ← ResumeData → UserInfo 转换
  │
  ├── resume_parser.cpp / .h      ← ★ 简历解析桥接 ★
  │     └── parseResumeFile() → resume_parser.py → 返回 ResumeData
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
        └── 中转文件: output/request.json, output/temp_response.json

Python 脚本:
  transformer_model.py            ← ★ Transformer 模型定义 + 训练 + 预测
  semantic_score.py               ← ★ C++ ↔ Python 桥接（评分推理入口）
  resume_parser.py                ← ★ 简历解析引擎（PDF/图片 → 结构化字段）
  plot.py                         ← Matplotlib 雷达图绘制
  semantic_model.py               ← [已废弃] 旧版线性回归模型
```

### 文件依赖关系

```
         main.cpp
        /    |     \
       /     |      \
  input.cpp  score.cpp  radar.cpp  ai.cpp  resume_parser.cpp
    │          │           │          │           │
    │          │_popen     │system    │system+curl│_popen
    │          ▼           ▼          ▼           ▼
    │     semantic_score.py  plot.py  DeepSeekAPI  resume_parser.py
    │          │
    │          │import
    │          ▼
    │     transformer_model.py
    │
    └── inputModeMenu() → 选择手动/简历模式
                           → 简历模式 → parseResumeFile()
```

---

## 二、主流程速览（main.cpp）

[main.cpp](main.cpp) 是整个程序的编排中心：

```cpp
int main() {
    system("chcp 65001 > nul");              // ① 设 UTF-8 编码

    int mode = inputModeMenu();              // ② 选择输入方式 [1]手动 [2]简历
    // 循环直到有效的 0/1/2 输入

    UserInfo user;

    if (mode == 1) {
        user = inputUserInfo();              // ③a 手动输入 8 个字段
    } else if (mode == 2) {
        getline(cin, filePath);              // ③b 输入简历文件路径
        ResumeData resume = parseResumeFile(filePath);  // 调用 Python 解析
        // 显示提取结果 → 用户确认/拒绝
        user = resumeToUserInfo(resume);     // 转换为 UserInfo
    }

    AbilityScore score = calculateScore(user);// ④ 评分
    printScore(score);                       // ⑤ 打印分数
    printDetailedScore(score);               // ⑥ 打印详细解释

    generateRadar(user, score);              // ⑦ 生成雷达图
    saveReport(score);                       // ⑧ 保存评分报告

    AIResult aiRes = getAIAnalysis(user, score);// ⑨ DeepSeek AI 分析
    printAIResult(aiRes);                    // ⑩ 打印 AI 分析
    saveAIResult(aiRes);                     // ⑪ 保存 AI 报告

    return 0;
}
```

---

## 三、评分核心——Transformer 调用全链路

这是最关键的模块。从 C++ 到 Python 再到 Transformer 模型，完整链路如下：

```
calculateScore()                         [score.cpp]
  │
  │  拼接文本: skills + " " + project + " " + challenge + " " + raw_text
  │
  ├── runPythonSemanticModel(all, s)     ← 优先尝试
  │     │
  │     │  ① 写文件: output/semantic_input.txt
  │     │  ② _popen("python semantic_score.py --file output/semantic_input.txt")
  │     │  ③ 读 stdout: "7.5 2.1 3.0 1.2 1.0 1.5"
  │     │  ④ 解析 6 个 float → 四舍五入 int → 赋值给 s
  │     │  ⑤ s.explanations.clear()
  │     │
  │     └── 成功? → return s
  │
  └── 失败? → calculateDimensionScore()  ← 兜底回退
        │
        └── 关键词匹配打分
```

### 3.1 C++ 入口 score.cpp

#### 核心函数 `runPythonSemanticModel`

- 把文本写入 `output/semantic_input.txt`（UTF-8）
- `_popen("python semantic_score.py --file output/semantic_input.txt", "r")` 调用 Python
- 读取 stdout 的 6 个空格分隔 float → 四舍五入为 int
- 成功后 `explanations.clear()` — 这是区分 "Transformer 评分" 和 "规则评分" 的标记

#### 调用入口 `calculateScore`

- 拼接文本时**包含 raw_text**（简历全文），提供更丰富的上下文
- 优先尝试 Transformer 评分，失败回退到规则评分

### 3.2 Python 桥接 semantic_score.py

仅 ~85 行。职责：解析 `--file` 参数 → 读取输入文本 → 加载 `transformer_model` → `predict()` → 输出 6 个空格分隔分数到 stdout。

### 3.3 Transformer 模型 transformer_model.py

详见 [ABILITYRADAR_AI.md](ABILITYRADAR_AI.md) 第 4 节。

### 3.4 回退机制：规则评分

回退触发条件：
- 拼接文本为空
- Python 脚本运行失败（PyTorch 未安装、模型文件损坏等）
- 输出无法解析为恰好 6 个 float

回退时由 `dimensionKeywords` 做关键词匹配打分，`explanations` 会包含匹配详情。

---

## 四、简历解析模块

### 架构总览

```
resume_parser.cpp::parseResumeFile()
  ├── 检查文件存在 + 格式（.pdf/.png/.jpg/...）
  ├── _popen("python resume_parser.py --file \"<path>\"", "rb")
  │     │
  │     resume_parser.py:
  │     ├── PDF → pdfminer.six（主力，CJK兼容好）→ 回退 PyMuPDF
  │     ├── 图片 → PaddleOCR
  │     └── parse_resume_fields() → 结构化字段提取
  │
  ├── 读取 stdout JSON
  ├── extractJsonString() 手工解析 JSON（不引入第三方库）
  └── 填充 ResumeData → 返回
```

### 4.1 C++ 入口 resume_parser.cpp

- `parseResumeFile(filePath)` — 主接口，返回 `ResumeData`
- `isResumeFile(filePath)` — 检查文件扩展名
- `executeCommand()` — UTF-8 → ANSI 转码后 `_popen("rb")` 二进制模式读取
- `extractJsonString()` / `extractJsonBool()` — 轻量手工 JSON 解析

### 4.2 Python 解析引擎 resume_parser.py

约 400 行，包含：

| 函数 | 职责 |
|------|------|
| `extract_text_from_pdf()` | pdfminer.six → PyMuPDF 双引擎回退 |
| `extract_text_from_image()` | PaddleOCR 中文 OCR |
| `extract_name()` | 多模式姓名识别 |
| `extract_gender()` | 性别匹配 |
| `extract_age()` | 年龄/出生日期推算 |
| `extract_education()` | 学历关键词 + 括号内匹配 |
| `extract_major()` | 专业/求职意向提取 |
| `extract_skills()` | 技能关键词库匹配 |
| `extract_section()` | 通用章节提取器 |
| `extract_project_experience()` | 项目经历提取 |
| `extract_challenge_and_self_eval()` | 自我评价提取 |
| `parse_resume_fields()` | 综合解析入口 |

### 4.3 字段提取逻辑

- **姓名**：`姓名：XXX` → "个人简历"后独立短行 → 前10行中2-3字纯中文
- **年龄**：`年龄：25` → `25岁` → `出生：2004` → 简历中 `2004.08` 格式出生年月推算
- **学历**：括号内匹配 `（本科）` → 关键词匹配
- **专业**：`XXX专业（` → `专业：XXX` → `求职意向：XXX`
- **技能**：技能关键词库（~80个词）正则匹配
- **项目经历**：章节提取器（`项目经历`...`奖项证书`之间）
- **自我评价**：章节提取器（`自我评价`...文末）

---

## 五、其他模块速览

### 5.1 用户输入 input.cpp

- `inputModeMenu()` — 显示 `[1]手动 [2]简历 [0]退出` 菜单，返回 1/2/0
- `inputUserInfo()` — 逐行 `getline` 读取 8 个字段
- `resumeToUserInfo(resume)` — `ResumeData` → `UserInfo` 转换，保留 `raw_text`

### 5.2 雷达图 radar.cpp + plot.py

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

### 5.3 AI 分析 ai.cpp

调用链：
```
ai.cpp::getAIAnalysis()
  ├── makePrompt()           ← 构建提示词（含简历全文 raw_text，最多3000字）
  ├── 写 output/request.json  ← {"model":"deepseek-chat", "messages":[...]}
  ├── system("curl ... deepseek API ...")  ← HTTP POST
  ├── 读 output/temp_response.json
  ├── extractAIResponse()     ← 解析 JSON 提取 content 字段
  └── 返回 AIResult.fullText
```

**注意**：AI 分析是独立的——它只知道最终的 6 个 int 分数 + UserInfo + raw_text。

### 5.4 报告保存 file_utils.cpp

- 把 6 个分数写入 `output/report.txt`
- 纯文本格式

---

## 六、数据结构一览

```cpp
// ── 定义在 input.h ──
struct UserInfo {
    string name;       // 姓名
    string gender;     // 性别
    string age;        // 年龄
    string major;      // 专业/职业
    string education;  // 学历
    string skills;     // 技能描述       ← 参与评分
    string project;    // 项目经历       ← 参与评分
    string challenge;  // 挑战经历       ← 参与评分
    string raw_text;   // ★ 简历全文     ← 参与评分 + AI分析
};

// ── 定义在 resume_parser.h ──
struct ResumeData {
    bool success;          // 解析是否成功
    string name, gender, age, major, education;
    string skills, project, challenge;
    string raw_text;       // 简历全文
    string error;          // 错误信息
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
    string fullText;   // 完整回答（实际只填充此字段）
};
```

---

## 七、如何修改 Transformer 评分逻辑

### 场景 1：调整模型超参数

编辑 [transformer_model.py](transformer_model.py) 第二部分：
```python
EMBED_DIM = 64      # 加大 → 模型更强但更慢
NUM_HEADS = 4       # 必须是 EMBED_DIM 的约数
NUM_LAYERS = 2      # 加深 → 更强，但数据太少会过拟合
DROPOUT = 0.3       # 加大 → 防过拟合
EPOCHS = 80         # 训练轮数
SYNTHETIC_SAMPLES = 800  # 合成数据量
```

改完删旧模型重新训练：
```bash
rm output/transformer_model.pt
python transformer_model.py --train
```

### 场景 2：添加更多短语提升模型质量

编辑 `PHRASE_POOL`，按现有格式添加：
```python
'professional': [
    ("你新加的短语描述", [3.0, 0.5, 1.0, 0.0, 0.0, 0.5]),
],
```
每个数值表示该短语对 6 个维度的贡献分（0-10）。

### 场景 3：完善简历字段提取

编辑 [resume_parser.py](resume_parser.py) 第三部分。几个关键位置：
- `TECH_SKILLS` 列表 — 添加新技能关键词
- `extract_name()` — 添加新的姓名匹配模式
- `extract_age()` — 添加新的年龄提取方式
- `extract_section()` — 修改章节识别逻辑

### 场景 4：修改评分维度（6 维 → N 维）

涉及多处修改：

| 文件 | 修改内容 |
|------|---------|
| `score.h` | `AbilityScore` 结构体增删字段 |
| `score.cpp` | `runPythonSemanticModel` 中解析 N 个 float |
| `score.cpp` | `printScore` 中打印 N 个维度 |
| `score.cpp` | `dimensionKeywords` 增删维度条目 |
| `transformer_model.py` | `DIMENSION_NAMES` 长度改为 N |
| `transformer_model.py` | `PHRASE_POOL` 增删维度 |
| `radar.cpp` | `generateRadar` 写入 N 个分数 |
| `plot.py` | `labels` 列表改为 N 个 |
| `ai.cpp` | `makePrompt` 提示词模板更新 |

---

## 八、调试技巧

### 单独测试 Python 端

```bash
# 1. 直接测 Transformer 模型
python transformer_model.py "精通C++和Python，5年开发经验"

# 2. 测桥接脚本（模拟 C++ 调用方式）
echo "精通Python和算法，独立完成多个项目" > output/semantic_input.txt
python semantic_score.py --file output/semantic_input.txt

# 3. 测简历解析
python resume_parser.py --file "C:/path/to/resume.pdf"

# 4. 检查模型文件
ls -la output/transformer_model.pt output/transformer_vocab.json
```

### 验证是否使用了 Transformer

运行后看"详细评分分析"——无关键词匹配信息 = Transformer 路径；有"匹配关键词"列表 = 回退到规则评分。

### 排查 C++ → Python 通信

在 `resume_parser.cpp` 的 `executeCommand()` 或 `score.cpp` 的 `runPythonSemanticModel()` 中加调试输出，检查 `cmd` 和 `output`。Python 输出也会保存到 `output/resume_debug.json` 供排查。

### 手动输入无 raw_text

手动输入模式下 `raw_text` 为空字符串，`ai.cpp` 的 `makePrompt()` 会自动跳过简历原文附件。

### 模型推理性能测试

```python
import time
from transformer_model import load_model, predict
model, chars, char2idx = load_model()
text = "精通C++和Python，5年开发经验" * 10

start = time.time()
for _ in range(100):
    predict(text, model, char2idx)
elapsed = time.time() - start
print(f"100次推理耗时: {elapsed:.3f}s, 平均: {elapsed/100*1000:.1f}ms")
```

---

> 最后更新：2026/06/07
>
> 如需更详细的 Transformer 原理和训练说明，请阅读 [ABILITYRADAR_AI.md](ABILITYRADAR_AI.md)（面向 AI 初学者）。
