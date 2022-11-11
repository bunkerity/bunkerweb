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
#include "modsecurity/transaction.h"


#ifndef SRC_ACTIONS_CTL_RULE_REMOVE_BY_ID_H_
#define SRC_ACTIONS_CTL_RULE_REMOVE_BY_ID_H_

namespace modsecurity {
namespace actions {
namespace ctl {


class RuleRemoveById : public Action {
 public:
    explicit RuleRemoveById(std::string action)
        : Action(action, RunTimeOnlyIfMatchKind) { }

    bool init(std::string *error) override;
    bool evaluate(Rule *rule, Transaction *transaction) override;

    std::list<std::pair<int, int> > m_ranges;
    std::list<int> m_ids;
};


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity

#endif  // SRC_ACTIONS_CTL_RULE_REMOVE_BY_ID_H_
