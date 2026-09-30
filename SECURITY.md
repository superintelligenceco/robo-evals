# Security policy

## Supported versions

Security fixes land on the latest minor release.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Report a vulnerability

Don't open a public issue for a security problem. Report it privately through
[GitHub private vulnerability reporting](https://github.com/superintelligenceco/robo-evals/security/advisories/new).

Include the version, the command you ran, and the smallest input that reproduces the problem. You
get an acknowledgment within 5 business days. After the fix ships, the advisory is published with
credit to you unless you ask otherwise.

## Trust model

- `--policy module:attr` and `--policy path/to/file.py:attr` import and run the code you name.
  Only evaluate policies you trust, as you would with any Python import.
- `robo-evals serve` and `examples/policy_server.py` have no authentication and bind to
  `127.0.0.1` by default. If you bind them to another interface, put them behind a network
  boundary you control.
- The remote client sends observations to the URL you give it and nothing else.

In scope:

- A malformed server reply or report file that makes the harness execute code or write outside the
  output directory.
- A way to make a report show a success rate that the episodes didn't produce.

A wrong success predicate or a nondeterministic result is a bug, not a vulnerability. Open a
regular issue for it.
