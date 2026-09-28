# AI-Assisted Contribution Policy

## Purpose

This document establishes guidelines for the responsible use of AI tools (e.g., ChatGPT, Claude, GitHub Copilot, Gemini) when contributing to the OWASP CRS project. The intent is to support contributor productivity while preserving the technical accuracy, originality, and security integrity that CRS demands.

CRS rules are deployed in production WAF environments worldwide. Incorrect regex, flawed detection logic, or poorly constructed tests can result in security bypasses (false negatives) or service disruptions (false positives). This makes human expertise and review non-negotiable.

## Scope

This policy applies to all contributions to CRS repositories, including but not limited to:

- Rule writing (SecLang/CRSlang, regex patterns)
- Test cases (both positive and negative)
- Tooling and scripts (e.g., crs-linter, utilities)
- Documentation and blog posts

## General Principles

1. **AI is a tool, not a substitute for expertise.** Contributors must understand the contributions they submit. AI-generated output that a contributor cannot explain, defend, or independently verify is not acceptable.

2. **Transparency is required.** If AI tools materially assisted in producing a contribution, this must be disclosed in the pull request.

3. **The contributor is accountable.** Regardless of how content was produced, the contributor is responsible for its correctness, security implications, and adherence to CRS coding conventions.

## Permitted Uses

AI tools may be used for supportive tasks, including:

- Exploring regex approaches or brainstorming detection strategies
- Improving clarity, grammar, or structure of documentation
- Generating initial test scaffolding that is then reviewed and adapted
- Learning about SecLang directives, CRS conventions, or ModSecurity behavior
- Refactoring or reformatting existing code

## Rules and Tests: Additional Requirements

Rule writing and test generation carry elevated risk and are subject to additional requirements:

### Rule Contributions

- AI-generated regex patterns **must** be independently validated by the contributor against known attack payloads and legitimate traffic samples before submission.
- Contributors must verify that AI-suggested patterns do not introduce catastrophic backtracking (ReDoS) or overly broad matching.
- All rules must pass [crs-linter](https://github.com/coreruleset/crs-linter) checks. AI tools are not aware of CRS-specific linting constraints unless explicitly guided (see the project's `copilot-instructions.md` where available).
- Do not rely on AI to determine paranoia levels, rule IDs, or phase assignments — these require project context that AI tools typically lack.

### Test Contributions

- AI-generated test payloads must be reviewed for correctness. LLMs frequently produce plausible but non-functional attack vectors or miss edge cases.
- Negative tests (expected to pass without triggering rules) require particular scrutiny — AI tools tend to generate overly simplistic benign samples that do not reflect real-world traffic patterns.
- Test descriptions and comments must accurately reflect what the test validates. Do not submit AI-generated boilerplate descriptions without review.

## Prohibited Uses

AI tools must **not** be used to:

- Generate substantial rule logic or regex that the contributor has not independently reviewed and validated
- Compensate for a lack of understanding of WAF concepts, SecLang syntax, or CRS architecture
- Produce bulk contributions (e.g., mass-generating rules or tests) without proportional manual review
- Circumvent or shortcut the standard review process

## Disclosure Requirements

When AI tools have materially contributed to a pull request, the contributor must disclose the following in the PR description:

1. **Which AI tools were used** (e.g., "GitHub Copilot", "Claude 4", "ChatGPT-4o")
2. **What was generated or assisted** (e.g., "initial regex pattern for SQL injection detection", "test case scaffolding", "documentation wording")
3. **What review was performed** (e.g., "validated regex against SQLi payload corpus", "ran full test suite", "manually reviewed all generated tests")

### PR Template Checkbox

All pull requests include an AI disclosure section. Contributors must complete it honestly.

## Enforcement

- Pull requests with undisclosed AI-generated content that is identified during review may be closed without merge.
- Reviewers are encouraged to ask about AI usage when contributions exhibit common AI-generation patterns (e.g., overly verbose comments, generic variable naming, plausible-but-incorrect regex).
- Repeated violations may result in additional scrutiny of future contributions, consistent with the project's Code of Conduct.

## Rationale

This policy reflects the OWASP Foundation's broader direction on AI in contributions (see the [OWASP GSoC AI Usage Guidelines](https://owasp.org/www-community/initiatives/gsoc/gsoc_ai_usage_guidelines)) and adapts it to the specific risk profile of CRS, where rule accuracy directly impacts the security posture of downstream users.
