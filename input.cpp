#include "input.h"
#include "resume_parser.h"
#include <iostream>
#include <string>
#include <windows.h>
using namespace std;

int inputModeMenu() {
    SetConsoleCP(CP_UTF8);
    SetConsoleOutputCP(CP_UTF8);

    cout << "\n请选择输入方式：\n";
    cout << "  [1] 手动输入信息\n";
    cout << "  [2] 上传简历文件（PDF / 图片）\n";
    cout << "  [0] 退出程序\n";
    cout << "请输入选项（0/1/2）：";

    string choice;
    getline(cin, choice);

    // 简单解析
    if (choice == "1") return 1;
    if (choice == "2") return 2;
    if (choice == "0") return 0;
    return -1;  // 无效输入
}

UserInfo inputUserInfo() {
    UserInfo u;

    // 设置控制台输入编码为UTF-8
    SetConsoleCP(CP_UTF8);
    SetConsoleOutputCP(CP_UTF8);

    cout << "请输入姓名："; getline(cin, u.name);
    cout << "请输入性别："; getline(cin, u.gender);
    cout << "请输入年龄："; getline(cin, u.age);
    cout << "请输入专业/职业："; getline(cin, u.major);
    cout << "请输入学历："; getline(cin, u.education);
    cout << "请输入技能描述："; getline(cin, u.skills);
    cout << "请输入项目经历："; getline(cin, u.project);
    cout << "请输入挑战与成长："; getline(cin, u.challenge);

    // 手动输入没有 raw_text
    u.raw_text = "";

    return u;
}

UserInfo resumeToUserInfo(const ResumeData& resume) {
    UserInfo u;
    u.name = resume.name;
    u.gender = resume.gender;
    u.age = resume.age;
    u.major = resume.major;
    u.education = resume.education;
    u.skills = resume.skills;
    u.project = resume.project;
    u.challenge = resume.challenge;
    u.raw_text = resume.raw_text;
    return u;
}