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

#ifdef __cplusplus
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include <memory>
#endif

#ifndef HEADERS_MODSECURITY_RULES_EXCEPTIONS_H_
#define HEADERS_MODSECURITY_RULES_EXCEPTIONS_H_

#ifdef __cplusplus


namespace modsecurity {
namespace actions {
class Action;
}
namespace variables {
class Variable;
}

class RulesExceptions {
 public:
    RulesExceptions();
    ~RulesExceptions();

    bool load(const std::string &data, std::string *error);
    bool addRange(int a, int b);
    bool addNumber(int a);
    bool contains(int a);
    bool merge(RulesExceptions *from);

    bool loadRemoveRuleByMsg(const std::string &msg, std::string *error);
    bool loadRemoveRuleByTag(const std::string &msg, std::string *error);

    bool loadUpdateTargetByMsg(const std::string &msg,
        std::unique_ptr<std::vector<std::unique_ptr<variables::Variable> > > v,
        std::string *error);

    bool loadUpdateTargetByTag(const std::string &tag,
        std::unique_ptr<std::vector<std::unique_ptr<variables::Variable> > > v,
        std::string *error);

    bool loadUpdateTargetById(double id,
        std::unique_ptr<std::vector<std::unique_ptr<variables::Variable> > > v,
        std::string *error);

    bool loadUpdateActionById(double id,
        std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > > actions,
        std::string *error);

    std::unordered_multimap<std::shared_ptr<std::string>,
        std::shared_ptr<variables::Variable>> m_variable_update_target_by_tag;
    std::unordered_multimap<std::shared_ptr<std::string>,
        std::shared_ptr<variables::Variable>> m_variable_update_target_by_msg;
    std::unordered_multimap<double,
        std::shared_ptr<variables::Variable>> m_variable_update_target_by_id;
    std::unordered_multimap<double,
        std::shared_ptr<actions::Action>> m_action_pre_update_target_by_id;
    std::unordered_multimap<double,
        std::shared_ptr<actions::Action>> m_action_pos_update_target_by_id;
    std::list<std::string> m_remove_rule_by_msg;
    std::list<std::string> m_remove_rule_by_tag;

 private:
    std::list<std::pair<int, int> > m_ranges;
    std::list<int> m_numbers;
};

}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULES_EXCEPTIONS_H_

