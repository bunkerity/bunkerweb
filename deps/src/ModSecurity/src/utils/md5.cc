

#include "src/utils/md5.h"
#include "others/mbedtls/md5.h"

namespace modsecurity {
namespace Utils {


std::string Md5::hexdigest(std::string& input) {
    unsigned char digest[16];

    mbedtls_md5(reinterpret_cast<const unsigned char *>(input.c_str()),
        input.size(), digest);

    char buf[33];
    for (int i = 0; i < 16; i++) {
        sprintf(buf+i*2, "%02x", digest[i]);
    }

    return std::string(buf, 32);
}


std::string Md5::digest(std::string& input) {
    unsigned char output[16];
    std::string ret;

    mbedtls_md5(reinterpret_cast<const unsigned char *>(input.c_str()),
        input.size(), output);

    ret.assign(reinterpret_cast<const char *>(output), 16);

    return ret;
}


}  // namespace Utils
}  // namespace modsecurity

