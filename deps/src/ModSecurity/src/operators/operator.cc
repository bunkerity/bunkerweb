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

#include "src/operators/operator.h"

#include <cstring>
#include <memory>
#include <string>

#include "modsecurity/transaction.h"
#include "src/run_time_string.h"
#include "src/utils/string.h"
#include "src/operators/begins_with.h"
#include "src/operators/contains.h"
#include "src/operators/contains_word.h"
#include "src/operators/detect_sqli.h"
#include "src/operators/detect_xss.h"
#include "src/operators/ends_with.h"
#include "src/operators/eq.h"
#include "src/operators/fuzzy_hash.h"
#include "src/operators/ge.h"
#include "src/operators/geo_lookup.h"
#include "src/operators/gsblookup.h"
#include "src/operators/gt.h"
#include "src/operators/inspect_file.h"
#include "src/operators/ip_match_f.h"
#include "src/operators/ip_match_from_file.h"
#include "src/operators/ip_match.h"
#include "src/operators/le.h"
#include "src/operators/lt.h"
#include "src/operators/no_match.h"
#include "src/operators/pm_f.h"
#include "src/operators/pm_from_file.h"
#include "src/operators/pm.h"
#include "src/operators/rbl.h"
#include "src/operators/rsub.h"
#include "src/operators/rx.h"
#include "src/operators/str_eq.h"
#include "src/operators/str_match.h"
#include "src/operators/validate_byte_range.h"
#include "src/operators/validate_dtd.h"
#include "src/operators/validate_hash.h"
#include "src/operators/validate_schema.h"
#include "src/operators/validate_url_encoding.h"
#include "src/operators/validate_utf8_encoding.h"
#include "src/operators/verify_cc.h"
#include "src/operators/verify_cpf.h"
#include "src/operators/verify_ssn.h"
#include "src/operators/verify_svnr.h"
#include "src/operators/within.h"
#include "src/operators/unconditional_match.h"

#define IF_MATCH(a) \
    if (op_ == #a)

namespace modsecurity {
namespace operators {


bool Operator::evaluateInternal(Transaction *transaction,
    Rule *rule, const std::string& a, std::shared_ptr<RuleMessage> rm) {
    bool res = evaluate(transaction, rule, a, rm);

    if (m_negation) {
        return !res;
    }

    return res;
}

bool Operator::evaluateInternal(Transaction *transaction,
    Rule *rule, const std::string& a) {
    bool res = evaluate(transaction, rule, a);

    if (m_negation) {
        return !res;
    }

    return res;
}

bool Operator::evaluateInternal(Transaction *transaction,
    const std::string& a) {
    bool res = evaluate(transaction, a);

    if (m_negation) {
        return !res;
    }

    return res;
}


std::string Operator::resolveMatchMessage(Transaction *t,
    std::string key, std::string value) {
    std::string ret = m_match_message;

    if (ret.empty() == true) {
        if (m_couldContainsMacro == false) {
            ret = "Matched \"Operator `" + m_op + "' with parameter `" +
                utils::string::limitTo(200, m_param) +
                "' against variable `" + key + "' (Value: `" +
                utils::string::limitTo(100,
                    utils::string::toHexIfNeeded(value)) + \
                "' )";
        } else {
            std::string p(m_string->evaluate(t));
            ret = "Matched \"Operator `" + m_op + "' with parameter `" +
                utils::string::limitTo(200, p) +
                "' against variable `" + key + "' (Value: `" +
                utils::string::limitTo(100,
                    utils::string::toHexIfNeeded(value)) +
                "' )";
        }
    }


    return ret;
}


bool Operator::evaluate(Transaction *transaction, const std::string& a) {
    ms_dbg_a(transaction, 2, "Operator: " + m_op + \
        " is not implemented or malfunctioning.");
    return true;
}

Operator *Operator::instantiate(std::string op, std::string param_str) {
    std::string op_ = utils::string::tolower(op);
    std::unique_ptr<RunTimeString> param(new RunTimeString());
    param->appendText(param_str);

    IF_MATCH(beginswith) { return new BeginsWith(std::move(param)); }
    IF_MATCH(contains) { return new Contains(std::move(param)); }
    IF_MATCH(containsword) { return new ContainsWord(std::move(param)); }
    IF_MATCH(detectsqli) { return new DetectSQLi(); }
    IF_MATCH(detectxss) { return new DetectXSS(); }
    IF_MATCH(endswith) { return new EndsWith(std::move(param)); }
    IF_MATCH(eq) { return new Eq(std::move(param)); }
    IF_MATCH(fuzzyhash) { return new FuzzyHash(std::move(param)); }
    IF_MATCH(geolookup) { return new GeoLookup(); }
    IF_MATCH(ge) { return new Ge(std::move(param)); }
    IF_MATCH(gsblookup) { return new GsbLookup(std::move(param)); }
    IF_MATCH(gt) { return new Gt(std::move(param)); }
    IF_MATCH(inspectfile) { return new InspectFile(std::move(param)); }
    IF_MATCH(ipmatchf) { return new IpMatchF(std::move(param)); }
    IF_MATCH(ipmatchfromfile) {
        return new IpMatchFromFile(std::move(param));
    }
    IF_MATCH(ipmatch) { return new IpMatch(std::move(param)); }
    IF_MATCH(le) { return new Le(std::move(param)); }
    IF_MATCH(lt) { return new Lt(std::move(param)); }
    IF_MATCH(nomatch) { return new NoMatch(); }
    IF_MATCH(pmfromfile) { return new PmFromFile(std::move(param)); }
    IF_MATCH(pmf) { return new PmF(std::move(param)); }
    IF_MATCH(pm) { return new Pm(std::move(param)); }
    IF_MATCH(rbl) { return new Rbl(std::move(param)); }
    IF_MATCH(rsub) { return new Rsub(std::move(param)); }
    IF_MATCH(rx) { return new Rx(std::move(param)); }
    IF_MATCH(streq) { return new StrEq(std::move(param)); }
    IF_MATCH(strmatch) { return new StrMatch(std::move(param)); }
    IF_MATCH(validatebyterange) {
        return new ValidateByteRange(std::move(param));
    }
    IF_MATCH(validatedtd) { return new ValidateDTD(std::move(param)); }
    IF_MATCH(validatehash) { return new ValidateHash(std::move(param)); }
    IF_MATCH(validateschema) { return new ValidateSchema(std::move(param)); }
    IF_MATCH(validateurlencoding) {
        return new ValidateUrlEncoding();
    }
    IF_MATCH(validateutf8encoding) {
        return new ValidateUtf8Encoding();
    }
    IF_MATCH(verifycc) { return new VerifyCC(std::move(param)); }
    IF_MATCH(verifycpf) { return new VerifyCPF(std::move(param)); }
    IF_MATCH(verifyssn) { return new VerifySSN(std::move(param)); }
    IF_MATCH(verifysvnr) { return new VerifySVNR(std::move(param)); }
    IF_MATCH(within) { return new Within(std::move(param)); }

    IF_MATCH(unconditionalmatch) {
        return new UnconditionalMatch();
    }

    throw std::invalid_argument("Operator not found.");
}

}  // namespace operators
}  // namespace modsecurity
