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

#include "modsecurity/rules_exceptions.h"

#include <string>

#include "src/utils/string.h"
#include "src/variables/variable.h"

namespace modsecurity {


RulesExceptions::RulesExceptions() {
}


RulesExceptions::~RulesExceptions() {
}


bool RulesExceptions::loadUpdateActionById(double id,
    std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > > actions,
    std::string *error) {

    for (auto &a : *actions) {
        if (a->action_kind == actions::Action::ConfigurationKind) {
            std::cout << "General failure, action: " << a->m_name;
            std::cout << " has not expected to be used with UpdateActionByID.";
            std::cout << std::endl;
        } else if (a->action_kind
            == actions::Action::RunTimeBeforeMatchAttemptKind) {
            m_action_pre_update_target_by_id.emplace(std::pair<double,
                std::unique_ptr<actions::Action>>(id , std::move(a)));
        } else if (a->action_kind == actions::Action::RunTimeOnlyIfMatchKind) {
            m_action_pos_update_target_by_id.emplace(std::pair<double,
                std::unique_ptr<actions::Action>>(id , std::move(a)));
        } else {
            std::cout << "General failure, action: " << a->m_name;
            std::cout << " has an unknown type." << std::endl;
        }
    }

    return true;
}


bool RulesExceptions::loadRemoveRuleByMsg(const std::string &msg,
    std::string *error) {
    m_remove_rule_by_msg.push_back(msg);

    return true;
}


bool RulesExceptions::loadRemoveRuleByTag(const std::string &msg,
    std::string *error) {
    m_remove_rule_by_tag.push_back(msg);

    return true;
}


bool RulesExceptions::loadUpdateTargetByMsg(const std::string &msg,
    std::unique_ptr<std::vector<std::unique_ptr<variables::Variable> > > var,
    std::string *error) {
    for (auto &i : *var) {
        m_variable_update_target_by_msg.emplace(
            std::pair<std::shared_ptr<std::string>,
            std::unique_ptr<variables::Variable>>(
                std::make_shared<std::string>(msg),
                std::move(i)));
    }

    return true;
}


bool RulesExceptions::loadUpdateTargetByTag(const std::string &tag,
    std::unique_ptr<std::vector<std::unique_ptr<variables::Variable> > > var,
    std::string *error) {

    for (auto &i : *var) {
        m_variable_update_target_by_tag.emplace(
            std::pair<std::shared_ptr<std::string>,
                std::unique_ptr<variables::Variable>>(
                    std::make_shared<std::string>(tag),
                    std::move(i)));
    }

    return true;
}


bool RulesExceptions::loadUpdateTargetById(double id,
    std::unique_ptr<std::vector<std::unique_ptr<variables::Variable> > > var,
    std::string *error) {

    for (auto &i : *var) {
        m_variable_update_target_by_id.emplace(
            std::pair<double,
                std::unique_ptr<variables::Variable>>(id,
                std::move(i)));
    }

    return true;
}


bool RulesExceptions::load(const std::string &a, std::string *error) {
    bool added = false;
    std::vector<std::string> toRemove = utils::string::ssplit(a, ' ');
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

            if (n1s > n2s) {
                error->assign("Invalid range: " + b);
                return false;
            }
            addRange(n1n, n2n);
            added = true;
        } else {
            try {
                int num = std::stoi(b);
                addNumber(num);
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

    error->assign("Not a number or range: " + a);
    return false;
}


bool RulesExceptions::addNumber(int a) {
    m_numbers.push_back(a);
    return true;
}


bool RulesExceptions::addRange(int a, int b) {
    m_ranges.push_back(std::make_pair(a, b));
    return true;
}


bool RulesExceptions::contains(int a) {
    for (int z : m_numbers) {
        if (a == z) {
            return true;
        }
    }

    for (auto z : m_ranges) {
        if (z.first <= a && z.second >= a) {
            return true;
        }
    }

    return false;
}


bool RulesExceptions::merge(RulesExceptions *from) {
    for (int a : from->m_numbers) {
        bool ret = addNumber(a);
        if (ret == false) {
            return ret;
        }
    }
    for (auto b : from->m_ranges) {
        bool ret = addRange(b.first, b.second);
        if (ret == false) {
            return ret;
        }
    }

    for (auto &p : from->m_variable_update_target_by_tag) {
        m_variable_update_target_by_tag.emplace(
            std::pair<std::shared_ptr<std::string>,
            std::shared_ptr<variables::Variable>>(p.first,
                p.second));
    }

    for (auto &p : from->m_variable_update_target_by_msg) {
        m_variable_update_target_by_msg.emplace(
            std::pair<std::shared_ptr<std::string>,
            std::shared_ptr<variables::Variable>>(p.first,
                p.second));
    }

    for (auto &p : from->m_variable_update_target_by_id) {
        m_variable_update_target_by_id.emplace(
            std::pair<double,
                std::shared_ptr<variables::Variable>>(p.first,
                    p.second));
    }

    for (auto &p : from->m_action_pos_update_target_by_id) {
        m_action_pos_update_target_by_id.emplace(
            std::pair<double,
                std::shared_ptr<actions::Action>>(p.first,
                    p.second));
    }

    for (auto &p : from->m_action_pre_update_target_by_id) {
        m_action_pre_update_target_by_id.emplace(
            std::pair<double,
                std::shared_ptr<actions::Action>>(p.first,
                    p.second));
    }

    for (auto &p : from->m_remove_rule_by_msg) {
        m_remove_rule_by_msg.push_back(p);
    }

    for (auto &p : from->m_remove_rule_by_tag) {
        m_remove_rule_by_tag.push_back(p);
    }

    return true;
}

}  // namespace modsecurity

