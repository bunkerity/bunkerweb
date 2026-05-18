/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#ifndef SRC_OPERATORS_VALIDATE_SCHEMA_H_
#define SRC_OPERATORS_VALIDATE_SCHEMA_H_

#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#ifdef WITH_LIBXML2
#include <libxml/xmlschemas.h>
#include <libxml/xpath.h>
#endif
#include <string>
#include <memory>
#include <utility>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

class ValidateSchema : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit ValidateSchema(std::unique_ptr<RunTimeString> param)
        : Operator("ValidateSchema", std::move(param)) { }
#ifdef WITH_LIBXML2

    bool evaluate(Transaction *transaction, const std::string  &str) override;
    bool init(const std::string &file, std::string *error) override;


    static void error_load(void *ctx, const char *msg, ...) {
        va_list args;
        va_start(args, msg);
        callback_func(ctx, append_msg, PREFIX_ERROR, msg, args);
        va_end(args);
    }


    static void warn_load(void *ctx, const char *msg, ...) {
        va_list args;
        va_start(args, msg);
        callback_func(ctx, append_msg, PREFIX_WARNING, msg, args);
        va_end(args);
    }


    static void error_runtime(void *ctx, const char *msg, ...) {
        va_list args;
        va_start(args, msg);
        callback_func(ctx, log_msg, PREFIX_ERROR, msg, args);
        va_end(args);
    }


    static void warn_runtime(void *ctx, const char *msg, ...) {
        va_list args;
        va_start(args, msg);
        callback_func(ctx, log_msg, PREFIX_WARNING, msg, args);
        va_end(args);
    }


    template<typename Pred>
    static void callback_func(void *ctx, Pred pred, const char *base_msg, const char *msg, va_list args) {
        char buf[1024];
        const auto len = vsnprintf(buf, sizeof(buf), msg, args);

        if (len > 0)
            pred(ctx, base_msg + std::string(buf));
    }

    static void log_msg(const void *ctx, const std::string &msg) {
        auto t = reinterpret_cast<const Transaction *>(ctx);
        ms_dbg_a(t, 4, msg);
    }

    static void append_msg(void *ctx, const std::string &msg) {
        auto s = reinterpret_cast<std::string*>(ctx);
        s->append(msg);
    }

    static constexpr auto PREFIX_WARNING = "XML Warning: ";
    static constexpr auto PREFIX_ERROR = "XML Error: ";

 private:
    std::string m_resource;
    std::string m_err;
#endif
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_VALIDATE_SCHEMA_H_
