
#include <stdio.h>
#include <string.h>

#include <modsecurity/modsecurity.h>


// Variable offset - REQUEST_HEADERS_NAMES

const char *request = "" \
    "GET /index.html?param1=value1&param2=value1&param3=value1 HTTP/\n" \
    "AuThOrIzAtIoN: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==\n" \
    "Host: localhost\n" \
    "Content-Length: 27\n" \
    "Content-Type: application/x-www-form-urlencoded\n";


int main() {
    modsecurity::ModSecurity msc;
    std::string json("");
    const char *err = NULL;
    int ret = 0;

    ret = msc.processContentOffset(request, strlen(request),
        "o0,4v64,13v114,4v130,14v149,12t:lowercase", &json, &err);

    if (ret >= 0) {
        std::cout << json << std::endl;
    } else {
        std::cout << err << std::endl;
    }

    return ret;
}
