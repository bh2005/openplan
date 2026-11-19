// Englische Handbuchtexte, Teil B (Team & Ressourcen, Kosten & Budget).
import type { HelpText } from './help.en'

export const helpEnB: Record<string, HelpText> = {
  ressourcen: {
    title: 'Resources',
    summary: 'Create people and devices, availability, daily rates, assignment.',
    html: `
<h2>Resources</h2>
<p>Resources are people (or devices) that you assign to tasks.</p>
<h3>Creating</h3>
<p>Tab <b>Resources</b> → enter a name → <b>Add</b>. <b>Max. availability %</b> is the capacity (100 = full time, 50 = half time).</p>
<p>Whoever may see costs (owners, possibly members) additionally sees <b>Daily rate (EUR)</b>, <b>Cost centre</b> and <b>Cost type</b>. Only owners may change these.</p>
<p>The <b>User</b> column links a resource to a user: type two or more characters (ID, name or email), pick a hit, remove the link with ×. It is needed so that <b>work packages</b> can be claimed (see the topic "Work packages"). If the resource name is still empty, the user's display name is suggested.</p>
<h3>Function and organization chart</h3>
<p>The <b>Function</b> column is free text per resource <i>and project</i>, e.g. "Project manager", "Network engineer" or "Network lead". The same person can have a different function in each project. The <b>Reports to</b> column defines who the resource is subordinate to in the <b>organization chart</b>; empty means directly the project lead (the owner). Circular references are rejected. If the superior resource is deleted, its staff move back under the project lead.</p>
<p>The chart is shown in the <b>Organization chart</b> tab of the project; managers find all visible projects under <b>Organization chart</b> in the header (choose a project). <b>Dashed</b> boxes are resources without a user account (externals), grey ones are members without a resource. Export as <b>PNG</b> (for slides), <b>SVG</b> or <b>PDF</b> (page format selectable: image size, A4 landscape, A3 landscape, slide 16:9).</p>
<p><b>Re-parenting with the mouse:</b> with edit rights, drag a box onto another one (it becomes subordinate to it) or onto the project lead (reports directly to them). Circles, i.e. dropping under your own subordinate, are not allowed. On touch devices use the <b>Reports to</b> column.</p>
<h3>Assigning a person (without a prior resource)</h3>
<p>The detail dialog of a task has <b>Assign person</b>: type a name or email, pick a hit, set the percentage. OpenPlan creates the <b>linked resource</b> automatically and gives the person access as a <b>worker</b> – so resources only exist for people who really have work, and nobody has to be added as a member beforehand.</p>
<h3>Assigning</h3>
<p>Double-click a task → <b>Resources</b>: tick the box and enter the <b>assignment in %</b> (e.g. 50 % = half-days). The assignment determines utilisation <i>and</i> personnel costs (duration × daily rate × assignment).</p>
<h3>Utilisation per week</h3>
<p>Below the table a matrix shows the <b>peak value</b> per resource and calendar week. <b>Red</b> = more planned than available. You see it day by day in the <b>Team</b> tab.</p>
<h3>Absences</h3>
<p>Below the resource table you enter <b>absences</b>: resource, <b>From</b>/<b>To</b> (both days inclusive), <b>Type</b> (vacation, training, sick, other) and a note. Owners and editors maintain all of them; someone linked to a resource as a <b>worker</b> only enters their <b>own</b>. An absence does not move any dates, but it removes the resource's capacity on the working days of that period: in the <b>Team</b> tab, planned work then counts as overload (⚠). These entries apply per project.</p>
<p><b>Personal absences:</b> everyone enters their own vacation once under <b>My absences</b> (header). It applies automatically in <i>all</i> projects where the person is linked to a resource via the <b>User</b> column and appears there with 👤 “personal” (read-only). Others see “Sick” only as “Other”; notes stay private.</p>
<h3>Deleting</h3>
<p>When you delete a resource its assignments and absences are lost (with confirmation).</p>`,
  },
  team: {
    title: 'Team & resource utilisation',
    summary: 'Utilisation per person and day, spot overload, reschedule by dragging.',
    html: `
<h2>Team &amp; resource utilisation</h2>
<p>One row per person with the <b>daily load</b> (in %). Below it their tasks appear as bars.</p>
<h3>Reading</h3>
<ul>
  <li><b>Green</b> = within availability, <b>red</b> = overloaded. The number in the box is the sum of assignments on that day.</li>
  <li>Left: <b>peak load / availability</b> (e.g. <i>150 / 100 %</i>) and the <b>effort in person-days</b> (PD).</li>
  <li><b>Hatched bands</b> in a person's row are <b>absences</b>; on those days capacity is 0, planned work turns red and the row on the left gets a ⚠.</li>
  <li><b>Resolve overload …</b> (shown on overload, for editors) suggests moves: tasks are only pushed back <i>within their free float</i>, so successors and the project end stay unchanged. You choose and apply – this sets “Start no earlier than”, undoable with Ctrl+Z. Started, completed and manually scheduled tasks are left alone, overload in the past is ignored. What cannot be solved within float is listed separately (“needs a decision”): assign differently, deliberately move the date or change capacity.</li>
  <li>The chip at the top states how many people are overloaded; <b>overloaded only</b> filters the list.</li>
  <li><b>Not assigned</b> (bottom) collects tasks without a resource.</li>
</ul>
<p>As in the Gantt: the table on the left stays in place when scrolling horizontally, the <b>divider</b> can be moved (double-click = default width).</p>
<h3>Rescheduling by dragging</h3>
<ul>
  <li>Drag <b>horizontally</b> = move the date (sets "Start no earlier than").</li>
  <li>Drag <b>vertically</b> onto another person's row = the assignment changes (percentage stays).</li>
  <li>Drag into the <b>Not assigned</b> area = remove assignment; from this area onto a person = assign (100 %).</li>
  <li><b>Double-click</b> opens the details.</li>
</ul>
<p class="help-tip">💡 Readers see the view but cannot drag anything.</p>`,
  },
  board: {
    title: 'Board (Kanban)',
    summary: 'Tasks as cards in the columns Open, In progress, Blocked, Done – dragging changes the status.',
    html: `
<h2>Board (Kanban)</h2>
<p>The board shows the same tasks as the Gantt, but ordered by <b>status</b>: <b>Open</b>, <b>In progress</b>, <b>Blocked</b>, <b>Done</b>. It is just another <b>view</b> – dates, dependencies and progress still come from the plan. Summary tasks (phases) do not appear as cards; their status is derived from their sub-tasks.</p>
<h3>Changing the status</h3>
<ul>
  <li><b>Drag a card</b> into another column (mouse) – on touch devices and with the keyboard use the <b>status field</b> at the bottom of the card.</li>
  <li>The usual rules apply: <b>Done</b> sets 100 %, <b>Open</b> 0 %; see the topic "Status &amp; progress".</li>
  <li><b>Blocked:</b> when you move a card there you are asked for the <b>reason</b> (optional). It is then shown on the card.</li>
  <li><b>Waiting predecessors:</b> if a task depends on predecessors that are not done yet, the card shows "⛓ waiting for n". Setting it to <i>In progress</i> or <i>Done</i> asks for confirmation; you can still confirm.</li>
  <li>Members without planning rights can only move <b>their own</b> tasks; readers see the board but cannot change anything.</li>
</ul>
<h3>The card</h3>
<p>A card shows the WBS number, name, period (red with ⚠ when late or past its deadline), progress, assigned people and markers: <b>!</b> critical path (red edge; completed tasks are no longer shown as critical), ◆ milestone, ◌ pool package without assignee, 💬 comments. A click opens the details.</p>
<h3>Filters &amp; lanes</h3>
<ul>
  <li><b>Search</b> in name, WBS, block reason, person and phase.</li>
  <li><b>Mine only</b> (tasks of your resource), <b>Pool only</b>, <b>Critical only</b>, <b>Hide completed</b>.</li>
  <li><b>Lanes</b>: additionally group cards by <i>phase</i> or <i>person</i> (with several people the first one counts). The choice is remembered in the browser.</li>
</ul>
<p class="help-tip">💡 The board does not plan anything: it has no order of its own and no custom columns. To reschedule dates or people use the Gantt or Team view.</p>`,
  },
  pakete: {
    title: 'Work packages',
    summary: 'Assign packages directly or provide them in the pool for self-service.',
    html: `
<h2>Work packages</h2>
<p>A work package is a normal task (with date, status, documents and costs) that is either <b>assigned directly to a resource</b> or lies <b>open in the pool</b>. Project members take their packages from the pool themselves.</p>
<h3>Filing under a task</h3>
<p>A package is a normal task and can lie under any phase or task. When creating it you choose <b>belongs to</b>; afterwards use "Indent" (⇥) in the Gantt. The parent task thereby becomes a summary task: duration, end, progress and status are calculated from its packages. For many similar steps see "Devices, templates &amp; import".</p>
<h3>Completion period (from – to)</h3>
<p>Each package can get a period in which it should be completed: <b>from</b> = earliest start (acts like "Start no earlier than" in scheduling), <b>to</b> = <b>deadline</b>. You enter both when creating it in the <i>Packages</i> tab or later in the detail dialog ("Start no earlier than" + "Deadline"). If the planned end is after the deadline, package list, table and dialog show a <b>⚠</b>. The automatic reminders (due, overdue, escalation) are based on the deadline if one is set. "From" must not be after "to".</p>
<h3>Creating</h3>
<ul>
  <li>Tab <b>Packages</b> → enter name and duration → choose <b>Open in pool</b> or <b>Assign: …</b> → <b>Create</b>.</li>
  <li>Every existing task can become a package: double-click → enable <b>Work package for self-service</b>. (Summary tasks are not possible.)</li>
</ul>
<h3>Claiming and releasing</h3>
<ul>
  <li>Under <b>Open in pool</b> you find every package without a resource. <b>Claim</b> assigns it to you (100 %) and sets the status from <i>open</i> to <i>in progress</i>. Only <b>one person</b> can claim a package.</li>
  <li><b>Release</b> removes the assignment again; the package is then back in the pool. The person who claimed it and the owner may release it ("To the pool").</li>
  <li>Claiming and releasing are logged in the <b>History</b>.</li>
</ul>
<h3>Requirements</h3>
<ul>
  <li><b>Editors</b> and the owner may claim. Readers only see the pool.</li>
  <li>The assignment works via a <b>resource linked to your user</b> (tab Resources → column User). If there is none yet, OpenPlan automatically creates a resource with your username when you claim for the first time.</li>
</ul>
<p class="help-tip">💡 Directly assigned packages appear like all tasks in the Gantt and in the Team tab. Pool packages are in the team planner under <b>Not assigned</b>, where you can also assign them to a person by dragging.</p>`,
  },
  geraete: {
    title: 'Devices, templates & import',
    summary: 'Import a device list (Excel/CSV): each device gets the work steps of its template – with matrix view.',
    html: `
<h2>Devices, templates &amp; import</h2>
<p>For rollouts with many similar devices (e.g. replacing switches) you do not create every step by hand: you import a <b>device list</b>, and OpenPlan creates the <b>work steps of its template</b> for each device (order, deliver, stage, configure, replace, test …).</p>
<h3>Structure in the plan</h3>
<p><b>Site</b> (phase) → <b>device</b> (task, named after the hostname) → <b>steps</b> (work packages). The steps are chained one after another; a wait time (e.g. lead time) lies between them as lag. Status, progress, dates and costs of device and site roll up from the steps.</p>
<h3>Templates ("Templates" menu)</h3>
<ul>
  <li>A template belongs to a <b>device type</b> (switch, access point, firewall …). The name of the template is the value of the column "Device type" in the list.</li>
  <li>Per step: <b>name, role, duration, wait afterwards, predecessor</b>. Three switches: <b>Price</b> (the price from the list is booked as planned cost on this step), <b>Window</b> (the maintenance window becomes the completion period), <b>Lead time</b> (the column "Lead time" overrides the wait time).</li>
  <li>Default templates for switch, access point and firewall exist – additionally as English copies ("Switch (English)" etc.), whose name must then appear in the "Device type" column. Editors may edit them; changes apply to later imports (existing tasks remain unchanged).</li>
</ul>
<h3>Importing a device list (tab "Devices")</h3>
<ol>
  <li><b>Import device list …</b> → choose Excel (.xlsx) or CSV. Required columns: <b>Hostname, Site, Device type</b>. You can download a sample with all columns, drop-down lists and your current templates via <b>⬇ Download sample Excel</b> ("Templates" menu or in the import dialog) – it is generated from the current templates on every download.</li>
  <li><b>Map columns</b> (suggested automatically), optionally a target task, define <b>Roles → resources</b>. Roles with a resource are assigned to it; the remaining steps go to the row's "Responsible", otherwise they are available as pool packages for self-service.</li>
  <li><b>Check preview</b>: shows new/updated devices, steps, new sites, errors per row (unknown device type, duplicate hostname, window "from after to" …). Without "skip rows" either everything or nothing is imported.</li>
  <li><b>Import</b>. With ↶ (Ctrl+Z) you revert the whole import in one step.</li>
</ol>
<h3>Location code &amp; data cleaning</h3>
<ul>
  <li><b>Location code</b> (e.g. <code>LOC024</code>): column "Location code" / <code>Location_ID</code>. The code is prefixed to the site phase ("LOC024 – Musterwerk"); all devices with the same code end up in <b>one</b> phase, however the place name is spelled. If the column is missing, the code is recognised from texts such as <code>LOC024__DE.Musterwerk</code>. Site <i>or</i> location code is enough.</li>
  <li><b>Columns are recognised</b>, also for inventory exports with a configurable prefix such as <code>INV_</code> (environment variable <code>IMPORT_HEADER_PREFIXES</code>; Node Name, IP_Address, Serial_Number, Model_ID, City, Priority, Location_ID …). "City" takes precedence over "Location" as the site.</li>
  <li><b>Cleaning:</b> invisible characters (zero-width, soft hyphen) and non-breaking spaces are removed, the priority is normalised ("non business critical" = "Non Business Critical"). Duplicate IP addresses or serial numbers appear as a warning in the report.</li>
</ul>
<p><b>Repeatable:</b> The hostname is the key. On re-import, subsequent deliveries are added, master data and maintenance windows of existing devices are updated – status and completed steps remain. Prices require the cost permission (owner/admin); otherwise they are ignored and this is reported.</p>
<h3>Matrix "Devices × steps"</h3>
<ul>
  <li>Each row is a device (grouped by site), each column a step, each cell the status: ○ open, ◐ in progress, ✓ done, ⛔ blocked, ⚠ deadline exceeded, dashed border = in pool.</li>
  <li><b>Click</b> selects a cell, <b>Ctrl-click</b> adds, <b>clicking the column heading</b> selects the step for all devices shown, <b>clicking the hostname</b> all steps of the device, <b>clicking the site</b> all steps of the site. Then set the status for the whole selection. <b>Double-click</b> opens the details (dates, costs, comments, documents).</li>
  <li>Filters by template, site, search (hostname, model, IP), "unfinished only"; <b>CSV export</b> for reports.</li>
</ul>
<p class="help-tip">💡 You create single devices without Excel with <b>+ Device from template</b>.</p>`,
  },
  kalender: {
    title: 'Calendar view',
    summary: 'Tasks by month, week or as a list.',
    html: `
<h2>Calendar view</h2>
<p>Shows what runs when – without the Gantt. Good for clients, teams and the phone.</p>
<ul>
  <li><b>Month / Week</b> – tasks as bars across the days; milestones with ◆, critical ones red, completed ones pale and struck through, blocked ones with an orange border.</li>
  <li><b>Year</b> – all twelve months at a glance: days off grey, <b>absences</b> blue (darker = more people at the same time), ◆ milestones and ⚑ deadlines. Hover a day for details, click to jump to the month view. The resource filter applies here too.</li>
  <li><b>List</b> – table of the tasks of the period (mobile friendly).</li>
  <li>In month and week a coloured strip at the bottom of a day shows who is absent.</li>
  <li><b>‹ Today ›</b> pages through; the filter <b>All resources</b> shows only the tasks of one person.</li>
  <li><b>Summary tasks</b> shows phases, <b>Hide completed</b> tidies up.</li>
  <li>Clicking a bar or a list row opens the details.</li>
</ul>`,
  },
  'budget-uebersicht': {
    title: 'Budget: overview & key figures',
    summary: 'Tiles, cost trend, breakdown, reconciliation.',
    html: `
<h2>Budget: overview</h2>
<p>The <b>Budget</b> tab is visible to <b>owners and admins</b>; members only see it if the owner enables it under <i>Budget &amp; master data</i>. All amounts are in <b>EUR</b>.</p>
<h3>Tiles</h3>
<table>
  <tr><th>Tile</th><th>Meaning</th></tr>
  <tr><td>Budget</td><td>Total budget and remainder (budget − actual)</td></tr>
  <tr><td>Plan (current)</td><td>Planned costs of today's plan; below it the baseline target (BAC)</td></tr>
  <tr><td>Actual costs (AC)</td><td>booked costs; below it the earned value (EV)</td></tr>
  <tr><td>Forecast at completion (EAC)</td><td>expected total costs at the cost efficiency so far; remaining costs (ETC)</td></tr>
  <tr><td>Cost index (CPI)</td><td>EV ÷ AC. <b>≥ 1</b> = within budget</td></tr>
  <tr><td>Schedule index (SPI)</td><td>EV ÷ PV. <b>≥ 1</b> = on schedule</td></tr>
</table>
<p>The border of the index tiles shows a traffic light: green ≥ 0.98 · yellow ≥ 0.90 · red below. Red warning bars appear when plan or actual exceed the budget or the forecast is above it.</p>
<h3>Cost trend</h3>
<p>Cumulative curves per month: <b>blue</b> plan (baseline), <b>red</b> actual, <b>yellow dashed</b> budget, <b>green dot</b> earned value at the status date. If the red curve is above the blue one, you are spending more than planned.</p>
<h3>Breakdowns</h3>
<ul>
  <li><b>By cost centre / cost type</b> – budget, plan, actual and actual/plan in %. Red numbers = over budget.</li>
  <li><b>Reconciliation cost centre × cost type</b> – plan − actual per combination; <b>Export CSV</b> for the reconciliation with SAP.</li>
  <li><b>By task</b> – plan, baseline, actual and EV per task including phase totals.</li>
</ul>
<p class="help-tip">💡 Without a baseline, EV and PV refer to the current plan – set the baseline in the Gantt so the key figures are meaningful. Terms: see <i>Key figures (glossary)</i>.</p>`,
  },
  'budget-plan': {
    title: 'Budget: planned costs',
    summary: 'Personnel costs from resources plus fixed costs per task.',
    html: `
<h2>Planned costs</h2>
<p>The planned costs of a task consist of two parts:</p>
<ul>
  <li><b>Personnel costs</b> – automatic: <i>duration × daily rate × assignment %</i>. You maintain daily rate, cost centre and cost type on the resource.</li>
  <li><b>Fixed costs</b> – material, licences, external services, travel … Entered here in the tab.</li>
</ul>
<h3>Entering fixed costs</h3>
<p>At the bottom of the table: choose a task, description, optionally <b>cost centre</b> and <b>cost type</b>, amount (<code>1.234,56</code> or <code>1234.56</code>) → <b>+</b>. You change existing items directly in the row, <b>×</b> deletes.</p>
<h3>Distribution over time</h3>
<p>Costs are spread evenly over the working days of the task (milestones on their day). This produces the plan trend (PV).</p>
<p class="help-tip">💡 The table <b>Planned costs per task</b> separates personnel and fixed costs. Resources without a daily rate are listed above as a warning – they result in €0 personnel costs.</p>`,
  },
  'budget-ist': {
    title: 'Budget: actual costs & SAP import',
    summary: 'Enter postings or import via CSV, duplicates, errors.',
    html: `
<h2>Actual costs</h2>
<p>Actual costs are booked amounts with date, optionally cost centre, cost type, task, document number and text. Credits are <b>negative</b>.</p>
<h3>Posting manually</h3>
<p><b>+ Posting</b>: date (<code>DD.MM.YYYY</code>), amount, optional assignments. Rows can be changed with ✎ and deleted with ×. The search filters by document number and text.</p>
<h3>CSV import (e.g. SAP export)</h3>
<ol>
  <li><b>Import CSV …</b> and choose a file – OpenPlan checks immediately (preview, <b>nothing booked yet</b>).</li>
  <li>Read the result: valid rows, duplicates, errors per row, the first preview rows.</li>
  <li>No errors? <b>Import</b>. With errors <b>nothing</b> is imported (all or nothing) – correct the file or choose "import the valid rows despite faulty ones".</li>
</ol>
<h3>Expected format</h3>
<table>
  <tr><th>Column (heading)</th><th></th></tr>
  <tr><td><b>Posting date</b> / Date / Budat</td><td>Required; <code>15.10.2026</code> or <code>2026-10-15</code></td></tr>
  <tr><td><b>Amount</b> / Value</td><td>Required; <code>1.234,56</code>, <code>1,234.56</code>, <code>-12,50</code>, <code>12,50-</code>, <code>(100)</code></td></tr>
  <tr><td>Cost centre / Kostl</td><td>must exist in the project (or let it be created automatically)</td></tr>
  <tr><td>Cost type / Kstar</td><td>ditto</td></tr>
  <tr><td>Document number / Beleg</td><td>for the duplicate protection</td></tr>
  <tr><td>Text / Posting text</td><td>Description</td></tr>
  <tr><td>Task / WBS no.</td><td>WBS number of the task, e.g. <code>3.1</code></td></tr>
  <tr><td>Currency</td><td>only <b>EUR</b>; other currencies are reported as errors</td></tr>
</table>
<ul>
  <li>Separator <code>;</code> <code>,</code> or tab; character set UTF-8 or Windows-1252 (umlauts stay correct).</li>
  <li><b>Leading zeros</b> in cost centres/types are ignored (<code>100200</code> matches <code>0000100200</code>).</li>
  <li><b>Duplicates:</b> the same document number + cost centre + cost type + amount + date is skipped – re-importing the same file is harmless.</li>
  <li>Options: <b>create unknown cost centres/types</b>, <b>import valid rows despite errors</b>.</li>
</ul>
<p class="help-tip">💡 <b>Export CSV</b> returns all postings again (Excel-friendly, semicolon, UTF-8 with BOM).</p>`,
  },
  'budget-stamm': {
    title: 'Budget: budget lines & master data',
    summary: 'Set the budget, maintain cost centres and cost types, visibility.',
    html: `
<h2>Budget &amp; master data</h2>
<h3>Budget lines</h3>
<p>A row without cost centre and cost type is the <b>total budget</b>. With cost centre and/or cost type you define <b>partial budgets</b> (e.g. "Hardware €185,000"). There is at most one row per combination. <b>Save budget</b> applies the changes.</p>
<h3>Cost centres &amp; cost types</h3>
<ul>
  <li>Create individually (number + description), change with ✎, delete with ×. Only what is no longer used anywhere can be deleted.</li>
  <li><b>Paste list / import from SAP:</b> per row <code>number;description</code> (also copied from Excel, tab allowed). Existing numbers are updated.</li>
  <li>Master data applies <b>per project</b>.</li>
</ul>
<h3>Visibility</h3>
<p>By default only owners and admins see costs. With the checkbox <b>Project members may see costs and budget</b> members get read access – only owners may still change them.</p>`,
  },
  kennzahlen: {
    title: 'Key figures (glossary)',
    summary: 'BAC, PV, EV, AC, CPI, SPI, EAC, ETC, VAC explained simply.',
    html: `
<h2>Key figures (glossary)</h2>
<p>OpenPlan uses the <b>earned value method</b>: planned, achieved and spent are compared in euros.</p>
<table>
  <tr><th>Abbr.</th><th>Name</th><th>Meaning</th></tr>
  <tr><td><b>BAC</b></td><td>Budget at Completion</td><td>Total costs according to the baseline</td></tr>
  <tr><td><b>PV</b></td><td>Planned Value</td><td>Planned costs that should have been incurred by the status date (today)</td></tr>
  <tr><td><b>EV</b></td><td>Earned Value</td><td>Value of the work done so far = planned costs × progress %</td></tr>
  <tr><td><b>AC</b></td><td>Actual Cost</td><td>actually booked costs</td></tr>
  <tr><td><b>CV</b></td><td>Cost Variance</td><td>EV − AC. Negative = more expensive than expected</td></tr>
  <tr><td><b>SV</b></td><td>Schedule Variance</td><td>EV − PV. Negative = behind plan</td></tr>
  <tr><td><b>CPI</b></td><td>Cost Performance Index</td><td>EV ÷ AC. 0.9 = for €1 of work you pay about €1.11</td></tr>
  <tr><td><b>SPI</b></td><td>Schedule Performance Index</td><td>EV ÷ PV. 0.9 = 10 % behind plan</td></tr>
  <tr><td><b>EAC</b></td><td>Estimate at Completion</td><td>Forecast of the total costs = BAC ÷ CPI</td></tr>
  <tr><td><b>ETC</b></td><td>Estimate to Complete</td><td>still expected costs = EAC − AC</td></tr>
  <tr><td><b>VAC</b></td><td>Variance at Completion</td><td>BAC − EAC. Negative = expected additional costs</td></tr>
</table>
<h3>Example</h3>
<p>BAC €100,000, 40 % done so far (EV €40,000), but €50,000 spent: CPI = 0.8 → EAC = €125,000 → you have to expect <b>€25,000 of additional costs</b> if things continue like this.</p>`,
  },
}
