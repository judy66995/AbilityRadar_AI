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

    // Save parameters to a temp JSON file
    ofstream tempFile("output/radar_args.txt");
    tempFile << user.name << endl;
    tempFile << s.professional << " " << s.learning << " "
             << s.project << " " << s.teamwork << " "
             << s.pressure << " " << s.innovation << endl;
    tempFile.close();

    // Call Python with simple arguments
    int result = system("python plot.py");
}
