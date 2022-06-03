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

#include "test/regression/custom_debug_log.h"

#include <iostream>
#include <string>

#include "modsecurity/debug_log.h"
#include "src/utils/regex.h"

namespace modsecurity_test {

CustomDebugLog::~CustomDebugLog() { }

void CustomDebugLog::write(int level, const std::string& message) {
    m_log << "[" << level << "] " << message << std::endl;
}

void CustomDebugLog::write(int level, const std::string &id,
    const std::string &uri, const std::string &msg) {
    std::string msgf = "[" + std::to_string(level) + "] " + msg;
    msgf = "[" + id + "] [" + uri + "] " + msgf;
    m_log << msgf << std::endl;
}

bool CustomDebugLog::contains(const std::string& pattern) {
    modsecurity::Utils::Regex re(pattern);
    std::string s = m_log.str();
    return modsecurity::Utils::regex_search(s, re);
}

std::string CustomDebugLog::log_messages() {
    return m_log.str();
}


int CustomDebugLog::getDebugLogLevel() {
    return 9;
}


}  // namespace modsecurity_test
