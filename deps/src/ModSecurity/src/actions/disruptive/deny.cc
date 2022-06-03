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

#include "src/actions/disruptive/deny.h"

#include <string.h>
#include <iostream>
#include <string>
#include <cstring>
#include <memory>

#include "modsecurity/transaction.h"

namespace modsecurity {
namespace actions {
namespace disruptive {


bool Deny::evaluate(Rule *rule, Transaction *transaction,
    std::shared_ptr<RuleMessage> rm) {
    ms_dbg_a(transaction, 8, "Running action deny");

    if (transaction->m_it.status == 200) {
        transaction->m_it.status = 403;
    }

    transaction->m_it.disruptive = true;
    intervention::freeLog(&transaction->m_it);
    rm->m_isDisruptive = true;
    transaction->m_it.log = strdup(
        rm->log(RuleMessage::LogMessageInfo::ClientLogMessageInfo).c_str());

    return true;
}


}  // namespace disruptive
}  // namespace actions
}  // namespace modsecurity
