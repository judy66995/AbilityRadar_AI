#include <iostream>
#include <string>
using namespace std;

// 用户信息结构体
struct User {
    string name;
    string major;
    string skills;
    string experience;
};

int main() {
    User user;

    cout << "请输入姓名：";
    getline(cin, user.name);

    cout << "请输入专业：";
    getline(cin, user.major);

    cout << "请输入技能：";
    getline(cin, user.skills);

    cout << "请输入项目/实践经历：";
    getline(cin, user.experience);

    cout << "\n信息收集完成！\n";
    return 0;
}