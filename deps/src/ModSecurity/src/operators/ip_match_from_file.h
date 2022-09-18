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
#ifndef SRC_OPERATORS_IP_MATCH_FROM_FILE_H_
#define SRC_OPERATORS_IP_MATCH_FROM_FILE_H_

#include <string>
#include <memory>
#include <utility>

#include "src/operators/ip_match.h"

namespace modsecurity {
namespace operators {

class IpMatchFromFile : public IpMatch {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit IpMatchFromFile(std::unique_ptr<RunTimeString> param)
        : IpMatch("IpMatchFromFile", std::move(param)) { }
    IpMatchFromFile(const std::string &n, std::unique_ptr<RunTimeString> param)
        : IpMatch(n, std::move(param)) { }
    bool init(const std::string& file, std::string *error) override;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_IP_MATCH_FROM_FILE_H_
