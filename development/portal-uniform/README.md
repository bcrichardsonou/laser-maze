# Uniform exhibit dashboards v1

Prepared October 13, 2026. Not yet installed or verified on Bluehost.

Both detailed dashboards and read-only viewing pages use Overview, Activity & outcomes, Equipment & components, and Recent history in that order. Remote access and Technical details remain private. Shared semantic section IDs give matching defaults and browser-local collapse preferences; section shortcuts open collapsed sections. Native details elements work without JavaScript. A self-hosted script is enabled through script-src 'self'; inline scripts remain blocked.

Component cards have administrator-only software archives and deployment history. A latest started/failed attempt is shown separately from historical verified deployment. The central archive page supports exhibit filters, component filtering, and pagination. No firmware or agent code changes.

Creating an exhibit creates an exhibit-scoped viewing link in the same transaction. Retrievable tokens are encrypted using the existing private encryption key; validation continues to use the existing hashed-token table. Preserve that encryption key in secure backups. Viewing links grant anonymous read-only access to high-level summaries. Existing links remain valid and revocable. Old links whose original token was never retained cannot be recovered; admins can create a new link in Manage and revoke the old one if desired.

The installer creates default links for existing active exhibits with no exhibit-link history. It leaves existing active links and revoked-link histories alone. It never recreates revoked links. Moving an exhibit retains the existing behavior of revoking exhibit links and clearing staff assignments.

Viewing pages expose activity totals, trends, recorded outcome analysis and equipment freshness. They omit raw events, exports, device identifiers, firmware details, software downloads, raw fault text and remote-access references. Prototype results remain labeled as test data. Counts are the existing measurements; no new telemetry or lifetime game outcome storage is introduced.

## Install

Mac, before transferring, unlock the key once:

```bash
ssh-add --apple-use-keychain ~/.ssh/id_bluehost
```

Transfer the single portal-uniform-v1.tar.gz archive to ~/zoco-portal-private on Bluehost. It includes update/, expected.json, install.php and this README, without live snapshots, private configuration, previews or test fixtures.

Bluehost:

```bash
tar -xzf ~/zoco-portal-private/portal-uniform-v1.tar.gz -C ~/zoco-portal-private/
php -l ~/zoco-portal-private/portal-uniform/install.php
php ~/zoco-portal-private/portal-uniform/install.php
```

Installer defaults to /srv/zoco/public_html/manage. It verifies exact hashes against the supplied production snapshot, validates PHP syntax, saves changed files and affected sharing records in a new private backup directory, stages replacements, and creates eligible viewing links inside a transaction. Failed activation restores changed files and rolls back uncommitted links. A repeated installation of the same files is a no-op.

## Acceptance and recovery

Refresh Laser Maze and Ultimate Design Challenge. Check shortcut styles, collapse Activity on one dashboard and inspect the other, then click its shortcut to reopen. Check component software history and filtered release navigation. Open viewing links in a signed-out browser and verify summaries appear without technical details. Create a disposable exhibit, confirm its default link, revoke it and confirm the old URL fails. Check a location viewing link still scopes exhibits correctly. Perform these production acceptance checks after installation; local tests are not hosting verification.

Backups remain in the private installer directory, including viewing-links-before.json. A manual code rollback restores only files listed in expected.json from that backup and removes the three new shared layout files (views/exhibit-layout.php and assets/exhibit-layout.css/js). Do not restore the entire portal or database from this small backup. Revoke any newly created viewing links in Manage if rolling back access; do not bulk replace sharing records and discard newer user changes. Keep private backups outside public_html.

## Validation

36 isolated PHP 8.3/SQLite checks pass: existing game analytics, shared sections and summaries, escaping, private-data exclusion, component release isolation, later unverified attempts, staff download exclusion, encrypted link retrieval, revocation, rollback and backfill idempotence. All changed PHP files and installer parse. Browser inspection confirmed remembered section preferences carry across dashboards, shortcuts reopen sections, and both layouts fit a 390px viewport without document overflow. Installer shell/lint operations and actual MySQL execution still require Bluehost acceptance.

Future exhibit renderers should call exhibit_navigation and exhibit_section_start/end from views/exhibit-layout.php, retain these semantic keys, use default expanded public sections and collapsed private sections, and keep measurements specific to each exhibit. The generic renderer automatically supplies this structure for newly registered exhibits while reporting unavailable analytics honestly.
