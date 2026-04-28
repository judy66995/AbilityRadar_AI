// file_utils.cpp
#include "file_utils.h"
#include <fstream>
using namespace std;

void saveReport(const AbilityScore& s) {// 保存能力评估报告到文本文件
    ofstream f("output/report.txt");
    f << "===== 能力评估报告 =====\n";
    f << "专业能力：" << s.professional << "\n";
    f << "学习能力：" << s.learning << "\n";
    f << "项目实践：" << s.project << "\n";
    f << "团队协作：" << s.teamwork << "\n";
    f << "抗压执行：" << s.pressure << "\n";
    f << "创新思维：" << s.innovation << "\n";
    f.close();
}