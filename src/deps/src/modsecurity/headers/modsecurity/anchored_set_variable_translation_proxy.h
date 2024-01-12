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


#ifdef __cplusplus
#include <string>
#include <algorithm>
#include <memory>
#include <functional>
#include <iostream>
#endif

#include "modsecurity/variable_value.h"
#include "modsecurity/anchored_set_variable.h"


#ifndef HEADERS_MODSECURITY_ANCHORED_SET_VARIABLE_TRANSLATION_PROXY_H_
#define HEADERS_MODSECURITY_ANCHORED_SET_VARIABLE_TRANSLATION_PROXY_H_

#ifdef __cplusplus

namespace modsecurity {


class AnchoredSetVariableTranslationProxy {
 public:
    AnchoredSetVariableTranslationProxy(
        const std::string &name,
        AnchoredSetVariable *fount)
        : m_name(name),
        m_fount(fount)
    {
        m_translate = [](std::string *name, std::vector<const VariableValue *> *l) {
            for (int i = 0; i < l->size(); ++i) {
                VariableValue *newVariableValue = new VariableValue(name, &l->at(i)->getKey(), &l->at(i)->getKey());
                const VariableValue *oldVariableValue = l->at(i);
                l->at(i) = newVariableValue;
                for (const auto &oldOrigin : oldVariableValue->getOrigin()) {
                    std::unique_ptr<VariableOrigin> newOrigin(new VariableOrigin);
                    newOrigin->m_length = oldVariableValue->getKey().size();
                    newOrigin->m_offset = oldOrigin->m_offset - oldVariableValue->getKey().size() - 1;
                    newVariableValue->addOrigin(std::move(newOrigin));
                }
                delete oldVariableValue;
            }
        };
    }

    virtual ~AnchoredSetVariableTranslationProxy()
    { }

    void resolve(std::vector<const VariableValue *> *l) {
        m_fount->resolve(l);
        m_translate(&m_name, l);
    }

    void resolve(std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) {
        m_fount->resolve(l, ke);
        m_translate(&m_name, l);
    }

    void resolve(const std::string &key,
        std::vector<const VariableValue *> *l) {
        m_fount->resolve(key, l);
        m_translate(&m_name, l);
    };

    void resolveRegularExpression(Utils::Regex *r,
        std::vector<const VariableValue *> *l) {
        m_fount->resolveRegularExpression(r, l);
        m_translate(&m_name, l);
    };

    void resolveRegularExpression(Utils::Regex *r,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke) {
        m_fount->resolveRegularExpression(r, l, ke);
        m_translate(&m_name, l);
    };

    std::unique_ptr<std::string> resolveFirst(const std::string &key) {
        std::vector<const VariableValue *> l;
        resolve(&l);

        if (l.empty()) {
            return nullptr;
        }

        std::unique_ptr<std::string> ret(new std::string(""));

        ret->assign(l.at(0)->getValue());

        while (!l.empty()) {
            auto &a = l.back();
            l.pop_back();
            delete a;
        }

        return ret;
    }

    std::string m_name;
 private:
    AnchoredSetVariable *m_fount;
    std::function<void(std::string *name, std::vector<const VariableValue *> *l)> m_translate;
};

}  // namespace modsecurity

#endif


#endif  // HEADERS_MODSECURITY_ANCHORED_SET_VARIABLE_TRANSLATION_PROXY_H_
