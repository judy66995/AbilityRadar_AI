#ifndef RESUME_PARSER_H
#define RESUME_PARSER_H

#include <string>

struct ResumeData {
    bool success;
    std::string name;
    std::string gender;
    std::string age;
    std::string major;
    std::string education;
    std::string skills;
    std::string project;
    std::string challenge;
    std::string raw_text;   // 简历全文
    std::string error;      // 错误信息
};

// 解析简历文件（PDF/图片）
// 内部调用 resume_parser.py
ResumeData parseResumeFile(const std::string& filePath);

// 检查文件是否是支持的简历格式
bool isResumeFile(const std::string& filePath);

#endif
