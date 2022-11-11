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

#include <ctime>
#include <iostream>
#include <string>
#include <list>

#include "modsecurity/modsecurity.h"

#ifndef SRC_UTILS_SYSTEM_H_
#define SRC_UTILS_SYSTEM_H_


namespace modsecurity {
namespace utils {


double cpu_seconds(void);
std::string find_resource(const std::string& file, const std::string& param,
    std::string *err);
std::string get_path(const std::string& file);
std::list<std::string> expandEnv(const std::string& var, int flags);
bool createDir(std::string dir, int mode, std::string *error);
bool isFile(std::string f);

}  // namespace utils
}  // namespace modsecurity

#endif  // SRC_UTILS_SYSTEM_H_
