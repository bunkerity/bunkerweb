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


#include <stdio.h>
#include <string.h>

#ifdef __cplusplus
#include <ctime>
#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <memory>
#endif

#include "modsecurity/rule.h"
#include "modsecurity/rule_with_operator.h"
#include "modsecurity/rule_with_actions.h"

#ifndef HEADERS_MODSECURITY_RULES_H_
#define HEADERS_MODSECURITY_RULES_H_


#ifdef __cplusplus
namespace modsecurity {


class Rules {
 public:
    void dump() const {
        for (int j = 0; j < m_rules.size(); j++) {
            std::cout << "    Rule ID: " << m_rules.at(j)->getReference();
            std::cout << "--" << m_rules.at(j) << std::endl;
        }
    }

    int append(Rules *from, const std::vector<int64_t> &ids, std::ostringstream *err) {
         size_t j = 0;
         for (; j < from->size(); j++) {
            RuleWithOperator *rule = dynamic_cast<RuleWithOperator *>(from->at(j).get());
            if (rule && std::binary_search(ids.begin(), ids.end(), rule->m_ruleId)) {
                 if (err != NULL) {
                     *err << "Rule id: " << std::to_string(rule->m_ruleId) \
                        << " is duplicated" << std::endl;
                 }
                 return -1;
             }
         }
         m_rules.insert(m_rules.end(), from->m_rules.begin(), from->m_rules.end());
         return j;
    }

    bool insert(const std::shared_ptr<Rule> &rule) {
        return insert(rule, nullptr, nullptr);
    }

    bool insert(std::shared_ptr<Rule> rule, const std::vector<int64_t> *ids, std::ostringstream *err) {
        RuleWithOperator *r = dynamic_cast<RuleWithOperator *>(rule.get());
        if (r && ids != nullptr && std::binary_search(ids->begin(), ids->end(), r->m_ruleId)) {
            if (err != nullptr) {
                *err << "Rule id: " << std::to_string(r->m_ruleId) \
                    << " is duplicated" << std::endl;
            }
            return false;
        }
        m_rules.push_back(rule);
        return true;
    }

    size_t size() const { return m_rules.size(); }
    std::shared_ptr<Rule> operator[](int index) const { return m_rules[index]; }
    std::shared_ptr<Rule> at(int index) const { return m_rules[index]; }

    std::vector<std::shared_ptr<Rule> > m_rules;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULES_H_

