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

#ifndef SRC_UTILS_SHARED_FILES_H_
#define SRC_UTILS_SHARED_FILES_H_


#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <utility>
#include <vector>
#include <fstream>
#include <string>


#include "modsecurity/transaction.h"
#include "modsecurity/audit_log.h"

/**
 * Not using this critical section yet.
 *
 */
/* #define MODSEC_USE_GENERAL_LOCK */

namespace modsecurity {
namespace utils {


typedef struct msc_file_handler {
    int shm_id_structure;
    char file_name[];
} msc_file_handler_t;


class SharedFiles {
 public:
    bool open(const std::string& fileName, std::string *error);
    void close(const std::string& fileName);
    bool write(const std::string& fileName, const std::string &msg,
        std::string *error);

    static SharedFiles& getInstance() {
        static SharedFiles instance;
        return instance;
    }

 protected:
    std::pair<msc_file_handler *, FILE *> find_handler(
        const std::string &fileName);
    std::pair<msc_file_handler *, FILE *> add_new_handler(
        const std::string &fileName, std::string *error);

 private:
    SharedFiles()
#ifdef MODSEC_USE_GENERAL_LOCK
        : m_generalLock(NULL)
#endif
    {
#ifdef MODSEC_USE_GENERAL_LOCK
        int shm_id;
        bool toBeCreated = true;
        bool err = false;

        m_memKeyStructure = ftok(".", 1);
        if (m_memKeyStructure < 0) {
            err = true;
            goto err_mem_key;
        }

        shm_id = shmget(m_memKeyStructure, sizeof(pthread_mutex_t),
            IPC_CREAT | IPC_EXCL | 0666);
        if (shm_id < 0) {
            shm_id = shmget(m_memKeyStructure, sizeof(pthread_mutex_t),
                IPC_CREAT | 0666);
            toBeCreated = false;
            if (shm_id < 0) {
                err = true;
                goto err_shmget1;
            }
        }

        m_generalLock = reinterpret_cast<pthread_mutex_t *>(
            shmat(shm_id, NULL, 0));
        if ((reinterpret_cast<char *>(m_generalLock)[0]) == -1) {
            err = true;
            goto err_shmat1;
        }

        if (toBeCreated) {
            memset(m_generalLock, '\0', sizeof(pthread_mutex_t));
            pthread_mutex_init(m_generalLock, NULL);
            pthread_mutex_unlock(m_generalLock);
        }

        if (err) {
err_mem_key:
            std::cerr << strerror(errno) << std::endl;
err_shmget1:
            std::cerr << "err_shmget1" << std::endl;
err_shmat1:
            std::cerr << "err_shmat1" << std::endl;
        }
        toBeCreated = false;
#endif
    }
    ~SharedFiles() {
#if MODSEC_USE_GENERAL_LOCK
        shmdt(m_generalLock);
        shmctl(m_memKeyStructure, IPC_RMID, NULL);
#endif
    }

    // C++ 03
    // ========
    // Dont forget to declare these two. You want to make sure they
    // are unacceptable otherwise you may accidentally get copies of
    // your singleton appearing.
    SharedFiles(SharedFiles const&);
    void operator=(SharedFiles const&);

    std::vector<std::pair<std::string,
        std::pair<msc_file_handler *, FILE *>>> m_handlers;
#if MODSEC_USE_GENERAL_LOCK
    pthread_mutex_t *m_generalLock;
    key_t m_memKeyStructure;
#endif
};


}  // namespace utils
}  // namespace modsecurity

#endif  // SRC_UTILS_SHARED_FILES_H_
