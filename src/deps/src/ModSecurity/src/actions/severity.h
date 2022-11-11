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
#include <memory>

#include "modsecurity/actions/action.h"

#ifndef SRC_ACTIONS_SEVERITY_H_
#define SRC_ACTIONS_SEVERITY_H_

#ifdef __cplusplus

namespace modsecurity {
class Transaction;

namespace actions {


class Severity : public Action {
 public:
    explicit Severity(std::string action)
        : Action(action),
        m_severity(0) { }

    bool evaluate(Rule *rule, Transaction *transaction,
        std::shared_ptr<RuleMessage> rm) override;
    bool init(std::string *error) override;

    int m_severity;
};


}  // namespace actions
}  // namespace modsecurity
#endif

#endif  // SRC_ACTIONS_SEVERITY_H_
