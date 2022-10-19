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

#ifdef __cplusplus
#include <string>
#endif

#ifndef HEADERS_MODSECURITY_DEBUG_LOG_H_
#define HEADERS_MODSECURITY_DEBUG_LOG_H_


#ifndef __cplusplus
typedef struct DebugLog_t DebugLog;
#endif

#ifdef __cplusplus

namespace modsecurity {
namespace debug_log {


/** @ingroup ModSecurity_CPP_API */
class DebugLog {
 public:
    DebugLog()
        : m_debugLevel(-1),
        m_fileName("") { }

    virtual ~DebugLog();

    virtual void write(int level, const std::string &msg);
    virtual void write(int level, const std::string &id,
        const std::string &uri, const std::string &msg);
    bool isLogFileSet();
    bool isLogLevelSet();
    void setDebugLogLevel(int level);
    void setDebugLogFile(const std::string &fileName, std::string *error);
    const std::string& getDebugLogFile();
    virtual int getDebugLogLevel();

    int m_debugLevel;
 private:
    std::string m_fileName;
};


}  // namespace debug_log
}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_DEBUG_LOG_H_
