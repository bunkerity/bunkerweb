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

#include "src/operators/verify_cpf.h"

#include <string>
#include <list>

#include "src/operators/operator.h"

namespace modsecurity {
namespace operators {

int VerifyCPF::convert_to_int(const char c) {
    int n;
    if ((c >= '0') && (c <= '9')) {
        n = c - '0';
    } else if ((c >= 'A') && (c <= 'F')) {
        n = c - 'A' + 10;
    } else if ((c >= 'a') && (c <= 'f')) {
        n = c - 'a' + 10;
    } else {
        n = 0;
    }
    return n;
}

bool VerifyCPF::verify(const char *cpfnumber, int len) {
    int factor, part_1, part_2, var_len = len;
    unsigned int sum = 0, i = 0, cpf_len = 11, c;
    int cpf[11];
    char s_cpf[11];
    char bad_cpf[12][12] = { "00000000000",
        "01234567890",
        "11111111111",
        "22222222222",
        "33333333333",
        "44444444444",
        "55555555555",
        "66666666666",
        "77777777777",
        "88888888888",
        "99999999999"};

    while ((*cpfnumber != '\0') && (var_len > 0)) {
        if (*cpfnumber != '-' || *cpfnumber != '.') {
            if (i < cpf_len && isdigit(*cpfnumber)) {
                s_cpf[i] = *cpfnumber;
                cpf[i] = convert_to_int(*cpfnumber);
                i++;
            }
        }
        cpfnumber++;
        var_len--;
    }


    if (i != cpf_len) {
        return 0;
    } else {
        for (i = 0; i< cpf_len; i++) {
            if (strncmp(s_cpf, bad_cpf[i], cpf_len) == 0) {
                return 0;
            }
        }
    }

    part_1 = convert_to_int(s_cpf[cpf_len-2]);
    part_2 = convert_to_int(s_cpf[cpf_len-1]);

    c = cpf_len;

    for (i = 0; i < 9; i++) {
        sum += (cpf[i] * --c);
    }

    factor = (sum % cpf_len);

    if (factor < 2) {
        cpf[9] = 0;
    } else {
        cpf[9] = cpf_len-factor;
    }

    sum = 0;
    c = cpf_len;

    for (i = 0; i < 10; i++) {
        sum += (cpf[i] * c--);
    }

    factor = (sum % cpf_len);

    if (factor < 2) {
        cpf[10] = 0;
    } else {
        cpf[10] = cpf_len-factor;
    }

    if (part_1 == cpf[9] && part_2 == cpf[10]) {
        return true;
    }

    return false;
}


bool VerifyCPF::evaluate(Transaction *t, Rule *rule,
    const std::string& input, std::shared_ptr<RuleMessage> ruleMessage) {
    std::list<SMatch> matches;
    bool is_cpf = false;
    int i;

    if (m_param.empty()) {
        return false;
    }

    for (i = 0; i < input.size() - 1 && is_cpf == false; i++) {
        matches = m_re->searchAll(input.substr(i, input.size()));
        for (const auto & i : matches) {
            is_cpf = verify(i.str().c_str(), i.str().size());
            if (is_cpf) {
                logOffset(ruleMessage, i.offset(), i.str().size());
                if (rule && t && rule->m_containsCaptureAction) {
                    t->m_collections.m_tx_collection->storeOrUpdateFirst(
                        "0", i.str());
                    ms_dbg_a(t, 7, "Added VerifyCPF match TX.0: " + \
                        i.str());
                }

                goto out;
            }
        }
    }

out:
    return is_cpf;
}


}  // namespace operators
}  // namespace modsecurity
