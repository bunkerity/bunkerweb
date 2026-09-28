/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#ifndef SRC_UTILS_SHA1_H_
#define SRC_UTILS_SHA1_H_

#include <array>
#include <cstddef>
#include <string>
#include <string_view>

#include "src/utils/string.h"
#include "mbedtls/md.h"

namespace modsecurity::Utils {


template<mbedtls_md_type_t DigestType, int DigestSize>
class DigestImpl {
 public:
    static bool digest(const std::string& input, std::string *output) {
        if (output == nullptr) {
            return false;
        }

        std::array<unsigned char, DigestSize> digestBytes;
        if (!calculateDigest(input, &digestBytes)) {
            return false;
        }

        output->assign(digestBytes.begin(), digestBytes.end());
        return true;
    }

    static bool digestReplace(std::string *value) {
        if (value == nullptr) {
            return false;
        }

        return digest(*value, value);
    }

    static bool hexdigest(const std::string& input, std::string *output) {
        if (output == nullptr) {
            return false;
        }

        std::array<unsigned char, DigestSize> digestBytes;
        if (!calculateDigest(input, &digestBytes)) {
            return false;
        }

        const auto *digestByteData =
            static_cast<const std::byte *>(static_cast<const void *>(digestBytes.data()));

        output->assign(utils::string::string_to_hex(digestByteData, digestBytes.size()));
        return true;
    }

 private:
    static bool calculateDigest(std::string_view input,
        std::array<unsigned char, DigestSize> *output) {
        if (output == nullptr) {
            return false;
        }

        const mbedtls_md_info_t *mdInfo = mbedtls_md_info_from_type(DigestType);
        if (mdInfo == nullptr) {
            return false;
        }

        const auto *inputBytes =
            static_cast<const unsigned char *>(static_cast<const void *>(input.data()));

        if (const int ret = mbedtls_md(
                mdInfo,
                inputBytes,
                input.size(),
                output->data()); ret != 0) {
            return false;
        }

        return true;
    }
};


class Sha1 : public DigestImpl<MBEDTLS_MD_SHA1, 20> {
};

}  // namespace modsecurity::Utils

#endif  // SRC_UTILS_SHA1_H_
