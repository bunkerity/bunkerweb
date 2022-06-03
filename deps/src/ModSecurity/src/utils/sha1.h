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


#ifndef SRC_UTILS_SHA1_H_
#define SRC_UTILS_SHA1_H_

#include <algorithm>
#include <iostream>
#include <string>

namespace modsecurity {
namespace Utils {

class Sha1 {
 public:
    Sha1() { }

    static std::string hexdigest(const std::string& input);
    static std::string digest(const std::string& input);
};

}  // namespace Utils
}  // namespace modsecurity

#endif  // SRC_UTILS_SHA1_H_
