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

#include "modsecurity/debug_log.h"

#include <stddef.h>

#include <fstream>

#include "src/debug_log/debug_log_writer.h"
#include "src/debug_log_writer_agent.h"


namespace modsecurity {
namespace debug_log {


DebugLog::~DebugLog() {
    DebugLogWriter::getInstance().close(m_fileName);
}

void DebugLog::setDebugLogFile(const std::string& fileName,
    std::string *error) {
    if (isLogFileSet()) {
        DebugLogWriter::getInstance().close(m_fileName);
    }

    m_fileName = fileName;

    DebugLogWriter::getInstance().open(m_fileName, error);
}


void DebugLog::setDebugLogLevel(int level) {
    m_debugLevel = level;
}


bool DebugLog::isLogFileSet() {
    return m_fileName.empty() == false;
}


bool DebugLog::isLogLevelSet() {
    return m_debugLevel != -1;
}


const std::string& DebugLog::getDebugLogFile() {
    return m_fileName;
}


int DebugLog::getDebugLogLevel() {
    if (m_debugLevel < 0) {
        return 0;
    }

    return m_debugLevel;
}


void DebugLog::write(int level, const std::string &id,
    const std::string &uri, const std::string &msg) {
    if (level <= m_debugLevel) {
        std::string msgf = "[" + std::to_string(level) + "] " + msg;
        msgf = "[" + id + "] [" + uri + "] " + msgf;

        DebugLogWriter &d = DebugLogWriter::getInstance();
        d.write_log(m_fileName, msgf);
    }
}


void DebugLog::write(int level, const std::string &msg) {
    if (level <= m_debugLevel) {
        std::string msgf = "[" + std::to_string(level) + "] " + msg;
        DebugLogWriter &d = DebugLogWriter::getInstance();
        d.write_log(m_fileName, msgf);
    }
}


}  // namespace debug_log
}  // namespace modsecurity
