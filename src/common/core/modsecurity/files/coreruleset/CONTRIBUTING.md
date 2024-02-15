# Contribution Guidelines

**Note:** An HTML version of these guidelines can be found on the CRS documentation site at https://coreruleset.org/docs/development/contribution_guidelines/

> The CRS project values third party contributions. To make the contribution process as easy as possible, a helpful set of contribution guidelines are in place which all contributors and developers are asked to adhere to.

## Getting Started with a New Contribution

1. Sign in to [GitHub](https://github.com/join).
2. Open a [new issue](https://github.com/coreruleset/coreruleset/issues) for the contribution, *assuming a similar issue doesn't already exist*.
    * **Clearly describe the issue**, including steps to reproduce if reporting a bug.
    * **Specify the CRS version in question** if reporting a bug.
    * Bonus points for submitting tests along with the issue.
3. Fork the repository on GitHub and begin making changes there.
4. Signed commits are preferred. (For more information and help with this, refer to the [GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)).

## Making Changes

* Base any changes on branch `main`.
* Create a topic branch for each new contribution.
* Fix only one problem at a time. This helps to quickly test and merge submitted changes. If intending to fix *multiple unrelated problems* then use a separate branch for each problem.
* Make commits of logical units.
* Make sure commits adhere to the contribution guidelines presented in this document.
* Make sure commit messages follow the [standard Git format](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html).
* Make sure changes are submitted as a pull request (PR) on [GitHub](https://github.com/coreruleset/coreruleset/pulls).
    * PR titles should follow the [Conventional Commits format](https://www.conventionalcommits.org/en/v1.0.0/), for example: `fix(rce): Fix a FP in rule 912345 with keyword 'time'`.
    * If a PR only affects a single rule then the rule ID should be included in the title.
    * If a PR title does not follow the correct format then a CRS developer will fix it.

## General Formatting Guidelines for Rules Contributions

* American English should be used throughout.
* 4 spaces should be used for indentation (no tabs).
* Files must end with a single newline character.
* No trailing whitespace at EOL.
* No trailing blank lines at EOF (only the required single EOF newline character is allowed).
* Adhere to an 80 character line length limit where possible.
* Add comments where possible and clearly explain any new rules.
* Comments must not appear between chained rules and should instead be placed before the start of a rule chain.
* All [chained rules](https://github.com/owasp-modsecurity/ModSecurity/wiki/Reference-Manual-(v2.x)#chain) should be indented like so, for readability:
```
SecRule .. .. \
    "..."
    SecRule .. .. \
        "..."
        SecRule .. .. \
            "..."
```
- Action lists in rules must always be enclosed in double quotes for readability, even if there is only one action (e.g., use `"chain"` instead of `chain`, and `"ctl:requestBodyAccess=Off"` instead of `ctl:requestBodyAccess=Off`).
- Always use numbers for phases instead of names.
- Format all use of `SecMarker` using double quotes, using UPPERCASE, and separating words with hyphens. For example:
```
SecMarker "END-RESPONSE-959-BLOCKING-EVALUATION"
SecMarker "END-REQUEST-910-IP-REPUTATION"
```
- Rule actions should appear in the following order, for consistency:
```
id
phase
allow | block | deny | drop | pass | proxy | redirect
status
capture
t:xxx
log
nolog
auditlog
noauditlog
msg
logdata
tag
sanitiseArg
sanitiseRequestHeader
sanitiseMatched
sanitiseMatchedBytes
ctl
ver
severity
multiMatch
initcol
setenv
setvar
expirevar
chain
skip
skipAfter
```
- Rule operators must always be explicitly specified. Although ModSecurity defaults to using the `@rx` operator, for clarity `@rx` should always be explicitly specified when used. For example, write:
```
SecRule ARGS "@rx foo" "id:1,phase:1,pass,t:none"
```
instead of
```
SecRule ARGS "foo" "id:1,phase:1,pass,t:none"
```
 * Only the tags listed in the [util/APPROVED_TAGS](util/APPROVED_TAGS) file can be added to a rule. If you want to add a new tag, you **must** add it to this file.

## Variable Naming Conventions

* Variable names should be lowercase and should use the characters a-z, 0-9, and underscores only.
* To reflect the different syntax between *defining* a variable (using `setvar`) and *using* a variable, the following visual distinction should be applied:
    * **Variable definition:** Lowercase letters for collection name, dot as the separator, variable name. E.g.: `setvar:tx.foo_bar_variable`
    * **Variable use:** Capital letters for collection name, colon as the separator, variable name. E.g.: `SecRule TX:foo_bar_variable`

## Writing Regular Expressions

* Use the following character class, in the stated order, to cover alphanumeric characters plus underscores and hyphens: `[a-zA-Z0-9_-]`

### Portable Backslash Representation

CRS uses `\x5c` to represent the backslash `\` character in regular expressions. Some of the reasons for this are:

* It's portable across web servers and WAF engines: it works with Apache, Nginx, and Coraza.
* It works with the [crs-toolchain](https://coreruleset.org/docs/development/crs_toolchain/) for building optimized regular expressions.

The older style of representing a backslash using the character class `[\\\\]` must _not_ be used. This was previously used in CRS to get consistent results between Apache and Nginx, owing to a quirk with how Apache would "double un-escape" character escapes. For future reference, the decision was made to stop using this older method because:

* It can be confusing and difficult to understand how it works.
* It doesn't work with [crs-toolchain](https://coreruleset.org/docs/development/crs_toolchain/).
* It doesn't work with Coraza.
* It isn't obvious how to use it in a character class, e.g., `[a-zA-Z<portable-backslash>]`.

### Forward Slash Representation

CRS uses literal, *unescaped* forward slash `/` characters in regular expressions.

Regular expression engines and libraries based on PCRE use the forward slash `/` character as the default delimiter. As such, forward slashes are often escaped in regular expression patterns. In the interests of readability, CRS does *not* escape forward slashes in regular expression patterns, which may seem unusual at first to new contributors.

If testing a CRS regular expression using a third party tool, it may be useful to change the delimiter to something other than `/` if a testing tool raises errors because a CRS pattern features unescaped forward slashes.

### When and Why to Anchor Regular Expressions

Engines running the OWASP CRS will use regular expressions to _search_ the input string, i.e., the regular expression engine is asked to find the first match in the input string. If an expression needs to match the entire input then the expression must be anchored appropriately.

#### Beginning of String Anchor (^)

It is often necessary to match something at the start of the input to prevent false positives that match the same string in the middle of another argument, for example. Consider a scenario where the goal is to match the value of `REQUEST_HEADERS:Content-Type` to `multipart/form-data`. The following regular expression could be used:

```python
"@rx multipart/form-data"
```

HTTP headers can contain multiple values, and it may be necessary to guarantee that the value being searched for is the _first_ value of the header. There are different ways to do this but the simplest one is to use the `^` caret anchor to match the beginning of the string:

```python
"@rx ^multipart/form-data"
```

It will also be useful to ignore case sensitivity in this scenario:

```python
"@rx (?i)^multipart/form-data"
```

#### End of String Anchor ($)

Consider, for example, needing to find the string `/admin/content/assets/add/evil` in the `REQUEST_FILENAME`. This could be achieved with the following regular expression:

```python
"@rx /admin/content/assets/add/evil"
```

If the input is changed, it can be seen that this expression can easily produce a false positive: `/admin/content/assets/add/evilbutactuallynot/nonevilfile`. If it is known that the file being searched for can't be in a subdirectory of `add` then the `$` anchor can be used to match the end of the input:

```python
"@rx /admin/content/assets/add/evil$"
```

This could be made a bit more general:

```python
"@rx /admin/content/assets/add/[a-z]+$"
```

#### Matching the Entire Input String

It is sometimes necessary to match the entire input string to ensure that it _exactly_ matches what is expected. It might be necessary to find the "edit" action transmitted by WordPress, for example. To avoid false positives on variations (e.g., "myedit", "the edit", "editable", etc.), the `^` caret and `$` dollar anchors can be used to indicate that an exact string is expected. For example, to only match the _exact_ strings `edit` or `editpost`:

```python
"@rx ^(?:edit|editpost)$"
```

#### Other Anchors

Other anchors apart from `^` caret and `$` dollar exist, such as `\A`, `\G`, and `\Z` in PCRE. CRS **strongly discourages** the use of other anchors for the following reasons:

- Not all regular expression engines support all anchors and the OWASP CRS should be compatible with as many regular expression engines as possible.
- Their function is sometimes not trivial.
- They aren't well known and would require additional documentation.
- In most cases that would justify their use the regular expression can be transformed into a form that doesn't require them, or the rule can be transformed (e.g., with an additional chain rule).

### Use Capture Groups Sparingly

Capture groups, i.e., parts of the regular expression surrounded by parentheses (`(` and `)`), are used to store the matched information from a string in memory for later use. Capturing input uses both additional CPU cycles and additional memory. In many cases, parentheses are *mistakenly* used for grouping and ensuring precedence.

To group parts of a regular expression, or to ensure that the expression uses the precedence required, surround the concerning parts with `(?:` and `)`. Such a group is referred to as being "non-capturing". The following will create a capture group:

```python
"@rx a|(b|c)d"
```

On the other hand, this will create a _non-capturing_ group, guaranteeing the precedence of the alternative _without_ capturing the input:

```python
"@rx a|(?:b|c)d"
```

### Lazy Matching

The question mark `?` can be used to turn "greedy" quantifiers into "lazy" quantifiers, i.e., `.+` and `.*` are greedy while `.+?` and `.*?` are lazy. Using lazy quantifiers can help with writing certain expressions that wouldn't otherwise be possible. However, in backtracking regular expression engines, like PCRE, lazy quantifiers can also be a source of performance issues. The following is an example of an expression that uses a lazy quantifier:

```python
"@rx (?i)\.cookie\b.*?;\W*?(?:expires|domain)\W*?="
```

This expression matches cookie values in HTML to detect session fixation attacks. The input string could be `document.cookie = "name=evil; domain=https://example.com";`.

The lazy quantifiers in this expression are used to reduce the amount of backtracking that engines such as PCRE have to perform (others, such as RE2, are not affected by this). Since the asterisk `*` is greedy, `.*` would match every character in the input up to the end, at which point the regular expression engine would realize that the next character, `;`, can't be matched and it will backtrack to the previous position (`;`). A few iterations later, the engine will realize that the character `d` from `domain` can't be matched and it will backtrack again. This will happen again and again, until the `;` at `evil;` is found. Only then can the engine proceed with the next part of the expression.

Using lazy quantifiers, the regular expression engine will instead match _as few characters as possible_. The engine will match ` ` (a space), then look for `;` and will not find it. The match will then be expanded to ` =` and, again, a match of `;` is attempted. This continues until the match is ` = "name=evil` and the engine finds `;`. While lazy matching still includes some work, in this case, backtracking would require many more steps.

Lazy matching can have the inverse effect, though. Consider the following expression:

```python
"@rx (?i)\b(?:s(?:tyle|rc)|href)\b[\s\S]*?="
```

It matches some HTML attributes and then expects to see `=`. Using a somewhat contrived input, the lazy quantifier will require more steps to match then the greedy version would: `style                     =`. With the lazy quantifier, the regular expression engine will expand the match by one character for each of the space characters in the input, which means 21 steps in this case. With the greedy quantifier, the engine would match up to the end in a single step, backtrack one character and then match `=` (note that `=` is included in `[\s\S]`), which makes 3 steps.

To summarize: **be very mindful about when and why you use lazy quantifiers in your regular expressions**.

### Possessive Quantifiers and Atomic Groups

Lazy and greedy matching change the order in which a regular expression engine processes a regular expression. However, the order of execution does not influence the backtracking behavior of backtracking engines.

Possessive quantifiers (e.g., `x++`) and atomic groups (e.g., `(?>x)`) are tools that can be used to prevent a backtracking engine from backtracking. They _can_ be used for performance optimization but are only supported by backtracking engines and, therefore, are not permitted in CRS rules.

### Writing Regular Expressions for Non-Backtracking Compatibility

Traditional regular expression engines use backtracking to solve some additional problems, such as finding a string that is preceded or followed by another string. While this functionality can certainly come in handy and has its place in certain applications, it can also lead to performance issues and, in uncontrolled environments, open up possibilities for attacks (the term "[ReDoS](https://en.wikipedia.org/wiki/ReDoS)" is often used to describe an attack that exhausts process or system resources due to excessive backtracking).

The OWASP CRS tries to be compatible with non-backtracking regular expression engines, such as RE2, because:

- Non-backtracking engines are less vulnerable to ReDoS attacks.
- Non-backtracking engines can often outperform backtracking engines.
- CRS aims to leave the choice of the engine to the user/system.

To ensure compatibility with non-backtracking regular expression engines, the following operations are **not** permitted in regular expressions:

- positive lookahead (e.g., `(?=regex)`)
- negative lookahead (e.g., `(?!regex)`)
- positive lookbehind (e.g., `(?<=regex)`)
- negative lookbehind (e.g., `(?<!regex)`)
- named capture groups (e.g., `(?P<name>regex)`)
- backreferences (e.g., `\1`)
- named backreferences (e.g., `(?P=name)`)
- conditionals (e.g., `(?(regex)then|else)`)
- recursive calls to capture groups (e.g., `(?1)`)
- possessive quantifiers (e.g., `(?:regex)++`)
- atomic (or possessive) groups (e.g., `(?>regex`))

This list is not exhaustive but covers the most important points. The [RE2 documentation](https://github.com/google/re2/wiki/Syntax) includes a complete list of supported and unsupported features that various engines offer.

### When and How to Optimize Regular Expressions

Optimizing regular expressions is hard. Often, a change intended to improve the performance of a regular expression will change the original semantics by accident. In addition, optimizations usually make expressions harder to read. Consider the following example of URL schemes:

```python
mailto|mms|mumble|maven
```

An optimized version (produced by the [crs-toolchain]({{< ref "crs_toolchain" >}})) could look like this:

```python
m(?:a(?:ilto|ven)|umble|ms)
```

The above expression is an optimization because it reduces the number of backtracking steps when a branch fails. The regular expressions in the CRS are often comprised of lists of tens or even hundreds of words. Reading such an expression in an optimized form is difficult: even the _simple_ optimized example above is difficult to read.

In general, contributors should not try to optimize contributed regular expressions and should instead strive for clarity. New regular expressions will usually be required to be submitted as a `.ra` file for the [crs-toolchain]({{< ref "crs_toolchain" >}}) to process. In such a file, the regular expression is decomposed into individual parts, making manual optimizations much harder or even impossible (and unnecessary with the `crs-toolchain`). The `crs-toolchain` performs some common optimizations automatically, such as the one shown above.

Whether optimizations make sense in a contribution is assessed for each case individually.

## Rules Compliance with Paranoia Levels

The rules in CRS are organized into **paranoia levels** (PLs) which makes it possible to define how aggressive CRS is. See the documentation on [paranoia levels](https://coreruleset.org/docs/concepts/paranoia_levels/) for an introduction and more detailed explanation.

Each rule that is placed into a paranoia level must contain the tag `paranoia-level/N`, where *N* is the PL value, however this tag can only be added if the rule does **not** use the nolog action.

The types of rules that are allowed at each paranoia level are as follows:

**PL 0:**

* ModSecurity / WAF engine installed, but almost no rules

**PL 1:**

* Default level: keep in mind that most installations will normally use this level
* Any complex, memory consuming evaluation rules will surely belong to a higher level, not this one
* CRS will normally use atomic checks in single rules at this level
* Confirmed matches only; all scores are allowed
* No false positives / low false positives: try to avoid adding rules with potential false positives!
* False negatives could happen

**PL 2:**

* [Chain](https://github.com/owasp-modsecurity/ModSecurity/wiki/Reference-Manual-%28v2.x%29#chain) usage is allowed
* Confirmed matches use score critical
* Matches that cause false positives are limited to using scores notice or warning
* Low false positive rates
* False negatives are not desirable

**PL 3:**

* Chain usage with complex regular expression look arounds and macro expansions are allowed
* Confirmed matches use scores warning or critical
* Matches that cause false positives are limited to using score notice
* False positive rates are higher but limited to multiple matches (not single strings)
* False negatives should be a very unlikely accident

**PL 4:**

* Every item is inspected
* Variable creations are allowed to avoid engine limitations
* Confirmed matches use scores notice, warning, or critical
* Matches that cause false positives are limited to using scores notice or warning
* False positive rates are higher (even on single strings)
* False negatives should not happen at this level
* Check everything against RFCs and allow listed values for the most popular elements

## ID Numbering Scheme

The CRS project uses the numerical ID rule namespace from 900,000 to 999,999 for CRS rules, as well as 9,000,000 to 9,999,999 for default CRS rule exclusion packages and plugins.

- Rules applying to the **incoming request** use the ID range 900,000 to 949,999.
- Rules applying to the **outgoing response** use the ID range 950,000 to 999,999.

The rules are grouped by the vulnerability class they address (SQLi, RCE, etc.) or the functionality they provide (e.g., initialization). These groups occupy blocks of thousands (e.g., SQLi: 942,000 - 942,999). These grouped rules are defined in files dedicated to a single group or functionality. The filename takes up the first three digits of the rule IDs defined within the file (e.g., SQLi: `REQUEST-942-APPLICATION-ATTACK-SQLI.conf`).

The individual rules within each file for a vulnerability class are organized by the paranoia level of the rules. PL 1 is first, then PL 2, etc.

The ID block 9xx000 - 9xx099 is reserved for use by CRS helper functionality. There are no blocking or filtering rules in this block.

Among the rules providing CRS helper functionality are rules that skip other rules depending on the paranoia level. These rules always use the following reserved rule IDs: 9xx011 - 9xx018, with very few exceptions.

The blocking and filter rules start at 9xx100 with a step width of 10, e.g., 9xx100, 9xx110, 9xx120, etc.

The ID of a rule does not correspond directly with its paranoia level. Given the size of rule groups and how they're organized by paranoia level (starting with the lower PL rules first), PL 2 and above tend to be composed of rules with higher ID numbers.

### Stricter Siblings

Within a rule file / block, there are sometimes smaller groups of rules that belong together. They're closely linked and very often represent copies of the original rules with a stricter limit (alternatively, they can represent the same rule addressing a different *target* in a second rule, where this is necessary). These are **stricter siblings** of the base rule. Stricter siblings usually share the first five digits of the rule ID and raise the rule ID by one, e.g., a base rule at 9xx160 and a stricter sibling at 9xx161.

Stricter siblings often have different paranoia levels. This means that the base rule and the stricter siblings don't usually reside next to each another in the rule file. Instead, they're ordered by paranoia level and are linked by the first digits of their rule IDs. It's good practice to introduce all stricter siblings together as part of the definition of the base rule: this can be done in the comments of the base rule. It's also good practice to refer back to the base rule with the keywords "stricter sibling" in the comments of the stricter siblings themselves. For example: "...This is performed in two separate stricter siblings of this rule: 9xxxx1 and 9xxxx2", and "This is a stricter sibling of rule 9xxxx0."

## Writing Tests

Each rule should be accompanied by tests. Rule tests are an invaluable way to check that a rule behaves as expected:

- Does the rule correctly match against the payloads and behaviors that the rule is designed to detect? (**Positive tests**)
- Does the rule correctly **not** match against legitimate requests, i.e., the rule doesn't cause obvious false positives? (**Negative tests**)

Rule tests also provide an excellent way to test WAF engines and implementations to ensure they behave and execute CRS rules as expected.

The rule tests are located under `tests/regression/tests`. Each CRS rule *file* has a corresponding *directory* and each individual *rule* has a corresponding *YAML file* containing all the tests for that rule. For example, the tests for rule 911100 *(Method is not allowed by policy)* are in the file `REQUEST-911-METHOD-ENFORCEMENT/911100.yaml`.

Full documentation of the required formatting and available options of the YAML tests can be found at https://github.com/coreruleset/ftw/blob/main/docs/YAMLFormat.md.

Documentation on how to run the CRS test suite can be found in the [online documentation](https://coreruleset.org/docs/development/testing/).

### Positive Tests

Example of a simple *positive test*:

```yaml
- test_title: 932230-26
  desc: "Unix command injection"
  stages:
    - stage:
        input:
          dest_addr: 127.0.0.1
          headers:
            Host: localhost
            User-Agent: "OWASP CRS test agent"
            Accept: text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5
          method: POST
          port: 80
          uri: "/post"
          data: "var=` /bin/cat /etc/passwd`"
          version: HTTP/1.1
        output:
          log_contains: id "932230"
```

This test will succeed if the log output contains `id "932230"`, which would indicate that the rule in question matched and generated an alert.

It's important that tests consistently include the HTTP header fields `Host`, `User-Agent`, and `Accept`. CRS includes rules that detect if these headers are missing or empty, so these headers should be included in each test to avoid unnecessarily causing those rules to match. Ideally, *each positive test should cause* **only** *the rule in question to match*.

The rule's description field, `desc`, is important. It should describe what is being tested: what *should* match, what should *not* match, etc.

### Negative Tests

Example of a simple *negative test*:

```yaml
- test_title: 932260-4
  stages:
    - stage:
        input:
          dest_addr: "127.0.0.1"
          method: "POST"
          port: 80
          headers:
            User-Agent: "OWASP CRS test agent"
            Host: "localhost"
            Accept: text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5
          data: 'foo=ping pong tables'
          uri: '/post'
        output:
          no_log_contains: id "932260"
```

This test will succeed if the log output does **not** contain `id "932260"`, which would indicate that the rule in question did **not** match and so did **not** generate an alert.

### Encoded and Raw Requests

It is possible to *encode* an entire test request. This encapsulates the request and means that the request headers and payload don't need to be explicitly declared. This is useful when a test request needs to use unusual bytes which might break YAML parsers, or when a test request must be intentionally malformed in a way that is impossible to describe otherwise. An encoded request is sent exactly as intended.

The `encoded_request` field works like so:

```yaml
encoded_request: <Base64 string>
```

For example:
```yaml
encoded_request: "R0VUIFwgSFRUUA0KDQoK"
```

where `R0VUIFwgSFRUUA0KDQoK` is the base64-encoded equivalent of `GET \ HTTP\r\n\r\n`.

The older method of using `raw_request` is deprecated as it's difficult to maintain and less portable than `encoded_request`.

### Using The Correct HTTP Endpoint

The CRS project uses [kennthreitz/httpbin](https://hub.docker.com/r/kennethreitz/httpbin) as the backend server for tests. This backend provides one dedicated endpoint for each HTTP method. Tests should target these endpoints to:

- improve test throughput (prevent HTML from being returned by the backend)
- add automatic HTTP method verification (the backend will respond with status code `405` (method not allowed) to requests whose method does not match the endpoint)

Test URIs should be structured as follows, where `<method>` must be replaced by the name of the HTTP method the test uses:

```yaml
#...
          method: <method>
          uri: /<method>/some/arbitrary/url
#...
```

## Further Guidance on Rule Writing

### Leaving Audit Log Configuration Unchanged

Former versions of CRS dynamically included the HTTP response body in the audit log via special `ctl` statements on certain individual response rules. This was never applied in a systematic way and, regardless, CRS should not change the format of the audit log by itself, namely because this can lead to information leakages. Therefore, the use of `ctl:auditLogParts=+E` or any other form of `ctl:auditLogParts` is not allowed in CRS rules.

## Non-Rules General Guidelines

* Remove trailing spaces from files (if they're not needed). This will make linters happy.
* EOF should have an EOL.

The `pre-commit` framework can be used to check for and fix these issues automatically. First, go to the [pre-commit](https://pre-commit.com/) website and download the framework. Then, after installing, use the command `pre-commit install` so that the tools are installed and run each time a commit is made. CRS provides a config file that will keep the repository clean.
