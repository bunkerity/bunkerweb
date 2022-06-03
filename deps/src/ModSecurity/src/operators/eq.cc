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

#include "src/operators/eq.h"

#include <string>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {


bool Eq::evaluate(Transaction *transaction, const std::string &input) {
    int p = 0;
    int i = 0;
    std::string pt(m_string->evaluate(transaction));

    try {
        p = std::stoi(pt);
    } catch (...) {
        p = 0;
    }
    try {
        i = std::stoi(input);
    } catch (...) {
        i = 0;
    }

    return p == i;
}


}  // namespace operators
}  // namespace modsecurity
