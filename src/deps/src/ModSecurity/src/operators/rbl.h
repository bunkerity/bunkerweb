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

#ifndef SRC_OPERATORS_RBL_H_
#define SRC_OPERATORS_RBL_H_

#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#include <string>
#include <memory>
#include <utility>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

class Rbl : public Operator {
 public:
    /**
     *
     */
    enum RblProvider {
        /**
         * UnknownProvider
         *
         */
        UnknownProvider,
        /**
         * httpbl.org
         *
         */
        httpbl,
        /**
         * uribl.com
         *
         */
        uribl,
        /**
         * spamhaus.org
         *
         */
        spamhaus,
    };

    /** @ingroup ModSecurity_Operator */
    explicit Rbl(std::unique_ptr<RunTimeString> param)
        : Operator("Rbl", std::move(param)),
        m_demandsPassword(false) {
            m_service = m_string->evaluate();
            m_provider = RblProvider::UnknownProvider;
            if (m_service.find("httpbl.org") != std::string::npos) {
                m_demandsPassword = true;
                m_provider = RblProvider::httpbl;
            } else if (m_service.find("uribl.com") != std::string::npos) {
                m_provider = RblProvider::httpbl;
            } else if (m_service.find("spamhaus.org") != std::string::npos) {
                m_provider = RblProvider::httpbl;
            }
        }
    bool evaluate(Transaction *transaction, Rule *rule,
        const std::string& input,
        std::shared_ptr<RuleMessage> ruleMessage) override;

    std::string mapIpToAddress(std::string ipStr, Transaction *trans);

    void futherInfo_httpbl(struct sockaddr_in *sin, std::string ipStr,
        Transaction *trans);
    void futherInfo_spamhaus(unsigned int high8bits, std::string ipStr,
        Transaction *trans);
    void futherInfo_uribl(unsigned int high8bits, std::string ipStr,
        Transaction *trans);
    void furtherInfo(struct sockaddr_in *sin, std::string ipStr,
        Transaction *trans);

    std::string m_service;
    bool m_demandsPassword;
    RblProvider m_provider;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_RBL_H_
