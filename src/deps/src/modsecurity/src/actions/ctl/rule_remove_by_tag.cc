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

#include "src/actions/ctl/rule_remove_by_tag.h"

#include <iostream>
#include <string>

#include "modsecurity/transaction.h"

namespace modsecurity {
namespace actions {
namespace ctl {


bool RuleRemoveByTag::init(std::string *error) {
    size_t pos = m_parser_payload.find("=");
    if (pos == std::string::npos) {
        error->assign(m_parser_payload + " is not a valid tag");
        return false;
    }
    std::string what = m_parser_payload.substr(pos + 1);
    m_tag = what;

    return true;
}

bool RuleRemoveByTag::evaluate(RuleWithActions *rule, Transaction *transaction) {
    transaction->m_ruleRemoveByTag.push_back(m_tag);
    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
