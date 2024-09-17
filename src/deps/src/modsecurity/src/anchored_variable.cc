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

#include <ctime>
#include <iostream>
#include <fstream>
#include <string>
#include <vector>

#include "../headers/modsecurity/anchored_variable.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/transaction.h"
#include "src/utils/regex.h"

namespace modsecurity {


AnchoredVariable::AnchoredVariable(Transaction *t,
    const std::string &name)
    : m_transaction(t),
    m_offset(0),
    m_name(name),
    m_value(""),
    m_var(&name) {
}


void AnchoredVariable::unset() {
    m_value.clear();
}


void AnchoredVariable::set(const std::string &a, size_t offset,
    size_t offsetLen) {
    m_offset = offset;
    m_value.assign(a.c_str(), a.size());
    m_var.addOrigin(offsetLen, offset);
}


void AnchoredVariable::set(const std::string &a, size_t offset) {
    m_offset = offset;
    m_value.assign(a.c_str(), a.size());
    m_var.addOrigin(m_value.size(), offset);
}


void AnchoredVariable::evaluate(std::vector<const VariableValue *> *l) {
    if (m_name.empty()) {
        return;
    }

    m_var.setValue(m_value);
    l->push_back(new VariableValue(&m_var));
}


std::string * AnchoredVariable::evaluate() {
    return &m_value;
}


std::unique_ptr<std::string> AnchoredVariable::resolveFirst() {
    if (m_value.empty()) {
        return nullptr;
    }
    return std::make_unique<std::string>(m_value);
}


}  // namespace modsecurity
