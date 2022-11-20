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

#include "src/actions/skip_after.h"

#include <iostream>
#include <string>

#include "modsecurity/rules_set.h"
#include "modsecurity/actions/action.h"
#include "modsecurity/transaction.h"


namespace modsecurity {
namespace actions {


bool SkipAfter::evaluate(RuleWithActions *rule, Transaction *transaction) {
    ms_dbg_a(transaction, 5, "Setting skipAfter for: " + *m_skipName);
    transaction->addMarker(m_skipName);
    return true;
}


}  // namespace actions
}  // namespace modsecurity
