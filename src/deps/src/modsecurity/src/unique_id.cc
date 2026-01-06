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

#include "src/unique_id.h"
#include "src/config.h"

#ifdef WIN32
#include "src/compat/msvc.h"
#include <WinSock2.h>
#include <iphlpapi.h>
#endif

#if (defined(__linux__) || defined(__gnu_linux__)) || DARWIN
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#endif

#ifdef DARWIN
#include <ifaddrs.h>
#include <net/if.h>
#include <net/if_dl.h>
#include <sys/types.h>
#ifndef IFT_ETHER
#define IFT_ETHER 0x6 /* Ethernet CSMACD */
#endif
#endif

#if (defined(__linux__) || defined(__gnu_linux__))
#include <linux/if.h>
#include <linux/sockios.h>
#include <sys/ioctl.h>
#endif

#ifdef HAVE_SYS_UTSNAME_H
#include <sys/utsname.h>
#endif

#include <stdio.h>
#ifndef WIN32
#include <unistd.h>
#else
#include <io.h>
#endif
#include <string.h>

#include "src/utils/sha1.h"

namespace modsecurity {

std::once_flag UniqueId::onceFlag;

void UniqueId::fillUniqueId() {
    std::string macAddress;
    std::string name;
    std::string data;

    macAddress = ethernetMacAddress();
    name = machineName();

    data = macAddress + name;

    this->uniqueId_str = Utils::Sha1::hexdigest(data);
}

// Based on:
// http://stackoverflow.com/questions/16858782/how-to-obtain-almost-unique-system-identifier-in-a-cross-platform-way
std::string UniqueId::machineName() {
    char machine_name[MAX_MACHINE_NAME_SIZE];
    size_t len = MAX_MACHINE_NAME_SIZE;
#ifdef WIN32
    DWORD lenComputerName = len;
#endif

    memset(machine_name, '\0', sizeof(char) * len);

#ifdef WIN32
    if (GetComputerName(machine_name, &lenComputerName) == 0) {
        goto failed;
    }
#endif

#ifdef HAVE_SYS_UTSNAME_H
    static struct utsname u;

    if (uname(&u) < 0) {
        goto failed;
    }

    snprintf(machine_name, len-1, "%s", u.nodename);
#endif

    return std::string(machine_name);

#if defined(HAVE_SYS_UTSNAME_H) || defined(WIN32)
failed:
    return std::string("");
#endif
}

std::string UniqueId::ethernetMacAddress() {
    char mac[MAC_ADDRESS_SIZE];
    memset(mac, '\0', sizeof(char)*(MAC_ADDRESS_SIZE));
#ifdef DARWIN
    struct ifaddrs* ifaphead;
    struct ifaddrs* ifap;
    int i = 0;

    if (getifaddrs(&ifaphead) != 0) {
        goto failed;
    }

    // iterate over the net interfaces
    for (ifap = ifaphead; ifap; ifap = ifap->ifa_next) {
        struct sockaddr_dl* sdl = (struct sockaddr_dl*)ifap->ifa_addr;
        if (sdl && (sdl->sdl_family == AF_LINK) && (sdl->sdl_type == IFT_ETHER)
                && mac[0] && mac[1] && mac[2] && i < 6) {
            snprintf(mac, MAC_ADDRESS_SIZE, "%02x:%02x:%02x:%02x:%02x:%02x",
                (unsigned char)LLADDR(sdl)[0],
                (unsigned char)LLADDR(sdl)[1],
                (unsigned char)LLADDR(sdl)[2],
                (unsigned char)LLADDR(sdl)[3],
                (unsigned char)LLADDR(sdl)[4],
                (unsigned char)LLADDR(sdl)[5]);
            break;
        }
    }

    freeifaddrs(ifaphead);
#endif

#if (defined(__linux__) || defined(__gnu_linux__))
    struct ifconf conf;
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    struct ifreq* ifr;
    if ( sock < 0 ) {
        goto failed;
    }

    char ifconfbuf[128 * sizeof(struct ifreq)];
    memset(ifconfbuf, 0, sizeof(ifconfbuf));
    conf.ifc_buf = ifconfbuf;
    conf.ifc_len = sizeof(ifconfbuf);
    if (ioctl(sock, SIOCGIFCONF, &conf)) {
        close(sock);
        goto failed;
    }

    for (ifr = conf.ifc_req; ifr < conf.ifc_req + conf.ifc_len; ifr++) {
        if (ioctl(sock, SIOCGIFFLAGS, ifr)) {
            continue;  // failed to get flags, skip it
        }

        if (ioctl(sock, SIOCGIFHWADDR, ifr) == 0) {
            if (!ifr->ifr_addr.sa_data[0] && !ifr->ifr_addr.sa_data[1]
                && !ifr->ifr_addr.sa_data[2]) {
                continue;
            }

            snprintf(mac, MAC_ADDRESS_SIZE, "%02x:%02x:%02x:%02x:%02x:%02x",
                (unsigned char)ifr->ifr_addr.sa_data[0],
                (unsigned char)ifr->ifr_addr.sa_data[1],
                (unsigned char)ifr->ifr_addr.sa_data[2],
                (unsigned char)ifr->ifr_addr.sa_data[3],
                (unsigned char)ifr->ifr_addr.sa_data[4],
                (unsigned char)ifr->ifr_addr.sa_data[5]);

            break;
        }
    }
    close(sock);
#endif

#if WIN32
    PIP_ADAPTER_INFO pAdapterInfo;
    PIP_ADAPTER_INFO pAdapter = NULL;
    DWORD dwRetVal = 0;

    ULONG ulOutBufLen = sizeof (IP_ADAPTER_INFO);
    pAdapterInfo = reinterpret_cast<IP_ADAPTER_INFO *>(malloc( \
        sizeof (IP_ADAPTER_INFO)));
    if (!pAdapterInfo) {
        goto failed;
    }

    if (GetAdaptersInfo(pAdapterInfo, &ulOutBufLen) == ERROR_BUFFER_OVERFLOW) {
        free(pAdapterInfo);
        pAdapterInfo = reinterpret_cast<IP_ADAPTER_INFO *>(malloc(ulOutBufLen));
        if (!pAdapterInfo) {
            goto failed;
        }
    }

    dwRetVal = GetAdaptersInfo(pAdapterInfo, &ulOutBufLen);
    if (dwRetVal != NO_ERROR) {
        free(pAdapterInfo);
        goto failed;
    }

    pAdapter = pAdapterInfo;
    while (pAdapter && !mac[0] && !mac[1] && !mac[2]) {
        if (pAdapter->AddressLength > 4) {
            snprintf(mac, MAC_ADDRESS_SIZE, "%02x:%02x:%02x:%02x:%02x:%02x",
                (unsigned char)pAdapter->Address[0],
                (unsigned char)pAdapter->Address[1],
                (unsigned char)pAdapter->Address[2],
                (unsigned char)pAdapter->Address[3],
                (unsigned char)pAdapter->Address[4],
                (unsigned char)pAdapter->Address[5]);
            break;
        }
        pAdapter = pAdapter->Next;
    }

    free(pAdapterInfo);
#endif

    return std::string(reinterpret_cast<const char *>(mac));
#if defined(__linux__) || defined(__gnu_linux__) || defined(DARWIN) || defined(WIN32)
failed:
    return std::string("");
#endif
}


}  // namespace modsecurity
