#include <cstdlib>
#include <iostream>
#include <string>
#include <sstream>
#include <vector>
#include <cstdio>
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
    string user_text = u8"我熟练使用C++和Python，参与过团队项目，解决过线上问题";
    // 正确的转义方式：用\"表示一个双引号，前后都加
    string cmd = "python test_onnx.py \"" + utf8_to_ansi(user_text) + "\"";

    cout << "C++ 正在调用 ONNX 模拟推理...\n";
    FILE* pipe = _popen(cmd.c_str(), "r");
    if (!pipe) {
        cerr << "调用失败！" << endl;
        return 1;
    }

    char buffer[256];
    string result;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }
    _pclose(pipe);

    cout << "Python 原始输出：[" << result << "]\n";

    vector<float> scores(6, 0.0f);
    istringstream iss(result);
    for (int i=0; i<6; i++) {
        iss >> scores[i];
    }

    cout << "推理结果（6维能力分）：\n";
    const char* labels[] = {
        "专业能力", "学习能力", "问题解决", "沟通协作", "创新能力", "项目管理"
    };
    for (int i=0; i<6; i++) {
        cout << labels[i] << ": " << scores[i] << "/10\n";
    }

    return 0;
}