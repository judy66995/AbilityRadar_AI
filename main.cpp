#include <iostream>
#include <windows.h>
#include "input.h"
#include "score.h"
#include "radar.h"
#include "file_utils.h"
#include "ai.h"

using namespace std;

int main() {
    system("chcp 65001 > nul");
    cout << "===== AbilityRadar_AI 能力评估系统 =====\n" << endl;

    UserInfo user = inputUserInfo();
    AbilityScore score = calculateScore(user);
    printScore(score);

    generateRadar(user, score);  // 已传user.name
    saveReport(score);

    AIResult aiRes = getAIAnalysis(user, score);
    printAIResult(aiRes);
    saveAIResult(aiRes);

    cout << "\n==================================================\n";
    cout << "✅ 全部完成！\n";
    cout << "📊 雷达图：output/radar.png\n";
    cout << "📄 AI报告：output/ai_analysis.txt\n";
    cout << "==================================================\n";

    return 0;
}