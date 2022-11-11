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

#include "src/utils/regex.h"

#include <pcre.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <string>
#include <list>

#include <fstream>
#include <iostream>

#include "src/utils/geo_lookup.h"

#if PCRE_HAVE_JIT
#define pcre_study_opt PCRE_STUDY_JIT_COMPILE
#else
#define pcre_study_opt 0
#endif

namespace modsecurity {
namespace Utils {


Regex::Regex(const std::string& pattern_)
    : pattern(pattern_.empty() ? ".*" : pattern_) {
    const char *errptr = NULL;
    int erroffset;

    m_pc = pcre_compile(pattern.c_str(), PCRE_DOTALL|PCRE_MULTILINE,
        &errptr, &erroffset, NULL);

    m_pce = pcre_study(m_pc, pcre_study_opt, &errptr);
}


Regex::~Regex() {
    if (m_pc != NULL) {
        pcre_free(m_pc);
        m_pc = NULL;
    }
    if (m_pce != NULL) {
#if PCRE_HAVE_JIT
        pcre_free_study(m_pce);
#else
        pcre_free(m_pce);
#endif
        m_pce = NULL;
    }
}


std::list<SMatch> Regex::searchAll(const std::string& s) const {
    const char *subject = s.c_str();
    const std::string tmpString = std::string(s.c_str(), s.size());
    int ovector[OVECCOUNT];
    int rc, i, offset = 0;
    std::list<SMatch> retList;

    do {
        rc = pcre_exec(m_pc, m_pce, subject,
            s.size(), offset, 0, ovector, OVECCOUNT);

        for (i = 0; i < rc; i++) {
            size_t start = ovector[2*i];
            size_t end = ovector[2*i+1];
            size_t len = end - start;
            if (end > s.size()) {
                rc = 0;
                break;
            }
            std::string match = std::string(tmpString, start, len);
            offset = start + len;
            retList.push_front(SMatch(match, start));

            if (len == 0) {
                rc = 0;
                break;
            }
        }
    } while (rc > 0);

    return retList;
}

int Regex::search(const std::string& s, SMatch *match) const {
    int ovector[OVECCOUNT];
    int ret = pcre_exec(m_pc, m_pce, s.c_str(),
        s.size(), 0, 0, ovector, OVECCOUNT) > 0;

    if (ret > 0) {
        *match = SMatch(
            std::string(s, ovector[ret-1], ovector[ret] - ovector[ret-1]),
            0);
    }

    return ret;
}

int Regex::search(const std::string& s) const {
    int ovector[OVECCOUNT];
    return pcre_exec(m_pc, m_pce, s.c_str(),
        s.size(), 0, 0, ovector, OVECCOUNT) > 0;
}

}  // namespace Utils
}  // namespace modsecurity
