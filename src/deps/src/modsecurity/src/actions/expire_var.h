/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <memory>
#include <string>
#include <utility>

#include "modsecurity/actions/action.h"
#include "src/run_time_string.h"

#ifndef SRC_ACTIONS_EXPIRE_VAR_H_
#define SRC_ACTIONS_EXPIRE_VAR_H_

class Transaction;

namespace modsecurity {
class Transaction;
class RuleWithOperator;

namespace actions {

class ExpireVar : public Action {
 public:
    explicit ExpireVar(const std::string &action) : Action(action) { }

    explicit ExpireVar(std::unique_ptr<RunTimeString> z)
        : Action("expirevar", RunTimeOnlyIfMatchKind),
            m_string(std::move(z)) { }

    bool evaluate(RuleWithActions *rule, Transaction *transaction) override;
    bool init(std::string *error) override;

 private:

    std::unique_ptr<RunTimeString> m_string;
};

}  // namespace actions
}  // namespace modsecurity


#endif  // SRC_ACTIONS_EXPIRE_VAR_H_
