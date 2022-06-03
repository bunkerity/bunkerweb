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


#ifdef __cplusplus
#include <ctime>
#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <set>
#include <cstring>
#endif


#ifndef HEADERS_MODSECURITY_RULES_PROPERTIES_H_
#define HEADERS_MODSECURITY_RULES_PROPERTIES_H_


#include "modsecurity/modsecurity.h"
#include "modsecurity/rule.h"
#include "modsecurity/rules_exceptions.h"
#include "modsecurity/actions/action.h"
#include "modsecurity/audit_log.h"

#define CODEPAGE_SEPARATORS  " \t\n\r"

#define merge_boolean_value(to, from, default)                               \
    if (to == PropertyNotSetConfigBoolean) {                                 \
        to = (from == PropertyNotSetConfigBoolean) ? default : from;         \
    }

#define merge_ruleengine_value(to, from, default)                            \
    if (to == PropertyNotSetRuleEngine) {                                    \
        to = (from == PropertyNotSetRuleEngine) ? default : from;            \
    }

#define merge_bodylimitaction_value(to, from, default)                       \
    if (to == PropertyNotSetBodyLimitAction) {                               \
        to = (from == PropertyNotSetBodyLimitAction) ? default : from;       \
    }

#ifdef __cplusplus

namespace modsecurity {
class RulesExceptions;
namespace Parser {
class Driver;
}

using modsecurity::debug_log::DebugLog;
using modsecurity::audit_log::AuditLog;

/** @ingroup ModSecurity_CPP_API */
class ConfigInt {
 public:
    ConfigInt() : m_set(false), m_value(0) { }
    bool m_set;
    int m_value;

    void merge(ConfigInt *from) {
        if (m_set == true || from->m_set == false) {
            return;
        }
        m_set = true;
        m_value = from->m_value;
        return;
    }
};


class ConfigDouble {
 public:
    ConfigDouble() : m_set(false), m_value(0) { }
    bool m_set;
    double m_value;

    void merge(ConfigDouble *from) {
        if (m_set == true || from->m_set == false) {
            return;
        }
        m_set = true;
        m_value = from->m_value;
        return;
    }
};


class ConfigString {
 public:
    ConfigString() : m_set(false), m_value("") { }
    bool m_set;
    std::string m_value;

    void merge(ConfigString *from) {
        if (m_set == true || from->m_set == false) {
            return;
        }
        m_set = true;
        m_value = from->m_value;
        return;
    }
};


class ConfigSet {
 public:
    ConfigSet() : m_set(false), m_clear(false) { }
    bool m_set;
    bool m_clear;
    std::set<std::string> m_value;
};


class UnicodeMapHolder {
 public:
    UnicodeMapHolder() {
        memset(m_data, -1, (sizeof(int)*65536));
    };

    int& operator[](int index) { return m_data[index]; }
    int operator[](int index) const { return m_data[index]; }

    int at(int index) const { return m_data[index]; }
    void change(int i, int a) { m_data[i] = a; }

    int m_data[65536];
};


class RulesProperties;
class ConfigUnicodeMap {
 public:
    ConfigUnicodeMap() : m_set(false),
        m_unicodeCodePage(0),
        m_unicodeMapTable(NULL) { }

    static void loadConfig(std::string f, double codePage,
        RulesProperties *driver, std::string *errg);

    void merge(ConfigUnicodeMap *from) {
        if (from->m_set == false) {
            return;
        }

        m_set = true;
        m_unicodeCodePage = from->m_unicodeCodePage;
        m_unicodeMapTable = from->m_unicodeMapTable;

        return;
    }

    bool m_set;
    double m_unicodeCodePage;
    std::shared_ptr<modsecurity::UnicodeMapHolder> m_unicodeMapTable;
};


class RulesProperties {
 public:
    RulesProperties() :
        m_auditLog(new AuditLog()),
        m_requestBodyLimitAction(PropertyNotSetBodyLimitAction),
        m_responseBodyLimitAction(PropertyNotSetBodyLimitAction),
        m_secRequestBodyAccess(PropertyNotSetConfigBoolean),
        m_secResponseBodyAccess(PropertyNotSetConfigBoolean),
        m_secXMLExternalEntity(PropertyNotSetConfigBoolean),
        m_tmpSaveUploadedFiles(PropertyNotSetConfigBoolean),
        m_uploadKeepFiles(PropertyNotSetConfigBoolean),
        m_debugLog(new DebugLog()),
        m_remoteRulesActionOnFailed(PropertyNotSetRemoteRulesAction),
        m_secRuleEngine(PropertyNotSetRuleEngine) { }


