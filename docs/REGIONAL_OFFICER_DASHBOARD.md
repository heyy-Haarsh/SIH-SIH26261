# Regional Officer dashboard — screen-by-screen UI

This document describes the regional officer interface as it is built. It is meant to be given to another model so it can reproduce the flow, the chrome, and every box, field, and button. Labels below are the labels shown in the interface.

The regional officer home is `/admin`. The demo role switcher stores the role as `regional_officer`. The seeded demo user is Priya Nair (`regional.demo@praman.local`, id `usr-adm-001`). Initials in the avatar are **PN**.

`/admin/requirements` is not a page. It redirects to `/admin/categories`.

---

## Shared chrome (present on every page)

The screen is a full-height row on a light gray canvas (`#F5F5F5`).

### Left sidebar

White panel, right border `#F0F0F0`. Expanded width **280px**. Collapsed width **64px**. On viewports below `lg`, the sidebar is hidden and opens as an overlay from the top-bar menu button.

**Brand block** (top, bottom border `#F0F0F0`, padding):

- Expanded: horizontal lockup.
  - Image `/aicte-logo.png` (the yellow gear mark), 68×68.
  - A thin vertical divider (`#0B3A6E` at 25% opacity, 48px tall).
  - Name in Source Serif 4, left aligned, two lines:
    - **All India Council** — 13px semibold, near black.
    - **for Technical Education** — 12px medium, `#2c2c2c`.
- Collapsed: the gear image only, 40×40, with accessible name “All India Council for Technical Education”.

**Navigation** (scrollable). Each item is a 36px-tall pill: 16px icon, label, optional count badge. Active item: gray fill `#F5F5F5`, semibold, black text. Inactive: `#555555`, hover `#F8F8F8`. Collapsed items are icon-only with a tooltip of the label. A badge is a small gray pill (`#F0F0F0` / `#333`) and only appears when the count is greater than 0.

Order:

| Label | Route | Notes |
| --- | --- | --- |
| Overview | `/admin` | Home. Active match is exact. |
| Application Categories | `/admin/categories` | |
| Rules & Validation | `/admin/rules` | |
| Verification Sources | `/admin/integrations` | |
| Audit Logs | `/admin/audit` | |
| System Settings | `/admin/settings` | |
| Delegation Queue | `/admin/delegation` | Starts the **OPERATIONS** group. Badge = number of unassigned applications. |
| System Health | `/admin/health` | |
| Users & Roles | `/admin/users` | |
| Handbook References | `/admin/handbook` | |

The **OPERATIONS** heading is 10px, uppercase, tracked, color `#AAAAAA`, with extra space above it. When the sidebar is collapsed, that heading becomes a hairline divider.

**Footer** (top border `#F0F0F0`):

- **Settings** — button, gear icon. It does not navigate. The real settings page is the **System Settings** item above.
- **Support** — button, help icon. It does not navigate.
- **Collapse** / **Expand sidebar** — chevron `‹` when expanded, `›` when collapsed, plus the word Collapse when expanded.

### Top bar

Height 56px, same gray as the canvas, bottom border `#F0F0F0`, horizontal padding 24px.

**Left**

- Mobile only: hamburger button, accessible name “Open navigation”.
- Breadcrumb: `SmartBuild` / then the page crumbs. Separator is `/` in `#CCCCCC`. Earlier crumbs are `#888888`. The last crumb is semibold `#111111`.

**Right**

- Label **Demo role** (hidden on very small screens) and a select, accessible name “Demo role switcher (not secure authentication)”, width 160px, height 32px, white, border `#E0E0E0`. Options, in this order:
  - Scrutiny Officer
  - Applicant
  - Regional Officer
  Changing the role navigates to that role’s home.
- **Notification bell.** Accessible name is “Notifications” or “Notifications, N unread”. A red count badge shows when unread is greater than 0 (caps at `99+`). Opening it shows a 320px dropdown titled **Notifications**:
  - **Mark all read** (only if something is unread).
  - A scrollable list (max height 320px). Each row is a button: title, optional body, timestamp. Unread rows have a tint and an orange dot.
  - Empty: “You have no notifications.”
  - Error: “Could not load notifications right now.”
  - Footer line: “In-app only. Email / SMS delivery is not configured.”
  - There is no “View all notifications” link for the regional officer. That link exists only for the applicant role.
  - The list refreshes every 30 seconds.
- Avatar: 32px circle, background `#2D2D2D`, white initials **PN**. Beside it (from `md` up): **Priya Nair** and the subtitle **Regional Officer**.

### Page header (inside the scrollable main column)

Padding: 32px horizontal, 32px top, 20px bottom.

- **Title:** 28px bold, `#111111`.
- **Description:** 14px, `#888888`, directly under the title, when the page provides one.
- **Actions:** right-aligned, top-aligned with the title. Each page’s actions are listed below.

Page content sits under the header with 32px horizontal padding and 32px bottom padding.

---

## 1. Overview

- Route: `/admin`
- Title: **Regional Overview**
- Description: “System-wide administration · Oversight of applications, officers, and integrations.”
- Breadcrumb: `SmartBuild / Regional Officer / Overview`
- Header actions:
  - **Manage Delegation** — orange filled button (`#E8622A`, hover `#D4541F`), white semibold text. Goes to `/admin/delegation`.
  - **System Health** — white button, border `#E0E0E0`, heart icon. Goes to `/admin/health`.

