#include <iostream>
#include <thread>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <vector>

#ifndef WIN32
#include <dirent.h>
#endif

#include <modsecurity/modsecurity.h>
#include <modsecurity/transaction.h>
#include <modsecurity/rules_set.h>

static void process_request(modsecurity::ModSecurity *modsec,
    modsecurity::RulesSet *rules, int tid, int iterations,
    std::atomic<int> *completed_threads) {
    std::cout << "Hello World! It's me, thread #" << tid << std::endl;

    for (int i = 0; i != iterations; i++) {
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

    completed_threads->fetch_add(1);
    std::cout << "Thread #" << tid << " exits" << std::endl;
}

#ifndef WIN32
static int count_open_fds(void) {
    int count = 0;
    DIR *dir = opendir("/proc/self/fd");
    if (dir == nullptr) {
        return -1;
    }

    while (readdir(dir) != nullptr) {
        count++;
    }
    closedir(dir);
    return count;
}
#endif

int main (int argc, const char *argv[]) {
    
    auto modsec = std::make_unique<modsecurity::ModSecurity>();
    modsec->setConnectorInformation("ModSecurity-test v0.0.1-alpha (Simple " \
        "example on how to use ModSecurity API");

    const char *main_rule_uri = "basic_rules.conf";
    if (argc >= 2) {
        main_rule_uri = argv[1];
    }

    int thread_count = 100;
    if (argc >= 3) {
        thread_count = std::atoi(argv[2]);
    }

    int iterations = 1000;
    if (argc >= 4) {
        iterations = std::atoi(argv[3]);
    }

    if (thread_count <= 0 || iterations <= 0) {
        std::cerr << "Usage: ./multithread [rules.conf] [threads] [iterations]" << std::endl;
        return 2;
    }

    auto rules = std::make_unique<modsecurity::RulesSet>();
    if (rules->loadFromUri(main_rule_uri) < 0) {
        std::cerr << "Problems loading the rules..." << std::endl;
        std::cerr << rules->m_parserError.str() << std::endl;
        return -1;
    }

    std::vector<std::thread> threads;
    threads.resize(thread_count);
    std::atomic completed_threads{0};

#ifndef WIN32
    const int open_fds_before = count_open_fds();
    std::cout << "open_fds_before=" << open_fds_before << std::endl;
#endif
    auto start = std::chrono::steady_clock::now();

    for (auto i = 0; i != threads.size(); ++i) {
        threads[i] = std::thread(
            [&modsec, &rules, i, iterations, &completed_threads]() {
                process_request(modsec.get(), rules.get(), static_cast<int>(i),
                    iterations, &completed_threads);
            });
    }

    std::this_thread::sleep_for(std::chrono::microseconds(10000));

    for (auto i = 0; i != threads.size(); ++i) {
        threads[i].join();
    }

    auto elapsed = std::chrono::steady_clock::now() - start;
    std::cout << "completed_threads=" << completed_threads.load() << std::endl;
    std::cout << "elapsed_ms="
        << std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count()
        << std::endl;

#ifndef WIN32
    const int open_fds_after = count_open_fds();
    std::cout << "open_fds_after=" << open_fds_after << std::endl;
#endif

    return 0;
}