    explicit RulesProperties(DebugLog *debugLog) :
        m_auditLog(new AuditLog()),
        m_requestBodyLimitAction(PropertyNotSetBodyLimitAction),
        m_responseBodyLimitAction(PropertyNotSetBodyLimitAction),
        m_secRequestBodyAccess(PropertyNotSetConfigBoolean),
        m_secResponseBodyAccess(PropertyNotSetConfigBoolean),
        m_secXMLExternalEntity(PropertyNotSetConfigBoolean),
        m_tmpSaveUploadedFiles(PropertyNotSetConfigBoolean),
        m_uploadKeepFiles(PropertyNotSetConfigBoolean),
        m_debugLog(debugLog),
        m_remoteRulesActionOnFailed(PropertyNotSetRemoteRulesAction),
        m_secRuleEngine(PropertyNotSetRuleEngine) { }


    ~RulesProperties() {
        int i = 0;
        /** Cleanup the rules */
        for (i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
            std::vector<Rule *> rules = m_rules[i];
            while (rules.empty() == false) {
                Rule *rule = rules.back();
                rules.pop_back();
                if (rule->refCountDecreaseAndCheck()) {
                    rule = NULL;
                }
            }
        }
        for (i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
            std::vector<actions::Action *> *tmp = &m_defaultActions[i];
            while (tmp->empty() == false) {
                actions::Action *a = tmp->back();
                tmp->pop_back();
                if (a->refCountDecreaseAndCheck()) {
                    a = NULL;
                }
            }
        }

        delete m_debugLog;
        delete m_auditLog;
    }


    /**
     *
     *
     */
    enum ConfigBoolean {
        TrueConfigBoolean,
        FalseConfigBoolean,
        PropertyNotSetConfigBoolean
    };


    /**
     *
     * The RuleEngine enumerator consists in mapping the different states
     * of the rule engine.
     *
     */
    enum RuleEngine {
     /**
      *
      * Rules won't be evaluated if Rule Engine is set to DisabledRuleEngine
      *
      */
     DisabledRuleEngine,
     /**
      *
      * Rules will be evaluated and disturb actions will take place if needed.
      *
      */
     EnabledRuleEngine,
     /**
      * Rules will be evaluated but it won't generate any disruptive action.
      *
      */
     DetectionOnlyRuleEngine,
     /**
      *
      */
     PropertyNotSetRuleEngine
    };


    /**
     *
     * Defines what actions should be taken in case the body (response or
     * request) is bigger than the expected size.
     *
     */
    enum BodyLimitAction {
     /**
      *
      * Process partial
      *
      */
     ProcessPartialBodyLimitAction,
     /**
      *
      * Reject the request
      *
      */
     RejectBodyLimitAction,
     /**
      *
      */
     PropertyNotSetBodyLimitAction
    };


    /**
     *
     * Defines what actions should be taken in case the remote rules failed to
     * be downloaded (independent of the circumstances)
     *
     *
     */
    enum OnFailedRemoteRulesAction {
     /**
      *
      * Abort
      *
      */
     AbortOnFailedRemoteRulesAction,
     /**
      *
      * Warn on logging
      *
      */
     WarnOnFailedRemoteRulesAction,
     /**
      *
      */
     PropertyNotSetRemoteRulesAction
    };


    static const char *ruleEngineStateString(RuleEngine i) {
        switch (i) {
        case DisabledRuleEngine:
            return "Disabled";
        case EnabledRuleEngine:
            return "Enabled";
        case DetectionOnlyRuleEngine:
            return "DetectionOnly";
        case PropertyNotSetRuleEngine:
            return "PropertyNotSet/DetectionOnly";
        }
        return NULL;
    }


