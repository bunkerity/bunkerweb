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
#include <string.h>

#ifdef __cplusplus
#include <ctime>
#include <iostream>
#include <string>
#include <vector>
#include <list>
#endif


#ifndef HEADERS_MODSECURITY_RULES_H_
#define HEADERS_MODSECURITY_RULES_H_

#include "modsecurity/rules_properties.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/transaction.h"

#ifdef __cplusplus

namespace modsecurity {
class Rule;
namespace Parser {
class Driver;
}


/** @ingroup ModSecurity_CPP_API */
class Rules : public RulesProperties {
 public:
    Rules()
        : RulesProperties(new DebugLog()),
        unicode_codepage(0),
#ifndef NO_LOGS
        m_secmarker_skipped(0),
#endif
        m_referenceCount(0) { }

    explicit Rules(DebugLog *customLog)
        : RulesProperties(customLog),
        unicode_codepage(0),
#ifndef NO_LOGS
        m_secmarker_skipped(0),
#endif
        m_referenceCount(0) { }

    ~Rules() { }

    void incrementReferenceCount(void);
    void decrementReferenceCount(void);

    int loadFromUri(const char *uri);
    int loadRemote(const char *key, const char *uri);
    int load(const char *rules);
    int load(const char *rules, const std::string &ref);

    void dump();

    int merge(Parser::Driver *driver);
    int merge(Rules *rules);

    int evaluate(int phase, Transaction *transaction);
    std::string getParserError();

    void debug(int level, const std::string &id, const std::string &uri,
        const std::string &msg);

    int64_t unicode_codepage;

 private:
    int m_referenceCount;
#ifndef NO_LOGS
    uint8_t m_secmarker_skipped;
#endif
};

#endif

#ifdef __cplusplus
extern "C" {
#endif

Rules *msc_create_rules_set(void);
void msc_rules_dump(Rules *rules);
int msc_rules_merge(Rules *rules_dst, Rules *rules_from, const char **error);
int msc_rules_add_remote(Rules *rules, const char *key, const char *uri,
    const char **error);
int msc_rules_add_file(Rules *rules, const char *file, const char **error);
int msc_rules_add(Rules *rules, const char *plain_rules, const char **error);
int msc_rules_cleanup(Rules *rules);

#ifdef __cplusplus
}
}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_RULES_H_
