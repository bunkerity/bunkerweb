/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "modsecurity/rules_set_properties.h"
#include "modsecurity/rules_set.h"
#include "modsecurity/modsecurity.h"
#include "src/utils/system.h"
#include "src/parser/driver.h"
#include "src/utils/https_client.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule_unconditional.h"
#include "modsecurity/rule_with_operator.h"


void print_help() {
    std::cout << "Use ./optimization /path/to/files.something" << std::endl;
    std::cout << std::endl;
    std::cout << std::endl;
}


int main(int argc, char **argv) {
    modsecurity::RulesSet *modsecRules = new modsecurity::RulesSet();
    std::list<std::string> files;
    int total = 0;

    int p = 1;
    while (p < argc) {
        std::list<std::string> tfiles = modsecurity::utils::expandEnv(
            argv[p], 0);
        for (const auto &file : tfiles) {
            files.insert(files.begin(), file);
        }
        p++;
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
    for (int j = 0; j < nphases; j++) {
        Rules *rules = modsecRules->m_rulesSetPhases[j];
        if (rules->size() == 0) {
            continue;
        }
        std::cout << "Phase: " << std::to_string(j);
        std::cout << " (" << std::to_string(rules->size());
        std::cout << " rules)" << std::endl;

        std::unordered_map<std::string, int> operators;

        for (int i = 0; i < rules->size(); i++) {
            auto z = rules->at(i);
            if (z == NULL) {
                continue;
            }

            if (dynamic_cast<modsecurity::RuleUnconditional *>(z.get()) != nullptr) {
                std::string op = "Unconditional";
                if (operators.count(op) > 0) {
                    operators[op] = 1 + operators[op];
                } else {
                    operators[op] = 1;
                }
            }

            if (dynamic_cast<modsecurity::RuleWithOperator *>(z.get()) != nullptr) {
                auto *rwo = dynamic_cast<modsecurity::RuleWithOperator *>(z.get());

                std::string op = rwo->getOperatorName();
                if (operators.count(op) > 0) {
                    operators[op] = 1 + operators[op];
                } else {
                    operators[op] = 1;
                }
            }

        }
        if (operators.empty()) {
            std::cout << " ~ no SecRule found ~ " << std::endl;
            continue;
        }

        std::cout << " Operators" << std::endl;
        for (const auto &z : operators) {
            const auto &s = z.second;
            std::cout << "   " << std::left << std::setw(20) << z.first;
            std::cout << std::right << std::setw(4) << s;
            std::cout << std::endl;
        }

        total += rules->size();
    }
    std::cout << std::endl;

    std::cout << "Total of: " << std::to_string(total) << " rules.";
    std::cout << std::endl;
    std::cout << std::endl;
    std::cout << std::endl;

    delete modsecRules;

    return 0;
}