    static std::string configBooleanString(ConfigBoolean i) {
        switch (i) {
        case TrueConfigBoolean:
            return "True";
        case FalseConfigBoolean:
            return "False";
        case PropertyNotSetConfigBoolean:
            return "Not set";
        }
        return NULL;
    }


    static int mergeProperties(RulesProperties *from, RulesProperties *to,
        std::ostringstream *err) {
        int amount_of_rules = 0;

        amount_of_rules = appendRules(from->m_rules, to->m_rules, err);
        if (amount_of_rules < 0) {
            return amount_of_rules;
        }

        merge_ruleengine_value(to->m_secRuleEngine, from->m_secRuleEngine,
                               PropertyNotSetRuleEngine);

        merge_boolean_value(to->m_secRequestBodyAccess,
                            from->m_secRequestBodyAccess,
                            PropertyNotSetConfigBoolean);

        merge_boolean_value(to->m_secResponseBodyAccess,
                            from->m_secResponseBodyAccess,
                            PropertyNotSetConfigBoolean);

        merge_boolean_value(to->m_secXMLExternalEntity,
                            from->m_secXMLExternalEntity,
                            PropertyNotSetConfigBoolean);

        merge_boolean_value(to->m_uploadKeepFiles,
                            from->m_uploadKeepFiles,
                            PropertyNotSetConfigBoolean);

        merge_boolean_value(to->m_tmpSaveUploadedFiles,
                            from->m_tmpSaveUploadedFiles,
                            PropertyNotSetConfigBoolean);

        to->m_requestBodyLimit.merge(&from->m_requestBodyLimit);
        to->m_responseBodyLimit.merge(&from->m_responseBodyLimit);

        merge_bodylimitaction_value(to->m_requestBodyLimitAction,
                                    from->m_requestBodyLimitAction,
                                    PropertyNotSetBodyLimitAction);

        merge_bodylimitaction_value(to->m_responseBodyLimitAction,
                                    from->m_responseBodyLimitAction,
                                    PropertyNotSetBodyLimitAction);

        to->m_uploadFileLimit.merge(&from->m_uploadFileLimit);
        to->m_uploadFileMode.merge(&from->m_uploadFileMode);
        to->m_uploadDirectory.merge(&from->m_uploadDirectory);
        to->m_uploadTmpDirectory.merge(&from->m_uploadTmpDirectory);

        to->m_secArgumentSeparator.merge(&from->m_secArgumentSeparator);

        to->m_secWebAppId.merge(&from->m_secWebAppId);

        to->m_unicodeMapTable.merge(&from->m_unicodeMapTable);

        to->m_httpblKey.merge(&from->m_httpblKey);

        to->m_exceptions.merge(&from->m_exceptions);

        to->m_components.insert(to->m_components.end(),
            from->m_components.begin(), from->m_components.end());

        if (from->m_responseBodyTypeToBeInspected.m_set == true) {
            if (from->m_responseBodyTypeToBeInspected.m_clear == true) {
                to->m_responseBodyTypeToBeInspected.m_value.clear();
                from->m_responseBodyTypeToBeInspected.m_value.clear();
            } else {
                for (std::set<std::string>::iterator
                    it = from->m_responseBodyTypeToBeInspected.m_value.begin();
                    it != from->m_responseBodyTypeToBeInspected.m_value.end();
                    ++it) {
                    to->m_responseBodyTypeToBeInspected.m_value.insert(*it);
                }
            }
            to->m_responseBodyTypeToBeInspected.m_set = true;
        }

        for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
            std::vector<actions::Action *> *actions_from = \
                from->m_defaultActions+i;
            std::vector<actions::Action *> *actions_to = to->m_defaultActions+i;
            for (size_t j = 0; j < actions_from->size(); j++) {
                actions::Action *action = actions_from->at(j);
                action->refCountIncrease();
                actions_to->push_back(action);
            }
        }

        if (to->m_auditLog) {
            std::string error;
            to->m_auditLog->merge(from->m_auditLog, &error);
            if (error.size() > 0) {
                *err << error;
                return -1;
            }
        }

