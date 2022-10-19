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

#include <string>

#include "modsecurity/actions/action.h"

#ifndef SRC_ACTIONS_RULE_ID_H_
#define SRC_ACTIONS_RULE_ID_H_

#ifdef __cplusplus
class Transaction;

namespace modsecurity {
class Transaction;
class Rule;

namespace actions {


class RuleId : public Action {
 public:
    explicit RuleId(std::string action)
        : Action(action, ConfigurationKind),
        m_ruleId(0) { }

    bool init(std::string *error) override;
    bool evaluate(Rule *rule, Transaction *transaction) override;

 private:
    double m_ruleId;
};

}  // namespace actions
}  // namespace modsecurity
#endif

#endif  // SRC_ACTIONS_RULE_ID_H_