### Metrics row

One white rounded card, six cells in a wrapping row. Each cell has an 11px uppercase tracked label (`#999`), a 28px bold value (`#111`), and an 11px hint (`#888`). Minimum cell width 140px.

| Label | Value | Hint |
| --- | --- | --- |
| Unassigned | queue length, or an em dash while loading | Need delegation |
| Officers at Cap | count of officers at their queue cap, or an em dash | Queue full |
| Managed Users | user count, or an em dash | Live, or Unavailable if stats failed |
| Active Rules | active rule count, or an em dash | Synthetic + official |
| Live Verification | On or Off | Server config |
| Audit Events (24h) | count, or an em dash | Append-only |

### Applications by Stage

White card, shown only when application statistics loaded.

- Heading: **Applications by Stage**
- Subline: `{total} total · {openClarifications} open clarification(s)`
- One row per stage, in this order: **Draft**, **Awaiting scrutiny**, **Under scrutiny**, **Awaiting applicant**, **Decided**.
- Each row: stage name (fixed 176px, 12px, `#888`), a 6px track (`#F0F0F0`) with a colored fill, and the count (12px semibold). Bar colors cycle blue `#1D4ED8`, orange `#E8622A`, amber `#B45309`, green `#2E7D52`, purple `#6D28D9`. The fill is at least 2% wide.

If statistics fail, an amber notice says “Regional officer statistics unavailable”.

### Quick Navigation

White card. Heading **Quick Navigation**. A wrap of outline buttons:

Delegation, Users, Categories, Rules & Validation, Handbook References, Integrations, System Health, Audit Trail, Settings.

They go to `/admin/delegation`, `/admin/users`, `/admin/categories`, `/admin/rules`, `/admin/handbook`, `/admin/integrations`, `/admin/health`, `/admin/audit`, `/admin/settings`.

### System status

While health is loading and there is no error: the text “Checking services…”.

If health fails: a red notice, “System health is unavailable — sign in as a regional officer with the API running.”

When health loads:

**Overall status bar** (white card): colored dot, bold status sentence, then a gray line `{environment} · {applicationsTotal} application(s) · {auditEvents} audit event(s) in 24h`.

Status sentences:

- ok → “All core services healthy” (green dot `#2E7D52`)
- degraded → “Running with limitations” (amber dot `#B45309`)
- unavailable → “A core service is down” (red dot `#B91C1C`)

**Warnings**, only if the health payload has any: an amber card with a bulleted list.

**Tabbed service list** (white card):

Tabs (underline style; switching a tab clears the search):

1. **Core Services**
2. **External Sources**

Right side of the tab bar:

- Search field: magnifying-glass icon, placeholder **Search**, about 128px wide, filters the visible rows by label.
- Link button with a download icon:
  - On Core Services: **View Details** → `/admin/health`
  - On External Sources: **Manage** → `/admin/integrations`

Column headers: **SERVICE / SOURCE** and **STATUS**.

Each row: colored status dot, service label (tooltip is the service message), and a status badge on the right. Badge text is one of: Healthy, Degraded, Unavailable, Not connected, Switched off, Simulated only. Hovering a row uses `#FAFAFA`. Empty filter result: “No items found.”

---

## 2. Application Categories

- Route: `/admin/categories`
- Title: **Application Categories**
- Description: “Each category is an application purpose. Its information fields, documents and rules are configured here.”
- Breadcrumb: `SmartBuild / Administration / Application Categories`
- Header action: **Create Category** (primary button, plus icon). Opens the create dialog.

Content is centered, max width 80rem, inside one card.

### Filter bar

Three controls in a row (search grows; the two selects are 180px and 220px from the `md` breakpoint). Filters apply about 200ms after a change.

- **Search by name or identifier** — text field, search icon inside the left of the field, placeholder “e.g. EOA or Extension”.
- **Status** — select: All / Available to institutions / Not available.
- **Configuration state** — select: All / Published / Unpublished changes / Not published.

### States

- Error notice **Could not load categories**, with a retry action. Body is the API message.
- Loading: “Loading categories”.
- Empty, no filters: title “No categories yet”, description “Create the first category to define an application purpose.”, button **Create Category**.
- Empty, filters on: title “No categories match these filters”, description “Clear the search or filters to see every category.”, button **Clear filters**.

### Table

Columns: **Category**, **Information fields**, **Documents**, **Rules**, **Configuration**, **Updated**, and an unlabeled actions column.

Each row:

- Category: name is a link to `/admin/categories/{id}`. Under it, the code in monospace, then a one-line truncated description.
- Information fields: a count.
- Documents: “{n} required” and “{n} optional” on two lines.
- Rules: “{n} active”, “{n} draft”, and “· {n} total”.
- Configuration: a badge plus optional `v{n}`, and a second line “Available to institutions” or “Not available to institutions”.
  - Badge **Published** (pass): “The working copy matches the published configuration.”
  - Badge **Unpublished changes** (warning): “Edits exist that applicants will not see until you publish.”
  - Badge **Not published** (neutral): “No configuration has been published yet.”
