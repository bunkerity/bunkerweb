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
#include "modsecurity/rule_message.h"

#ifndef SRC_ACTIONS_DISRUPTIVE_BLOCK_H_
#define SRC_ACTIONS_DISRUPTIVE_BLOCK_H_

#ifdef __cplusplus
class Transaction;

namespace modsecurity {
class Transaction;

namespace actions {


class Block : public Action {
 public:
    explicit Block(std::string action) : Action(action) { }

    bool evaluate(Rule *rule, Transaction *transaction,
        std::shared_ptr<RuleMessage> rm) override;
};


}  // namespace actions
}  // namespace modsecurity
#endif

#endif  // SRC_ACTIONS_DISRUPTIVE_BLOCK_H_
