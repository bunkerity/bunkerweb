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

#include "src/parser/driver.h"

#include "modsecurity/rules_set_properties.h"
#include "src/parser/seclang-parser.hh"
#include "modsecurity/audit_log.h"
#include "modsecurity/rule_marker.h"

using modsecurity::audit_log::AuditLog;
using modsecurity::RuleWithOperator;

namespace modsecurity {
namespace Parser {

Driver::Driver()
  : RulesSetProperties(),
  trace_scanning(false),
  trace_parsing(false),
  m_lastRule(nullptr) { }


Driver::~Driver() {

    while (loc.empty() == false) {
        yy::location *a = loc.back();
        loc.pop_back();
        delete a;
    }
}


int Driver::addSecMarker(std::string marker, std::unique_ptr<std::string> fileName, int lineNumber) {
    // FIXME: we might move this to the parser.
    for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
        RuleMarker *r = new RuleMarker(marker, std::unique_ptr<std::string>(new std::string(*fileName)), lineNumber);
        std::unique_ptr<RuleMarker> rule(r);
        rule->setPhase(i);
        m_rulesSetPhases.insert(std::move(rule));
    }
    return 0;
}


int Driver::addSecAction(std::unique_ptr<RuleWithActions> rule) {
    if (rule->getPhase() >= modsecurity::Phases::NUMBER_OF_PHASES) {
        m_parserError << "Unknown phase: " << std::to_string(rule->getPhase());
        m_parserError << std::endl;
        return false;
    }

    m_rulesSetPhases.insert(std::move(rule));

    return true;
}


int Driver::addSecRuleScript(std::unique_ptr<RuleScript> rule) {
    m_rulesSetPhases.insert(std::move(rule));
    return true;
}


int Driver::addSecRule(std::unique_ptr<RuleWithActions> r) {
    if (r->getPhase() >= modsecurity::Phases::NUMBER_OF_PHASES) {
        m_parserError << "Unknown phase: " << std::to_string(r->getPhase());
        m_parserError << std::endl;
        return false;
    }

    /* is it a chained rule? */
    if (m_lastRule != nullptr && m_lastRule->isChained()) {
        r->setPhase(m_lastRule->getPhase());
        if (r->hasDisruptiveAction()) {
            m_parserError << "Disruptive actions can only be specified by";
            m_parserError << " chain starter rules.";
            return false;
        }
        m_lastRule->m_chainedRuleChild = std::move(r);
        m_lastRule->m_chainedRuleChild->m_chainedRuleParent = m_lastRule;
        m_lastRule = m_lastRule->m_chainedRuleChild.get();
        return true;
    }

    std::shared_ptr<RuleWithActions> rule(std::move(r));
    /*
     * Checking if the rule has an ID and also checking if this ID is not used
     * by other rule
     */
    if (rule->m_ruleId == 0) {
        m_parserError << "Rules must have an ID. File: ";
        m_parserError << rule->getFileName() << " at line: ";
        m_parserError << std::to_string(rule->getLineNumber()) << std::endl;
        return false;
    }

    for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
        Rules *rules = m_rulesSetPhases[i];
        for (int j = 0; j < rules->size(); j++) {
            RuleWithOperator *lr = dynamic_cast<RuleWithOperator *>(rules->at(j).get());
            if (lr && lr->m_ruleId == rule->m_ruleId) {
                m_parserError << "Rule id: " << std::to_string(rule->m_ruleId) \
                    << " is duplicated" << std::endl;
                return false;
            }
        }
    }

    m_lastRule = rule.get();
    m_rulesSetPhases.insert(rule);

    return true;
}


int Driver::parse(const std::string &f, const std::string &ref) {
    m_lastRule = nullptr;
    loc.push_back(new yy::location());
    if (ref.empty()) {
        m_filenames.push_back("<<reference missing or not informed>>");
        loc.back()->begin.filename = loc.back()->end.filename = &(m_filenames.back());
    } else {
        m_filenames.push_back(ref);
        loc.back()->begin.filename = loc.back()->end.filename = &(m_filenames.back());
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
     * need to check for rules marked as chained but without
     * a chained rule.
     *
     */
    /*
    if (m_lastRule != nullptr && m_lastRule->isChained()) {
        m_parserError << "Last rule is marked as chained but there " \
            "isn't a subsequent rule." << std::endl;
        return false;
    }
    */

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
