#include "score.h"
#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <algorithm>
#include <cctype>
#include <regex>
#include <iomanip>
#include <windows.h>
#include <cstdio>
#include <sstream>
#include <fstream>

using namespace std;

static string utf8_to_ansi(const string& utf8) {
    if (utf8.empty()) return {};
    int wide_size = MultiByteToWideChar(CP_UTF8, 0, utf8.data(), (int)utf8.size(), nullptr, 0);
    if (wide_size <= 0) return {};
    wstring wide(wide_size, 0);
    MultiByteToWideChar(CP_UTF8, 0, utf8.data(), (int)utf8.size(), &wide[0], wide_size);

    int ansi_size = WideCharToMultiByte(CP_ACP, 0, wide.data(), wide_size, nullptr, 0, nullptr, nullptr);
    if (ansi_size <= 0) return {};
    string ansi(ansi_size, 0);
    WideCharToMultiByte(CP_ACP, 0, wide.data(), wide_size, &ansi[0], ansi_size, nullptr, nullptr);
    return ansi;
}

static string escapeCommandArg(const string& text) {
    string escaped;
    for (char c : text) {
        if (c == '"') {
            escaped += "\\\"";
        } else {
            escaped += c;
        }
    }
    return escaped;
}

static bool runPythonSemanticModel(const string& text, AbilityScore& s) {
    if (text.empty()) {
        return false;
    }

    CreateDirectoryA("output", nullptr);
    const string tempPath = "output/semantic_input.txt";

    ofstream outFile(tempPath, ios::out | ios::trunc);
    if (!outFile.is_open()) {
        return false;
    }
    outFile << text;
    outFile.close();

    string cmd = "python semantic_score.py --file " + tempPath;
    string ansiCmd = utf8_to_ansi(cmd);
    if (ansiCmd.empty()) {
        return false;
    }

    FILE* pipe = _popen(ansiCmd.c_str(), "r");
    if (!pipe) {
        return false;
    }

    char buffer[512];
    string output;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    _pclose(pipe);

    istringstream iss(output);
    vector<float> values;
    float value;
    while (iss >> value) {
        values.push_back(value);
    }
    if (values.size() != 6) {
        return false;
    }

    s.professional = static_cast<int>(values[0] + 0.5f);
    s.learning = static_cast<int>(values[1] + 0.5f);
    s.project = static_cast<int>(values[2] + 0.5f);
    s.teamwork = static_cast<int>(values[3] + 0.5f);
    s.pressure = static_cast<int>(values[4] + 0.5f);
    s.innovation = static_cast<int>(values[5] + 0.5f);
    s.explanations.clear();
    return true;
}

// 关键词权重结构
struct KeywordWeight {
    string keyword;
    double weight;
    string category;  // 程度词、时间词、专业词等
};

// 维度关键词数据库
static map<string, vector<KeywordWeight>> dimensionKeywords = {
    {"professional", {
        {"精通", 3.0, "level"}, {"熟练", 2.5, "level"}, {"掌握", 2.0, "level"}, {"熟悉", 1.5, "level"}, {"了解", 1.0, "level"}, {"入门", 0.5, "level"},
        {"10年", 3.0, "experience"}, {"5年", 2.5, "experience"}, {"3年", 2.0, "experience"}, {"2年", 1.5, "experience"}, {"1年", 1.0, "experience"},
        {"C++", 2.5, "skill"}, {"Python", 2.5, "skill"}, {"Java", 2.5, "skill"}, {"算法", 2.0, "skill"}, {"数据结构", 2.0, "skill"}, 
        {"数据库", 1.8, "skill"}, {"编程", 1.5, "skill"}, {"开发", 1.5, "skill"}, {"专业", 1.2, "skill"}
    }},
    {"learning", {
        {"自学", 2.5, "action"}, {"主动学习", 2.5, "action"}, {"持续学习", 2.5, "action"}, {"研究", 2.0, "action"}, {"探索", 2.0, "action"},
        {"掌握新技术", 2.5, "achievement"}, {"学习新知识", 2.0, "achievement"}, {"提升技能", 2.0, "achievement"}, {"进修", 1.8, "achievement"},
        {"快速适应", 1.5, "quality"}, {"学习能力强", 1.5, "quality"}
    }},
    {"project", {
        {"独立完成项目", 3.0, "scale"}, {"带领团队项目", 3.0, "scale"}, {"大型项目", 2.5, "scale"}, {"复杂项目", 2.5, "scale"}, {"项目", 1.5, "scale"},
        {"从零搭建", 2.5, "complexity"}, {"架构设计", 2.5, "complexity"}, {"系统开发", 2.0, "complexity"}, {"功能实现", 1.8, "complexity"}, {"开发", 1.2, "complexity"},
        {"部署上线", 2.0, "deployment"}, {"生产环境", 1.8, "deployment"}, {"用户使用", 1.5, "deployment"}
    }},
    {"teamwork", {
        {"团队协作", 2.5, "skill"}, {"跨部门沟通", 2.5, "skill"}, {"项目协调", 2.0, "skill"}, {"配合默契", 2.0, "skill"},
        {"带领团队", 3.0, "leadership"}, {"指导新人", 2.5, "leadership"}, {"培训同事", 2.0, "leadership"}, {"团队", 1.5, "skill"},
        {"解决冲突", 2.0, "conflict"}, {"调解分歧", 1.8, "conflict"}, {"沟通", 1.2, "skill"}
    }},
    {"pressure", {
        {"高压力环境", 2.5, "environment"}, {"紧急任务", 2.0, "environment"}, {"deadline", 2.0, "environment"}, {"高压力", 2.5, "environment"}, {"压力", 1.5, "environment"},
        {"坚持不懈", 2.5, "quality"}, {"责任心强", 2.0, "quality"}, {"按时交付", 2.0, "quality"}, {"克服困难", 2.0, "quality"},
        {"独立解决问题", 1.8, "problem"}, {"故障排查", 1.8, "problem"}, {"执行", 1.2, "quality"}
    }},
    {"innovation", {
        {"创新设计", 3.0, "creation"}, {"技术创新", 2.5, "creation"}, {"优化方案", 2.5, "creation"}, {"改进流程", 2.0, "creation"},
        {"创意想法", 2.0, "idea"}, {"新思路", 1.8, "idea"}, {"突破传统", 1.8, "idea"},
        {"效率提升", 2.0, "result"}, {"性能优化", 2.0, "result"}, {"用户体验改善", 1.8, "result"}
    }}
};

