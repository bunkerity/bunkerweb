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
#include <fstream>
#include <string>

#ifndef SRC_DEBUG_LOG_WRITER_AGENT_H_
#define SRC_DEBUG_LOG_WRITER_AGENT_H_

namespace modsecurity {

/** @ingroup ModSecurity_CPP_API */
class DebugLogWriterAgent : public std::ofstream {
 public:
    explicit DebugLogWriterAgent(const std::string& fileName);
    ~DebugLogWriterAgent() {
        if (is_open()) {
            close();
        }
    }

    void write(const std::string& msg);
    bool refCountDecreaseAndCheck() {
        this->m_referenceCount--;
        if (this->m_referenceCount == 0) {
            return true;
        }
        return false;
    }

    void refCountIncrease() {
        this->m_referenceCount++;
    }

    int m_referenceCount;
    std::string m_fileName;
};


}  // namespace modsecurity

#endif  // SRC_DEBUG_LOG_WRITER_AGENT_H_
