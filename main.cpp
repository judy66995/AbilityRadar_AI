#include <iostream>
#include <windows.h>
#include "input.h"
#include "score.h"
#include "radar.h"
#include "file_utils.h"
#include "ai.h"
#include "resume_parser.h"

using namespace std;

int main() {
    system("chcp 65001 > nul");// 设置控制台为UTF-8编码，确保中文显示正常
    cout << "===== AbilityRadar_AI 能力评估系统 =====\n" << endl;

    // ── 第一步：选择输入方式 ──
    int mode = inputModeMenu();
    while (mode < 0 || mode > 2) {
        cout << "⚠️  无效选项，请重新输入（0/1/2）：";
        mode = inputModeMenu();
    }

    if (mode == 0) {
        cout << "已退出程序。\n";
        return 0;
    }

    UserInfo user;

    if (mode == 1) {
        // ── 手动输入模式 ──
        cout << "\n--- 手动输入模式 ---\n";
        user = inputUserInfo();
    } else if (mode == 2) {
        // ── 简历上传模式 ──
        cout << "\n--- 简历上传模式 ---\n";
        cout << "请输入简历文件路径（支持 PDF/PNG/JPG）：";
        string filePath;
        getline(cin, filePath);

        // 去除路径首尾可能的引号
        if (!filePath.empty() && filePath.front() == '"') {
            filePath.erase(0, 1);
        }
        if (!filePath.empty() && filePath.back() == '"') {
            filePath.pop_back();
        }

        cout << "\n⏳ 正在解析简历，请稍候...\n" << endl;

        ResumeData resume = parseResumeFile(filePath);

        if (!resume.success) {
            cout << "❌ 简历解析失败：" << resume.error << "\n";
            cout << "是否切换到手动输入模式？(y/n)：";
            string yn;
            getline(cin, yn);
            if (yn == "y" || yn == "Y" || yn == "yes" || yn == "是") {
                cout << "\n--- 手动输入模式 ---\n";
                user = inputUserInfo();
            } else {
                return 1;// 直接退出程序
            }
        } else {
            // ── 显示提取结果并确认 ──
            cout << "\n===== 简历解析结果 =====\n";
            cout << "姓名：" << (resume.name.empty() ? "(未识别)" : resume.name) << "\n";
            cout << "性别：" << (resume.gender.empty() ? "(未识别)" : resume.gender) << "\n";
            cout << "年龄：" << (resume.age.empty() ? "(未识别)" : resume.age) << "\n";
            cout << "学历：" << (resume.education.empty() ? "(未识别)" : resume.education) << "\n";
            cout << "专业：" << (resume.major.empty() ? "(未识别)" : resume.major) << "\n";
            cout << "技能：\n" << (resume.skills.empty() ? "(未识别)" : resume.skills) << "\n";
            cout << "项目经历：\n" << (resume.project.empty() ? "(未识别)" : resume.project) << "\n";
            cout << "自我评价/挑战：\n" << (resume.challenge.empty() ? "(未识别)" : resume.challenge) << "\n";
            cout << "========================\n";

            cout << "\n信息是否正确？\n";
            cout << "  [y] 确认，继续评估\n";
            cout << "  [n] 切换到手动输入\n";
            cout << "  [0] 退出程序\n";
            cout << "请输入（y/n/0）：";
            string yn;
            getline(cin, yn);

            if (yn == "0") {
                cout << "已退出程序。\n";
                return 0;
            } else if (yn == "n" || yn == "N" || yn == "no" || yn == "否") {
                cout << "\n--- 手动输入模式 ---\n";
                user = inputUserInfo();
            } else {
                // 默认：确认使用提取结果
                user = resumeToUserInfo(resume);
            }
        }
    }

    // ── 后续流程：评分 → 雷达图 → AI 分析 ──
    cout << "\n⏳ 正在进行能力评估...\n";

    AbilityScore score = calculateScore(user);// 计算能力分数
    printScore(score);// 打印能力分数
    printDetailedScore(score);// 打印详细评分分析

    generateRadar(user, score);  // 生成雷达图
    saveReport(score);// 保存能力评估报告

    AIResult aiRes = getAIAnalysis(user, score);// 获取AI分析结果
    printAIResult(aiRes);// 打印AI分析结果
    saveAIResult(aiRes);// 保存AI分析结果

    cout << "\n==================================================\n";
    cout << "✅ 全部完成！\n";
    cout << "📊 雷达图：output/radar.png\n";
    cout << "📄 AI报告：output/ai_analysis.txt\n";
    cout << "==================================================\n";

    return 0;
}