- Updated: date and time.
- **Open** button (small outline) goes to the same category page as the name link.

### Create Category dialog

- Title: **Create Category**
- Subtitle: “A new category starts unpublished and is not offered to institutions until you publish and enable it.”
- Width: large (`max-w-lg`).
- Fields:
  - **Identifier** — text, forced uppercase, monospace, placeholder `NEW-COLLEGE`. Help: “Permanent. 2 to 64 characters: A–Z, 0–9, hyphen, underscore.”
  - **Name** — text.
  - **Application purpose** — textarea, 3 rows, placeholder “What an institution applies for with this category.”
- Error notice **Could not create the category** if the save fails.
- Footer: **Cancel** (outline, disabled while saving) and **Create Category** (disabled until identifier and name are each at least 2 characters; label becomes **Creating** while busy).
- On success the dialog closes and the app opens the new category.

---

## 3. Category detail

Opened from a category name or **Open**. Not a sidebar item.

- Title: the category name.
- Description: “Information, documents and rules for this application purpose.”
- Breadcrumb: `SmartBuild / Administration / Application Categories / {CODE}`
- Header actions:
  - **All categories** — text link with a left chevron, back to `/admin/categories`.
  - **Publish Configuration** — primary button. Disabled unless validation is valid and there are unpublished changes. Tooltip when disabled: “Nothing to publish” or “Resolve validation errors first”.

Loading title is “Category” with “Loading category”. Load failure is a notice **Could not load this category** (retry) and a link **Back to categories**.

Content is a vertical stack, max width 80rem. An action failure shows the notice **That did not work**.

### Card: Category details

Two-column grid:

- **Name** — text.
- **Identifier** — text, monospace, disabled. The code cannot be edited.
- **Application purpose** — textarea, 2 rows, full width.
- Checkbox, full width: **Available to institutions (requires a published configuration)**.

Then a row:

- **Save details** (becomes **Saving**). Disabled unless something changed and the name is at least 2 characters.
- Configuration badge, `version {n}` when a version exists, and the badge’s hint sentence (same three states as the list).

### Card: Required information

- Title **Required information**
- Description: “Collected from the institution in the first step of the application.”
- If there are no extra fields: “No additional information is collected for this category. Institution name, programme, academic year and contact email are always collected.”
- Each field is its own bordered box:
  - **Label** — text. On a new field, typing the label also fills the key.
  - **Key** — monospace. Disabled once the field has been saved.
  - **Type** — select. Labels: Short text, Long text, Number, Date, Choice list, Email address, Yes / no confirmation.
  - Icon buttons: Move up, Move down, Remove (trash). Move up is disabled on the first field; move down on the last.
  - **Help text** — text.
  - Checkbox **Required**.
  - If type is Choice list: **Options (one per line)** — textarea, 3 rows.
  - If type is Short text or Long text: **Minimum length** and **Maximum length** (numeric).
  - If type is Number: **Minimum value** and **Maximum value** (decimal).
- **Add field** (outline, plus icon) appends a short-text optional field.
- **Save fields** (becomes **Saving**). Disabled when nothing changed, while saving, or while problems exist.
- “Unsaved changes” appears in warning color when the draft differs from the saved list.
- Warning notice **Resolve before saving** lists the problems.
- Success notice after save: “Information fields saved to the working copy. Publish to make them visible to institutions.”

### Card: Required documents

- Heading **Required documents**
- Subline: “One row per document requirement. Rules attach to a requirement.”
- **Add Document Requirement** (outline, plus icon).

Empty: “No documents are configured. Institutions can only be asked for documents you add here.”

Table columns: **Document**, **Need**, **Type and size**, **Rules**, **Status**, **Actions**.

- Document: name, and the code in monospace under it. Inactive rows are muted.
- Need: Required or Optional.
- Type and size: allowed extensions, then “up to {n} MB” or “platform size limit”.
- Rules: “{active} active · {draft} draft”.
- Status badge: **Active** or **Inactive**.
- Actions, right aligned:
  - **View Rules**
  - **Add Rule** (disabled if the requirement is inactive)
  - **Edit Requirement**
  - **Deactivate** or **Reactivate**
  - Move up (arrow; disabled on the first row)
  - Move down (arrow; disabled on the last row)

### Two cards side by side (from the `lg` breakpoint)

**Validation summary**

- Badge **Ready to publish** or **Cannot be published yet**.
- Count line: “{n} fields · {n} documents · {n} active rules”.
- Error notices and warning notices from validation.
- If there are unpublished changes: heading **Unpublished changes** and a bulleted list.

**Version history**

- Heading **Version history**
- Subline: “Applications keep the version they were created under.”
- Empty: “Nothing has been published yet.”
- Each version: `v{n}`, badge **Published** or **Superseded**, summary or “No summary recorded”, then “{datetime} · {publisher or unknown} · {n} documents, {n} rules”.

### Dialog: Add / Edit Document Requirement

