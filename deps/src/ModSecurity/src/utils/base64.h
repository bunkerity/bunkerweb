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


#ifndef SRC_UTILS_BASE64_H_
#define SRC_UTILS_BASE64_H_

#include <string>

namespace modsecurity {
namespace Utils {

class Base64 {
 public:
    Base64() { }

    static std::string encode(const std::string& data);

    static std::string decode(const std::string& data, bool forgiven);
    static std::string decode(const std::string& data);
    static std::string decode_forgiven(const std::string& data);

    static void decode_forgiven_engine(unsigned char *output,
        size_t output_size, size_t *aiming_size, const unsigned char *input,
        size_t input_size);
};


}  // namespace Utils
}  // namespace modsecurity

#endif  // SRC_UTILS_BASE64_H_

