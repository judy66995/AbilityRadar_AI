#ifndef INPUT_H
#define INPUT_H

#include <string>

struct UserInfo {
    std::string name;
    std::string gender;
    std::string age;
    std::string major;
    std::string education;
    std::string skills;
    std::string project;
    std::string challenge;
};

UserInfo inputUserInfo();

#endif