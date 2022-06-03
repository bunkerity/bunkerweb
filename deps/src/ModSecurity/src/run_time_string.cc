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


#include <memory>

#include "src/run_time_string.h"

#include "modsecurity/variable_value.h"
#include "modsecurity/transaction.h"
#include "src/variables/rule.h"
#include "src/variables/tx.h"
#include "src/variables/highest_severity.h"
#include "src/utils/string.h"
#include "src/variables/variable.h"


namespace modsecurity {


void RunTimeString::appendText(std::string text) {
    std::unique_ptr<RunTimeElementHolder> r(new RunTimeElementHolder);
    r->m_string = text;
    m_elements.push_back(std::move(r));
}


void RunTimeString::appendVar(
    std::unique_ptr<modsecurity::variables::Variable> var) {
    std::unique_ptr<RunTimeElementHolder> r(new RunTimeElementHolder);
    r->m_var = std::move(var);
    m_elements.push_back(std::move(r));
    m_containsMacro = true;
}


std::string RunTimeString::evaluate(Transaction *t) {
    return evaluate(t, NULL);
}


std::string RunTimeString::evaluate(Transaction *t, Rule *r) {
    std::string s;
    for (auto &z : m_elements) {
        if (z->m_string.size() > 0) {
            s.append(z->m_string);
        } else if (z->m_var != NULL && t != NULL) {
            std::vector<const VariableValue *> l;
            z->m_var->evaluate(t, r, &l);
            if (l.size() > 0) {
                s.append(l[0]->getValue());
            }
            for (auto &i : l) {
                delete i;
            }
        }
    }
    return s;
}

}  // namespace modsecurity
