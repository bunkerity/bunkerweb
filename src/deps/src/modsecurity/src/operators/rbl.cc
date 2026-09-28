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

#include "src/operators/rbl.h"

#include <sys/types.h>
#ifndef WIN32
#include <sys/socket.h>
#include <netdb.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#else
#include <WinSock2.h>
#include <WS2tcpip.h>
#endif

#include <string>

#include "modsecurity/rules_set.h"
#include "src/operators/operator.h"

namespace modsecurity {
namespace operators {


std::string Rbl::mapIpToAddress(const std::string &ipStr, Transaction *trans) const {
    std::string addr;
    int h0, h1, h2, h3;
    std::string key;
    if (trans && trans->m_rules->m_httpblKey.m_set == true) {
        key = trans->m_rules->m_httpblKey.m_value;
    }

    if (sscanf(ipStr.c_str(), "%d.%d.%d.%d", &h0, &h1, &h2, &h3) != 4) {
        ms_dbg_a(trans, 0, std::string("Failed to understand `" + ipStr +
            "' as a valid IP address, assuming domain format input"));

        addr = ipStr + "." + m_service;
        return addr;
    }

    if (m_demandsPassword && key.empty()) {
        ms_dbg_a(trans, 0, std::string("Missing RBL key, cannot continue " \
            "with the operator execution, please set the key using: " \
            "SecHttpBlKey"));
        return addr;
    }

    addr = std::to_string(h3) + "." +
        std::to_string(h2) + "." +
        std::to_string(h1) + "." +
        std::to_string(h0) + "." +
        m_service;

    if (m_demandsPassword) {
        addr = key + "." + addr;
    }

    return addr;
}


void Rbl::futherInfo_httpbl(struct sockaddr_in *sin, const std::string &ipStr,
    const Transaction *trans) {
    const char *respBl;
    int first, days, score, type;
#ifndef NO_LOGS
    std::string ptype;
#endif

    respBl = inet_ntoa(sin->sin_addr);

    if (sscanf(respBl, "%d.%d.%d.%d", &first, &days, &score, &type) != 4) {
        ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " failed: bad response");
        return;
    }

    if (first != 127) {
        ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " failed: bad response");
        return;
    }

#ifndef NO_LOGS
    switch (type) {
        case 0:
            ptype = "Search Engine";
            break;
        case 1:
            ptype = "Suspicious IP";
            break;
        case 2:
            ptype = "Harvester IP";
            break;
        case 3:
            ptype = "Suspicious harvester IP";
            break;
        case 4:
            ptype = "Comment spammer IP";
            break;
        case 5:
            ptype = "Suspicious comment spammer IP";
            break;
        case 6:
            ptype = "Harvester and comment spammer IP";
            break;
        case 7:
            ptype = "Suspicious harvester comment spammer IP";
            break;
        default:
            ptype = " ";
    }
#endif

    ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded. %s: " \
        + std::to_string(days) + " " \
        "days since last activity, threat score " \
        + std::to_string(score) +  ". Case: " + ptype);
}


void Rbl::futherInfo_spamhaus(unsigned int high8bits, const std::string &ipStr,
    const Transaction *trans) {
    switch (high8bits) {
        case 2:
        case 3:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded " \
                "(Static UBE sources).");
            break;
        case 4:
        case 5:
        case 6:
        case 7:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded " \
                "(Illegal 3rd party exploits).");
            break;
        case 10:
        case 11:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded " \
                "(Delivering unauthenticated SMTP email).");
            break;
        default:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded ");
            break;
    }
}


void Rbl::futherInfo_uribl(unsigned int high8bits, const std::string &ipStr,
    const Transaction *trans) {
    switch (high8bits) {
        case 2:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded (BLACK).");
        break;
        case 4:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded (GREY).");
            break;
        case 8:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded (RED).");
            break;
        case 14:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded " \
                "(BLACK,GREY,RED).");
            break;
        case 255:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded " \
                "(DNS IS BLOCKED).");
            break;
        default:
            ms_dbg_a(trans, 4, "RBL lookup of " + ipStr + " succeeded (WHITE).");
            break;
    }
}


void Rbl::furtherInfo(struct sockaddr_in *sin, const std::string &ipStr,
    const Transaction *trans, RblProvider provider) {
    unsigned int high8bits = sin->sin_addr.s_addr >> 24;

    switch (provider) {
        case RblProvider::UnknownProvider:
            ms_dbg_a(trans, 2, "RBL lookup of " + ipStr + " succeeded.");
            break;
        case RblProvider::httpbl:
            futherInfo_httpbl(sin, ipStr, trans);
            break;
        case RblProvider::uribl:
            futherInfo_uribl(high8bits, ipStr, trans);
            break;
        case RblProvider::spamhaus:
            futherInfo_spamhaus(high8bits, ipStr, trans);
            break;
    }
}


bool Rbl::evaluate(Transaction *t, RuleWithActions *rule,
        const std::string& ipStr,
        RuleMessage &ruleMessage) {
    struct addrinfo *info = NULL;
    std::string host = Rbl::mapIpToAddress(ipStr, t);
    int rc = 0;

    if (host.empty()) {
        return false;
    }

    rc = getaddrinfo(host.c_str(), NULL, NULL, &info);

    if (rc != 0) {
        if (info != NULL) {
            freeaddrinfo(info);
        }
        ms_dbg_a(t, 5, "RBL lookup of " + ipStr + " failed.");
        return false;
    }

    // SonarCloud suggested to use the init-statement to declare "addr" inside the if statement.
    // I think that's not good here, because we need that in the else block
    const struct sockaddr *addr = info->ai_addr;  // NOSONAR
    if (addr->sa_family == AF_INET) {  // NOSONAR
        struct sockaddr_in sin{};  // initialize an empty struct; we don't need port info
        memcpy(&sin.sin_addr, addr->sa_data + 2, sizeof(sin.sin_addr));
        sin.sin_family = AF_INET;
        furtherInfo(&sin, ipStr, t, m_provider);
    }
    else {
        ms_dbg_a(t, 7,  "Unsupported address family: " + std::to_string(addr->sa_family));
        freeaddrinfo(info);
        return false;
    }

    freeaddrinfo(info);
    if (rule && t && rule->hasCaptureAction()) {
        t->m_collections.m_tx_collection->storeOrUpdateFirst(
        "0", std::string(ipStr));
        ms_dbg_a(t, 7, "Added RXL match TX.0: " + \
            std::string(ipStr));
    }

    return true;
}


}  // namespace operators
}  // namespace modsecurity
