/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#include <string.h>
#include <sys/stat.h>
#ifndef WIN32
#include <unistd.h>
#else
#include <io.h>
#endif

#include <ctime>
#include <iostream>
#include <string>

#include "modsecurity/rules_set.h"
#include "modsecurity/modsecurity.h"


void print_help(const char *name) {
    std::cout << "Use: " << name << " [<filename>|SecLangCommand]" << std::endl;
    std::cout << std::endl;
}


int main(int argc, char **argv) {
    auto rules = std::make_unique<modsecurity::RulesSet>();
    char **args = argv;
    int ret = 0;

    args++;

    if (*args == NULL) {
        print_help(argv[0]);
        return 0;
    }

    while (*args != NULL) {
        struct stat buffer;
        std::string arg = *args;
        std::string err;
        int r;

        // strip arg from leading and trailing '"' chars
        arg.erase(arg.find_last_not_of('\"')+1);
        arg.erase(0, arg.find_first_not_of('\"'));

        if (arg.empty() == true) {
            args++;
            continue;
        }

        std::cout << " : " << arg << "  --  ";
        if (stat(arg.c_str(), &buffer) == 0) {
            r = rules->loadFromUri(arg.c_str());
        } else {
            r = rules->load(arg.c_str());
        }

        if (r < 0) {
            err.assign(rules->m_parserError.str());
            rules->m_parserError.str("");
            rules->m_parserError.clear();
            ret = -1;
        }
        std::cout << "Loaded " << std::to_string(r) << " rules." << std::endl;
        if (err.empty() == false) {
            std::cerr << "    " << err << std::endl;
        }

        args++;
    }

    if (ret < 0) {
        std::cout << "Test failed." << std::endl;
    } else {
        std::cout << "Test ok." << std::endl;
    }

    return ret;
}
