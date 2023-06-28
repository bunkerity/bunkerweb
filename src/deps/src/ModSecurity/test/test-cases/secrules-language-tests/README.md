# SecRules Test Set (STS)

STS was built to support the development of new implementations of SecRules, and also to avoid regression on the existing ones. The STS does not have any test script, containing only test cases.

This repository does not include all the operators supported by ModSecurity. This repository contains operators that are not supported by ModSecurity yet.

The tests in this repository came from ModSecurity unit tests (originally saved in the format of a Perl script). These tests were converted from Perl to JSON to make them easier to be opened (and parsed) in different platforms.


## How does it work?

All the test cases are saved into text files in JSON format. Every file contains an array of hashes, as illustrated below:

```
   {
      "ret" : 0,
      "type" : "op",
      "name" : "gt",
      "param" : "0",
      "input" : ""
   },
```

The hashes describe the operator to be used with a given parameter and input content to be tested. The outcome result is also part of the hash, allowing the verification if the target application is working as expected.


## Test Organization

The directory "operators" contains unit tests for the SecRules operators. The file names are given after the operator name. Notice that the file name is just a matter of organization, and it does not interfere in the test. The operator name is also made explicit inside the test structure.

The hash that describes a unit test is disposed in the following structure:

 - ret: Return code, can be 1 or 0 (True or False)
 - type: Always "op"
 - name: Operator name
 - param: Operator parameter
 - input: Input data

## How do I add STS to my implementation?

It is recommended to add this repository as a git submodule:

$ git submodule add https://github.com/SpiderLabs/secrules-language-tests
