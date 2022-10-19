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

#include <stdio.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/types.h>

#include <iostream>
#include <map>
#include <string>
#include <cstring>


#ifndef SRC_DEBUG_LOG_DEBUG_LOG_WRITER_H_
#define SRC_DEBUG_LOG_DEBUG_LOG_WRITER_H_


namespace modsecurity {
namespace debug_log {


/** @ingroup ModSecurity_CPP_API */
class DebugLogWriter {
 public:
    static DebugLogWriter& getInstance() {
        static DebugLogWriter instance;
        return instance;
    }

    void write_log(const std::string& file, const std::string& msg);
    void close(const std::string& m_fileName);
    int open(const std::string& m_fileName, std::string *error);

 private:
    DebugLogWriter() : m_first(NULL) { }
    ~DebugLogWriter() { }

    // C++ 03
    // ========
    // Dont forget to declare these two. You want to make sure they
    // are unacceptable otherwise you may accidentally get copies of
    // your singleton appearing.
    DebugLogWriter(DebugLogWriter const&);
    void operator=(DebugLogWriter const&);

    struct debug_log_file_handler *m_first;
};


}  // namespace debug_log
}  // namespace modsecurity

#endif  // SRC_DEBUG_LOG_DEBUG_LOG_WRITER_H_
