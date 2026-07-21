/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/operators/inspect_file.h"

#include <stdio.h>
#include <string.h>

#include <iostream>
#include <array>
#include <sstream>
#include <string>
#include <vector>

#include "src/operators/operator.h"
#include "src/utils/system.h"

#ifdef WIN32
#include "src/compat/msvc.h"
#include <windows.h>
#else
#include <errno.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;
#endif

namespace modsecurity {
namespace operators {

#ifdef WIN32
namespace {
bool stringToWide(const std::string &input, std::wstring *output) {
    if (output == nullptr) {
        return false;
    }

    if (input.empty()) {
        output->clear();
        return true;
    }

    int needed = MultiByteToWideChar(CP_UTF8, 0, input.c_str(), -1, nullptr, 0);
    if (needed <= 0) {
        return false;
    }

    output->resize(needed);
    int written = MultiByteToWideChar(CP_UTF8, 0, input.c_str(), -1, &(*output)[0], needed);
    if (written != needed) {
        return false;
    }

    output->pop_back();
    return true;
}

std::wstring quoteWindowsArg(const std::wstring &arg) {
    if (arg.empty()) {
        return L"\"\"";
    }

    bool requires_quotes = false;
    for (wchar_t c : arg) {
        if (c == L' ' || c == L'\t' || c == L'\"') {
            requires_quotes = true;
            break;
        }
    }

    if (requires_quotes == false) {
        return arg;
    }

    std::wstring out;
    out.push_back(L'"');

    size_t backslashes = 0;
    for (wchar_t c : arg) {
        if (c == L'\\') {
            backslashes++;
            continue;
        }

        if (c == L'"') {
            out.append(backslashes * 2 + 1, L'\\');
            out.push_back(L'"');
            backslashes = 0;
            continue;
        }

        if (backslashes > 0) {
            out.append(backslashes, L'\\');
            backslashes = 0;
        }

        out.push_back(c);
    }

    if (backslashes > 0) {
        out.append(backslashes * 2, L'\\');
    }

    out.push_back(L'"');
    return out;
}
}  // namespace
#endif

bool InspectFile::init(const std::string &param2, std::string *error) {
    std::ifstream *iss;
    std::string err;
    std::string err_lua;

    m_file = utils::find_resource(m_param, param2, &err);
    iss = new std::ifstream(m_file, std::ios::in);

    if (iss->is_open() == false) {
        error->assign("Failed to open file: " + m_param + ". " + err);
        delete iss;
        return false;
    }

    if (engine::Lua::isCompatible(m_file, &m_lua, &err_lua) == true) {
        m_isScript = true;
    }

    delete iss;
    return true;
}


bool InspectFile::evaluate(Transaction *transaction, const std::string &str) {
    if (m_isScript) {
        return m_lua.run(transaction, str);
    } else {
#ifndef WIN32
        std::array<int, 2> pipefd = {{-1, -1}};
        if (pipe(pipefd.data()) == -1) {
            return false;
        }

        posix_spawn_file_actions_t actions;
        if (posix_spawn_file_actions_init(&actions) != 0) {
            close(pipefd[0]);
            close(pipefd[1]);
            return false;
        }

        bool action_error = false;
        if (posix_spawn_file_actions_addclose(&actions, pipefd[0]) != 0) {
            action_error = true;
        }
        if (!action_error
            && posix_spawn_file_actions_adddup2(&actions, pipefd[1], STDOUT_FILENO) != 0) {
            action_error = true;
        }
        if (!action_error
            && posix_spawn_file_actions_addclose(&actions, pipefd[1]) != 0) {
            action_error = true;
        }

        if (action_error) {
            posix_spawn_file_actions_destroy(&actions);
            close(pipefd[0]);
            close(pipefd[1]);
            return false;
        }

        std::vector<std::string> argv_storage;
        argv_storage.emplace_back(m_file);
        argv_storage.emplace_back(str);

        std::vector<char *> argv;
        argv.reserve(argv_storage.size() + 1);
        // cppcheck-suppress constVariableReference
        for (std::string &arg : argv_storage) {
            argv.push_back(arg.data());
        }
        argv.push_back(nullptr);

        pid_t pid = 0;
        int spawn_rc = posix_spawn(&pid, m_file.c_str(), &actions, nullptr, argv.data(),
            environ);

        posix_spawn_file_actions_destroy(&actions);

        close(pipefd[1]);

        if (spawn_rc != 0) {
            close(pipefd[0]);
            return false;
        }

        std::array<char, 512> buff = {};
        std::stringstream s;
        bool read_error = false;
        bool done_reading = false;
        while (!done_reading) {
            ssize_t count = read(pipefd[0], buff.data(), buff.size());
            if (count > 0) {
                s.write(buff.data(), count);
            } else if (count == 0) {
                done_reading = true;
            } else if (errno != EINTR) {
                read_error = true;
                done_reading = true;
            }
        }

        close(pipefd[0]);

        int wstatus = 0;
        while (waitpid(pid, &wstatus, 0) == -1) {
            if (errno != EINTR) {
                return false;
            }
        }

        if (read_error || WIFEXITED(wstatus) == 0 || WEXITSTATUS(wstatus) != 0) {
            return false;
        }

        std::string res = s.str();
        if (res.size() > 1 && res[0] != '1') {
            return true; /* match */
        }

        /* no match */
        return false;
#else
        std::wstring executable_path;
        std::wstring argument;
        if (stringToWide(m_file, &executable_path) == false
            || stringToWide(str, &argument) == false) {
            return false;
        }

        SECURITY_ATTRIBUTES security_attributes;
        memset(&security_attributes, 0, sizeof(security_attributes));
        security_attributes.nLength = sizeof(security_attributes);
        security_attributes.bInheritHandle = TRUE;

        HANDLE child_stdout_read = nullptr;
        HANDLE child_stdout_write = nullptr;
        if (CreatePipe(&child_stdout_read, &child_stdout_write,
                &security_attributes, 0) == FALSE) {
            return false;
        }

        if (SetHandleInformation(child_stdout_read, HANDLE_FLAG_INHERIT, 0) == FALSE) {
            CloseHandle(child_stdout_read);
            CloseHandle(child_stdout_write);
            return false;
        }

        STARTUPINFOW startup_info;
        PROCESS_INFORMATION process_info;
        memset(&startup_info, 0, sizeof(startup_info));
        memset(&process_info, 0, sizeof(process_info));
        startup_info.cb = sizeof(startup_info);
        startup_info.dwFlags = STARTF_USESTDHANDLES;
        startup_info.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
        startup_info.hStdOutput = child_stdout_write;
        startup_info.hStdError = GetStdHandle(STD_ERROR_HANDLE);

        std::wstring command_line = quoteWindowsArg(executable_path);
        command_line.append(L" ");
        command_line.append(quoteWindowsArg(argument));

        if (CreateProcessW(executable_path.c_str(), &command_line[0], nullptr,
                nullptr, TRUE, 0, nullptr, nullptr, &startup_info,
                &process_info) == FALSE) {
            CloseHandle(child_stdout_read);
            CloseHandle(child_stdout_write);
            return false;
        }

        CloseHandle(child_stdout_write);

        char buff[512];
        std::stringstream s;
        bool read_error = false;

        while (true) {
            DWORD bytes_read = 0;
            BOOL read_ok = ReadFile(child_stdout_read, buff, sizeof(buff), &bytes_read, nullptr);
            if (read_ok == FALSE) {
                DWORD err = GetLastError();
                if (err == ERROR_BROKEN_PIPE) {
                    break;
                }
                read_error = true;
                break;
            }

            if (bytes_read == 0) {
                break;
            }

            s.write(buff, bytes_read);
        }

        CloseHandle(child_stdout_read);

        DWORD wait_rc = WaitForSingleObject(process_info.hProcess, INFINITE);
        if (wait_rc != WAIT_OBJECT_0) {
            CloseHandle(process_info.hThread);
            CloseHandle(process_info.hProcess);
            return false;
        }

        DWORD exit_code = 1;
        BOOL got_exit_code = GetExitCodeProcess(process_info.hProcess, &exit_code);

        CloseHandle(process_info.hThread);
        CloseHandle(process_info.hProcess);

        if (read_error || got_exit_code == FALSE || exit_code != 0) {
            return false;
        }

        std::string res = s.str();
        if (res.size() > 1 && res[0] != '1') {
            return true; /* match */
        }

        /* no match */
        return false;
#endif
    }
}


}  // namespace operators
}  // namespace modsecurity
