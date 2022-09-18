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

#ifdef __cplusplus
#include <string>
#include <map>
#include <stack>
#include <vector>
#include <list>
#endif


#ifndef SRC_PARSER_DRIVER_H_
#define SRC_PARSER_DRIVER_H_

#include "modsecurity/modsecurity.h"
#include "modsecurity/rules_set.h"
#include "modsecurity/rules_set_properties.h"
#include "modsecurity/audit_log.h"
#include "src/rule_script.h"
#ifndef MS_CPPCHECK_DISABLED_FOR_PARSER
#include "src/parser/seclang-parser.hh"
#endif

using modsecurity::RuleWithOperator;
using modsecurity::RulesSet;


# define YY_DECL \
  yy::seclang_parser::symbol_type yylex(modsecurity::Parser::Driver& driver)

YY_DECL;

namespace modsecurity {
namespace Parser {

#ifdef __cplusplus
class Driver;
#else
typedef struct Driver_t Driver;
#endif


/**
 *
 * FIXME: There is a memory leak in the filename at yy::location.
 *        The filename should be converted into a shared string to
 *        save memory or be associated with the life cycle of the
 *        driver class.
 *
 **/
class Driver : public RulesSetProperties {
 public:
    Driver();
    virtual ~Driver();

    int addSecRule(std::unique_ptr<RuleWithActions> rule);
    int addSecAction(std::unique_ptr<RuleWithActions> rule);
    int addSecMarker(std::string marker, std::unique_ptr<std::string> fileName, int lineNumber);
    int addSecRuleScript(std::unique_ptr<RuleScript> rule);

    bool scan_begin();
    void scan_end();
    bool trace_scanning;

    int parseFile(const std::string& f);
    int parse(const std::string& f, const std::string &ref);

    std::string file;

    bool trace_parsing;

    void error(const yy::location& l, const std::string& m);
    void error(const yy::location& l, const std::string& m,
        const std::string& c);

    std::list<yy::location *> loc;

    std::string buffer;
    RuleWithActions *m_lastRule;

    RulesSetPhases m_rulesSetPhases;
};


}  // namespace Parser
}  // namespace modsecurity

#endif  // SRC_PARSER_DRIVER_H_
