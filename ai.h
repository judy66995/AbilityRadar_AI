#ifndef AI_H
#define AI_H

#include "input.h"
#include "score.h"
#include <string>

// AI 分析结果结构体
struct AIResult {
    std::string summary;     // 综合评价
    std::string trend;       // 发展趋势
    std::string advice;      // 提升建议
    std::string fullText;    // 完整回答
};

// 调用AI接口获取分析
AIResult getAIAnalysis(const UserInfo& user, const AbilityScore& score);

// 打印AI结果
void printAIResult(const AIResult& res);

// 保存AI结果到文件
void saveAIResult(const AIResult& res);

#endif