- Title: **Add Document Requirement** or **Edit Document Requirement**
- Subtitle: “Category: {name}”
- Warning, only after the server asks for acknowledgement: **Existing applications are affected**, plus the server message.
- **Identifier** — uppercase monospace, placeholder `FIRE_NOC`. Disabled when editing. Help: “Permanent. Results and applications refer to it.”
- **Document name**
- **Guidance shown to the institution** — textarea, 2 rows.
- Radio group **Requirement**: **Required** / **Optional**.
- Checkbox group **Accepted file types**: `pdf`, `png`, `jpg`, `jpeg`.
- **Maximum file size (MB)** — numeric, placeholder “Platform default”. Invalid text shows “Enter a whole number of MB.”
- **Fields to extract** — placeholder `registration_number, valid_until`. Help: “Comma separated. Rules can only check these fields.”
- Error notice **Could not save**.
- Footer: **Cancel**, and **Save** (becomes **Saving**; disabled if the name is under 2 characters, no file type is chosen, the size is invalid, or a new identifier is under 2 characters). If impact must be acknowledged, the primary button is **Confirm and save** instead.

### Dialog: Deactivate this document requirement?

Shown when deactivation needs acknowledgement.

- Title: **Deactivate this document requirement?**
- Body: the server’s impact message.
- Footer: **Cancel** and **Deactivate** (danger).

### Dialog: Publish {category name}

- Subtitle: “This creates version {current + 1}”
- Heading **What changes**, then a bulleted list of pending changes.
- Paragraph: “New applications will use this version, including only active documents and active rules. Draft rules are not included. Applications that already exist keep the version they were pinned to.”
- **Note (optional)** — textarea, 2 rows.
- Footer: **Cancel** and **Publish** (becomes **Publishing**).

### Dialog: Rules (View Rules)

- Title starts as **Rules**, then becomes `{code}: {title}` after a rule is opened.
- Subtitle: “Category: {name} · Document: {requirement name}”
- Loading: “Loading rules”.
- Empty: title “No rules for this document yet”, description “Without rules, this document is only checked for presence, type and size.”, button **Add Rule**.
- List: each rule is a full-width button with code, title, type label, “active v{n}” and “draft v{n}” when present, and a status badge (Active, Draft, Inactive, Superseded).
- List footer: **Close** and **Add Rule**.
- Opened rule:
  - Status badge, rule-type label, and “Source: …” or “No source reference recorded”.
  - Buttons: **Continue editing draft** or **Edit (creates a new version)**; **Duplicate**; **Deactivate** (only if active); **Activate v{n}** and **Discard draft** (only if a draft exists); **Activate v{n}** again for an inactive rule with no draft.
  - Activating a plain-language draft has the tooltip “Activating confirms you reviewed the structured interpretation”.
  - Definition box with tabs **Human-readable** and **Structured JSON**, plus “version {n} · {Active | Draft | Retired}”.
  - Human-readable definition lists: **What is checked**, **If it passes**, **If it does not pass**, **If it cannot be evaluated**, and, when present, **Original wording (not executed)**. If there is no definition: “This version has no structured definition, so it cannot be activated or run.”
  - JSON view: a preformatted block and **Copy JSON** (becomes **Copied**).
  - **Version history**: each version is a button showing `v{n}`, summary or title, datetime, and a status badge. Clicking it changes which definition is shown.
  - Detail footer: **All rules** (back to the list).

Rule type labels used in this UI: Field present, Field format, Allowed values, Field comparison, Not expired, Not in the future, Date age limit, Date order, Cross-document match, File type, File size, No structured check yet.

### Dialog: Add Rule / Edit Rule {code}

Opened by **Add Rule** or by editing from the rules dialog.

- Title: **Add Rule** or **Edit Rule {code}**
- Fields: **Rule title**, **Description**, **Source reference** (placeholder “Citation you have verified, e.g. the clause of the applicable regulation”), **Internal notes**.
- Authoring tabs: **Plain Language** and **JSON**.
- Plain Language:
  - **Describe the check in your own words** — textarea, placeholder “e.g. The registration number must be present and the certificate must not be expired.”
  - **Interpret text** (outline; disabled until the text is at least 5 characters; label becomes **Interpreting**).
- **Structured definition** textarea (placeholder is the schema example). In plain-language mode the label adds “(proposed, editable)”.
- Notices **Fix before activating** and **Please note** when validation returns errors or warnings.
- **Sample extracted fields (JSON)** and **Run dry run** (small outline; disabled until a definition exists).
- Notice **Something went wrong** on a request failure.
- Footer: **Cancel** (ghost), **Validate** (outline), **Save draft** (outline; disabled until the title is non-empty), **Activate** (disabled until validation has passed; tooltip “Validate first”).

---

## 4. Rules & Validation

- Route: `/admin/rules`
- Title: **Rules & Validation**
- Description: “Every document rule across categories. Rules are edited from the category that owns them.”
- Breadcrumb: `SmartBuild / Administration / Rules & Validation`
- Header action: text link **Platform-wide regulatory rules** → `/admin/rules/platform`.

One card, max width 80rem.

### Filters (four columns)

They reload the list as they change.

- **Category** — select, default **All categories**, then one option per category name.
- **Status** — All / Active / Draft / Inactive.
- **Rule type** — All, then the same type labels listed in the rules dialog.
- **Config version** — numeric text, placeholder **Any**. Non-digits are stripped.

