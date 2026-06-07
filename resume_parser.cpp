#include "resume_parser.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <windows.h>
#include <cstdio>

using namespace std;

// ── 工具函数：UTF-8 转 ANSI（Windows _popen 需要） ──
static string utf8_to_ansi(const string& utf8) {
    if (utf8.empty()) return {};
    int wide_size = MultiByteToWideChar(CP_UTF8, 0, utf8.data(), (int)utf8.size(), nullptr, 0);
    if (wide_size <= 0) return utf8;  // 降级返回原串
    wstring wide(wide_size, 0);
    MultiByteToWideChar(CP_UTF8, 0, utf8.data(), (int)utf8.size(), &wide[0], wide_size);

    int ansi_size = WideCharToMultiByte(CP_ACP, 0, wide.data(), wide_size, nullptr, 0, nullptr, nullptr);
    if (ansi_size <= 0) return utf8;
    string ansi(ansi_size, 0);
    WideCharToMultiByte(CP_ACP, 0, wide.data(), wide_size, &ansi[0], ansi_size, nullptr, nullptr);
    return ansi;
}

// ── 工具函数：简单的 JSON 字符串值提取 ──
// 从 JSON 中提取 "key": "value" 的值
static string extractJsonString(const string& json, const string& key) {
    string search = "\"" + key + "\": \"";
    size_t pos = json.find(search);
    if (pos == string::npos) {
        // 也搜索没有空格的格式
        search = "\"" + key + "\":\"";
        pos = json.find(search);
        if (pos == string::npos) return "";
        pos += search.length();
    } else {
        pos += search.length();
    }

    string result;
    bool escape = false;
    for (size_t i = pos; i < json.size(); i++) {
        char c = json[i];
        if (escape) {
            switch (c) {
                case 'n': result += '\n'; break;
                case 'r': result += '\r'; break;
                case 't': result += '\t'; break;
                case '\\': result += '\\'; break;
                case '"': result += '"'; break;
                default: result += c; break;
            }
            escape = false;
        } else if (c == '\\') {
            escape = true;
        } else if (c == '"') {
            break;
        } else {
            result += c;
        }
    }
    return result;
}

// ── 提取 JSON 中的 bool 值 ──
static bool extractJsonBool(const string& json, const string& key) {
    string search = "\"" + key + "\": true";
    if (json.find(search) != string::npos) return true;
    search = "\"" + key + "\":true";
    if (json.find(search) != string::npos) return true;
    return false;
}

// ── 读取文件全部内容 ──
static string readFile(const string& path) {
    ifstream f(path, ios::binary);
    if (!f.is_open()) return "";
    return string((istreambuf_iterator<char>(f)), istreambuf_iterator<char>());
}

// ── 执行命令并获取 stdout 输出 ──
static string executeCommand(const string& cmd) {
    string ansiCmd = utf8_to_ansi(cmd);// 转换命令为 ANSI，避免 Windows cmd 乱码问题
    if (ansiCmd.empty()) ansiCmd = cmd;// 转换失败则使用原命令（可能会乱码，但至少不崩溃）

    // ★ "rb" 二进制模式：Python 输出 UTF-8，避免 Windows ANSI 转换损坏中文
    FILE* pipe = _popen(ansiCmd.c_str(), "rb");
    if (!pipe) return "";

    char buffer[1024];
    string output;// 读取命令输出
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    _pclose(pipe);
    return output;
}

// ═══════════════════════════════════════════════
// 公开接口
// ═══════════════════════════════════════════════

bool isResumeFile(const string& filePath) {
    // 获取扩展名（小写）
    size_t dot = filePath.find_last_of('.');
    if (dot == string::npos) return false;

    string ext = filePath.substr(dot);
    for (char& c : ext) c = tolower(c);

    return ext == ".pdf" || ext == ".png" || ext == ".jpg"
        || ext == ".jpeg" || ext == ".bmp" || ext == ".tiff" || ext == ".tif";
}

ResumeData parseResumeFile(const string& filePath) {
    ResumeData data{};// 默认构造，success 默认为 false，其他字段为空字符串
    data.success = false;

    // ── 1. 检查文件存在 ──
    ifstream testFile(filePath);
    if (!testFile.is_open()) {
        data.error = "文件不存在: " + filePath;
        return data;
    }
    testFile.close();

    // ── 2. 检查文件格式 ──
    if (!isResumeFile(filePath)) {
        data.error = "不支持的文件格式，请使用 PDF、PNG、JPG 格式";
        return data;
    }

    // ── 3. 确保 output 目录存在 ──
    CreateDirectoryA("output", nullptr);

    // ── 4. 调用 Python 解析脚本 ──
    // 用引号包裹文件路径，处理空格
    string cmd = "python resume_parser.py --file \"" + filePath + "\"";
    string jsonOutput = executeCommand(cmd);

    if (jsonOutput.empty()) {
        data.error = "Python 脚本执行失败，请确认 resume_parser.py 存在且 Python 环境正确";
        return data;
    }

    // ── 5. 解析 JSON 输出 ──
    // 保存原始输出便于调试
    ofstream debugFile("output/resume_debug.json", ios::out | ios::trunc);
    if (debugFile.is_open()) {
        debugFile << jsonOutput;
        debugFile.close();
    }

    bool success = extractJsonBool(jsonOutput, "success");
    if (!success) {
        data.error = extractJsonString(jsonOutput, "error");
        if (data.error.empty()) {
            data.error = "简历解析失败，请检查文件格式是否正确";
        }
        return data;
    }

    // ── 6. 提取各字段 ──
    data.success = true;
    data.name = extractJsonString(jsonOutput, "name");
    data.gender = extractJsonString(jsonOutput, "gender");
    data.age = extractJsonString(jsonOutput, "age");
    data.major = extractJsonString(jsonOutput, "major");
    data.education = extractJsonString(jsonOutput, "education");
    data.skills = extractJsonString(jsonOutput, "skills");
    data.project = extractJsonString(jsonOutput, "project");
    data.challenge = extractJsonString(jsonOutput, "challenge");
    data.raw_text = extractJsonString(jsonOutput, "raw_text");

    return data;
}
