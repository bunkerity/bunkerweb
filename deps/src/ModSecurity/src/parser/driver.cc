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

#include "src/parser/driver.h"

#include "src/parser/seclang-parser.hh"
#include "modsecurity/audit_log.h"
#include "modsecurity/rules_properties.h"

using modsecurity::audit_log::AuditLog;
using modsecurity::Rule;

namespace modsecurity {
namespace Parser {

Driver::Driver()
  : RulesProperties(),
  trace_scanning(false),
  trace_parsing(false),
  lastRule(NULL) { }


Driver::~Driver() {
    while (loc.empty() == false) {
        yy::location *a = loc.back();
        loc.pop_back();
        delete a;
    }
}


int Driver::addSecMarker(std::string marker) {
    for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
        Rule *rule = new Rule(marker);
        rule->m_phase = i;
        m_rules[i].push_back(rule);
    }
    return 0;
}


int Driver::addSecAction(Rule *rule) {
    if (rule->m_phase >= modsecurity::Phases::NUMBER_OF_PHASES) {
        m_parserError << "Unknown phase: " << std::to_string(rule->m_phase);
        m_parserError << std::endl;
        return false;
    }

    m_rules[rule->m_phase].push_back(rule);

    return true;
}


int Driver::addSecRuleScript(RuleScript *rule) {
    m_rules[rule->m_phase].push_back(rule);
    return true;
}


int Driver::addSecRule(Rule *rule) {
    if (rule->m_phase >= modsecurity::Phases::NUMBER_OF_PHASES) {
        m_parserError << "Unknown phase: " << std::to_string(rule->m_phase);
        m_parserError << std::endl;
        return false;
    }

    if (lastRule && lastRule->m_chained) {
        if (lastRule->m_chainedRuleChild == NULL) {
            rule->m_phase = lastRule->m_phase;
            if (rule->m_theDisruptiveAction) {
                m_parserError << "Disruptive actions can only be specified by";
                m_parserError << " chain starter rules.";
                return false;
            }
            lastRule->m_chainedRuleChild = rule;
            rule->m_chainedRuleParent = lastRule;
            return true;
        } else {
            Rule *a = lastRule->m_chainedRuleChild;
            while (a->m_chained && a->m_chainedRuleChild != NULL) {
                a = a->m_chainedRuleChild;
            }
            if (a->m_chained && a->m_chainedRuleChild == NULL) {
                a->m_chainedRuleChild = rule;
                rule->m_chainedRuleParent = a;
                if (a->m_theDisruptiveAction) {
                    m_parserError << "Disruptive actions can only be ";
                    m_parserError << "specified by chain starter rules.";
                    return false;
                }
                return true;
            }
        }
    }


    /*
     * Checking if the rule has an ID and also checking if this ID is not used
     * by other rule
     */
    if (rule->m_ruleId == 0) {
        m_parserError << "Rules must have an ID. File: ";
        m_parserError << rule->m_fileName << " at line: ";
        m_parserError << std::to_string(rule->m_lineNumber) << std::endl;
        return false;
    }
    for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
        std::vector<Rule *> rules = m_rules[i];
        for (int j = 0; j < rules.size(); j++) {
            if (rules[j]->m_ruleId == rule->m_ruleId) {
                m_parserError << "Rule id: " << std::to_string(rule->m_ruleId) \
                    << " is duplicated" << std::endl;
                return false;
            }
        }
    }

    lastRule = rule;
    m_rules[rule->m_phase].push_back(rule);
    return true;
}


int Driver::parse(const std::string &f, const std::string &ref) {
    lastRule = NULL;
    loc.push_back(new yy::location());
    if (ref.empty()) {
        loc.back()->begin.filename = loc.back()->end.filename = new std::string("<<reference missing or not informed>>");
    } else {
        loc.back()->begin.filename = loc.back()->end.filename = new std::string(ref);
    }

    if (f.empty()) {
        return 1;
    }

    buffer = f;
    scan_begin();
    yy::seclang_parser parser(*this);
    parser.set_debug_level(trace_parsing);
    int res = parser.parse();
    scan_end();

    /*
    if (m_auditLog->init(&error) == false) {
        m_parserError << "Problems while initializing the audit logs: " \
            << error << std::endl;
        return false;
    }
    */

    return res == 0;
}


int Driver::parseFile(const std::string &f) {
    std::ifstream t(f);
    std::string str;

    if (utils::isFile(f) == false) {
        m_parserError << "Failed to open the file: " << f << std::endl;
        return false;
    }

    t.seekg(0, std::ios::end);
    str.reserve(t.tellg());
    t.seekg(0, std::ios::beg);

    str.assign((std::istreambuf_iterator<char>(t)),
        std::istreambuf_iterator<char>());

    return parse(str, f);
}


void Driver::error(const yy::location& l, const std::string& m) {
    error(l, m, "");
}


void Driver::error(const yy::location& l, const std::string& m,
    const std::string& c) {
    if (m_parserError.tellp() == 0) {
        m_parserError << "Rules error. ";
        m_parserError << "File: " << *l.end.filename << ". ";
        m_parserError << "Line: " << l.end.line << ". ";
        m_parserError << "Column: " << l.end.column - 1 << ". ";
    }

    if (m.empty() == false) {
        m_parserError << "" << m << " ";
    }

    if (c.empty() == false) {
        m_parserError << c;
    }
}


}  // namespace Parser
}  // namespace modsecurity