### States

- Error notice **Could not load rules**, with retry.
- Loading: “Loading rules”.
- Empty, no filters: “No rules have been created” / “Open a category, choose a document and add a rule to start.” Button **Open categories**.
- Empty, filters on: “No rules match these filters” / “Clear a filter to widen the view.” Button **Clear filters**.

### Table

Columns: **Rule**, **Category**, **Document**, **Type**, **Status**, **Updated**.

- Rule: title links to that rule’s category page. Under it, monospace code, optional `· v{activeVersion}`, optional `· config v{n}`.
- Category name, or `-`.
- Document name, or the requirement code, or `-`.
- Type label.
- Status badge: Active, Draft, or Inactive.
- Updated datetime.

---

## 5. Platform-wide regulatory rules

Opened from the link on Rules & Validation. Not a sidebar item.

- Route: `/admin/rules/platform`
- Title: **Regulatory rules**
- Breadcrumb: `SmartBuild / Regional Officer / Rules`
- No header actions.

A left-border note (not a banner): “Rules shipped with the demo are synthetic and labelled so. Official rules need a verified source citation. Activating a version only affects future checks — results already recorded keep the version that produced them.”

### Tabs

1. **Rules & versions** — count is the number of rules.
2. **Import JSON**
3. **Draft from description**

An error is red alert text. A success message is a small status strip.

### Tab: Rules & versions

Filter chips (small buttons; the selected one is primary): **all**, **synthetic**, **official**.

Three columns from the `xl` breakpoint.

**Card: Create rule** — description “Validated before it is saved”.

- **Code**
- **Name**
- **Kind** — select: Synthetic demo / Official (verified source required).
- If official:
  - **Handbook reference**
  - **Verified source citation** — placeholder “Document / gazette / verified handbook citation”.
- **Definition (JSON)** — monospace textarea, 4 rows.
- **Validate & create**. On success the status says “Rule created and published as v1.” Invalid JSON is reported as “The definition is not valid JSON: …”. A failed check is “Validation failed: …” joined errors.

**Card: Rules** — description “{n} listed”. A scrolling list (max height 32rem). Each rule is a button:

- Code, badge **synthetic** or **official**, badge **on** or **off**, and “{n} draft” if drafts exist.
- Second line: name · current version.
- The selected rule has an accent border.

**Card: Versions** — title is the selected rule code, or **Versions** if none is selected. Description is the rule name, or “Select a rule”.

Empty: “Select a rule to see and manage its versions.”

When a rule is selected:

- **Reason (used for the action you click)** — placeholder “Why are you making this change?”. Actions refuse a reason shorter than the minimum for that action.
- **Switch rule off** or **Switch rule on** (outline).
- Heading **Version history**. Each version row shows the version name, a status badge, an **in use** badge on the current published version, a status explanation, the change reason or an em dash, the effective from/to dates (“Not yet effective” if none), and “produced {n} recorded finding(s)” when usage exists.
  - **Show definition** / **Hide definition** reveals the JSON.
  - Draft versions: **Activate** and **Discard** (reason at least 3 characters).
  - Retired versions, and published versions that are not current: **Reactivate** (reason at least 5 characters).
- A usage note from the server, when present.
- Heading **New version (history is never edited)**.
  - **Version name**
  - **Definition (JSON)** — monospace, 3 rows.
  - **Save as draft** (outline) and **Publish now** (primary). Both need a reason of at least 5 characters.

### Tab: Import JSON

Card **Import rules from JSON**.

- Textarea, placeholder `A JSON array of rules, or {"rules": [...]}`.
- **Validate** (outline; disabled while busy or while the box is empty).
- **Save** (disabled until validation succeeded).
- Saving returns the user to the Rules & versions tab and reloads the list.

### Tab: Draft from description

Card **Draft a rule from a description**.

- Textarea, placeholder “Describe the rule in plain language”.
- **Draft** (disabled until the text is at least 10 characters, or while busy).
- After a proposal: a review checkbox and **Save**, enabled only when the proposal was reviewed and its validation is valid.
- Saving returns to Rules & versions.

---

## 6. Verification Sources

- Route: `/admin/integrations`
- Title: **Integrations**
- Breadcrumb: `SmartBuild / Regional Officer / Integrations`
- No header actions.

Left-border note: “This page shows what is really connected. Endpoints and credentials are set in the server configuration and are never shown or edited here. You can switch a connected source off (for example during an outage); you cannot switch on something that is not configured.”

- Load error is red alert text.
- A status strip shows the result of a check or a toggle.
- While loading: “Checking integrations…”.
- Summary chips: a health badge plus a count, one chip per health bucket returned by the API (Healthy, Degraded, Unavailable, Not connected, Switched off, Simulated only).

Sources are grouped under headings, in this order, and a heading is omitted when the group is empty:

1. **Infrastructure**
2. **Document processing**
3. **AI assistance**
4. **Verification sources**

Each source is a card in a two-column grid from `lg`:

