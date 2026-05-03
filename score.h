#ifndef SCORE_H
#define SCORE_H

#include "input.h"
#include <vector>
#include <string>

struct ScoreExplanation {
    std::string dimension;
    int score;
    double confidence;  // 0.0-1.0
    std::vector<std::string> matchedKeywords;
    std::vector<std::string> reasoning;
};

struct AbilityScore {
    int professional;
    int learning;
    int project;
    int teamwork;
    int pressure;
    int innovation;
    
    // 新增：详细评分解释
    std::vector<ScoreExplanation> explanations;
};

AbilityScore calculateScore(const UserInfo& u);
void printScore(const AbilityScore& s);
void printDetailedScore(const AbilityScore& s);

#endif