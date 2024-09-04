#include <iostream>
#include <thread>
#include <array>

#include <modsecurity/modsecurity.h>
#include <modsecurity/transaction.h>
#include <modsecurity/rules_set.h>

static void process_request(modsecurity::ModSecurity *modsec, modsecurity::RulesSet *rules, int tid) {
    std::cout << "Hello World! It's me, thread #" << tid << std::endl;

    for(int i = 0; i != 1'000; i++) {
        auto modsecTransaction = std::make_unique<modsecurity::Transaction>(modsec, rules, nullptr);

        modsecTransaction->processConnection("127.0.0.1", 12345, "127.0.0.1", 80);
        modsecTransaction->processURI(
            "https://www.modsecurity.org/test?foo=herewego",
            "GET", "1.1");

        modsecTransaction->addRequestHeader("User-Agent",
            "Basic ModSecurity example");
        modsecTransaction->processRequestHeaders();
        modsecTransaction->processRequestBody();

        modsecTransaction->addResponseHeader("HTTP/1.1",
            "200 OK");
        modsecTransaction->processResponseHeaders(200, "HTTP 1.2");
        modsecTransaction->processResponseBody();

        modsecTransaction->processLogging();

        std::this_thread::sleep_for(std::chrono::microseconds(100));
    }

    std::cout << "Thread #" << tid << " exits" << std::endl;
}

int main (int argc, char *argv[]) {
    auto modsec = std::make_unique<modsecurity::ModSecurity>();
    modsec->setConnectorInformation("ModSecurity-test v0.0.1-alpha (Simple " \
        "example on how to use ModSecurity API");

    char main_rule_uri[] = "basic_rules.conf";
    auto rules = std::make_unique<modsecurity::RulesSet>();
    if (rules->loadFromUri(main_rule_uri) < 0) {
        std::cerr << "Problems loading the rules..." << std::endl;
        std::cerr << rules->m_parserError.str() << std::endl;
        return -1;
    }

    constexpr auto NUM_THREADS = 100;
    std::array<std::thread, NUM_THREADS> threads;

    for (auto i = 0; i != threads.size(); ++i) {
        threads[i] = std::thread(
            [&modsec, &rules, i]() {
                process_request(modsec.get(), rules.get(), i);
            });
    }

    std::this_thread::sleep_for(std::chrono::microseconds(10000));

    for (auto i = 0; i != threads.size(); ++i) {
        threads[i].join();
    }

    return 0;
}