# Changelog

All notable changes to DimeView are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] - 2026-05-25

### Added
- **From City / To City** fields in the Data Entry tab. Each city dropdown
  is dependent on the matching state — pick `MD: Maryland` and the From
  City list updates to cities in Maryland. The dropdowns are searchable
  (case-insensitive substring match via `QCompleter`) and editable so
  you can type a city that isn't in the bundled list.
- New monthly sheets are created with the extended column layout
  (Date, Load No., Driver ID, Truck ID, From State, **From City**, To State,
  **To City**, Transaction, Delivery Status, Payment Status, Credit, Debit,
  More Details). Summary table moves from N/O/P to P/Q/R.
- **Tools → Migrate Sheet Structure…** action for upgrading existing
  workbooks created before this release. The migration:
  - Inserts the two new columns into the Template and every monthly sheet.
  - Preserves historical row values (new columns are blank for old rows).
  - Rewrites the income / expense `INDIRECT` formulas to point at the
    relocated Credit and Debit columns.
  - Is idempotent — re-running it skips sheets that are already migrated.
- **Driver Report** Trip column now shows `{State},{City}-{State},{City}`
  (e.g. `MD,Baltimore-NJ,Newark`). Historical rows without city data
  continue to render as `{State}-{State}` (e.g. `GA-DE`).
- Bundled `cities.json` resource with 1,061 cities across all 50 states
  to seed the dropdowns.

### Changed
- The Driver Report's Trip column width auto-sizes against the longest
  trip string in the report (capped so the table still fits the page);
  other dollar columns are tightened slightly to make room. Long trip
  strings wrap inside the cell instead of overflowing.
- Monthly-sheet schema is now driven by a single source of truth in
  `model.py` (`HEADER_IDX` + `HEADER_NAMES`). Adding or moving columns
  in a future release will only require editing those dicts.

### Fixed
- `detect_field_changes` (used to confirm "this will update all previous
  entries of Load No. X") was using hardcoded column indices that no
  longer matched the schema after the migration. It now derives every
  index from `HEADER_IDX`, so the confirmation prompt accurately reflects
  what changed — including any From City / To City updates.
- App popups (the startup migration warning and the migration result
  dialogs) reliably appear in front of the main window. Previously they
  could be hidden behind the not-yet-visible main window on first launch.
- `installer.nsi` version drift — was stuck at `3.0.0` while
  `__init__.py` had moved to `3.1.0`. Both now report `3.2.0`.

### Migration / Upgrade Notes
- On first launch with an existing workbook, the app detects the old
  column layout and refuses to save new entries until the migration is
  run. Open **Tools → Migrate Sheet Structure…** and confirm; the
  migration takes a few seconds per monthly sheet.
- After migration completes the app behaves normally and the warning
  doesn't reappear on subsequent launches.

## [3.1.0] - 2026

### Added
- Driver Report PDF export.
- Editable summary section on reports.

### Fixed
- Fraction calculation refinement.

## [3.0.0] - 2026

### Changed
- Refactor to use universal variables so the app works for any trucking
  business, not just one hardcoded configuration.

[3.2.0]: https://github.com/eashangallage/DimeView/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/eashangallage/DimeView/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/eashangallage/DimeView/releases/tag/v3.0.0
