// Englische Handbuchtexte, Teil C (Zusammenarbeit, Referenz).
import type { HelpText } from './help.en'

export const helpEnC: Record<string, HelpText> = {
  dokumente: {
    title: 'Documents & links',
    summary: 'Delivery notes, timesheets, Excel files or OneDrive links on tasks.',
    html: `
<h2>Documents &amp; links</h2>
<p>You can attach documents to every task – e.g. <b>delivery notes</b>, <b>timesheets</b> or <b>Excel files</b>. Open the task by double-clicking; the <b>Documents &amp; links</b> section is below the notes. In the table a <b>📎</b> next to the name shows that documents exist.</p>
<h3>Uploading</h3>
<ul>
  <li><b>Drag</b> files into the field or click, several at once are possible. Optionally enter a <b>comment</b> beforehand (e.g. "delivery note no. 4711").</li>
  <li>Maximum file size is <b>25 MB</b> by default (administrator setting <code>MAX_UPLOAD_MB</code>).</li>
  <li>Executable/scriptable formats (e.g. <code>.exe</code>, <code>.bat</code>, <code>.ps1</code>, <code>.js</code>) as well as HTML and SVG are not allowed.</li>
</ul>
<h3>Link to OneDrive / SharePoint</h3>
<p><b>🔗 Attach link</b> → paste a sharing link, optionally a title. The file stays in OneDrive (permissions and versions there); OpenPlan only stores the reference. <code>http(s)</code> links are allowed.</p>
<h3>Opening &amp; deleting</h3>
<ul>
  <li><b>Download</b> downloads the file; for PDFs and images <b>View</b> shows a preview in a new tab. Links open in a new tab.</li>
  <li><b>×</b> deletes (with confirmation). When a task or project is deleted, its files are removed too.</li>
</ul>
<h3>Permissions</h3>
<p>View/download: everyone with access to the project. Upload/delete: owners and editors.</p>
<p class="help-tip">💡 Documents are <b>not</b> part of JSON/XML exports. For a backup, save the server's <code>data/</code> folder.</p>`,
  },
  rechte: {
    title: 'Roles, owner & permissions',
    summary: 'Who may do what – admin, owner, members.',
    html: `
<h2>Roles, owner &amp; permissions</h2>
<p class="help-tip">💡 If sign-in via <b>Active Directory</b> is set up, employees sign in with their Windows username and password. The account is created at the first login; the password is still changed in AD. The local admin remains as emergency access.</p>
<h3>Global role (user account)</h3>
<table>
  <tr><th>Role</th><th>May</th></tr>
  <tr><td><b>admin</b></td><td>everything, in all projects; manage users (menu <b>Administration</b>)</td></tr>
  <tr><td><b>editor</b></td><td>create/import projects; plan in projects in which they are member or owner</td></tr>
  <tr><td><b>viewer</b></td><td>read only – in the projects in which they are a member</td></tr>
  <tr><td><b>viewer + "All projects"</b></td><td>"Viewer (all projects)": sees <b>all</b> projects, read-only – e.g. for managers. Costs only if a project releases them to members. Set per user in the administration or via an AD group (viewer group).</td></tr>
</table>
<h3>Role in the project</h3>
<table>
  <tr><th>Role</th><th>May</th></tr>
  <tr><td><b>Owner</b> (project manager)</td><td>everything in the project: settings, members, baseline, budget &amp; costs, delete, transfer ownership</td></tr>
  <tr><td><b>Member – Editor</b></td><td>edit tasks, dates, status, resource assignment, documents</td></tr>
  <tr><td><b>Member – Reader</b></td><td>view and download documents</td></tr>
  <tr><td><b>Worker</b> (automatic)</td><td>results from the <b>assignment</b>: whoever is assigned to a task sees the project and may maintain status, progress and block reason of <i>their</i> tasks, write comments, attach documents and claim pool packages – but not plan. If the assignment is removed, the access ends again.</td></tr>
</table>
<p>Every project <b>has exactly one owner</b>. The global role <i>viewer</i> caps every project role to "read".</p>
<h3>Visibility</h3>
<p>Projects are only visible to owners, members, <b>assigned workers</b>, "Viewer (all projects)" users and admins. Everyone else gets "not found" – they do not even learn that the project exists.</p>
<h3>Managing members</h3>
<p>In the project <b>Settings</b> (owner only): choose a member from the list → <b>Add</b>, set the role Editor/Reader.</p>
<h3>Transferring ownership</h3>
<p>Settings → choose a new <b>Owner</b> (only users without the viewer role) → Save, confirm the prompt. Afterwards you may no longer have access. A user who still owns projects cannot be deleted.</p>
<h3>Costs</h3>
<p>Costs and budget are only seen by the owner (and admins); the owner can release read access to members. Details: <i>Budget &amp; master data</i>.</p>
<h3>My account</h3>
<p>Menu <b>Administration</b>: change the password (at least 8 characters); admins also create users there.</p>`,
  },
  verwaltung: {
    title: 'Administration: sign-in & server certificate',
    summary: 'Active Directory login and ACME certificate (administrators only).',
    html: `
<h2>Administration: sign-in &amp; server certificate</h2>
<p>Under <b>Administration</b> (top bar, administrators only) there are several areas: Users, Sign-in (AD), Notifications (email), Reminders, Reports, Server certificate, API access, Webhooks, Backup, Audit log and Release notes (change history per version; each area has its own tab colour). For email, reminders and reports see "Notifications &amp; reports".</p>
<h3>Users</h3>
<p>Create and delete users. Under <b>Sign-in</b> you choose <i>local</i> (password in OpenPlan) or <i>Active Directory</i> (password in AD, create the account without a password beforehand).</p>
<p>For local accounts there is <b>Set password</b> (an admin sets a new password) and, for everyone, <b>End sessions</b> (signs the user out everywhere). After a password change – your own or by an admin – all previous sessions of that user end; with your own change the current one stays.</p>
<h3>Sign-in (Active Directory)</h3>
<ul>
  <li><b>Server:</b> LDAP URL (please <code>ldaps://</code>), base DN and, for an internal CA, its certificate in PEM format. Enter <b>several servers</b> (e.g. two domain controllers) one after another separated by a space or comma: the next one is only tried on connection problems, never on a wrong password. The connection test names the server that answered and lists the user's direct groups – handy for copying the group DNs.</li>
  <li><b>Sign-in check:</b> either enter only the <b>domain</b> (sign-in as <code>user@domain</code>) or specify a <b>service account</b> that searches for the user. The service password is stored but never shown again.</li>
  <li><b>Authorisation:</b> with a <b>required group</b> only its members may sign in. The <b>admin group</b> makes members OpenPlan administrators. New users get the selected role.</li>
  <li><b>Test connection</b> checks the values from the form – even unsaved – step by step (bind, user search, password, groups).</li>
  <li>The local admin always remains as emergency access. Passwords of AD accounts are changed in AD.</li>
</ul>
<h3>Holiday API</h3>
<p>This area sets where <b>Load public holidays</b> (project settings) fetches the statutory holidays from. The default is <code>https://get.api-feiertage.de</code>; a custom URL (e.g. an internal mirror) must deliver the same JSON format. The server appends <code>years=YYYY</code> or replaces the <code>{year}</code> placeholder. <b>Test connection</b> calls the (even unsaved) URL for the current year and shows the result. Changing the URL clears the cache; it can also be cleared by hand.</p>
<h3>Server environment (.env) &amp; restart</h3>
<ul>
  <li>This area edits the container's <b>.env</b> (credentials, proxy, ports, AD defaults …). Comments in the file are kept. <b>Passwords and keys</b> (names with PASSWORD, SECRET, TOKEN, _KEY …) are never shown: empty field = unchanged, a new value replaces the old one. The input suggests names (autocomplete).</li>
  <li><b>Save</b> first backs up the old file (<code>data/env-backups/</code>, the last 10) and writes the change to the audit log – only the variable <i>names</i>, never the values.</li>
  <li>Changes only take effect after <b>Restart container</b>: the application exits, Docker restarts it (policy <code>unless-stopped</code>), the file is re-read and the page reloads itself. The application is unreachable for about 10–30 seconds.</li>
  <li>Prerequisite (Compose): mount <code>./.env:/app/.env</code> (file owned by uid 10001), <code>ENV_FILE=/app/.env</code>, <code>ALLOW_SELF_RESTART=1</code> and <code>restart: unless-stopped</code>. Otherwise the area says “Not enabled”.</li>
</ul>
<p class="help-tip">💡 If the application no longer starts after a change (e.g. wrong port), copy the backed-up file from <code>data/env-backups/</code> to <code>.env</code> on the host and run <code>docker compose up -d</code>.</p>
<h3>Backup</h3>
<ul>
  <li><b>Back up now</b> creates a <code>.tar.gz</code> with the database (consistent, even while running) and all documents. Passwords and keys (JWT secret, TLS key) are deliberately not included.</li>
  <li><b>Automatic:</b> daily from a given time, the last <i>n</i> backups are kept. <b>Verify</b> opens the archive and performs an integrity check of the database; <b>Download</b> fetches it for external storage.</li>
  <li><b>Restore</b> is only possible offline via the command line (<code>python backup.py restore &lt;file&gt; --yes</code>, instructions in the Backup area). The previous data remains as <code>*.before-restore-…</code>.</li>
  <li>Tip: put <code>BACKUP_DIR</code> on another drive and additionally back up the directory externally.</li>
</ul>
<h3>Audit log</h3>
<p>Logs sign-ins (also <b>failed</b> ones, with IP), user/permission changes, settings (AD, email, ACME, reminders), backups and the deletion of projects. Search, filter by action and export as CSV; entries are kept for 365 days.</p>
<h3>Server certificate (ACME)</h3>
<ul>
  <li>Enter the <b>directory URL</b> of the CA (e.g. the internal step-ca), the <b>domains</b> and optionally an email, save and click <b>Request certificate</b>. The result appears at the top (issuer, domains, expiry, fingerprint).</li>
  <li>The CA confirms via <b>HTTP-01</b>: port 80 of the domain must point to the app (container port 8080).</li>
  <li><b>Renew automatically</b> checks every six hours and renews from the set number of days before expiry – also when the domain list changes.</li>
  <li>With <code>TLS_PORT</code> (e.g. 8443) the container starts an HTTPS listener that reloads renewed certificates itself. Alternatively chain and key are in <code>data/tls/</code> for a reverse proxy. Only the public chain can be downloaded, never the key.</li>
</ul>
<p class="help-tip">💡 If the request fails, the CA's message is shown in the "Last run" area – usually port 80 is not reachable or the CA URL/CA certificate is wrong.</p>`,
  },
  benachrichtigungen: {
    title: 'Notifications & reports',
    summary: 'Bell and email on assignment, project reports, reports for managers and cost centre owners.',
    html: `
<h2>Notifications &amp; reports</h2>
<h3>On assignment</h3>
<p>If a task or work package is assigned to you (or taken away), it appears under the <b>🔔 bell</b> in the top bar and – if email sending is set up – as an <b>email</b>. The link opens the details of the task directly. After signing in you are taken there automatically.</p>
<ul>
  <li>Requirement: your <b>resource is linked to your user</b> (tab Resources → column <i>User</i>). If you claim a package yourself, you get no message.</li>
  <li>You enter your <b>email address</b> under <i>Administration → My account</i> (for AD accounts it comes from the directory). There you can also switch emails off; the bell remains.</li>
</ul>
<h3>Comments and @mentions</h3>
<p>In the detail dialog of a task there are <b>Comments</b> at the bottom. With <b>@name</b> (suggestions appear while typing) you notify a project participant directly; the assignees of the task also learn about new comments. In the table <b>💬</b> shows the number. The author and the owner can delete. Readers see comments but do not write.</p>
<h3>Automatic reminders</h3>
<ul>
  <li><b>Due:</b> assignees are reminded one or two days before the end (pool packages without assignee: the owner).</li>
  <li><b>Overdue:</b> the assignee; after a few days the owner additionally gets an <b>escalation</b>.</li>
  <li><b>Blocked:</b> if a task has been blocked for several days, owner and assignee are informed (with the reason).</li>
  <li>Each message is sent only <b>once</b> per task and date. Thresholds and time are set by the administrator under <i>Administration → Reminders</i>.</li>
</ul>
<h3>Project report</h3>
<p>The owner activates it under <b>Settings → Automatic report</b>: weekday, time and recipients (owner or all members). The report states progress, <b>overdue</b> and <b>blocked</b> tasks, <b>upcoming</b> dates (14 days), open pool packages and – per recipient – their <b>own open tasks</b>, all with links. <b>Preview</b> and <b>Send now</b> are in the same dialog.</p>
<h3>Cross-project reports</h3>
<ul>
  <li><b>Portfolio report</b> (for managers): all or selected projects with traffic light, progress, end, deviation from the baseline, overdue and blocked tasks; optionally with budget, actual costs and CPI.</li>
  <li><b>Cost centre report</b> (for cost centre owners): per project budget, plan, actual and remainder of their own cost centre, plus total. No tasks and no other cost centres are shown.</li>
  <li>Recipients need <b>no project access</b>. Under <b>Reports</b> (top bar) they see their reports online; by email they arrive according to the set schedule.</li>
  <li>Setting up: <i>Administration → Reports</i> (administrators only) – create a report, assign cost centres to the owners.</li>
</ul>
<p class="help-tip">💡 Email sending (SMTP, sender, public URL for the links) is set up under <i>Administration → Notifications (email)</i> and checked there with a test email.</p>`,
  },
  verlauf: {
    title: 'History (change log)',
    summary: 'Trace who changed what and when.',
    html: `
<h2>History</h2>
<p>The <b>History</b> tab lists the latest changes to the project: time (UTC), user, action and details (e.g. "Duration 3 → 5", "Document uploaded", "Actual cost import").</p>
<ul>
  <li>Changes to tasks, dependencies, resources, status, baseline, members, budget and documents are logged.</li>
  <li>Plan changes can be undone with <b>↶ / Ctrl+Z</b> (see "Gantt &amp; task table"); the history helps to reverse other changes by hand.</li>
  <li>If several people work at the same time, the view updates automatically within a second. When the same cell is edited simultaneously, the change saved last wins.</li>
</ul>`,
  },
  importexport: {
    title: 'Import & export',
    summary: 'MS Project (XML), CSV for Excel, JSON.',
    html: `
<h2>Import &amp; export</h2>
<h3>Export</h3>
<p>In the Gantt: <b>Export …</b></p>
<table>
  <tr><th>Format</th><th>Use</th></tr>
  <tr><td><b>MS Project (XML)</b></td><td>MSPDI – can be opened in MS Project: tasks, outline, dependencies with lag, constraints, resources, assignments</td></tr>
  <tr><td><b>CSV (Excel)</b></td><td>Table with WBS, name, duration, dates, %, predecessors, resources, float, critical (semicolon, UTF-8)</td></tr>
  <tr><td><b>OpenPlan JSON</b></td><td>complete exchange between OpenPlan instances</td></tr>
</table>
<h3>Import</h3>
<p>Project list → <b>Import …</b>: <code>.xml</code> (MS Project) or <code>.json</code> (OpenPlan). It always creates a <b>new project</b> of which you are the owner.</p>
<ul>
  <li>From MS Project, constraints other than "As soon as possible", "Start no earlier than", "Must start on" and "Finish no later than" become "As soon as possible".</li>
  <li>Inactive tasks are skipped; durations are converted to working days (8 hours).</li>
  <li>Costs, budget, documents and status are not taken over from foreign files (the status is derived from the progress).</li>
</ul>
<p class="help-tip">💡 Actual costs are not part of the project export; for those there is a separate CSV export under <i>Budget → Actual costs</i>.</p>`,
  },
  api: {
    title: 'API & interfaces',
    summary: 'Swagger, API tokens, webhooks – for scripts and other systems.',
    html: `
<h2>API &amp; interfaces</h2>
<p>OpenPlan has a REST API for scripts and other systems (e.g. Ansible, Checkmk, ServiceNow middleware, AutoPatch). Everything you do in the interface can also be done through the API.</p>
<h3>API documentation (Swagger)</h3>
<p>Administrators open it via <b>Administration → API docs ↗</b> (or directly <code>/docs</code>). All endpoints are grouped by topic there, with a short description, fields and the option to try calls (<b>Try it out</b>). If the page was opened from a signed-in OpenPlan session, "Try it out" uses that session – <b>changes are real</b>. The machine-readable description (OpenAPI) is at <code>/openapi.json</code>. The page loads nothing from the internet.</p>
<table>
  <tr><th>Setting <code>API_DOCS</code></th><th>Effect</th></tr>
  <tr><td><code>1</code> (default)</td><td><code>/docs</code> and <code>/openapi.json</code> are reachable by anyone who can reach the server (the endpoints themselves still require a token)</td></tr>
  <tr><td><code>admin</code></td><td>the description can only be fetched by signed-in administrators</td></tr>
  <tr><td><code>0</code></td><td>documentation is switched off (404)</td></tr>
</table>
<p>The variable lives in the <code>.env</code> (Administration → Server environment) and takes effect after a container restart.</p>
<h3>Access for scripts: API tokens</h3>
<p>Administration → <b>API access</b>: name, service account, scope (<b>read only</b> or <b>read and write</b>), optionally projects and validity. The token (<code>op_…</code>) is shown <b>only once</b>. The service account has no password login and must be a member of the project. A token can be revoked at any time.</p>
<pre>curl -H "Authorization: Bearer op_…" https://&lt;server&gt;/api/projects</pre>
<h3>Webhooks and callbacks</h3>
<ul>
  <li><b>Administration → Webhooks</b>: OpenPlan sends events (status change, blocker, assignment, new device) signed to an <code>https://</code> address. Failed deliveries are retried; the <b>log</b> shows every delivery.</li>
  <li><b>External references</b> (task dialog): e.g. the number of a ServiceNow change or an Ansible job with a link. Scripts find tasks by hostname or reference.</li>
  <li><b>Callback</b>: an external system sets status, progress and note of a task and attaches a reference at the same time.</li>
  <li><b>AutoPatch</b> reports back per server after patch and CVE jobs; OpenPlan matches the server to a device by hostname and DNS.</li>
</ul>
<p class="help-tip">💡 A detailed guide with examples and signature verification is in the repository under <code>docs/integration-api.md</code>.</p>`,
  },
  tastatur: {
    title: 'Keyboard shortcuts & tips',
    summary: 'Work faster.',
    html: `
<h2>Keyboard shortcuts &amp; tips</h2>
<table>
  <tr><th>Key</th><th>Effect</th></tr>
  <tr><td><code>F1</code> or <code>?</code></td><td>Open/close help for the current page</td></tr>
  <tr><td><code>Esc</code></td><td>Close help, cancel cell editing</td></tr>
  <tr><td><code>Ins</code></td><td>Insert a new task behind the selection</td></tr>
  <tr><td><code>Del</code></td><td>Delete the selected task (with confirmation)</td></tr>
  <tr><td><code>Alt</code>+<code>→</code> / <code>←</code></td><td>Indent / outdent</td></tr>
  <tr><td><code>Alt</code>+<code>↑</code> / <code>↓</code></td><td>Move up / down</td></tr>
  <tr><td><code>Ctrl</code>+click / <code>Shift</code>+click</td><td>Multiple selection</td></tr>
  <tr><td><code>Ctrl</code>+<code>Z</code> / <code>Ctrl</code>+<code>Y</code></td><td>Undo / redo plan change</td></tr>
  <tr><td><code>Enter</code></td><td>Confirm cell editing</td></tr>
</table>
<h3>Tips</h3>
<ul>
  <li>Enter durations, not end dates – the plan calculates the end itself.</li>
  <li>Dependencies instead of fixed dates: if a predecessor moves, the rest follows automatically.</li>
  <li>Approve the plan → <b>Set baseline</b> → in daily work only maintain status/progress.</li>
  <li><b>Smartphone:</b> The header becomes a menu (☰). In a project the Gantt tab shows a <b>list</b> of cards (tapping opens the details, the circle on the left toggles done/open); <b>Timeline</b> switches to the Gantt chart, and under <b>Tools</b> you find filters, baseline and export. The tabs can be swiped sideways.</li>
  <li>The page is <b>installable as an app</b> (browser menu "Install") and also shows the most recently loaded data offline.</li>
  <li>Language (DE/EN) and appearance (automatic, light, dark) can be switched by each user via the buttons in the top bar; the choice is saved in the profile.</li>
</ul>`,
  },
  faq: {
    title: 'Frequently asked questions',
    summary: 'Why can\'t I …? Why is everything red?',
    html: `
<h2>Frequently asked questions</h2>
<h3>I can't change the duration of a phase (e.g. WBS 1).</h3>
<p>Phases are summary tasks: duration, end and progress result from the subtasks. Change the subtasks – or change the <b>start</b> of the phase or drag the summary bar to move the whole phase.</p>
<h3>Why is almost everything red?</h3>
<p><b>Total float</b> = working days a task may slip without moving the <i>project end</i>; <b>free float</b> = working days it may slip without moving a <i>successor</i> (always ≤ total float). For summary tasks the smallest total float of their children is shown. Calculated on the project calendar – resource absences do not change float.</p>
<p>Red = critical path (float 0). In linear plans almost everything lies on it. With the <b>Critical path</b> checkbox you hide the colouring. Parallel work creates float.</p>
<h3>I drag a bar to the left, but nothing happens.</h3>
<p>A task cannot start before its predecessor. Choose <b>Manual: start on (fixed)</b> in the detail dialog if you want that deliberately. The message below the bar explains the limitation.</p>
<h3>The start of a task jumps to another date after entering it.</h3>
<p>If the date falls on a weekend or a holiday, the start slides to the next working day.</p>
<h3>I don't see the "Budget" tab.</h3>
<p>Costs are reserved for owners and admins. Ask the owner for approval (Budget &amp; master data → Visibility).</p>
<h3>A project has disappeared.</h3>
<p>Either the membership was removed, the ownership transferred or the project deleted. Ask the owner.</p>
<h3>Why is a completed task suddenly at 90 %?</h3>
<p>You changed it from "Done" to "In progress" or "Blocked". 100 % does not fit "not finished", hence 90 %.</p>
<h3>The actual cost import reports "cost centre … unknown".</h3>
<p>Create the cost centre under <b>Budget &amp; master data</b>, import the master data list or enable "create unknown cost centres/types automatically" in the import.</p>
<h3>Uploading a document is rejected.</h3>
<p>Possible reasons: larger than the limit (25 MB), empty file, disallowed type (executable, HTML, SVG) or you only have read access. Alternatively: attach a link to the file in OneDrive.</p>`,
  },
}
