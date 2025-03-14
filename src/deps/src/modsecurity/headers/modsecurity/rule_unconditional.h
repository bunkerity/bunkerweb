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

#ifndef HEADERS_MODSECURITY_RULE_UNCONDITIONAL_H_
#define HEADERS_MODSECURITY_RULE_UNCONDITIONAL_H_

#include "modsecurity/modsecurity.h"
#include "modsecurity/variable_value.h"
#include "modsecurity/rule.h"
#include "modsecurity/rules_set.h"
#include "modsecurity/rule_with_actions.h"
#include "modsecurity/actions/action.h"

#ifdef __cplusplus

#include <vector>
#include <string>
#include <memory>

namespace modsecurity {


class RuleUnconditional : public RuleWithActions {
 public:
    using RuleWithActions::RuleWithActions;

    virtual bool evaluate(Transaction *transaction, RuleMessage &ruleMessage) override;
};


}  // namespace modsecurity

#endif

#endif  // HEADERS_MODSECURITY_RULE_UNCONDITIONAL_H_
