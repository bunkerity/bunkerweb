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

#ifndef SRC_OPERATORS_CONTAINS_H_
#define SRC_OPERATORS_CONTAINS_H_

#include <string>
#include <list>
#include <memory>
#include <utility>

#include "modsecurity/transaction.h"
#include "modsecurity/rule_message.h"
#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

class Contains : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit Contains(std::unique_ptr<RunTimeString> param)
        : Operator("Contains", std::move(param)) { }
    bool evaluate(Transaction *transaction, Rule *rule,
        const std::string &str,
        std::shared_ptr<RuleMessage> ruleMessage) override;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_CONTAINS_H_
