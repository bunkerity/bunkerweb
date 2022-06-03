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

#include "modsecurity/actions/action.h"

#include <iostream>
#include <string>

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "src/utils/string.h"

#include "src/actions/block.h"
#include "src/actions/chain.h"
#include "src/actions/disruptive/deny.h"
#include "src/actions/disruptive/redirect.h"
#include "src/actions/data/status.h"
#include "src/actions/rule_id.h"
#include "src/actions/phase.h"
#include "src/actions/severity.h"
#include "src/actions/capture.h"
#include "src/actions/disruptive/pass.h"
#include "src/actions/log.h"
#include "src/actions/no_log.h"
#include "src/actions/no_audit_log.h"
#include "src/actions/multi_match.h"


#define IF_MATCH(a) \
    if (op.compare(1, std::strlen(#a), #a) == 0)

namespace modsecurity {
namespace actions {


std::string Action::evaluate(std::string value,
    Transaction *transaction) {
    return value;
}


bool Action::evaluate(Rule *rule, Transaction *transaction) {
    return true;
}


}  // namespace actions
}  // namespace modsecurity
