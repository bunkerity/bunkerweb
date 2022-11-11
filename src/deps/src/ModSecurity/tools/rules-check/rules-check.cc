/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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
#include <unistd.h>

#include <ctime>
#include <iostream>
#include <string>

#include "modsecurity/modsecurity.h"
#include "modsecurity/rules.h"


void print_help(const char *name) {
    std::cout << "Use: " << name << " [<filename>|SecLangCommand]" << std::endl;
    std::cout << std::endl;
}


int main(int argc, char **argv) {
    modsecurity::Rules *rules;
    char **args = argv;
    rules = new modsecurity::Rules();
    int ret = 0;

    args++;

    if (*args == NULL) {
        print_help(argv[0]);
        return 0;
    }

    while (*args != NULL) {
        struct stat buffer;
        std::string argFull("");
        const char *arg = *args;
        std::string err;
        int r;

        if (argFull.empty() == false) {
            if (arg[strlen(arg)-1] == '\"') {
                argFull.append(arg, strlen(arg)-1);
                goto next;
            } else {
                argFull.append(arg);
                goto next;
            }
        }

        if (arg[0] == '\"' && argFull.empty() == true) {
            if (arg[strlen(arg)-1] == '\"') {
                argFull.append(arg+1, strlen(arg) - 2);
            } else {
                argFull.append(arg+1);
                goto next;
            }
        }

        if (argFull.empty() == false) {
            arg = argFull.c_str();
            argFull.clear();
        }

        std::cout << " : " << arg << "  --  ";
        if (stat(arg, &buffer) == 0) {
            r = rules->loadFromUri(arg);
        } else {
            r = rules->load(arg);
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
next:
        args++;
    }

    delete rules;

    if (ret < 0) {
        std::cout << "Test failed." << std::endl;
    } else {
        std::cout << "Test ok." << std::endl;
    }

    return ret;
}
