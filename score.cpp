#include "score.h"
#include <iostream>
#include <vector>
#include <string>
using namespace std;

static int countKey(const string& text, const vector<string>& keys) {// 统计文本中包含的关键词数量，大小写不敏感
    int cnt = 0;
    string t = text;
    for (auto& c : t) c = tolower(c);
    for (auto k : keys) {
        string lk = k;
        for (auto& c : lk) c = tolower(c);
        if (t.find(lk) != string::npos) cnt++;
    }
    return cnt;
}

static int scoreByCount(int cnt) {
    if (cnt >= 5) return 10;
    if (cnt >= 3) return 7;
    if (cnt >= 1) return 4;
    return 0;
}

AbilityScore calculateScore(const UserInfo& u) {// 根据用户信息计算能力分数
    string all = u.skills + " " + u.project + " " + u.challenge;
    AbilityScore s{};

    s.professional = scoreByCount(countKey(all, {
        "编程", "算法", "开发", "C++", "Python", "数据结构", "数据库", "专业"
    }));

    s.learning = scoreByCount(countKey(all, {
        "自学", "学习", "掌握", "研究", "提升", "新知识", "主动学习"
    }));

    s.project = scoreByCount(countKey(all, {
        "项目", "开发", "实现", "部署", "实战", "完成", "搭建"
    }));

    s.teamwork = scoreByCount(countKey(all, {
        "团队", "协作", "沟通", "配合", "合作", "小组"
    }));

    s.pressure = scoreByCount(countKey(all, {
        "压力", "按时", "执行", "负责", "解决", "坚持", "目标"
    }));

    s.innovation = scoreByCount(countKey(all, {
        "创新", "优化", "改进", "设计", "创意", "效率"
    }));

    return s;
}

void printScore(const AbilityScore& s) {// 打印能力分数到控制台
    cout << "\n===== 能力评分（0-10）=====\n";
    cout << "专业能力：" << s.professional << endl;
    cout << "学习能力：" << s.learning << endl;
    cout << "项目实践：" << s.project << endl;
    cout << "团队协作：" << s.teamwork << endl;
    cout << "抗压执行：" << s.pressure << endl;
    cout << "创新思维：" << s.innovation << endl;
}