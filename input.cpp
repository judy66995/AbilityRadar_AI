#include "input.h"
#include <iostream>
using namespace std;

UserInfo inputUserInfo() {
    UserInfo u;
    cout << "请输入姓名："; getline(cin, u.name);
    cout << "请输入性别："; getline(cin, u.gender);
    cout << "请输入年龄："; getline(cin, u.age);
    cout << "请输入专业/职业："; getline(cin, u.major);
    cout << "请输入学历："; getline(cin, u.education);
    cout << "请输入技能描述："; getline(cin, u.skills);
    cout << "请输入项目经历："; getline(cin, u.project);
    cout << "请输入挑战与成长："; getline(cin, u.challenge);
    return u;
}