## Proposed changes

Describe the big picture of your changes here to communicate to the maintainers why we should accept this pull request. If it fixes a bug or resolves a feature request, be sure to link to that issue.

<!-- Github Tip: adding the text 'Fixes #<issue>' or 'Closes #<issue>' will automatically close the mentioned issue. -->

## PR Checklist

<!-- _Put an `x` in the boxes that apply. You can also fill these out after creating the PR. If you're unsure about any of them, don't hesitate to ask. We're here to help! This is simply a reminder of what we are going to look for before merging your code._ -->

- [ ] I have read the [CONTRIBUTING](https://github.com/coreruleset/coreruleset/blob/v4.0/dev/CONTRIBUTING.md) doc
- [ ] I have added positive tests proving my fix/feature works as intended.
- [ ] I have added negative tests that prove my fix/feature considers common cases that might end in false positives
- [ ] In case you changed a regular expression, you are not adding a ReDOS for pcre. You can check this using [regexploit](https://github.com/doyensec/regexploit)
- [ ] My test use the `comment` field to write the expected behavior
- [ ] I have added documentation for the rule or change (when appropriate)

## Further comments

<!-- If this is a relatively large or complex change, kick off the discussion by explaining why you chose the solution you did and what alternatives you considered, etc... If there are no additional comments, you may remove this section. -->

## For the reviewer

<!-- Don't remove this part. Reviewers will use it as guidance for the review process. -->

- [ ] Positive and negative tests were added
- [ ] Tests cover the intended fix/feature properly
- [ ] No usage of dangerous constructs like `ctl:requestBodyAccess=Off` were used in the rule
- [ ] In case a regular expression was changed, [there is no ReDOS](https://github.com/coreruleset/coreruleset/wiki/Testing-for-Regular-Expresion-DoS)
- [ ] Documentation is clear for the rule/change
