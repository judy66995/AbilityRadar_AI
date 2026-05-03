#include <cstdlib>
#include <iostream>
#include <string>
#include <windows.h>
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

int main() {
    SetConsoleOutputCP(CP_UTF8); // 设置控制台输出编码为 UTF-8

    // C++ 传给 Python 的内容
    string name = u8"MyProject";
    string score = "8.5";

    // 拼接命令：调用 Python + 脚本 + 参数
    string cmd = "python test.py " + utf8_to_ansi(name) + " " + score;

    cout << "C++ 正在调用 Python...\n";
    system(cmd.c_str()); // 执行命令
    cout << "调用完成！\n";

    return 0;
}