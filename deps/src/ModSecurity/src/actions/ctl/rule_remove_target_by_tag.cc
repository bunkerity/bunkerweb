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

#include "src/actions/ctl/rule_remove_target_by_tag.h"

#include <iostream>
#include <string>
#include <vector>
#include <utility>

#include "modsecurity/transaction.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace actions {
namespace ctl {


bool RuleRemoveTargetByTag::init(std::string *error) {
    std::string what(m_parser_payload, 22, m_parser_payload.size() - 22);
    std::vector<std::string> param = utils::string::split(what, ';');

    if (param.size() < 2) {
        error->assign(what + " is not a valid `TAG;VARIABLE'");
        return false;
    }

    m_tag = param[0];
    m_target = param[1];

    return true;
}

bool RuleRemoveTargetByTag::evaluate(Rule *rule, Transaction *transaction) {
    transaction->m_ruleRemoveTargetByTag.push_back(
        std::make_pair(m_tag, m_target));
    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
