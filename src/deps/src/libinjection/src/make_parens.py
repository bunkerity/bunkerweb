#!/usr/bin/env python3
# pylint: disable=C0103,R0911,R0912,R0915
# disable short-variable-names, too many branches, returns, statements
"""
fingerprint fuzzer and generator

Given a fingerprint, this generates other similar fingerprints
that are functionally equivalent for SQLi detection
"""

import sys

class PermuteFingerprints(object):
    """ class to mutate / fuzz fingerprints to find new SQLi """

    def __init__(self):
        """ initialization """
        self.fingerprints = set()
        self.blacklist = set([
            'E1n', 'sns', '1&n', 's1s', '1n1', '1o1', '1os', 'sn1',
            'sonc', 'so1', 'n&n', 'son', 'nov', 'n&s', 'E1s', 'nos',
            'nkn&n', '1sn', 'n&nkn', 's1n', 'n&nEn', 's&sn', '1os1o',
            'sU', 'nU', 'n,(n)', 'n&n&n', 'Enkn', 'nk1;',
            '1os1o', '1n1;', 's*1s', '1s1', 'nknEn', 'n&sn',
            'so1', 'nkn;', 'n&n;', 'von', 'n&nc', 'sonkn',
            'n)o1', 'Enn;', 'nBn', 'Ennc', 'n&En', 'nEnEn', 'Esn',
            'n1s', 'n(1)s', 'En1', 'En(1)', 'n(1)n', 'n1v',
            'n(1)1', 'n&EUE', 'n&EkU', 's&EUE', 's&EkU', 'v&EUE', 'v&EkU',
            'n&nTn', 'nA', 'nos;n', 'UEn', 'so1no', '1)on', '1k(1)',
            's)on', '1;TnE', 's&1s', 'n)c', 'svs', '1n(1)',
            'so1s(', 'son1s', 'nf(1n', 'so1sf', 'son1s', 'nf(n)', 'En1c',
            'n)on', "nok&n", "n;Tkn",
            "nEnc",
            "nok&1",
            "nok&f",
            "nok&s",
            "nok&v",
            "nk(n)",
            "nknc",
            "son1n",
            "n&nBn",
            ])
        self.whitelist = set([
            'T(vv)', 'Tnvos', 'Tnv;', '1UEnn', '1;Tvk'
            ])

    def aslist(self):
        """
        return the fingerprints as a sorted list
        """
        return sorted(list(self.fingerprints))

    def insert(self, fingerprint):
        """
        insert a new fingerprint, with possible variations
        """
        if len(fingerprint) > 5:
            fingerprint = fingerprint[0:5]
        if self.validate(fingerprint):
            self.fingerprints.add(fingerprint)

    def validate(self, s):
        """
        detemines if a fingerprint could be used a SQLi
        """
        if len(s) == 0:
            return False
        if s in self.whitelist:
            return True
        if s in self.blacklist:
            return False

        # SQL Types are rarely used
        if 't' in s and 'f(t' not in s and 'At' not in s:
            return False

        if 'Un' in s:
            return False
        if '1nf' in s:
            return False
        if 's1o' in s:
            return False
        if 'oo' in s:
            return False
        if 'v,s' in s:
            return False
        if 's,v' in s:
            return False
        if 'v,v' in s:
            return False
        if 'v,1' in s:
            return False
        if 'v,n' in s:
            return False
        if 'n,v' in s:
            return False
        if '1,v' in s:
            return False
        if 'Eo(' in s:
            return False
        if '(o(' in s:
            return False
        if '(o1' in s:
            return False
        if '(on' in s:
            return False
        if '(os' in s:
            return False
        if '(of' in s:
            return False
        if '(ov' in s:
            return False
        if 'B(n)' in s:
            return False
        if 'oso' in s:
            return False
        if 'o1o' in s:
            return False
        if 'ono' in s:
            return False

        # only 1 special case for this
        # 1;foo:goto foo
        # 1;n:k
        # the 'foo' can only be a 'n' type
        if ':' in s and not 'n:' in s:
            return False

        if '11' in s:
            return False

        if '))' in s:
            return False
        if '((' in s:
            return False
        if 'v1' in s:
            return False

        if 'nv' in s and 'T' not in s:
            return False
        if 'nn' in s and 'T' not in s:
            return False

        # select @version foo is legit
        # but unlikely anywhere else
        if 'vn' in s and 'Evn' not in s:
            return False

        if 'oE' in s:
            return False

        if 'A1' in s:
            return False
        if 'An' in s:
            return False
        if 'A(1' in s:
            return False

        if 'vov' in s:
            return False
        if 'vo1' in s:
            return False
        if 'von' in s:
            return False

        if 'ns' in s:
            if 'U' in s:
                return True
            if 'T' in s:
                return True
            return False

        if 'sn' in s:
            # that is... Tsn is ok
            if s.find('T') != -1 and s.find('T') < s.find('sn'):
                return True
            return False

        # select foo (as) bar is only nn type i know
        if 'nn' in s and 'Enn' not in s and 'T' not in s:
            return False

        if ',o' in s:
            return False

        if 'kk' in s and 'Tkk' not in s:
            return False

        if 'ss' in s:
            return False

        if 'ff' in s:
            return False

        if '1no' in s:
            return False

        if 'kno' in s:
            return False

        if 'nEk' in s:
            return False

        if 'n(n' in s:
            return False
        if '1so' in s:
            return False
        if '1s1' in s:
            return False
        if 'noo' in s:
            return False
        if 'ooo' in s:
            return False

        if 'vvv' in s:
            return False

        if '1vn' in s:
            return False
        if '1n1' in s:
            return False
        if '&1n' in s:
            return False
        if '&1v' in s:
            return False
        if '&1s' in s:
            return False
        if 'nnk' in s:
            return False
        if 'n1f' in s:
            return False
        # folded away
        if s.startswith('('):
            return False

        if '&o' in s:
            return False

        if '1,1' in s:
            return False
        if '1,s' in s:
            return False
        if '1,n' in s:
            return False
        if 's,1' in s:
            return False
        if 's,s' in s:
            return False
        if 's,n' in s:
            return False
        if 'n,1' in s:
            return False
        if 'n,s' in s:
            return False
        if 'n,n' in s:
            return False
        if '1o1' in s:
            return False
        if '1on' in s:
            return False
        if 'no1' in s:
            return False
        if 'non' in s:
            return False
        if '1(v' in s:
            return False
        if '1(n' in s:
            return False
        if '1(s' in s:
            return False
        if '1(1' in s:
            return False
        if 's(s' in s:
            return False
        if 's(n' in s:
            return False
        if 's(1' in s:
            return False
        if 's(v' in s:
            return False
        if 'v(s' in s:
            return False
        if 'v(n' in s:
            return False
        if 'v(1' in s and 'Tv(1' not in s:
            return False
        if 'v(v' in s:
            return False
        if 'TTT' in s:
            return False
        if s.startswith('n('):
            return False
        if s.startswith('vs'):
            return False

        if s.startswith('o'):
            return False

        if ')(' in s:
            return False

        # need to investigate T(vv) to see
        # if it's correct
        if 'vv' in s and s != 'T(vv)':
            return False

        # unlikely to be sqli but case FP
        if s in ('so1n)', 'sonoE'):
            return False

        return True

    def permute(self, fp):
        """
        generate alternative (possiblely invalid) fingerprints
        """
        self.insert(fp)

        # do this for safety
        if len(fp) > 1 and len(fp) < 5 and fp[-1] != ';' and fp[-1] != 'c':
            self.insert(fp + ";")
            self.insert(fp + ";c")

        # do this for safety
        if len(fp) > 1 and len(fp) < 5 and fp[-1] != 'c':
            self.insert(fp + "c")

        for i in range(len(fp)):
            if fp[i] == '1':
                self.insert(fp[0:i] + 'n'    + fp[i+1:])
                self.insert(fp[0:i] + 'v'    + fp[i+1:])
                self.insert(fp[0:i] + 's'    + fp[i+1:])
                self.insert(fp[0:i] + 'f(1)' + fp[i+1:])
                self.insert(fp[0:i] + 'f()'  + fp[i+1:])
                self.insert(fp[0:i] + '1os'  + fp[i+1:])
                self.insert(fp[0:i] + '1ov'  + fp[i+1:])
                self.insert(fp[0:i] + '1on'  + fp[i+1:])
                self.insert(fp[0:i] + '(1)'  + fp[i+1:])
            elif fp[i] == 's':
                self.insert(fp[0:i] + 'v'    + fp[i+1:])
                self.insert(fp[0:i] + '1'    + fp[i+1:])
                self.insert(fp[0:i] + 'f(1)' + fp[i+1:])
                self.insert(fp[0:i] + 'f()'  + fp[i+1:])
                self.insert(fp[0:i] + 'so1'  + fp[i+1:])
                self.insert(fp[0:i] + 'sov'  + fp[i+1:])
                self.insert(fp[0:i] + 'son'  + fp[i+1:])
                self.insert(fp[0:i] + '(s)'  + fp[i+1:])
            elif fp[i] == 'v':
                self.insert(fp[0:i] + 's'    + fp[i+1:])
                self.insert(fp[0:i] + '1'    + fp[i+1:])
                self.insert(fp[0:i] + 'f(1)' + fp[i+1:])
                self.insert(fp[0:i] + 'f()'  + fp[i+1:])
                self.insert(fp[0:i] + 'vo1'  + fp[i+1:])
                self.insert(fp[0:i] + 'vos'  + fp[i+1:])
                self.insert(fp[0:i] + 'von'  + fp[i+1:])
                self.insert(fp[0:i] + '(v)'  + fp[i+1:])
            elif fp[i] == 'E':
                # Select top, select distinct, case when
                self.insert(fp[0:i] + 'Ek'   + fp[i+1:])
            elif fp[i] == ')':
                self.insert(fp[0:i] + '))'   + fp[i+1:])
                self.insert(fp[0:i] + ')))'  + fp[i+1:])
                self.insert(fp[0:i] + '))))' + fp[i+1:])
        if ';E' in fp:
            self.insert(fp.replace(';E', ';T'))
        if fp.startswith('T'):
            self.insert('1;' + fp)
            self.insert('1);' + fp)

        if 'At' in fp:
            self.insert(fp.replace('At', 'As'))

        if '(' in fp:

            done = False
            parts = []
            for char in fp:
                if char == '(' and done is False:
                    parts.append(char)
                    done = True
                parts.append(char)
            newline = ''.join(parts)
            self.insert(newline)

            done = False
            parts = []
            for char in fp:
                if char == '(':
                    if done is True:
                        parts.append(char)
                    else:
                        done = True
                parts.append(char)
            newline = ''.join(parts)
            self.insert(newline)

            done = False
            parts = []
            for char in fp:
                if char == '(':
                    parts.append(char)
                parts.append(char)
            newline = ''.join(parts)
            self.insert(newline)


def main():
    """ main entrance """
    mutator = PermuteFingerprints()

    for line in sys.stdin:
        mutator.permute(line.strip())

    for fingerprint in mutator.aslist():
        print(fingerprint)


if __name__ == '__main__':
    main()

