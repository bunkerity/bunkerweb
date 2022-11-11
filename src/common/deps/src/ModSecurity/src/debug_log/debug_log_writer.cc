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

#include "src/debug_log/debug_log_writer.h"

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <fstream>

#include "src/utils/shared_files.h"

namespace modsecurity {
namespace debug_log {


int DebugLogWriter::open(const std::string& fileName, std::string *error) {
    return utils::SharedFiles::getInstance().open(fileName, error);
}


void DebugLogWriter::close(const std::string& fileName) {
     utils::SharedFiles::getInstance().close(fileName);
}


void DebugLogWriter::write_log(const std::string& fileName,
    const std::string &msg) {
    std::string err;
    std::string lmsg = msg + "\n";
    utils::SharedFiles::getInstance().write(fileName, lmsg, &err);
}


}  // namespace debug_log
}  // namespace modsecurity
