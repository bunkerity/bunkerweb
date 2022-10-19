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

#include "src/variables/variable.h"

#include <iostream>
#include <string>
#include <vector>
#include <list>

#include "modsecurity/transaction.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace variables {


Variable::Variable(std::string name)
    : m_name(name),
    m_collectionName("") {
    size_t a = m_name.find(":");
    if (a == std::string::npos) {
        a = m_name.find(".");
    }
    if (a != std::string::npos) {
        m_collectionName = utils::string::toupper(std::string(m_name, 0, a));
        m_name = std::string(m_name, a + 1, m_name.size());
        m_fullName = std::make_shared<std::string>(m_collectionName
            + ":" + m_name);
    } else {
        m_fullName = std::make_shared<std::string>(m_name);
        m_collectionName = m_name;
        m_name = "";
    }
}


Variable::Variable(Variable *var) :
    m_name(var->m_name),
    m_collectionName(var->m_collectionName),
    m_fullName(var->m_fullName) { }


void Variable::addsKeyExclusion(Variable *v) {
    std::unique_ptr<KeyExclusion> r;
    VariableModificatorExclusion *ve = \
        dynamic_cast<VariableModificatorExclusion *>(v);
    VariableRegex *vr;

    if (!ve) {
        return;
    }

    vr = dynamic_cast<VariableRegex *>(ve->m_base.get());

    if (vr == NULL) {
        r.reset(new KeyExclusionString(v->m_name));
    } else {
        r.reset(new KeyExclusionRegex(vr->m_regex));
    }

    m_keyExclusion.push_back(std::move(r));
}


std::string operator+(std::string a, Variable *v) {
    return a + *v->m_fullName.get();
}


std::string operator+(std::string a, Variables *v) {
    std::string test;
    for (auto &b : *v) {
        if (test.empty()) {
            test = std::string("") + b;
        } else {
            test = test + "|" + b;
        }
    }

    return a + test;
}


}  // namespace variables
}  // namespace modsecurity
