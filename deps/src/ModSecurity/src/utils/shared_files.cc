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

#include "src/utils/shared_files.h"

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#include <utility>
#include <fstream>
#include <string>

namespace modsecurity {
namespace utils {


std::pair<msc_file_handler *, FILE *> SharedFiles::find_handler(
    const std::string &fileName) {
    for (const auto &i : m_handlers) {
        if (i.first == fileName) {
            return i.second;
        }
    }
    return std::pair<modsecurity::utils::msc_file_handler *,
        FILE *>(NULL, NULL);
}


std::pair<msc_file_handler *, FILE *> SharedFiles::add_new_handler(
    const std::string &fileName, std::string *error) {
    int shm_id;
    int ret;
    key_t mem_key_structure;
    msc_file_handler_t *new_debug_log = NULL;
    struct shmid_ds shared_mem_info;
    FILE *fp;
    bool toBeCreated = true;

    fp = fopen(fileName.c_str(), "a");
    if (fp == 0) {
        error->assign("Failed to open file: " + fileName);
        goto err_fh;
    }

    mem_key_structure = ftok(fileName.c_str(), 1);
    if (mem_key_structure < 0) {
        error->assign("Failed to select key for the shared memory (1): ");
        error->append(strerror(errno));
        goto err_mem_key;
    }

    shm_id = shmget(mem_key_structure, sizeof (msc_file_handler_t) \
        + fileName.size() + 1, IPC_CREAT | IPC_EXCL | 0666);
    if (shm_id < 0) {
        shm_id = shmget(mem_key_structure, sizeof (msc_file_handler_t)
            + fileName.size() + 1, IPC_CREAT | 0666);
        toBeCreated = false;
        if (shm_id < 0) {
            error->assign("Failed to allocate shared memory (1): ");
            error->append(strerror(errno));
            goto err_shmget1;
        }
    }

    ret = shmctl(shm_id, IPC_STAT, &shared_mem_info);
    if (ret < 0) {
        error->assign("Failed to get information on shared memory (1): ");
        error->append(strerror(errno));
        goto err_shmctl1;
    }

    new_debug_log = reinterpret_cast<msc_file_handler_t *>(
            shmat(shm_id, NULL, 0));
    if ((reinterpret_cast<char *>(new_debug_log)[0]) == -1) {
        error->assign("Failed to attach shared memory (1): ");
        error->append(strerror(errno));
        goto err_shmat1;
    }

    if (toBeCreated == false && shared_mem_info.shm_nattch == 0) {
        toBeCreated = true;
    }

    if (toBeCreated) {
        memset(new_debug_log, '\0', sizeof(msc_file_handler_t));
        new_debug_log->shm_id_structure = shm_id;
        memcpy(new_debug_log->file_name, fileName.c_str(), fileName.size());
        new_debug_log->file_name[fileName.size()] = '\0';
    }
    m_handlers.push_back(std::make_pair(fileName,
        std::make_pair(new_debug_log, fp)));

    return std::make_pair(new_debug_log, fp);
err_shmat1:
    shmdt(new_debug_log);
err_shmctl1:
err_shmget1:
err_mem_key:
    fclose(fp);
err_fh:
    return std::pair<modsecurity::utils::msc_file_handler *,
        FILE *>(NULL, NULL);
}


bool SharedFiles::open(const std::string& fileName, std::string *error) {
    std::pair<msc_file_handler *, FILE *> a;
    bool ret = true;

    #if MODSEC_USE_GENERAL_LOCK
    pthread_mutex_lock(m_generalLock);
#endif

    a = find_handler(fileName);
    if (a.first == NULL) {
        a = add_new_handler(fileName, error);
        if (error->size() > 0) {
            ret = false;
            goto out;
        }
    }
    if (a.first == NULL) {
        error->assign("Not able to open: " + fileName);
        ret = false;
        goto out;
    }

out:
#if MODSEC_USE_GENERAL_LOCK
    pthread_mutex_unlock(m_generalLock);
#endif

    return ret;
}


void SharedFiles::close(const std::string& fileName) {
    std::pair<msc_file_handler *, FILE *> a;
    /* int ret; */
    /* int shm_id; */
    /* struct shmid_ds shared_mem_info; */
    /* int j = 0; */

#if MODSEC_USE_GENERAL_LOCK
    pthread_mutex_lock(m_generalLock);
#endif

    if (fileName.empty()) {
        goto out;
    }

    a = find_handler(fileName);
    if (a.first == NULL || a.second == NULL) {
        goto out;
    }

    /* fclose(a.second); */
    a.second = 0;

    /*
     * Delete the file structure will be welcomed, but we cannot delay
     * while the process is being killed.
     *
    for (std::pair<std::string,
        std::pair<msc_file_handler *, FILE *>> i : m_handlers) {
        if (i.first == fileName) {
            j++;
        }
    }

    m_handlers.erase(m_handlers.begin()+j);
    */

    /* hmdt(a.second); */
    shmctl(a.first->shm_id_structure, IPC_RMID, NULL);

    /*
     *
     * We could check to see how many process attached to the shared memory
     * we have, prior to the deletion of the shared memory.
     *
    ret = shmctl(a.first->shm_id_structure, IPC_STAT, &shared_mem_info);
    if (ret < 0) {
        goto out;
    }
    ret = shared_mem_info.shm_nattch;
    shm_id = a.first->shm_id_structure;
    */

out:
#if MODSEC_USE_GENERAL_LOCK
    pthread_mutex_unlock(m_generalLock);
#endif
    return;
}


bool SharedFiles::write(const std::string& fileName,
    const std::string &msg, std::string *error) {
    std::pair<msc_file_handler *, FILE *> a;
    std::string lmsg = msg;
    size_t wrote;
    struct flock lock{};
    bool ret = true;

    a = find_handler(fileName);
    if (a.first == NULL) {
        error->assign("file is not open: " + fileName);
        return false;
    }

    //Exclusively lock whole file
    lock.l_start = lock.l_len = lock.l_whence = 0;
    lock.l_type = F_WRLCK;
    fcntl(fileno(a.second), F_SETLKW, &lock);

    wrote = fwrite(lmsg.c_str(), 1, lmsg.size(), a.second);
    if (wrote < msg.size()) {
        error->assign("failed to write: " + fileName);
        ret = false;
    }
    fflush(a.second);

    //Remove exclusive lock
    lock.l_type = F_UNLCK;
    fcntl(fileno(a.second), F_SETLKW, &lock);

    return ret;
}


}  // namespace utils
}  // namespace modsecurity
