/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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


#ifdef __cplusplus
#include <string>
#include <chrono>
#endif


#ifndef SRC_COLLECTION_DATA_H_
#define SRC_COLLECTION_DATA_H_

#ifdef __cplusplus
namespace modsecurity {
namespace collection {
namespace backend {

class CollectionData {
public:
    CollectionData() :
        m_hasValue(false),
	m_hasExpiryTime(false) { }

    CollectionData(const std::string &value) :
        m_hasValue(true),
	m_hasExpiryTime(false),
	m_value(value) { }

    void setValue(const std::string &value) {
        m_value = value;
        m_hasValue = true;
    }
    bool hasValue() const { return m_hasValue;}
    const std::string& getValue() const { return m_value;}

    void setExpiry(int32_t seconds_until_expiry);
    bool hasExpiry() const { return m_hasExpiryTime;}
    bool isExpired() const;

    std::string getSerialized() const;
    void setFromSerialized(const char* serializedData, size_t length);

private:
    bool m_hasValue;
    bool m_hasExpiryTime;
    std::string m_value;
    std::chrono::system_clock::time_point m_expiryTime;
};

}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
#endif

#endif  // SRC_COLLECTION_DATA_H_
