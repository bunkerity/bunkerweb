
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
    bool evaluate(Transaction *transaction, Rule *rule,
        const std::string &input) override {
        return evaluate(transaction, NULL, input, NULL);
    }
    bool evaluate(Transaction *transaction,
        const std::string &input) override {
        return evaluate(transaction, NULL, input);
    }
    bool evaluate(Transaction *transaction, Rule *rule,
        const std::string& input,
        std::shared_ptr<RuleMessage> ruleMessage) override;

    int convert_to_int(const char c);
    bool verify(const char *ssnumber, int len);

 private:
    Regex *m_re;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_VERIFY_SVNR_H_

