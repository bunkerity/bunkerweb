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

#include "src/actions/ctl/rule_remove_by_id.h"

#include <iostream>
#include <string>

#include "modsecurity/transaction.h"
#include "src/utils/string.h"

namespace modsecurity {
namespace actions {
namespace ctl {


bool RuleRemoveById::init(std::string *error) {
    std::string what(m_parser_payload, 15, m_parser_payload.size() - 15);
    bool added = false;
    std::vector<std::string> toRemove = utils::string::ssplit(what, ' ');
    for (std::string &a : toRemove) {
        std::string b = modsecurity::utils::string::parserSanitizer(a);
        if (b.size() == 0) {
            continue;
        }

        size_t dash = b.find('-');
        if (dash != std::string::npos) {
            std::string n1s = std::string(b, 0, dash);
            std::string n2s = std::string(b, dash + 1, b.size() - (dash + 1));
            int n1n = 0;
            int n2n = 0;
            try {
                n1n = std::stoi(n1s);
                added = true;
            } catch (...) {
                error->assign("Not a number: " + n1s);
                return false;
            }
            try {
                n2n = std::stoi(n2s);
                added = true;
            } catch (...) {
                error->assign("Not a number: " + n2s);
                return false;
            }

            if (n1n > n2n) {
                error->assign("Invalid range: " + b);
                return false;
            }
            m_ranges.push_back(std::make_pair(n1n, n2n));
            added = true;
        } else {
            try {
                int num = std::stoi(b);
                m_ids.push_back(num);
                added = true;
            } catch (...) {
                error->assign("Not a number or range: " + b);
                return false;
            }
        }
    }

    if (added) {
        return true;
    }

    error->assign("Not a number or range: " + what);
    return false;
}

bool RuleRemoveById::evaluate(Rule *rule, Transaction *transaction) {
    for (auto &i : m_ids) {
        transaction->m_ruleRemoveById.push_back(i);
    }
    for (auto &i : m_ranges) {
        transaction->m_ruleRemoveByIdRange.push_back(i);
    }

    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
