# Release workflow validation

Prepared October 13, 2026. Not deployed to Bluehost or the Pi.

Eight Python tests passed, covering an allowlisted source/binary archive, checksums and versions, exact-package retry, immutable labels, path/symlink rejection, persistent report retry, no flash after archive failure, no activation after upload/firmware verification failure, and activation with a queued final report after transport failure. Compilation/upload and serial verification were simulated; the saved source version entry point ran locally.

Twenty-four PHP checks passed using the available PHP 8.3 WebAssembly runtime with an isolated SQLite database. They cover syntax; wrong credentials; retired/non-opted-in components; bad archive hashes and paths; idempotent archive/deployment retries; immutable labels; version mismatches; terminal-state conflicts; anonymous/staff denial; administrator rendering and HTML escaping; and authenticated download checksums/corruption rejection.

The tests replace MySQL connection and FOR UPDATE semantics with SQLite and stub the pre-existing rate limiter. They do not establish MySQL concurrency, hosting configuration, production source compatibility, live authentication flows, browser layout, or physical upload behavior. The portal page reuses the existing portal CSS; its output was generated locally but has not been inspected in a browser.

Reproduction in this workspace:

```sh
python3 -m unittest discover -s development/releases/tests -v
/Users/EXAMPLE_USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node development/releases/tests/portal-checks.cjs
```

Live acceptance steps and known limits are in README.md. No production files, database tables, credentials, or running services were changed.
