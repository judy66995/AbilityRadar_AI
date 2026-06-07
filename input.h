#ifndef INPUT_H
#define INPUT_H

#include <string>

struct UserInfo {
    std::string name;
    std::string gender;
    std::string age;
    std::string major;
    std::string education;
    std::string skills;
    std::string project;
    std::string challenge;
    std::string raw_text;   // 简历全文（AI分析用，手动输入时为空）
};

// 输入方式选择菜单，返回 1=手动输入，2=简历上传
int inputModeMenu();

// 手动控制台输入
UserInfo inputUserInfo();

// 从 ResumeData 转换为 UserInfo
UserInfo resumeToUserInfo(const struct ResumeData& resume);

#endif