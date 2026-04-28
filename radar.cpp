#include "radar.h"
#include <iostream>
#include <cstdlib>
#include <string>
#include <windows.h>
#include <fstream>
#include <sstream>
#include "input.h"

using namespace std;

void generateRadar(const UserInfo& user, const AbilityScore& s) {
    system("if not exist output mkdir output");

    // 将用户姓名和能力分数写入临时文件，供Python脚本读取
    ofstream tempFile("output/radar_args.txt");
    tempFile << user.name << endl;
    tempFile << s.professional << " " << s.learning << " "
             << s.project << " " << s.teamwork << " "
             << s.pressure << " " << s.innovation << endl;
    tempFile.close();

    // 调用Python脚本生成雷达图
    int result = system("python plot.py");
}
