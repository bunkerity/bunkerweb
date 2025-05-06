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

#include "normalise_path.h"


namespace modsecurity::actions::transformations {


bool NormalisePath::transform(std::string &value, const Transaction *trans) const {
    return normalize_path_inplace(value, false);
}


/**
 *
 * IMP1 Assumes NUL-terminated
 */
bool NormalisePath::normalize_path_inplace(std::string &val, const bool win) {
    int hitroot = 0;
    int done = 0;
    int relative;
    int trailing;

    bool changed = false;

    /* Need at least one byte to normalize */
    if(val.empty()) return false;

    auto input = reinterpret_cast<unsigned char*>(val.data());
    const auto input_len = val.length();

    /*
     * ENH: Deal with UNC and drive letters?
     */

    auto src = input;
    auto dst = input;
    const auto *end = input + (input_len - 1);

    relative = ((*input == '/') || (win && (*input == '\\'))) ? 0 : 1;
    trailing = ((*end == '/') || (win && (*end == '\\'))) ? 1 : 0;

    while (!done && (src <= end) && (dst <= end)) {
        /* Convert backslash to forward slash on Windows only. */
        if (win) {
            if (*src == '\\') {
                *src = '/';
                changed = true;
            }
            if ((src < end) && (*(src + 1) == '\\')) {
                *(src + 1) = '/';
                changed = true;
            }
        }

        /* Always normalize at the end of the input. */
        if (src == end) {
            done = 1;
        } else if (*(src + 1) != '/') {
        /* Skip normalization if this is NOT the
         *end of the path segment. */
            goto copy; /* Skip normalization. */
        }

        /*** Normalize the path segment. ***/

        /* Could it be an empty path segment? */
        if ((src != end) && *src == '/') {
            /* Ignore */
            changed = true;
            goto copy; /* Copy will take care of this. */
        } else if (*src == '.') {
        /* Could it be a back or self reference? */
            /* Back-reference? */
            if ((dst > input) && (*(dst - 1) == '.')) {
                /* If a relative path and either our normalization has
                 * already hit the rootdir, or this is a backref with no
                 * previous path segment, then mark that the rootdir was hit
                 * and just copy the backref as no normilization is possible.
                 */
                if (relative && (hitroot || ((dst - 2) <= input))) {
                    hitroot = 1;

                    goto copy; /* Skip normalization. */
                }

                /* Remove backreference and the previous path segment. */
                dst -= 3;
                while ((dst > input) && (*dst != '/')) {
                    dst--;
                }

                /* But do not allow going above rootdir. */
                if (dst <= input) {
                    hitroot = 1;
                    dst = input;

                    /* Need to leave the root slash if this
                     * is not a relative path and the end was reached
                     * on a backreference.
                     */
                    if (!relative && (src == end)) {
                        dst++;
                    }
                }

                if (done) goto skip_copy; /* Skip the copy. */
                src++;

                changed = true;
            } else if (dst == input) {
                /* Relative Self-reference? */
                changed = true;

                /* Ignore. */

                if (done) goto skip_copy; /* Skip the copy. */
                src++;
            } else if (*(dst - 1) == '/') {
            /* Self-reference? */
                changed = true;

                /* Ignore. */

                if (done) goto skip_copy; /* Skip the copy. */
                dst--;
                src++;
            }
        } else if (dst > input) {
        /* Found a regular path segment. */
            hitroot = 0;
        }

copy:
        /*** Copy the byte if required. ***/

        /* Skip to the last forward slash when multiple are used. */
        if (*src == '/') {
            const unsigned char *oldsrc = src;

            while ((src < end)
                && ((*(src + 1) == '/') || (win && (*(src + 1) == '\\'))) ) {
                src++;
            }
            if (oldsrc != src) changed = true;

            /* Do not copy the forward slash to the root
             * if it is not a relative path.  Instead
             * move over the slash to the next segment.
             */
            if (relative && (dst == input)) {
                src++;
                goto skip_copy; /* Skip the copy */
            }
        }

        *(dst++) = *(src++);

skip_copy:
        ;   // nop for the goto label to work
    }
    /* Make sure that there is not a trailing slash in the
     * normalized form if there was not one in the original form.
     */
    if (!trailing && (dst > input) && *(dst - 1) == '/') {
        dst--;
    }

    /* Always NUL terminate */
    *dst = '\0';

    val.resize(dst - input);
    return changed;
}


}  // namespace modsecurity::actions::transformations
