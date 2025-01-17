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

#ifndef SRC_UTILS_SHARED_FILES_H_
#define SRC_UTILS_SHARED_FILES_H_


#include <stdio.h>
#ifdef WIN32
#include <Windows.h>
#endif

#include <unordered_map>
#include <string>


namespace modsecurity {
namespace utils {


class SharedFiles {
public:
    bool open(const std::string& fileName, std::string *error);
    void close(const std::string& fileName);
    bool write(const std::string& fileName, const std::string &msg,
        std::string *error);

    static SharedFiles& getInstance() {
        static SharedFiles instance;
        return instance;
    }

private:
    SharedFiles() = default;
    ~SharedFiles() = default;

    // C++ 03
    // ========
    // Dont forget to declare these two. You want to make sure they
    // are unacceptable otherwise you may accidentally get copies of
    // your singleton appearing.
    SharedFiles(SharedFiles const&) = delete;
    void operator=(SharedFiles const&) = delete;

     struct handler_info {
         FILE* fp;
#ifdef WIN32
         HANDLE hMutex;
#endif
         unsigned int cnt;
     };

    using handlers_map = std::unordered_map<std::string, handler_info>;
    handlers_map m_handlers;

    handlers_map::iterator add_new_handler(
        const std::string &fileName, std::string *error);
};


}  // namespace utils
}  // namespace modsecurity

#endif  // SRC_UTILS_SHARED_FILES_H_