        if (from->m_debugLog && to->m_debugLog &&
            from->m_debugLog->isLogFileSet()) {
            if (to->m_debugLog->isLogFileSet() == false) {
                std::string error;
                to->m_debugLog->setDebugLogFile(
                    from->m_debugLog->getDebugLogFile(),
                    &error);
                if (error.size() > 0) {
                    *err << error;
                    return -1;
                }
            }
        }

        if (from->m_debugLog && to->m_debugLog &&
            from->m_debugLog->isLogLevelSet()) {
            if (to->m_debugLog->isLogLevelSet() == false) {
                to->m_debugLog->setDebugLogLevel(
                    from->m_debugLog->getDebugLogLevel());
            }
        }

        return amount_of_rules;
    }


    static int appendRules(
        std::vector<modsecurity::Rule *> *from,
        std::vector<modsecurity::Rule *> *to,
        std::ostringstream *err) {
        int amount_of_rules = 0;
        // TODO: std::vector could be replaced with something more efficient.
        std::vector<int64_t> v;
        for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
            std::vector<modsecurity::Rule *> *rules_to = to+i;
            v.reserve(rules_to->size());
            for (size_t z = 0; z < rules_to->size(); z++) {
                Rule *rule_ckc = rules_to->at(z);
                if (rule_ckc->m_secMarker == true) {
                    continue;
                }
                v.push_back(rule_ckc->m_ruleId);
            }
        }
        std::sort (v.begin(), v.end());

        for (int i = 0; i < modsecurity::Phases::NUMBER_OF_PHASES; i++) {
            std::vector<modsecurity::Rule *> *rules_from = from+i;
            std::vector<modsecurity::Rule *> *rules_to = to+i;
            for (size_t j = 0; j < rules_from->size(); j++) {
                Rule *rule = rules_from->at(j);
                if (std::binary_search(v.begin(), v.end(), rule->m_ruleId)) {
                    if (err != NULL) {
                        *err << "Rule id: " << std::to_string(rule->m_ruleId) \
                            << " is duplicated" << std::endl;
                    }
                    return -1;
                }
                amount_of_rules++;
                rule->refCountIncrease();
                rules_to->push_back(rule);
            }
        }
        return amount_of_rules;
    }


    std::vector<modsecurity::Rule *> *getRulesForPhase(int phase) {
        if (phase >= modsecurity::Phases::NUMBER_OF_PHASES) {
            return NULL;
        }
        return &m_rules[phase];
    }


    audit_log::AuditLog *m_auditLog;
    BodyLimitAction m_requestBodyLimitAction;
    BodyLimitAction m_responseBodyLimitAction;
    ConfigBoolean m_secRequestBodyAccess;
    ConfigBoolean m_secResponseBodyAccess;
    ConfigBoolean m_secXMLExternalEntity;
    ConfigBoolean m_tmpSaveUploadedFiles;
    ConfigBoolean m_uploadKeepFiles;
    ConfigDouble m_requestBodyLimit;
    ConfigDouble m_requestBodyNoFilesLimit;
    ConfigDouble m_responseBodyLimit;
    ConfigInt m_uploadFileLimit;
    ConfigInt m_uploadFileMode;
    DebugLog *m_debugLog;
    OnFailedRemoteRulesAction m_remoteRulesActionOnFailed;
    RuleEngine m_secRuleEngine;
    RulesExceptions m_exceptions;
    std::list<std::string> m_components;
    std::ostringstream m_parserError;
    ConfigSet m_responseBodyTypeToBeInspected;
    ConfigString m_httpblKey;
    ConfigString m_uploadDirectory;
    ConfigString m_uploadTmpDirectory;
    ConfigString m_secArgumentSeparator;
    ConfigString m_secWebAppId;
    std::vector<actions::Action *> m_defaultActions[modsecurity::Phases::NUMBER_OF_PHASES];
    std::vector<modsecurity::Rule *> m_rules[modsecurity::Phases::NUMBER_OF_PHASES];
    ConfigUnicodeMap m_unicodeMapTable;
};


#endif

#ifdef __cplusplus
}  // namespace modsecurity
#endif

#endif  // HEADERS_MODSECURITY_RULES_PROPERTIES_H_
