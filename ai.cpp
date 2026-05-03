#include "ai.h"
#include <iostream>
#include <fstream>
#include <string>
#include <windows.h>
#include <cstdio>
#include <algorithm>

using namespace std;

//秘钥不要直接写在代码里
#define DEEPSEEK_API_KEY "sk-d616e455978a47429b22d2385xxxxx"

// JSON 转义函数（确保特殊字符在JSON中正确传递）
string escapeJson(const string &s) {
    string res;
    for (char c : s) {
        switch (c) {
            case '"':  res += "\\\""; break;
            case '\\': res += "\\\\"; break;
            case '\n': res += "\\n";  break;
            case '\r': res += "\\r";  break;
            case '\t': res += "\\t";  break;
            default:   res += c;      break;
        }
    }
    return res;
}

// 生成标准提示词
string makePrompt(const UserInfo& u, const AbilityScore& s) {
    char buf[4096];
    sprintf(buf,
        "你是专业能力评估专家，请根据以下用户信息和6项能力分数，严格输出3部分内容：\n"
        "1. 综合评价（100字内，简洁总结能力水平）\n"
        "2. 未来发展趋势（80字内，判断职业发展方向）\n"
        "3. 针对性提升建议（分3条，每条50字内，实用可落地）\n\n"
        "用户信息：\n"
        "姓名：%s\n专业：%s\n技能：%s\n项目经历：%s\n挑战经历：%s\n\n"
        "能力分数（满分10分）：\n"
        "专业能力：%d\n学习能力：%d\n项目实践：%d\n团队协作：%d\n抗压执行：%d\n创新思维：%d\n\n"
        "要求：语言正式、分点清晰、无多余格式、不使用Markdown。",
        u.name.c_str(), u.major.c_str(),
        u.skills.c_str(), u.project.c_str(), u.challenge.c_str(),
        s.professional, s.learning, s.project,
        s.teamwork, s.pressure, s.innovation
    );
    return string(buf);
}

// 读取文件内容（二进制模式，避免编码问题）
string readFile(const string& path) {
    ifstream f(path, ios::binary);
    if (!f.is_open()) return "文件读取失败";
    return string((istreambuf_iterator<char>(f)), istreambuf_iterator<char>());
}

// 提取AI响应中的文本内容，兼容错误信息和不同字段位置
string extractAIResponse(const string& json) {
    // 第一步：先检查是否有错误信息
    size_t errorPos = json.find("\"error\"");
    if (errorPos != string::npos) {
        size_t msgPos = json.find("\"message\":\"", errorPos);
        if (msgPos != string::npos) {
            msgPos += 11;
            size_t endPos = json.find("\"", msgPos);
            return "API 错误：" + json.substr(msgPos, endPos - msgPos);
        }
        return "API 返回错误，请检查Key/网络";
    }

    // 第二步：寻找内容字段，兼容不同接口的字段名
    size_t contentPos = json.find("\"content\":\"");
    if (contentPos == string::npos) {
        // 兼容DeepSeek部分接口的字段名变化
        contentPos = json.find("\"text\":\"");
        if (contentPos == string::npos) {
            // 打印原始JSON方便排查
            ofstream debugLog("output/debug_json.txt", ios::out);
            debugLog << json;
            debugLog.close();
            return "解析失败，已保存原始返回到 output/debug_json.txt，请检查";
        }
        contentPos += 7;
    } else {
        contentPos += 11;
    }

    // 第三步：完整提取内容，处理转义
    string res;
    bool escape = false;
    for (size_t i = contentPos; i < json.size(); i++) {
        char c = json[i];
        if (escape) {
            if (c == 'n') res += '\n';
            else if (c == 'r') res += '\r';
            else if (c == 't') res += '\t';
            else res += c;
            escape = false;
        } else if (c == '\\') {
            escape = true;
        } else if (c == '"') {
            break;
        } else {
            res += c;
        }
    }
    return res;
}

// 联网调用DeepSeek AI获取分析结果
AIResult getAIAnalysis(const UserInfo& user, const AbilityScore& score) {
    AIResult res;
    string prompt = makePrompt(user, score);

    // 确保output目录存在
    system("if not exist output mkdir output");

    // 使用临时文件传递JSON请求，避免命令行长度限制和转义问题
    // 先构建JSON请求文件
    ofstream reqFile("output/request.json", ios::out | ios::trunc);
    reqFile << "{\"model\":\"deepseek-chat\",\"messages\":[";
    reqFile << "{\"role\":\"user\",\"content\":\"" << escapeJson(prompt) << "\"}";
    reqFile << "],\"temperature\":0.3,\"max_tokens\":1000}";
    reqFile.close();

    // 使用 --data-binary 读取文件，避免命令行转义问题
    char cmd[1024];
    snprintf(cmd, sizeof(cmd),
        "curl -s -m 30 -X POST https://api.deepseek.com/chat/completions "
        "-H \"Authorization: Bearer %s\" "
        "-H \"Content-Type: application/json; charset=utf-8\" "
        "--data-binary @output/request.json > output/temp_response.json 2>&1",
        DEEPSEEK_API_KEY);

    // 执行请求
    int ret = system(cmd);
    if (ret != 0) {
        res.fullText = "curl 执行失败，请检查是否安装curl/网络是否正常";
        return res;
    }

    // 读取返回并解析
    string json = readFile("output/temp_response.json");
    res.fullText = extractAIResponse(json);

    return res;
}

// 打印AI结果
void printAIResult(const AIResult& res) {
    cout << "\n=====================================\n";
    cout << "              🧠 AI 深度分析\n";
    cout << "=====================================\n";
    cout << res.fullText << endl;
}

// 保存AI报告
void saveAIResult(const AIResult& res) {
    ofstream f("output/ai_analysis.txt", ios::out | ios::trunc);
    if (f.is_open()) {
        f << res.fullText;
        f.close();
    }
}