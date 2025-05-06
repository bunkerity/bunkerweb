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

#include <stdio.h>
#include <string.h>

#ifdef __cplusplus
#include <ctime>
#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <cstdint>
#endif


#ifndef HEADERS_MODSECURITY_RULES_SET_H_
#define HEADERS_MODSECURITY_RULES_SET_H_

#include "modsecurity/rules_set_properties.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rules_set_phases.h"

#ifdef __cplusplus

namespace modsecurity {
class RuleWithOperator;
namespace Parser {
class Driver;
}



/** @ingroup ModSecurity_CPP_API */
class RulesSet : public RulesSetProperties {
 public:
    RulesSet()
        : RulesSetProperties(new DebugLog())
#ifndef NO_LOGS
        ,m_secmarker_skipped(0)
#endif
        { }

    explicit RulesSet(DebugLog *customLog)
        : RulesSetProperties(customLog)
#ifndef NO_LOGS
        ,m_secmarker_skipped(0)
#endif
        { }

    ~RulesSet() { }

    int loadFromUri(const char *uri);
    int loadRemote(const char *key, const char *uri);
    int load(const char *rules);
    int load(const char *rules, const std::string &ref);

    void dump() const;

    int merge(Parser::Driver *driver);
    int merge(RulesSet *rules);

    int evaluate(int phase, Transaction *transaction);
    std::string getParserError();

    void debug(int level, const std::string &id, const std::string &uri,
        const std::string &msg);

    RulesSetPhases m_rulesSetPhases;
 private:
#ifndef NO_LOGS
    uint8_t m_secmarker_skipped;
#endif
};

#endif

#ifdef __cplusplus
extern "C" {
#endif

RulesSet *msc_create_rules_set(void);
void msc_rules_dump(const RulesSet *rules);
int msc_rules_merge(RulesSet *rules_dst, RulesSet *rules_from, const char **error);
int msc_rules_add_remote(RulesSet *rules, const char *key, const char *uri,
    const char **error);
int msc_rules_add_file(RulesSet *rules, const char *file, const char **error);
int msc_rules_add(RulesSet *rules, const char *plain_rules, const char **error);
void msc_rules_error_cleanup(const char *error);
int msc_rules_cleanup(RulesSet *rules);

#ifdef __cplusplus
}
}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_RULES_SET_H_
