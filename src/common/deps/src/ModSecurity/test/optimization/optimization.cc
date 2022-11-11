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

#include <ctime>
#include <iostream>
#include <string>
#include <list>

#include "modsecurity/modsecurity.h"
#include "modsecurity/rules.h"
#include "src/utils/system.h"
#include "src/parser/driver.h"
#include "src/utils/https_client.h"
#include "modsecurity/rules_properties.h"
#include "modsecurity/transaction.h"

void print_help() {
    std::cout << "Use ./optimization /path/to/files.something" << std::endl;
    std::cout << std::endl;
    std::cout << std::endl;
}


int main(int argc, char **argv) {
    modsecurity::Rules *modsecRules = new modsecurity::Rules();
    std::list<std::string> files;
    int total = 0;

    int i = 1;
    while (i < argc) {
        std::list<std::string> tfiles = modsecurity::utils::expandEnv(
            argv[i], 0);
        for (const auto &file : tfiles) {
            files.insert(files.begin(), file);
        }
        i++;
    }


    for (auto &x : files) {
        std::cout << "Loading file: " << x << std::endl;
        if (modsecRules->loadFromUri(x.c_str()) < 0) {
            std::cout << "Not able to load the rules" << std::endl;
            std::cout << modsecRules->getParserError() << std::endl;
            delete modsecRules;
            return -1;
        }
    }

    std::cout << std::endl;
    std::cout << std::endl;
    std::cout << "Rules optimization" << std::endl;
    std::cout << std::endl;

    int nphases = modsecurity::Phases::NUMBER_OF_PHASES;
    for (int i = 0; i < nphases; i++) {
        std::vector<Rule *> rules = modsecRules->m_rules[i];
        if (rules.size() == 0) {
            continue;
        }
        std::cout << "Phase: " << std::to_string(i);
        std::cout << " (" << std::to_string(rules.size());
        std::cout << " rules)" << std::endl;

        std::unordered_map<std::string, int> operators;
        std::unordered_map<std::string, int> variables;
        std::unordered_map<std::string, int> op2var;
        for (auto &z : rules) {
            std::string key;
            if (z == NULL) {
                continue;
            }
            if (z->m_op != NULL) {
                std::string op = z->m_op->m_op;
                if (operators.count(op) > 0) {
                    operators[op] = 1 + operators[op];
                } else {
                    operators[op] = 1;
                }
                key = op;
            }
            if (z->m_variables != NULL) {
                std::string var = std::string("") + z->m_variables;
                if (variables.count(var) > 0) {
                    variables[var] = 1 + variables[var];
                } else {
                    variables[var] = 1;
                }
                key = key + var;
            }
            if (z->m_variables != NULL && z->m_op != NULL) {
                if (op2var.count(key) > 0) {
                    op2var[key] = 1 + op2var[key];
                } else {
                    op2var[key] = 1;
                }
            }
        }

        if (operators.empty() && variables.empty() && op2var.empty()) {
            std::cout << " ~ no SecRule found ~ " << std::endl;
            continue;
        }
        std::cout << " Operators" << std::endl;
        for (auto &z : operators) {
            auto &s = z.second;
            std::cout << "   " << std::left << std::setw(20) << z.first;
            std::cout << std::right << std::setw(4) << s;
            std::cout << std::endl;
        }

        std::cout << " Variables" << std::endl;
        for (auto &z : variables) {
            auto &s = z.second;
            std::cout << "   " << std::left << std::setw(20) << z.first;
            std::cout << std::right << std::setw(4) << s;
            std::cout << std::endl;
        }
        std::cout << " Operators applied to variables" << std::endl;
        for (auto &z : op2var) {
            auto &s = z.second;
            std::cout << "   " << std::left << std::setw(40) << z.first;
            std::cout << std::right << std::setw(4) << s;
            std::cout << std::endl;
        }

        total += rules.size();
    }
    std::cout << std::endl;

    std::cout << "Total of: " << std::to_string(total) << " rules.";
    std::cout << std::endl;
    std::cout << std::endl;
    std::cout << std::endl;

    delete modsecRules;

    return 0;
}
