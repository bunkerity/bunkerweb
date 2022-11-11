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

#include "src/actions/disruptive/pass.h"

#include <iostream>
#include <string>
#include <memory>

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rules.h"
#include "modsecurity/rule_message.h"

namespace modsecurity {
namespace actions {
namespace disruptive {


bool Pass::evaluate(Rule *rule, Transaction *transaction,
    std::shared_ptr<RuleMessage> rm) {
    intervention::free(&transaction->m_it);
    intervention::reset(&transaction->m_it);

    ms_dbg_a(transaction, 8, "Running action pass");

    return true;
}


}  // namespace disruptive
}  // namespace actions
}  // namespace modsecurity