// 工具函数：字符串转小写
static string toLower(const string& str) {
    string result = str;
    transform(result.begin(), result.end(), result.begin(), ::tolower);
    return result;
}

// 工具函数：计算文本相似度（改进版，支持中文）
static double calculateSimilarity(const string& text, const string& keyword) {
    // 对于中文，不进行大小写转换
    const string& t = text;
    const string& k = keyword;
    
    // 精确匹配
    if (t.find(k) != string::npos) {
        return 1.0;
    }
    
    return 0.0;  // 只做精确匹配
}

// 智能评分函数
static ScoreExplanation calculateDimensionScore(const string& text, const string& dimension) {
    ScoreExplanation result;
    result.dimension = dimension;
    result.score = 0;
    result.confidence = 0.0;
    
    auto it = dimensionKeywords.find(dimension);
    if (it == dimensionKeywords.end()) {
        return result;
    }
    
    const auto& keywords = it->second;
    double totalWeight = 0.0;
    double matchedWeight = 0.0;
    vector<string> matched;
    vector<string> reasoning;
    
    for (const auto& kw : keywords) {
        double similarity = calculateSimilarity(text, kw.keyword);
        totalWeight += kw.weight;
        
        if (similarity > 0.0) {
            double effectiveWeight = kw.weight * similarity;
            matchedWeight += effectiveWeight;
            
            matched.push_back(kw.keyword);
            reasoning.push_back("匹配关键词 '" + kw.keyword + "' (权重: " + to_string(kw.weight) + ")");
        }
    }
    
    // 计算得分 (0-10分)
    if (totalWeight > 0) {
        double scoreRatio = matchedWeight / totalWeight;
        result.score = static_cast<int>(scoreRatio * 10.0 + 0.5);  // 四舍五入
        result.score = max(0, min(10, result.score));  // 确保范围
    }
    
    // 计算置信度
    if (!matched.empty()) {
        result.confidence = min(1.0, matched.size() / 3.0);  // 匹配越多置信度越高
    }
    
    result.matchedKeywords = matched;
    result.reasoning = reasoning;
    
    return result;
}

AbilityScore calculateScore(const UserInfo& u) {// 根据用户信息计算能力分数
    string all = u.skills + " " + u.project + " " + u.challenge;
    AbilityScore s{};

    if (runPythonSemanticModel(all, s)) {
        return s;
    }

    // 如果模型调用失败，则继续使用本地规则评分
    auto profExp = calculateDimensionScore(all, "professional");
    auto learnExp = calculateDimensionScore(all, "learning");
    auto projExp = calculateDimensionScore(all, "project");
    auto teamExp = calculateDimensionScore(all, "teamwork");
    auto pressExp = calculateDimensionScore(all, "pressure");
    auto innovExp = calculateDimensionScore(all, "innovation");

    s.professional = profExp.score;
    s.learning = learnExp.score;
    s.project = projExp.score;
    s.teamwork = teamExp.score;
    s.pressure = pressExp.score;
    s.innovation = innovExp.score;
    s.explanations = {profExp, learnExp, projExp, teamExp, pressExp, innovExp};

    return s;
}

void printScore(const AbilityScore& s) {// 打印能力分数到控制台
    cout << "\n===== 能力评分（0-10）=====\n";
    cout << "专业能力：" << s.professional << endl;
    cout << "学习能力：" << s.learning << endl;
    cout << "项目实践：" << s.project << endl;
    cout << "团队协作：" << s.teamwork << endl;
    cout << "抗压执行：" << s.pressure << endl;
    cout << "创新思维：" << s.innovation << endl;
}

void printDetailedScore(const AbilityScore& s) {// 打印详细评分解释
    cout << "\n===== 详细评分分析 =====\n";
    
    for (const auto& exp : s.explanations) {
        cout << "\n📊 " << exp.dimension << " (得分: " << exp.score << "/10, 置信度: " << fixed << setprecision(1) << exp.confidence * 100 << "%)\n";
        
        if (!exp.matchedKeywords.empty()) {
            cout << "   匹配关键词: ";
            for (size_t i = 0; i < exp.matchedKeywords.size(); ++i) {
                cout << exp.matchedKeywords[i];
                if (i < exp.matchedKeywords.size() - 1) cout << ", ";
            }
            cout << "\n";
            
            cout << "   评分依据:\n";
            for (const auto& reason : exp.reasoning) {
                cout << "   • " << reason << "\n";
            }
        } else {
            cout << "   未匹配到相关关键词\n";
        }
    }
    cout << "\n💡 提示：置信度越高表示匹配度越好，评分越可靠\n";
}