- Name, health badge, and a neutral badge of the mode string.
- Description (muted) and message (secondary).
- If credentials are required: “Credentials in server configuration: **present** or **not present** (values are never shown)”.
- If a last check exists: “Last check {datetime}: not probed / ok / failed — {message}”.
- If an administrator switched it off: “Switched off by {name or an administrator} on {datetime} — {reason}”.
- Limitations as a bulleted list.
- **Show details** / **Hide details** when the source has detail pairs. Opened details are “label: value” lines (booleans become yes/no, lists are comma-separated).
- Footer row: **Run check** (outline). If the source can be toggled: a text field **Reason (required)** (accessible name “Reason for changing {label}”, max width 220px) and either **Switch off** or **Clear switch-off**. A reason shorter than 3 characters is refused with “Enter a reason (at least 3 characters) before changing {label}.”

---

## 7. Audit Logs

- Route: `/admin/audit`
- Title: **Audit trail**
- Breadcrumb: `SmartBuild / Regional Officer / Audit`
- Header actions:
  - **Verify chain** (outline, shield icon). Status becomes “Verifying…”, then “Tamper-evident chain intact — {n} event(s) verified.” or “Chain broken at sequence {n}: {detail}”.
  - **Export CSV** (outline, download icon). Downloads the current filter as a CSV (default file name `praman-audit-log.csv`). Success note: “Export downloaded. The export itself has been recorded in the audit trail.”

Error notice is a red card. The verify/export note is a green card.

### Search card

- Heading **Search**
- Subline: “{n} matching event(s)” and, when facets loaded, “of {total} recorded”.
- Form, four columns from `md`:
  - **Search text** (spans two columns) — placeholder “Application number, institution, action, actor, detail…”
  - **Application number** — placeholder “e.g. AIC-2026”
  - **Actor** — placeholder “Name”
  - **Area** — select, default **All areas**, then facet values with counts.
  - **Actor role** — select, default **Any role**, then facet values with counts.
  - **Record type** — select, default **Any record**, then facet values with underscores turned into spaces, plus counts.
  - **From** and **To** — date inputs, sharing one grid cell.
  - **Search** (submit) and **Clear**.
- Search and Clear reset the open row and load page 1. Page size is 40. Dates are sent as the start of From and the end of To.

### Event list

White card. Each event is a full-width button:

- First line: human label (or the action code), an optional category chip, and the action code in monospace.
- Second line: detail.
- Third line: actor, role in parentheses, timestamp, optional application number, optional record type.

Opening a row loads the detail underneath (background `#FAFAFA`):

- “Loading details…” until it arrives.
- The full detail text.
- A two-column definition list: Event ID, Record ID, Application ID, Actor ID (an id is omitted when absent).
- If metadata has before/after: a table with columns **Field**, **Before**, **After**. Other metadata is a JSON block.
- **Related events**: “{datetime} · {label or action} · {actor}”.

Empty: “No events match these filters.”

Footer: **Previous** (disabled on the first page), “{from}–{to} of {total}”, **Next** (disabled on the last page).

---

## 8. System Settings

- Route: `/admin/settings`
- Title: **Verification & Settings**
- Breadcrumb: `SmartBuild / Regional Officer / Settings`
- No header actions.

Left-border note: “Safe non-secret configuration only. API keys and passwords cannot be stored here. Settings can only make the platform stricter than the server configuration; the note under each setting says whether it is enforced or advisory. Switch integrations on or off on the Integrations page.”

A failed load is an amber strip. A save result is a neutral status strip.

Settings are a two-column grid of cards from `lg`. One card per setting returned by the API. The card title is the setting key. The description is the server description, or “Regional officer setting”. A badge repeats the key; the `verification` key uses a warning badge, others are neutral.

Each card:

- **Value (JSON)** — textarea, 10 rows, pretty-printed JSON.
- If the setting reports enforcement, a list of `` `{field}`: {how} ``.
- **Change reason** — placeholder “Why this change?”. Fewer than 3 characters shows “Provide a change reason (≥3 characters).”
- **Save {key}**. The browser asks “Save setting "{key}"? This is audited and must not contain secrets.” Invalid JSON surfaces as a save failure.
- If previously updated: “Last update: {timestamp} — {last reason}”.

---

## 9. Delegation Queue

- Route: `/admin/delegation`
- Title: **Delegation Queue**
- Description: “Incoming applications are auto-assigned on submit. Clear leftovers, reassign, and tune load-balancing weights.”
- Breadcrumb: `SmartBuild / Regional Officer / Delegation`
- Header actions:
  - **Auto-delegate all ({n})** — orange filled, workflow icon. Disabled while busy or when the queue is empty. Success: “Auto-delegated {ok} application(s)” and, if some failed, “, {fail} still unassigned.”
  - **Refresh** — outline, refresh icon, accessible name “Refresh delegation queue”. Disabled while busy.

An error is an amber card. A success message is a green card with a check icon. Possible success lines also include “Assigned manually.”, “Auto-assigned to the least-burdened officer.”, and “Delegation weights saved.”

Layout: the queue is the wide column; a 320px column sits to its right from the `xl` breakpoint.

### Unassigned Applications

White card.

- Heading **Unassigned Applications**
- Subline: “Loading…” or “{n} waiting for a scrutiny officer”.

Table, minimum width 600px. Columns: **Application**, **Institution**, **Submitted**, **Assign to**, and an empty actions header.

