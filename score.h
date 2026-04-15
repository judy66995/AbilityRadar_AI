#ifndef SCORE_H
#define SCORE_H

#include "input.h"

struct AbilityScore {
    int professional;
    int learning;
    int project;
    int teamwork;
    int pressure;
    int innovation;
};

AbilityScore calculateScore(const UserInfo& u);
void printScore(const AbilityScore& s);

#endif