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

#include "test/common/modsecurity_test.h"

#ifdef WITH_YAJL
#include <yajl/yajl_tree.h>
#endif
#include <dirent.h>
#include <string.h>
#include <sys/stat.h>

#include <fstream>
#include <cstdlib>
#include <sstream>
#include <string>
#include <iostream>

#include "modsecurity/modsecurity.h"

namespace modsecurity_test {

template <class T>
std::string ModSecurityTest<T>::header() {
    std::stringstream i;

    i << "ModSecurity " << MODSECURITY_VERSION << " - tests" << std::endl;
#if not HAS_GETOPT
    i << "(options are not available -- missing GetOpt)" << std::endl;
#endif
    i << std::endl;

    return i.str();
}

template <class T>
bool ModSecurityTest<T>::load_test_json(std::string file) {
    char errbuf[1024];
    yajl_val node;

    std::ifstream myfile;
    myfile.open(file.c_str());
    if (myfile.is_open() == false) {
        std::cout << "Problems opening file: " << file << std::endl;
        return false;
    }

    std::string str((std::istreambuf_iterator<char>(myfile)),
        std::istreambuf_iterator<char>());
    node = yajl_tree_parse((const char *) str.c_str(), errbuf, sizeof(errbuf));
    if (node == NULL) {
        std::cout << "Problems parsing file: " << file << std::endl;
        if (strlen(errbuf) > 0) {
            std::cout << errbuf << std::endl;
        }
        return false;
    }

    size_t num_tests = node->u.array.len;
    for ( int i = 0; i < num_tests; i++ ) {
        yajl_val obj = node->u.array.values[i];

        T *u = T::from_yajl_node(obj);
        u->filename = file;

        if (this->count(u->filename + ":" + u->name) == 0) {
            std::vector<T *> *vector = new std::vector<T *>;
            vector->push_back(u);
            std::pair<std::string, std::vector<T *> *> a(u->filename + ":" +
                u->name, vector);
            this->insert(a);
        } else {
            std::vector<T *> *vec = this->at(u->filename + ":" + u->name);
            vec->push_back(u);
        }
    }

    yajl_tree_free(node);

    return true;
}


template <class T>
std::pair<std::string, std::vector<T *>>*
ModSecurityTest<T>::load_tests(std::string path) {
    DIR *dir;
    struct dirent *ent;
    struct stat buffer;

    if ((dir = opendir(path.c_str())) == NULL) {
        /* if target is a file, use it as a single test. */
        if (stat(path.c_str(), &buffer) == 0) {
            if (load_test_json(path) == false) {
                std::cout << "Problems loading from: " << path;
                std::cout << std::endl;
            }
        }
        return NULL;
    }

    while ((ent = readdir(dir)) != NULL) {
        std::string filename = ent->d_name;
        std::string json = ".json";
        if (filename.size() < json.size()
            || !std::equal(json.rbegin(), json.rend(), filename.rbegin())) {
            continue;
        }
        if (load_test_json(path + "/" + filename) == false) {
            std::cout << "Problems loading tests from: " << filename;
            std::cout << std::endl;
        }
    }
    closedir(dir);

    return NULL;
}


template <class T>
std::pair<std::string, std::vector<T *>>* ModSecurityTest<T>::load_tests() {
    return load_tests(this->target);
}

template <class T>
void ModSecurityTest<T>::cmd_options(int argc, char **argv) {
    int i = 1;
    if (argc > i && strcmp(argv[i], "automake") == 0) {
        i++;
        m_automake_output = true;
    }
    if (argc > i && strcmp(argv[i], "countall") == 0) {
        i++;
        m_count_all = true;
    }
    if (const char* env_p = std::getenv("AUTOMAKE_TESTS")) {
        m_automake_output = true;
    }

    if (argc > i && argv[i]) {
        this->target = argv[i];
        size_t pos = this->target.find(":");
        if (pos != std::string::npos) {
            std::string test_numbers = std::string(this->target, pos + 1,
                this->target.length() - pos);
            this->target = std::string(this->target, 0, pos);
            m_test_number = std::atoi(test_numbers.c_str());
        }
    } else {
        this->target = default_test_path;
    }
}

}  // namespace modsecurity_test
