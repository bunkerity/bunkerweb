#!/usr/bin/env python
"""

 ModSecurity, http://www.modsecurity.org/
 Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)

 You may not use this file except in compliance with
 the License.  You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 If any of the files related to licensing are missing or if you have any
 other questions related to licensing please contact Trustwave Holdings, Inc.
 directly using the email address security@modsecurity.org.

 Author: Felipe "Zimmerle" Costa <fcosta at trustwave dot com>

"""

import sys
import unittest

sys.path.append("..")
sys.path.append(".")
import modsecurity


class TestStringMethods(unittest.TestCase):

  def test_version(self):
      self.assertRegexpMatches(str(modsecurity.ModSecurity().whoAmI()), ".*ModSecurity.*")

  def test_load_rules(self):
      rules = modsecurity.Rules()
      ret = rules.load('SecRule ARGS_POST|XML:/* "(\n|\r)" "id:1,deny,phase:2"')
      self.assertEqual(ret, 1)
      ret = rules.load("""
        SecRule ARGS_POST|XML:/* "(\n|\r)" "id:1,deny,phase:2"
        SecRule ARGS_POST|XML:/* "(\n|\r)" "id:2,deny,phase:2"
      """)
      self.assertEqual(ret, 2)
      ret = rules.getRulesForPhase(3)
      self.assertEqual(ret.size(), 3)

  def test_load_bad_rules(self):
      rules = modsecurity.Rules()
      ret = rules.load('SecRule ARGS_POST|XML:/* "(\n|\r)" "deny,phase:2"')
      self.assertEqual(ret, -1)
      ret = rules.getParserError()
      self.assertRegexpMatches(ret, "Rules must have an ID.*")

if __name__ == '__main__':
    unittest.main()

