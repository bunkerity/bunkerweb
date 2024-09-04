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

#include "parity_even_7bit.h"


namespace modsecurity::actions::transformations {


bool ParityEven7bit::transform(std::string &value, const Transaction *trans) const {
    return ParityEven7bit::inplace<true>(value);
}


}  // namespace modsecurity::actions::transformations
