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
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#ifdef __OpenBSD__
#include <glob.h>
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
#include <direct.h>
#elif defined __GNUC__
#include <sys/types.h>
#include <sys/stat.h>
#endif

#include "src/utils/system.h"
#include "src/config.h"

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
    std::ifstream *iss;

    err->assign("Looking at: ");
    // Trying absolute or relative to the current dir.
    iss = new std::ifstream(resource, std::ios::in);
    if (iss->is_open()) {
        iss->close();
        delete iss;
        return resource;
    } else {
        err->append("'" + resource + "', ");
    }
    delete iss;

    // What about `*' ?
    if (utils::expandEnv(resource, 0).size() > 0) {
        return resource;
    } else {
        err->append("'" + resource + "', ");
    }

    // Trying the same path of the configuration file.
    std::string f = get_path(config) + "/" + resource;
    iss = new std::ifstream(f, std::ios::in);
    if (iss->is_open()) {
        iss->close();
        delete iss;
        return f;
    } else {
        err->append("'" + f + "', ");
    }
    delete iss;

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

#ifdef __OpenBSD__
    glob_t p;
    if (glob(var.c_str(), flags, NULL, &p) == false) {
        if (p.gl_pathc) {
            for (char** exp = p.gl_pathv; *exp; ++exp) {
#else
    wordexp_t p;
    if (wordexp(var.c_str(), &p, flags) == false) {
        if (p.we_wordc) {
            for (char** exp = p.we_wordv; *exp; ++exp) {
#endif
                std::ifstream *iss = new std::ifstream(exp[0], std::ios::in);
                if (iss->is_open()) {
                    iss->close();
                    vars.push_back(exp[0]);
                }
                delete iss;
            }
        }
#ifdef __OpenBSD__
        globfree(&p);
#else
        wordfree(&p);
#endif
    }
    return vars;
}

bool createDir(std::string dir, int mode, std::string *error) {
    int ret = mkdir(dir.data(), mode);
    if (ret != 0 && errno != EEXIST) {
        error->assign("Not able to create directory: " + dir + ": " \
            + strerror(errno) + ".");
        return false;
    }

    return true;
}


bool isFile(std::string f) {
    struct stat fileInfo;
    FILE *fp = fopen(f.c_str(), "r");
    if (fp == NULL) {
        return false;
    }
    fstat(fileno(fp), &fileInfo);
    if (!S_ISREG(fileInfo.st_mode)) {
        fclose(fp);
        return false;
    }
    fclose(fp);

    return true;
}


}  // namespace utils
}  // namespace modsecurity
