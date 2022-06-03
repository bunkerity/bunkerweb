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


#include <algorithm>
#include <random>
#include <memory>
#include <functional>
#include <string>

#include "modsecurity/modsecurity.h"

namespace modsecurity {
namespace utils {


double random_number(const double from, const double to) {
    std::random_device rd;
    std::mt19937 mt(rd());
    return std::bind(
        std::uniform_real_distribution<>{from, to},
        std::default_random_engine{ mt() })();
}


double generate_transaction_unique_id() {
    return random_number(0, 100);
}


}  // namespace utils
}  // namespace modsecurity

