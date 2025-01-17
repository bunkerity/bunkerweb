
#ifndef SRC_OPERATORS_VERIFY_SVNR_H_
#define SRC_OPERATORS_VERIFY_SVNR_H_

#include <string>
#include <memory>
#include <utility>

#include "src/operators/operator.h"
#include "src/utils/regex.h"


namespace modsecurity {
using Utils::SMatch;
using Utils::regex_search;
using Utils::Regex;

namespace operators {

class VerifySVNR : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit VerifySVNR(std::unique_ptr<RunTimeString> param)
        : Operator("VerifySVNR", std::move(param)) {
        m_re = new Regex(m_param);
    }

    ~VerifySVNR() {
        delete m_re;
    }

    bool operator=(const VerifySVNR &a) = delete;
    VerifySVNR(const VerifySVNR &a) = delete;

    bool evaluate(Transaction *transaction, RuleWithActions *rule,
        const std::string& input,
        std::shared_ptr<RuleMessage> ruleMessage) override;

    bool verify(const char *ssnumber, int len);

 private:
    Regex *m_re;
    static int convert_to_int(const char c);
    const char bad_svnr[12][11] = { "0000000000",
        "0123456789",
        "1234567890",
        "1111111111",
        "2222222222",
        "3333333333",
        "4444444444",
        "5555555555",
        "6666666666",
        "7777777777",
        "8888888888",
        "9999999999"};
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_VERIFY_SVNR_H_

