# RouterOS v6 User Manager bulk-read research

**Status:** design investigation only. No RouterOS device was contacted. No bulk reader is enabled, and no import or source-side write is performed.

## Verified from the current code

- Backend pins `routeros-api==0.17.0`.
- The adapter uses `RouterOsResource.call(command, arguments, queries)` for API requests.
- The current `_count_only` helper issues `print count-only` and reads the returned `ret` value. It can supply RouterOS query filters separately from command attributes.
- The current individual-user diagnostic first counts an exact username match, then requests a limited `.proplist`. This is a single-record diagnostic, not a bulk retrieval strategy.
- `user_manager_batches.py` and `user_manager_preview_batches.py` provide bounded orchestration and atomic persistence, but deliberately depend on a source reader that already enforces a page limit. They do not implement RouterOS pagination.

## What the protocol documentation establishes

The official RouterOS API documentation establishes that:

1. `print` accepts query words for server-side filtering.
2. Query words support exact matches, presence checks, less-than and greater-than comparisons, and boolean stack operations.
3. `.proplist` limits the requested properties.
4. Regular expressions are not supported in API query words.
5. The documented `print` interface does not define general `offset` or `limit` parameters.

The `routeros-api 0.17.0` resource implementation exposes command arguments and query dictionaries; it does not add a generic page/offset abstraction. The library's documented count-only example reads the count from the final `ret` value. A count-only request is useful for preflight, but it does not make a later full `print` response bounded.

### Additional library finding: comparison queries can be encoded

The pinned library does have a lower-level escape hatch for query words beyond its simple equality-query dictionary:

- `RouterOsResource.call(..., additional_queries=...)` forwards query objects to the API communicator.
- `routeros_api.query.IsGreaterQuery`, `IsLessQuery`, and `AndQuery` encode query words such as `?>username=value`, `?<username=value`, and `?#&`.
- A focused backend unit test now verifies this exact serialization using the pinned dependency.

This is a useful implementation capability, but it is **not** evidence that the User Manager v6 `user` menu correctly applies lexical comparisons to `username`, nor that such ranges provide complete, stable, bounded partitions. The current official API manual surfaced during this investigation is for RouterOS 7.26; its query grammar must not be treated as a substitute for testing the user's exact v6 release and User Manager package.

The next safe technical step is therefore a disposable-lab test of the actual User Manager resource. Do not connect this query builder to production batch fetching until the resource-specific tests pass.


References:
- MikroTik RouterOS API: https://manual.mikrotik.com/docs/developer-guides/api/
- RouterOS API library 0.17.0 resource implementation: https://github.com/socialwifi/RouterOS-api/blob/0.17.0/routeros_api/resource.py
- RouterOS API library 0.17.0 usage documentation: https://github.com/socialwifi/RouterOS-api/tree/0.17.0

## Decision

**Do not implement or run bulk User Manager reads yet.**

Do not:
- call an unfiltered users `print` and slice the response in Python;
- assume `offset`, `limit`, `from`, or `count` provide bounded API pages;
- treat `count-only` as a page-size guarantee;
- infer stable ordering from the order in which `print` happens to return records;
- use a username range query as pagination until its behavior is demonstrated on the target RouterOS v6 User Manager version.

Query-range partitioning using `<` and `>` is a candidate for investigation, not a proven paging method. It only becomes acceptable if the target User Manager resource applies those comparisons consistently to the chosen key, every partition can be bounded before details are fetched, partition boundaries are exhaustive and non-overlapping, and repeated runs prove there are no missing or duplicate records. The API documentation alone does not prove those properties for User Manager usernames.

## Required isolated lab validation

Before writing a production bulk reader, use a disposable RouterOS v6 test instance or a specifically approved test router and a small synthetic User Manager dataset. Do not run these experiments against production cards.

1. Record the exact RouterOS and User Manager package versions and available memory.
2. Confirm exact-match query behavior for both `count-only` and `print` on the User Manager user resource.
3. Test `<username=` and `>username=` on usernames containing numeric, alphabetic, mixed-case, punctuation, and non-ASCII characters where supported.
4. Verify the comparison order and boundary inclusion/exclusion; do not assume locale or lexical behavior.
5. Build a complete partition plan and compare the union of partition results against a separately verified small test inventory. Assert zero missing IDs, zero duplicates, and stable counts.
6. Measure response size, elapsed time, CPU, memory, and timeout behavior at gradually increasing test sizes.
7. Repeat while records are added or removed between requests. If the result can skip or repeat records, require a source snapshot/freeze window or reject the approach.
8. Only after these checks, define a page contract with a server-enforced maximum, stable continuation cursor, and explicit restart behavior.

If query partitioning cannot guarantee a bounded response for every possible supported username, stop and evaluate a different supported export mechanism rather than falling back to an unbounded API read.

## Separate resource plans

- **Users/cards:** no bulk read until bounded partitioning is proven.
- **Profiles and limitations:** investigate separately; their expected cardinality is smaller, but still use count preflight and explicit property lists.
- **Active sessions:** separate live snapshot; never merge these rows into historical sessions without a stable source identity.
- **Historical sessions:** separate reader and validation. Do not assume session fields, retention, or stable IDs from the user resource.
- **Customers and profile-limitation relations:** read only after resource-specific field and relation behavior is verified.

## Safety gates

- Read-only API account with least privileges.
- API-SSL preferred; do not send v6.43+ plaintext-login credentials over an untrusted network.
- Short connection/read timeouts and bounded retry policy.
- Per-run record, page, elapsed-time, and memory budgets.
- Atomic persistence of each accepted page and its checkpoint.
- Idempotency based on source identity; changed source snapshots must be reconciled, not silently overwritten.
- No passwords in previews, logs, checkpoints, or this research document.
- No source writes, card imports, cutover, or production-device test without explicit approval.

## Current outcome

The existing bounded batch runner and transactional preview persistence are useful foundations, but they must remain disconnected from a real RouterOS bulk source until the lab validation above passes. The next implementation step is a test harness/specification for source-side partition experiments, not a production bulk reader.
