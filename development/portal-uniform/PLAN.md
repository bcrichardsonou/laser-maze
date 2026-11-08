# Shared exhibit dashboard update

Requested October 13, 2026. Implementation pending current production source snapshot.

## Shared structure

Every exhibit uses the same section order and navigation styling: Overview; Activity and outcomes; Equipment and components; Recent history. Private administrative sections: Remote access; Technical details. Exhibit-specific measures belong within these shared sections.

Use a shared section renderer and stylesheet so future dashboards inherit the same expand/collapse behavior, headings, anchors, spacing, and mobile navigation. Corresponding sections have matching default expanded states across dashboards. Selecting an anchor opens its section. Remember section preferences using stable semantic IDs, while preserving keyboard accessibility.

## Component releases

Each component has an administrator-only Software section: latest verified deployment, most recent attempt and its status, archived releases and expandable deployment history. Archive presence does not imply installed software. Keep the central release library as a filtered cross-exhibit administration tool with pagination.

## Viewing links

Generate an exhibit-scoped read-only viewing link when creating an exhibit, within the creation transaction. Provide existing exhibits with links without duplicating active links. Keep links retrievable by administrators and revocable/replaceable; do not silently regenerate revoked links. Preserve existing links.

Shared pages show consolidated activity, charts, results and freshness. Omit remote access, device identities, raw logs, release downloads and administrative actions. Filter all data to the linked exhibit. Mark bench/simulator data and separate it from visitor activity. Do not present stale snapshots as current.

## Validation and delivery

Obtain current public source files without private configuration or credentials. Prepare an additive guarded installer with private backups, source compatibility checks and PHP lint. Test authenticated and viewing-link permissions, exhibit isolation, creation/link transactions, revocation, release component scope, empty/stale states, charts and mobile section navigation. Verify both current exhibits after installation. Update the reusable workflow after acceptance.

## Suggested additions

Use consistent date ranges and local timezone labels, define count denominators, distinguish unavailable from zero, show sample size and data-retention limits, and expose last-report freshness in all views. Never count incomplete sessions as losses.

## Access limitation

Direct read-only SSH attempt could not authenticate with the protected hosting key. Use the user's established Mac SSH key workflow to copy only public application source into live-reference. No private config or database export is needed for this snapshot.
