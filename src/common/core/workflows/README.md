The Workflows plugin adds the policy layer between single settings and the Lua protections: reusable, ordered rules you attach to services, each pairing a condition tree with one action.

A rule answers a question the individual settings cannot express on their own:

> **If** the request comes from France **and** targets `/login`, **and** it exceeds 10 requests per minute, **then** show an hCaptcha challenge.

Workflows **orchestrate** the existing protections rather than replacing them. A `challenge` action hands the request to Antibot; a rate threshold uses the same counter Limit uses. Every setting you already have keeps working.

### How a rule is evaluated

For each service, its attached workflows are evaluated in attachment order, and the rules inside each workflow in the order you arranged them. **The first rule that effectively matches wins** and runs its single action; nothing after it is evaluated.

A condition is a tree of `ALL` / `ANY` / `NOT` nodes over:

| Condition | Matches on |
|---|---|
| IP / CIDR | the effective client IP, after Real-IP resolution |
| Country | the ISO country resolved from the GeoIP database |
| ASN | the autonomous system number of the client IP |
| URI | the normalised path — exact, prefix or regular expression |
| HTTP method | the request method |
| Resource group | an IP, country or ASN group you maintain elsewhere, referenced by id |

Conditions are **three-valued**. A predicate is true, false, or *unknown* when the fact it needs is unavailable — a missing GeoIP database, for example. A rule only matches when its tree resolves to true, so a broken database makes a rule stop matching rather than start matching by accident.

### Rate thresholds are a gate, not an action

A rule may carry a threshold. It is not "then rate-limit": it decides **whether the rule matches at all**. Below the threshold the rule loses and evaluation continues with the next rule.

That is what lets you express "above 10 requests per minute answer 429, otherwise show a challenge" as two ordered rules with the same conditions — the first with the threshold and a block, the second without.

The counter is scoped to service + rule + client IP, so it never interferes with the `LIMIT_REQ_*` counters.

### Actions

* **challenge** — show a specific Antibot provider (`captcha`, `hcaptcha`, `turnstile`, …). It works even on a service where `USE_ANTIBOT` is `no`, and it overrides Antibot's own ignore lists: the exclusions you want belong in the rule's conditions. The service must already hold that provider's credentials.
* **block** — answer with the instance's deny status, or `429` for a rule whose purpose is capping a rate.
* **redirect** — send the client to a fixed URL with a 301/302/303/307/308.

### Detect mode

`SECURITY_MODE=detect` runs the identical trees, in the identical order, with the identical rate counters — but enforces nothing. The action that *would* have been taken is recorded in the reports, so a policy can be measured on real traffic before it is turned on.

### Failure behaviour

An instance that has not received the compiled policy yet — first boot, or a push that never arrived — logs one error and serves traffic under its ordinary protections. Conversely, a policy the control plane cannot compile is never distributed at all: the push is abandoned and every instance keeps the policy it already had. Deleting a resource group a rule references is refused while that rule exists.

### Managing workflows

Everything is done from the **Workflows** page of the web UI, or through the `/workflows` API endpoints. Rules are stored centrally and compiled into a single artefact distributed to every instance with the usual configuration push.
