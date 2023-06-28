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

#include "src/utils/regex.h"

#include <string>
#include <list>

#include <fstream>
#include <iostream>

#include "src/utils/geo_lookup.h"

#ifndef WITH_PCRE2
#if PCRE_HAVE_JIT
#define pcre_study_opt PCRE_STUDY_JIT_COMPILE
#else
#define pcre_study_opt 0
#endif
#endif

namespace modsecurity {
namespace Utils {

// Helper function to tell us if the current config indicates CRLF is a valid newline sequence
bool crlfIsNewline() {
#if WITH_PCRE2
    uint32_t newline = 0;
    pcre2_config(PCRE2_CONFIG_NEWLINE, &newline);
    bool crlf_is_newline =
        newline == PCRE2_NEWLINE_ANY ||
        newline == PCRE2_NEWLINE_CRLF ||
        newline == PCRE2_NEWLINE_ANYCRLF;
#else
    int d = 0;
    pcre_config(PCRE_CONFIG_NEWLINE, &d);

    unsigned int option_bits = (d == 13)? PCRE_NEWLINE_CR :
        (d == 10)? PCRE_NEWLINE_LF :
        (d == (13<<8 | 10))? PCRE_NEWLINE_CRLF :
        (d == -2)? PCRE_NEWLINE_ANYCRLF :
        (d == -1)? PCRE_NEWLINE_ANY : 0;

    bool crlf_is_newline =
        option_bits == PCRE_NEWLINE_ANY ||
        option_bits == PCRE_NEWLINE_CRLF ||
        option_bits == PCRE_NEWLINE_ANYCRLF;
#endif
    return crlf_is_newline;
}

Regex::Regex(const std::string& pattern_, bool ignoreCase)
    : pattern(pattern_.empty() ? ".*" : pattern_) {
#if WITH_PCRE2
    PCRE2_SPTR pcre2_pattern = reinterpret_cast<PCRE2_SPTR>(pattern.c_str());
    uint32_t pcre2_options = (PCRE2_DOTALL|PCRE2_MULTILINE);
    if (ignoreCase) {
        pcre2_options |= PCRE2_CASELESS;
    }
    int errornumber = 0;
    PCRE2_SIZE erroroffset = 0;
    m_pc = pcre2_compile(pcre2_pattern, PCRE2_ZERO_TERMINATED,
        pcre2_options, &errornumber, &erroroffset, NULL);
    m_pcje = pcre2_jit_compile(m_pc, PCRE2_JIT_COMPLETE);
#else
    const char *errptr = NULL;
    int erroffset;
    int flags = (PCRE_DOTALL|PCRE_MULTILINE);

    if (ignoreCase == true) {
        flags |= PCRE_CASELESS;
    }
    m_pc = pcre_compile(pattern.c_str(), flags,
        &errptr, &erroffset, NULL);

    m_pce = pcre_study(m_pc, pcre_study_opt, &errptr);
#endif
}


Regex::~Regex() {
#if WITH_PCRE2
    pcre2_code_free(m_pc);
#else
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
#endif
}


std::list<SMatch> Regex::searchAll(const std::string& s) const {
    std::list<SMatch> retList;
    int rc = 0;
#ifdef WITH_PCRE2
    PCRE2_SPTR pcre2_s = reinterpret_cast<PCRE2_SPTR>(s.c_str());
    PCRE2_SIZE offset = 0;

    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(m_pc, NULL);
    do {
        if (m_pcje == 0) {
            rc = pcre2_jit_match(m_pc, pcre2_s, s.length(),
                            offset, 0, match_data, NULL);
        } 
        
        if (m_pcje != 0 || rc == PCRE2_ERROR_JIT_STACKLIMIT) {
            rc = pcre2_match(m_pc, pcre2_s, s.length(),
                            offset, PCRE2_NO_JIT, match_data, NULL);
        }
        PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
#else
    const char *subject = s.c_str();
    int ovector[OVECCOUNT];
    int offset = 0;

    do {
        rc = pcre_exec(m_pc, m_pce, subject,
            s.size(), offset, 0, ovector, OVECCOUNT);
#endif
        for (int i = 0; i < rc; i++) {
            size_t start = ovector[2*i];
            size_t end = ovector[2*i+1];
            size_t len = end - start;
            if (end > s.size()) {
                rc = -1;
                break;
            }
            std::string match = std::string(s, start, len);
            offset = start + len;
            retList.push_front(SMatch(match, start));

            if (len == 0) {
                rc = 0;
                break;
            }
        }
    } while (rc > 0);

#ifdef WITH_PCRE2
    pcre2_match_data_free(match_data);
#endif
    return retList;
}

bool Regex::searchOneMatch(const std::string& s, std::vector<SMatchCapture>& captures) const {
#ifdef WITH_PCRE2
    PCRE2_SPTR pcre2_s = reinterpret_cast<PCRE2_SPTR>(s.c_str());
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(m_pc, NULL);
    int rc = 0;
    if (m_pcje == 0) {
        rc = pcre2_jit_match(m_pc, pcre2_s, s.length(), 0, 0, match_data, NULL);
    } 
    
    if (m_pcje != 0 || rc == PCRE2_ERROR_JIT_STACKLIMIT) {
        rc = pcre2_match(m_pc, pcre2_s, s.length(), 0, PCRE2_NO_JIT, match_data, NULL);
    }
    PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
#else
    const char *subject = s.c_str();
    int ovector[OVECCOUNT];

    int rc = pcre_exec(m_pc, m_pce, subject, s.size(), 0, 0, ovector, OVECCOUNT);
#endif

    for (int i = 0; i < rc; i++) {
        size_t start = ovector[2*i];
        size_t end = ovector[2*i+1];
        size_t len = end - start;
        if (end > s.size()) {
            continue;
        }
        SMatchCapture capture(i, start, len);
        captures.push_back(capture);
    }

#ifdef WITH_PCRE2
    pcre2_match_data_free(match_data);
#endif
    return (rc > 0);
}

bool Regex::searchGlobal(const std::string& s, std::vector<SMatchCapture>& captures) const {
    bool prev_match_zero_length = false;
#ifdef WITH_PCRE2
    PCRE2_SPTR pcre2_s = reinterpret_cast<PCRE2_SPTR>(s.c_str());
    PCRE2_SIZE startOffset = 0;

    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(m_pc, NULL);
    while (startOffset <= s.length()) {
        uint32_t pcre2_options = 0;
        if (prev_match_zero_length) {
            pcre2_options = PCRE2_NOTEMPTY_ATSTART | PCRE2_ANCHORED;
        }
        int rc = pcre2_match(m_pc, pcre2_s, s.length(),
                            startOffset, pcre2_options, match_data, NULL);
        PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);

#else
    const char *subject = s.c_str();
    int startOffset = 0;

    while (startOffset <= s.length()) {
        int ovector[OVECCOUNT];
        int pcre_options = 0;
        if (prev_match_zero_length) {
            pcre_options = PCRE_NOTEMPTY_ATSTART | PCRE_ANCHORED;
        }
        int rc = pcre_exec(m_pc, m_pce, subject, s.length(), startOffset, pcre_options, ovector, OVECCOUNT);

#endif
        if (rc > 0) {
            size_t firstGroupForThisFullMatch = captures.size();
            for (int i = 0; i < rc; i++) {
                size_t start = ovector[2*i];
                size_t end = ovector[2*i+1];
                size_t len = end - start;
                if (end > s.length()) {
                    continue;
                }
                SMatchCapture capture(firstGroupForThisFullMatch + i, start, len);
                captures.push_back(capture);

                if (i == 0) {
                    if (len > 0) {
                        // normal case; next call to pcre_exec should start after the end of the last full match string
                        startOffset = end;
                        prev_match_zero_length = false;
                    } else {
                        if ( startOffset == s.length()) {
                            // zero-length match at end of string; force end of while-loop
                            startOffset++;
                        } else {
                            // zero-length match mid-string; adjust next match attempt
                            prev_match_zero_length = true;
                        }
                    }
                }
            }
        } else {
            if (prev_match_zero_length) {
                // The n-1 search found a zero-length match, so we did a subsequent search
                // with the special flags. That subsequent exec did not find a match, so now advance
                // by one character (unless CRLF, then advance by two)
                startOffset++;
                if (crlfIsNewline() && (startOffset < s.length()) && (s[startOffset-1] == '\r')
                    && (s[startOffset] == '\n')) {
                    startOffset++;
                }
                prev_match_zero_length = false;
            } else {
                // normal case; no match on most recent scan (with options=0).  We are done.
                break;
            }
        }
    }

#ifdef WITH_PCRE2
    pcre2_match_data_free(match_data);
#endif
    return (captures.size() > 0);
}

int Regex::search(const std::string& s, SMatch *match) const {
#ifdef WITH_PCRE2
    PCRE2_SPTR pcre2_s = reinterpret_cast<PCRE2_SPTR>(s.c_str());
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(m_pc, NULL);
    int ret = 0;
    if (m_pcje == 0) {
        ret = pcre2_match(m_pc, pcre2_s, s.length(),
            0, 0, match_data, NULL) > 0;
    } 
    
    if (m_pcje != 0 || ret == PCRE2_ERROR_JIT_STACKLIMIT) {
        ret = pcre2_match(m_pc, pcre2_s, s.length(),
            0, PCRE2_NO_JIT, match_data, NULL) > 0;
    }
    if (ret > 0) { // match
        PCRE2_SIZE *ovector = pcre2_get_ovector_pointer(match_data);
#else
    int ovector[OVECCOUNT];
    int ret = pcre_exec(m_pc, m_pce, s.c_str(),
        s.size(), 0, 0, ovector, OVECCOUNT) > 0;

    if (ret > 0) {
#endif
        *match = SMatch(
            std::string(s, ovector[ret-1], ovector[ret] - ovector[ret-1]),
            0);
    }

#ifdef WITH_PCRE2
    pcre2_match_data_free(match_data);
#endif
    return ret;
}

int Regex::search(const std::string& s) const {
#ifdef WITH_PCRE2
    PCRE2_SPTR pcre2_s = reinterpret_cast<PCRE2_SPTR>(s.c_str());
    pcre2_match_data *match_data = pcre2_match_data_create_from_pattern(m_pc, NULL);
    int rc = 0;
    if (m_pcje == 0) {
        rc = pcre2_jit_match(m_pc, pcre2_s, s.length(), 0, 0, match_data, NULL);
    }

    if (m_pcje != 0 || rc == PCRE2_ERROR_JIT_STACKLIMIT) {
        rc = pcre2_match(m_pc, pcre2_s, s.length(), 0, PCRE2_NO_JIT, match_data, NULL);
    }
    pcre2_match_data_free(match_data);
    if (rc > 0) {
        return 1; // match
    } else {
        return 0; // no match
    }
#else
    int ovector[OVECCOUNT];
    return pcre_exec(m_pc, m_pce, s.c_str(),
        s.size(), 0, 0, ovector, OVECCOUNT) > 0;
#endif
}

}  // namespace Utils
}  // namespace modsecurity
