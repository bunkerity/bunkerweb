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

#include "src/actions/set_uid.h"

#include <iostream>
#include <string>

#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"


namespace modsecurity {
namespace actions {


bool SetUID::init(std::string *error) {
    return true;
}


bool SetUID::evaluate(Rule *rule, Transaction *t) {
    std::string colNameExpanded(m_string->evaluate(t));
    ms_dbg_a(t, 8, "User collection initiated with value: \'"
        + colNameExpanded + "\'.");

    t->m_collections.m_user_collection_key = colNameExpanded;
    t->m_variableUserID.set(colNameExpanded, t->m_variableOffset);

    return true;
}

}  // namespace actions
}  // namespace modsecurity
