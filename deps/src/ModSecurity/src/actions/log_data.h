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
#include <utility>

#include "modsecurity/actions/action.h"
#include "src/run_time_string.h"

#ifndef SRC_ACTIONS_LOG_DATA_H_
#define SRC_ACTIONS_LOG_DATA_H_

class Transaction;

namespace modsecurity {
class Transaction;
namespace actions {


class LogData : public Action {
 public:
    explicit LogData(std::string action)
        : Action(action, RunTimeOnlyIfMatchKind) { }

    explicit LogData(std::unique_ptr<RunTimeString> z)
        : Action("logdata", RunTimeOnlyIfMatchKind),
            m_string(std::move(z)) { }

    bool evaluate(Rule *rule, Transaction *transaction,
       std::shared_ptr<RuleMessage> rm) override;

    std::string data(Transaction *Transaction);

    std::unique_ptr<RunTimeString> m_string;
};


}  // namespace actions
}  // namespace modsecurity

#endif  // SRC_ACTIONS_LOG_DATA_H_
