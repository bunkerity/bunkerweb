
#include "src/operators/verify_svnr.h"

#include <string>

#include "src/operators/operator.h"

#include "modsecurity/rule.h"
#include "modsecurity/rule_message.h"
#include "modsecurity/rules_properties.h"
namespace modsecurity {
namespace operators {

int VerifySVNR::convert_to_int(const char c)
{
    int n;
    if ((c>='0') && (c<='9'))
        n = c - '0';
    else
        n = 0;
    return n;
}

bool VerifySVNR::verify(const char *svnrnumber, int len) {
    int var_len = len;
    int sum = 0;
    unsigned int i = 0, svnr_len = 10;
    int svnr[11];
    char s_svnr[11];
    char bad_svnr[12][11] = { "0000000000",
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

    while ((*svnrnumber != '\0') && ( var_len > 0))
    {
        if (*svnrnumber != '-' || *svnrnumber != '.')
        {
            if (i < svnr_len && isdigit(*svnrnumber))
            {
                s_svnr[i] = *svnrnumber;
                svnr[i] = convert_to_int(*svnrnumber);
                i++;
            }
        }
        svnrnumber++;
        var_len--;
    }


    if (i != svnr_len)
    {
        return 0;
    }
    else
    {
        for (i = 0; i< svnr_len; i++)
        {
            if (strncmp(s_svnr,bad_svnr[i],svnr_len) == 0)
            {
                return 0;
            }
        }
    }
    //Laufnummer mit 3, 7, 9
    //Geburtsdatum mit 5, 8, 4, 2, 1, 6
    sum = svnr[0] * 3 + svnr[1] * 7 + svnr[2] * 9 + svnr[4] * 5 + svnr[5] * 8 + svnr[6] * 4 + svnr[7] * 2 + svnr[8] * 1 + svnr[9] * 6;
    sum %= 11;
    if(sum == 10){
    	sum = 0;
    }
    if (sum == svnr[3])
    {
        return true;
    }
    return false;
}


bool VerifySVNR::evaluate(Transaction *t, Rule *rule,
    const std::string& input, std::shared_ptr<RuleMessage> ruleMessage) {
    std::list<SMatch> matches;
    bool is_svnr = false;
    int i;

    if (m_param.empty()) {
        return is_svnr;
    }

    for (i = 0; i < input.size() - 1 && is_svnr == false; i++) {
        matches = m_re->searchAll(input.substr(i, input.size()));

        for (const auto & i : matches) {
            is_svnr = verify(i.str().c_str(), i.str().size());
            if (is_svnr) {
                logOffset(ruleMessage, i.offset(), i.str().size());
                if (rule && t && rule->m_containsCaptureAction) {
                    t->m_collections.m_tx_collection->storeOrUpdateFirst(
                        "0", i.str());
                    ms_dbg_a(t, 7, "Added VerifySVNR match TX.0: " + \
                        i.str());
                }

                goto out;
            }
        }
    }

out:
    return is_svnr;
}


}  // namespace operators
}  // namespace modsecurity
