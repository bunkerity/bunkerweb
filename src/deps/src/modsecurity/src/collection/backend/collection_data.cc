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

#include "src/collection/backend/collection_data.h"


namespace modsecurity {
namespace collection {
namespace backend {


bool CollectionData::isExpired() const {
    if (m_hasExpiryTime == false) {
        return false;
    }
    auto now = std::chrono::system_clock::now();
    return (now >= m_expiryTime);
}


void CollectionData::setExpiry(int32_t seconds_until_expiry) {
    m_expiryTime = std::chrono::system_clock::now() + std::chrono::seconds(seconds_until_expiry);
    m_hasExpiryTime = true;
}

std::string CollectionData::getSerialized() const {
    std::string serialized;
    if (hasValue()) {
        serialized.reserve(30 + 10 + getValue().size());
    } else {
        serialized.reserve(16+10);
    }

    serialized.assign("{");

    if (hasExpiry()) {
        serialized.append("\"__expire_\":");
        uint64_t expiryEpochSeconds = std::chrono::duration_cast<std::chrono::seconds>(m_expiryTime.time_since_epoch()).count();
        serialized.append(std::to_string(expiryEpochSeconds));
	if (hasValue()) {
            serialized.append(",");
	}
    }
    if (hasValue()) {
        serialized.append("\"__value_\":\"");
        serialized.append(getValue());
        serialized.append("\"");
    }

    serialized.append("}");

    return serialized;
}

void CollectionData::setFromSerialized(const char* serializedData, size_t length) {
    const static std::string expiryPrefix("\"__expire_\":");
    const static std::string valuePrefix("\"__value_\":\"");
    m_hasValue = false;
    m_hasExpiryTime = false;

    std::string serializedString(serializedData, length);
    if ((serializedString.find("{") == 0) && (serializedString.substr(serializedString.length()-1) == "}")) {
        size_t currentPos = 1;
        uint64_t expiryEpochSeconds = 0;
        bool invalidSerializedFormat = false;
        bool doneParsing = false;

        // Extract the expiry time, if it exists
        if (serializedString.find(expiryPrefix, currentPos) == currentPos) {
            currentPos += expiryPrefix.length();
            std::string expiryDigits = serializedString.substr(currentPos, 10);
            if (expiryDigits.find_first_not_of("0123456789") == std::string::npos) {
                expiryEpochSeconds = strtoll(expiryDigits.c_str(), NULL, 10);
            } else {
                invalidSerializedFormat = true;
	    }
            currentPos += 10;
        }

        if ((!invalidSerializedFormat) && (expiryEpochSeconds > 0)) {
            if (serializedString.find(",", currentPos) == currentPos) {
                currentPos++;
            } else if (currentPos == serializedString.length()-1) {
	        doneParsing = true;
	    } else {
                invalidSerializedFormat = true;
	    }
	}

        if ((!invalidSerializedFormat) && (!doneParsing)) {
            // Extract the value
            if ((serializedString.find(valuePrefix, currentPos) == currentPos)) {
                currentPos += valuePrefix.length();
                size_t expectedCloseQuotePos = serializedString.length() - 2;
                if ((serializedString.substr(expectedCloseQuotePos, 1) == "\"") && (expectedCloseQuotePos >= currentPos)) {
                    m_value = serializedString.substr(currentPos);
                    m_value.resize(m_value.length()-2);
                    m_hasValue = true;
                } else {
                    invalidSerializedFormat = true;
                }
            } else {
                invalidSerializedFormat = true;
            }
        }

        // Set the object's expiry time, if we found one
        if ((!invalidSerializedFormat) && (expiryEpochSeconds > 0)) {
            std::chrono::seconds expiryDuration(expiryEpochSeconds);
            std::chrono::system_clock::time_point expiryTimePoint(expiryDuration);
            m_expiryTime = expiryTimePoint;
            m_hasExpiryTime = true;
	}
        if (!invalidSerializedFormat) {
            return;
	}
    }

    // this is the residual case; the entire string is a simple value (not JSON-ish encoded)
    // the foreseen case here is lmdb content from prior to the serialization support
    m_value.assign(serializedData, length);
    m_hasValue = true;
    return;
}

}  // namespace backend
}  // namespace collection
}  // namespace modsecurity
