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

#ifdef __cplusplus
#include <string>
#include <memory>
#endif

#ifndef HEADERS_MODSECURITY_VARIABLE_ORIGIN_H_
#define HEADERS_MODSECURITY_VARIABLE_ORIGIN_H_


#ifndef __cplusplus
typedef struct DebugLog_t DebugLog;
#endif

#ifdef __cplusplus

namespace modsecurity {


/** @ingroup ModSecurity_CPP_API */
class VariableOrigin {
 public:
    VariableOrigin()
        : m_length(0),
        m_offset(0) { }
    VariableOrigin(size_t length, size_t offset)
        : m_length(length),
        m_offset(offset) { } 

    std::string toText() const {
        const auto offset = std::to_string(m_offset);
        const auto len = std::to_string(m_length);
        return "v" + offset + "," + len;
    }

    size_t m_length;
    size_t m_offset;
};


}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_VARIABLE_ORIGIN_H_


