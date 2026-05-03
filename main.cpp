#include <iostream>
#include <windows.h>
#include "input.h"
#include "score.h"
#include "radar.h"
#include "file_utils.h"
#include "ai.h"

using namespace std;

int main() {
    system("chcp 65001 > nul");// 设置控制台为UTF-8编码，确保中文显示正常
    cout << "===== AbilityRadar_AI 能力评估系统 =====\n" << endl;

    UserInfo user = inputUserInfo();// 输入用户信息
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