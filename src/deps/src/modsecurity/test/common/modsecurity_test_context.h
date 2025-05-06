#ifndef TEST_COMMON_MODSECURITY_TEST_CONTEXT_H_
#define TEST_COMMON_MODSECURITY_TEST_CONTEXT_H_

#include "modsecurity/modsecurity.h"
#include "modsecurity/rules_set.h"
#include "modsecurity/transaction.h"
#include "custom_debug_log.h"

#include <sstream>

namespace modsecurity_test {

    class ModSecurityTestContext {
    public:
        explicit ModSecurityTestContext(const std::string &connector)
            : m_modsec_rules(new CustomDebugLog) {
            m_modsec.setConnectorInformation(connector);
            m_modsec.setServerLogCb(logCb);
        }
        ~ModSecurityTestContext() = default;

        modsecurity::Transaction create_transaction() {
            return modsecurity::Transaction(&m_modsec,
                                            &m_modsec_rules,
                                            &m_server_log);
        }

        modsecurity::ModSecurity m_modsec;
        modsecurity::RulesSet m_modsec_rules;
        std::stringstream m_server_log;

    private:
        static void logCb(void *data, const void *msgv) {
            auto msg = reinterpret_cast<const char *>(msgv);
            auto ss = reinterpret_cast<std::stringstream *>(data);
            *ss << msg << std::endl;
        }
    };

} // namespace modsecurity_test

#endif // TEST_COMMON_MODSECURITY_TEST_H_
