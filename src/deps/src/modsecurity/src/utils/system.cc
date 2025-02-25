/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#ifdef __OpenBSD__
#include <glob.h>
#elif defined(WIN32)
#include "Poco/Glob.h"
#include <algorithm>
#else
#include <wordexp.h>
#endif
#include <stdint.h>
#include <inttypes.h>

#include <ctime>
#include <iostream>
#include <string>
#include <vector>

#if defined _MSC_VER
#include "src/compat/msvc.h"
#include <direct.h>
#elif defined __GNUC__
#include <sys/types.h>
#include <sys/stat.h>
#endif

#include "src/utils/system.h"
#include "src/config.h"

#ifdef WIN32

// Public domain code from mingw-w64's winpthreads
// https://sourceforge.net/p/mingw-w64/code/HEAD/tree/trunk/mingw-w64-libraries/winpthreads/src/clock.c
// 

#define CLOCK_PROCESS_CPUTIME_ID    2
#define POW10_7                 10000000

// NOTE: includes only CLOCK_PROCESS_CPUTIME_ID implementation, ignores clock_id argument
static int clock_gettime(int clock_id, struct timespec *tp)
{
    unsigned __int64 t;
    LARGE_INTEGER pf, pc;
    union {
        unsigned __int64 u64;
        FILETIME ft;
    }  ct, et, kt, ut;

    if(0 == GetProcessTimes(GetCurrentProcess(), &ct.ft, &et.ft, &kt.ft, &ut.ft))
        return -1;
    t = kt.u64 + ut.u64;
    tp->tv_sec = t / POW10_7;
    tp->tv_nsec = ((int) (t % POW10_7)) * 100;

    return 0;
}

#endif

namespace modsecurity {
namespace utils {


double cpu_seconds(void) {
    /*
     * FIXME: Temporary hack to fix build on MacOS X.  Very issuficient way, but
     *      works.  Worth reimplementing using mach_absolute_time().
     */
#ifndef MACOSX
    struct timespec t;
    if (!clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &t))
        return static_cast<double>(t.tv_sec)
            + static_cast<double>(t.tv_nsec / 1000000000.0);
    else
        return static_cast<double>(clock()) /
            static_cast<double>(CLOCKS_PER_SEC);
#endif
        return 0;
}


std::string find_resource(const std::string& resource,
    const std::string& config, std::string *err) {

    err->assign("Looking at: ");
    // Trying absolute or relative to the current dir.
    auto iss = std::ifstream(resource, std::ios::in);
    if (iss.is_open()) {
        return resource;
    } else {
        err->append("'" + resource + "', ");
    }

    // What about `*' ?
    if (utils::expandEnv(resource, 0).size() > 0) {
        return resource;
    } else {
        err->append("'" + resource + "', ");
    }

    // Trying the same path of the configuration file.
    std::string f = get_path(config) + "/" + resource;
    iss = std::ifstream(f, std::ios::in);
    if (iss.is_open()) {
        return f;
    } else {
        err->append("'" + f + "', ");
    }

    // What about `*' ?
    if (utils::expandEnv(f, 0).size() > 0) {
        return f;
    } else {
        err->append("'" + f + "'.");
    }

    return std::string("");
}


std::string get_path(const std::string& file) {
    size_t found;

    found = file.find_last_of("/\\");
    if (found > 0) {
        return file.substr(0, found);
    }

    return std::string("");
}


std::list<std::string> expandEnv(const std::string& var, int flags) {
    std::list<std::string> vars;
#ifdef WIN32
    // NOTE: align scopes with if & if in other versions
    {
        {
            std::set<std::string> files;
            Poco::Glob::glob(var, files);
            for(auto file : files) {
                std::replace(file.begin(), file.end(), '\\', '/');  // preserve unix-like paths
                const char* exp[] = { file.c_str() };
#elif defined(__OpenBSD__)
    glob_t p;
    if (glob(var.c_str(), flags, NULL, &p) == false) {
        if (p.gl_pathc) {
            for (char** exp = p.gl_pathv; *exp; ++exp) {
#else
    wordexp_t p;
    flags = flags | WRDE_NOCMD;
    if (wordexp(var.c_str(), &p, flags) == false) {
        if (p.we_wordc) {
            for (char** exp = p.we_wordv; *exp; ++exp) {
#endif
                auto iss = std::ifstream(exp[0], std::ios::in);
                if (iss.is_open())
                    vars.push_back(exp[0]);
            }
        }
#ifdef WIN32
#elif defined(__OpenBSD__)
        globfree(&p);
#else
        wordfree(&p);
#endif
    }
    return vars;
}

bool createDir(const std::string& dir, int mode, std::string *error) {
#ifndef WIN32
    int ret = mkdir(dir.data(), mode);
#else
    if (dir == ".")
        return true;
    int ret = _mkdir(dir.c_str());
#endif
    if (ret != 0 && errno != EEXIST) {
        error->assign("Not able to create directory: " + dir + ": " \
            + strerror(errno) + ".");
        return false;
    }

    return true;
}


bool isFile(const std::string& f) {
    struct stat fileInfo;
    FILE *fp = fopen(f.c_str(), "r");
    if (fp == NULL) {
        return false;
    }
    fstat(fileno(fp), &fileInfo);
    if (!S_ISREG(fileInfo.st_mode)) { // cppcheck-suppress syntaxError ; false positive
        fclose(fp);
        return false;
    }
    fclose(fp);

    return true;
}


}  // namespace utils
}  // namespace modsecurity
