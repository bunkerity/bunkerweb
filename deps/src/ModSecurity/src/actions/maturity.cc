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

#include "src/actions/maturity.h"

#include <iostream>
#include <string>

#include "modsecurity/actions/action.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"


namespace modsecurity {
namespace actions {


bool Maturity::init(std::string *error) {
    try {
        m_maturity = std::stoi(m_parser_payload);
    }  catch (...) {
        error->assign("Maturity: The input \"" + m_parser_payload + "\" is " \
            "not a number.");
        return false;
    }
    return true;
}


bool Maturity::evaluate(Rule *rule, Transaction *transaction) {
    rule->m_maturity = m_maturity;
    return true;
}


}  // namespace actions
}  // namespace modsecurity
