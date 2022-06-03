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

#include "src/operators/le.h"

#include <string>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

bool Le::evaluate(Transaction *transaction, const std::string &input) {
    std::string p(m_string->evaluate(transaction));

    bool le = atoll(input.c_str()) <= atoll(p.c_str());

    return le;
}


}  // namespace operators
}  // namespace modsecurity
