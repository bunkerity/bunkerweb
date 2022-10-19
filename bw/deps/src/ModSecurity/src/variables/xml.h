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

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>

#ifndef SRC_VARIABLES_XML_H_
#define SRC_VARIABLES_XML_H_

#include "src/variables/variable.h"
#include "src/variables/xml.h"

namespace modsecurity {

class Transaction;
namespace variables {


/* Invocation without an XPath expression makes sense
 * with functions that manipulate the document tree.
 */
class XML_NoDictElement : public Variable {
 public:
    XML_NoDictElement()
        : Variable("XML"),
        m_plain("[XML document tree]"),
        m_var(&m_name, &m_plain) {
        }

    void evaluate(Transaction *transaction,
        Rule *rule,
        std::vector<const VariableValue *> *l) override {
        l->push_back(new VariableValue(&m_var));
    }

    std::string m_plain;
    VariableValue m_var;
};


class XML : public Variable {
 public:
    explicit XML(std::string _name)
        : Variable(_name) { }

    void evaluate(Transaction *transaction,
        Rule *rule,
        std::vector<const VariableValue *> *l) override;
};


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_XML_H_