Loading: four skeleton rows.

Empty: “✓ No unassigned applications” and “All applications have been delegated.”

Each application:

- Application number (monospace, semibold) links to `/officer/applications/{id}`. Category name under it.
- Institution name.
- Relative submitted time.
- Select, accessible name “Assign {number} to officer”:
  - **Auto (least burdened)** (empty value)
  - One option per officer: “{name} ({activeCount}/{maxQueueCap})”, plus “ — at cap” and the option disabled when that officer is at cap.
- **Assign** (outline). Disabled while busy. An empty select auto-assigns; a chosen officer assigns manually.

### Officer Workload

White card. Heading **Officer Workload**. Subline “Active queue vs capacity”.

Loading: three pulsing placeholders.

Each officer:

- Name, and a status dot **At cap** (failed) or **Available** (pass).
- A 5px capacity bar. Green `#2E7D52` at or under 70%, orange `#E8622A` above 70%, red `#B91C1C` at cap.
- “{active} / {cap} · {openIssues} open issues” and, on the right, the relative last-assigned time or “never assigned”.

### Load-Balancing Weights

White card, shown once settings have loaded.

- Heading **Load-Balancing Weights**
- Subline: “Adjust how officers are scored for auto-assignment.”
- Number fields:
  - **Active count weight** (step 0.1)
  - **Open issues weight** (step 0.1)
  - **Recency weight** (step 0.1)
  - **Max queue cap** (step 1)
- **Save weights** — full-width orange button. Disabled while busy.

---

## 10. System Health

- Route: `/admin/health`
- Title: **System health**
- Breadcrumb: `SmartBuild / Regional Officer / Health`
- Header actions:
  - **Verify audit chain** (outline). Status text: “Verifying…”, then “Audit chain intact — {n} event(s) verified.” or “Audit chain broken at sequence {n}: {detail}”.
  - **Refresh** (primary, refresh icon). Disabled while refreshing.

While loading: “Checking services…”. A failed load is red alert text. The chain result is a small status strip.

### Overall card

- Badge: “All core services healthy”, “Running with limitations”, or “A core service is down”.
- Beside it: `{environment} · v{version} · checked {datetime}`.
- Warnings as an amber bulleted list, when present.

### Two cards

**Core services** — description “What the platform needs to run”. One bordered row per component: label, health badge, message, then each limitation on its own muted line.

**External sources** — description “Connections to outside systems”. Same row layout. Header link **Manage** goes to `/admin/integrations`.

### Activity card

Title **Activity — last {windowHours} hours**. Description “Counts come straight from the database”.

Stat tiles (uppercase 11px label, semibold value, optional warning line):

- Applications (all time)
- Validation runs — warning “{n} failed” when that count is non-zero
- Extraction runs — warning “{n} need attention”
- Audit events
- Source-unavailable checks
- Last validation — datetime, or “none yet”
- Last audit event — datetime, or “none yet”

Under the tiles, application statuses are neutral badges: “{status with spaces}: {count}”.

### Processing jobs

Card title **Processing jobs**. Description is the server message, or “Recent validation and extraction runs”.

- Select, accessible name “Filter jobs by outcome”: **All outcomes**, **Completed**, **In progress**, **Failed**, **Needs attention**.
- Error text, or “Loading jobs…”, or “No runs match this filter.”
- Table, first 25 rows. Columns: **Run**, **Application**, **Result**, **Started**, **Took**, **Error**.
  - Run: the job kind, capitalized.
  - Application: link to `/officer/applications/{id}`, showing the application number or the first 8 characters of the id.
  - Result: outcome badge (Completed, In progress, Failed, Needs attention) plus the raw status with spaces.
  - Started: datetime.
  - Took: “{n}s” or an em dash.
  - Error: the error string, in failed color, or blank.

---

## 11. Users & Roles

- Route: `/admin/users`
- Title: **Users & Roles**
- Description: “Create and manage system users · Applicants require an institution · All destructive actions are audited.”
- Breadcrumb: `SmartBuild / Regional Officer / Users`
- Header action: **Add User** (orange, user-plus icon). While the form is open the same button reads **Cancel**.

Errors are an amber card. Success text (“User "{name}" created.”, “Deactivated {email}.”, or a failure message) is a green card.

### Create New User

White card, only while the form is open. Four columns from `lg` (two from `sm`):

- **Full name** — placeholder “Jane Smith”
- **Email** — email input, placeholder “jane@example.com”
- **Role** — select, default Scrutiny Officer: Applicant, Scrutiny Officer, Regional Officer
- **Institution** — select, only when Role is Applicant. Default **Select…**, then institution names.

**Create user** (primary, user-plus icon, disabled while busy). On success the form clears, closes, and the directory reloads. An applicant is created with the chosen institution; other roles are created with no institution.

### Directory

White card.

Toolbar: heading **Directory** and “{shown} of {total} user(s)”. Search field, accessible name “Search users”, placeholder “Search by name, email, role…”, filters the loaded list locally.

Table columns: **Name**, **Email**, **Role**, **Institution**, **Status**, and an empty actions column.

