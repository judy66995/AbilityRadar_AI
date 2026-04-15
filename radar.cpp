#include "radar.h"
#include <cstdlib>
#include <string>
#include <windows.h>
#include "input.h"

using namespace std;

void generateRadar(const UserInfo& user, const AbilityScore& s) {
    system("if not exist output mkdir output");

    // 转换UTF-8到宽字符以正确处理中文
    int len = MultiByteToWideChar(CP_UTF8, 0, user.name.c_str(), -1, NULL, 0);
    std::wstring wname(len, 0);
    MultiByteToWideChar(CP_UTF8, 0, user.name.c_str(), -1, &wname[0], len);

    // 构建命令字符串
    std::wstring cmd = L"python plot.py \"" + wname + L"\" " +
        std::to_wstring(s.professional) + L" " + std::to_wstring(s.learning) + L" " +
        std::to_wstring(s.project) + L" " + std::to_wstring(s.teamwork) + L" " +
        std::to_wstring(s.pressure) + L" " + std::to_wstring(s.innovation);

    // 使用ShellExecuteW执行命令以避免编码问题
    ShellExecuteW(NULL, L"open", L"cmd.exe", (L"/c " + cmd).c_str(), NULL, SW_HIDE);
}