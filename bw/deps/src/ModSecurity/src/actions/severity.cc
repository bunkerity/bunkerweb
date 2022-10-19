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

#include "src/actions/severity.h"

#include <iostream>
#include <string>
#include <memory>

#include "modsecurity/actions/action.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rules.h"
#include "src/utils/string.h"
#include "modsecurity/rule_message.h"


namespace modsecurity {
namespace actions {


bool Severity::init(std::string *error) {
    std::string a = utils::string::tolower(m_parser_payload);
    if (a == "emergency") {
        m_severity = 0;
        return true;
    } else if (a == "alert") {
        m_severity = 1;
        return true;
    } else if (a == "critical") {
        m_severity = 2;
        return true;
    } else if (a == "error") {
        m_severity = 3;
        return true;
    } else if (a == "warning") {
        m_severity = 4;
        return true;
    } else if (a == "notice") {
        m_severity = 5;
        return true;
    } else if (a == "info") {
        m_severity = 6;
        return true;
    } else if (a == "debug") {
        m_severity = 7;
        return true;
    } else {
        try {
            m_severity = std::stoi(a);
            return true;
        }  catch (...) {
            error->assign("Severity: The input \"" + a + "\" is " \
                "not a number.");
        }
    }

    return false;
}


bool Severity::evaluate(Rule *rule, Transaction *transaction,
    std::shared_ptr<RuleMessage> rm) {
    ms_dbg_a(transaction, 9, "This rule severity is: " + \
        std::to_string(this->m_severity) + " current transaction is: " + \
        std::to_string(transaction->m_highestSeverityAction));

    rm->m_severity = m_severity;

    if (transaction->m_highestSeverityAction > this->m_severity) {
        transaction->m_highestSeverityAction = this->m_severity;
    }

    return true;
}


}  // namespace actions
}  // namespace modsecurity
