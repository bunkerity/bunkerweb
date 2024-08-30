import argparse

# WARNING: This script is EXPERIMENTAL. Use with caution.
#
# Known issues:
#   * At the moment, it will probably not work with more than two strings.
#
# Known limitations:
#   * Any substrings of a target string will also NOT be matched. This is probably due to a limitation in this technique,
#   make sure that subtrings of the negative lookahead are not harmful in any way.

parser = argparse.ArgumentParser(description="This script takes a list of strings and converts them into \
    a regex that acts like a negative lookahead")
parser.add_argument("strings", type=str, nargs='+',
    help="the strings to convert into a negative lookahead")
parser.add_argument("--prefix", type=str, default="",
    help="sets a prefix for the resulting regex")
parser.add_argument("--suffix", type=str, default="",
    help="sets a suffix for the resulting regex")

args = parser.parse_args()

# Return the longest prefix of all list elements. Shamelessly copied from:
# https://stackoverflow.com/questions/6718196/determine-the-common-prefix-of-multiple-strings
def commonprefix(m):
    "Given a list of pathnames, returns the longest common leading component"
    if not m: return ''
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1

# flatten returns a string with concatenated dictionary keys
def flatten(dict):
    s = ""

    for key in dict.keys():
        s += key

    return s

# set returns a character set containing the unique characters across all strings for the given index
def set(strings, index, flags):
    dict = {}

    for s in strings:
        # Continue so we don't panic
        if index > len(s) -1:
            continue
        
        dict[s[index]] = ''
    
    return "[" + flags + flatten(dict) + "]"

# prepare converts a string for negative lookaheads emulation
def prepare(s, offset):
    r = ""

    if len(s) == 0:
        return r

    for i in range(offset, len(s)):
        for j in range(0, i + 1):
            if j == i:
                r += "[^" + s[j] + "]"
            else:
                r += s[j]

        if i != len(s) - 1:
            r += "|"

    return r

# run runs the 
def run():
    strings = args.strings

    r = ""
    r += set(strings, 0, "^")

    c = ""
    d = {}

    # Only find common string if we have more than one
    if len(strings) > 1:
        c = commonprefix(strings)
        
        # Collect all characters after the common substring from every string
        for s in strings:
            if len(s) > len(c) and s.startswith(c):
                d[s[len(c)]] = ''

    # Add the common string to the regex to prevent accidental matching
    if len(c) > 0:
        if len(c) > 1:
            r += "|" +  "(?:" + prepare(c, 1) + ")"

        r +=  "|" + "(?:" + c + "[^" + flatten(d) + "]" + ")"

    for s in strings:
        g = ""

        # When the common string is > 0, offset with len(c) + 1 because we handled this earlier
        if len(c) > 0:
            g = prepare(s, len(c) + 1)
        else:
            g = prepare(s, 1)
        
        # Add OR boolean if necessary
        if len(g) > 0:
            r += "|"

        r += g

    print(args.prefix + "(?:" + r + ")" + args.suffix)

# Only run if script is called directly
if __name__ == "__main__":
    run()