- Loading: four skeleton rows.
- Empty search: “No users match that search.”
- Empty directory: “No users found.”
- Role text: Applicant, Scrutiny Officer, or Regional Officer.
- Institution: the name, or an em dash.
- Status dot: **Active** or **Inactive**.
- **Deactivate** (red outline text) only for an active user who is not one of the four seeded demo accounts (`usr-app-001`, `usr-off-001`, `usr-off-002`, `usr-adm-001`). The browser asks “Deactivate {email}? This action is audited.”

---

## 12. Handbook References

- Route: `/admin/handbook`
- Title: **Handbook references**
- Breadcrumb: `SmartBuild / Regional Officer / Handbook references`
- No header actions.

Left-border note: “Officers and applicants only see a handbook edition, section and page for a finding when a reference below is complete and marked verified. Enter a reference only after checking it against the printed AICTE Approval Process Handbook. The system never invents one.”

A load error is red alert text. A save or delete result is a status strip.

Two areas: a form card (one column) and a list card (two columns) from the `xl` breakpoint.

### Add or update a reference

Description: “Key is the rule code (e.g. SYN-RULE-003) or a document-check code”.

- **Reference key** — placeholder “Rule or check code”
- A three-column row: **Edition** (placeholder “e.g. 2025-26”), **Section**, **Page**
- A two-column row: **Academic year (optional)** (placeholder “e.g. 2025-26”), **Application types (optional)** (placeholder “e.g. NEW-ENG, EOA”)
- **Title**
- **Where you checked it** — textarea, 2 rows, placeholder “Handbook title, copy or URL you verified against”
- Checkbox: “I checked this reference against the handbook and it is correct.” Disabled until edition, section, and page are all filled. While disabled, the label adds “(Edition, section and page are required first.)”
- **Save reference** (disabled while busy or while the key is blank) and **Clear** (outline; resets the form).

Editing a row copies that reference into this form. Saving the same key updates it. Success: “Saved {key}.”

### References

Description “{n} on file”. While loading: “Loading…”.

Each row:

- The key in code style.
- Badge **Verified** or **Not verified — not shown to users**.
- Line: edition, `§{section}`, `p. {page}`, joined by middots, or “Incomplete”. Then “ — {title}”, the academic year, and the application types when present.
- If verified: “Verified by {name} on {datetime}”.
- **Edit** (outline) and **Delete** (outline). Delete asks “Delete the reference for {key}?”

Empty list: “No references yet. Until you add verified ones, every finding says its handbook reference is not verified.”

---

## 13. Application case (opened from this dashboard)

This is not a sidebar page. The application number on Delegation Queue, and the application link on a System Health job, open `/officer/applications/{id}`. A regional officer is allowed to use it. The back link says **Back to Queue** and goes to `/officer/queue` (the scrutiny-officer queue, not the delegation page).

- Title: the application number.
- Description: “Evidence-first case workspace · Automated checks support the officer; they do not replace the official assessment.”
- Breadcrumb: `SmartBuild / Regional Officer / Applications / {number}`
- No header action buttons. Actions live in the case header.

States before the case loads:

- “This page is for scrutiny officers” if the role is not an officer or a regional officer.
- Title “Loading…” while the record loads.
- Title “Application not found” with a notice of that name.

### Case header card

- If the record is not from the API, a blue strip: “Synthetic demo data — open an application created via the API for a live scrutiny review.”
- Institution name, status badge, priority badge, and a **Score** chip when a priority score exists. The score tooltip is “Priority score — ordering aid only, not proof of fraud or compliance”.
- Line: `{category} · {programme} · AY {year}`
- Line: `#{number} · Submitted {date} · Officer: {name or Unassigned} · {contact email}`
- Buttons, only for an API record: **Check issuers** (outline, plug icon) and **PDF report** (outline, download icon). **Start scrutiny** appears when the case can be started.
- Snapshot strip: **Status**, **Open issues**, **Uploaded** (“{n} doc(s)”), **Missing**. Open issues and missing counts are highlighted when greater than zero. If a last transition note exists, its first line (up to 80 characters) is labelled **Last note**.
- Optional line **Why prioritized:** “queue ordering aid only — not a fraud probability.” Then either factor names with points, or “Driven by open findings, missing documents, and related workload signals.”
- A workflow status or error strip appears only after an action.

### Tabs

Inside one card:

1. **Case workspace** — count is the number of open issues. Three regions: “Documents and findings”, “Document viewer”, and “Evidence and actions”, plus a “Verification dimensions” section.
2. **All issues** — the issues list, including verified handbook marks where a reference is verified.
3. **Documents** — count is the number of documents. Opens a document report (document name as the heading, and a close button).
4. **Cross-document** — count is the number of mismatches, omitted when zero.
5. **Authenticity** — count is the number of open authenticity items, omitted when zero. Includes an **Officer note** field.
6. **Review & decision** — count is the number of open deficiencies, omitted when zero.
   - Clarification **Title**
   - Clarification details, placeholder “Tell the applicant exactly what to correct and which document it is in…”
   - **Applicant preview**
   - **Decision reason**, placeholder “Reason for the decision…”
   - Internal note, placeholder “Add an internal note…”

A document report can also open over the case: heading is the document name, with an outline close button.
