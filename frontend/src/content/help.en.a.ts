// Englische Handbuchtexte, Teil A (Erste Schritte, Planen). Schlüssel = Themen-ID aus help.ts.
import type { HelpText } from './help.en'

export const helpEnA: Record<string, HelpText> = {
  start: {
    title: 'Welcome to OpenPlan',
    summary: 'What OpenPlan can do and how to get started in five minutes.',
    html: `
<h2>Welcome to OpenPlan</h2>
<p>OpenPlan is project planning in the browser – an open-source alternative to MS Project. You plan tasks with dates and dependencies, see the critical path, distribute work across your team and keep an eye on the budget.</p>
<h3>Your first plan in five minutes</h3>
<ol>
  <li>In the <b>project list</b> click <b>+ New project</b> (name and start date are enough). You become the project <b>owner</b>.</li>
  <li>Create a <b>+ Task</b>. Enter name and duration by <b>double-clicking</b> the table cell.</li>
  <li>Link tasks: drag the blue dot at the right end of a bar onto the successor task – or enter the WBS number in the <b>Predecessors</b> column (e.g. <code>1.1</code>).</li>
  <li>Build phases: select a task and click <b>⇥</b> (indent) – it becomes a subtask of the row above.</li>
  <li>Plan ready? Click <b>Set baseline</b> in the Gantt. From now on OpenPlan shows deviations (tracking).</li>
</ol>
<h3>The fastest way to learn is by example</h3>
<p>In the project list, <b>Create sample project</b> creates a complete network rollout (Cisco → Extreme, 3 employees, 4 sites, 60 devices) with plan, team, budget and actual costs – to try out and break.</p>
<h3>Where do I find what?</h3>
<table>
  <tr><th>Tab in the project</th><th>Purpose</th></tr>
  <tr><td><b>Gantt</b></td><td>Planning: tasks, dates, dependencies, status, baseline</td></tr>
  <tr><td><b>Team</b></td><td>Utilisation per person, reschedule by dragging</td></tr>
  <tr><td><b>Packages</b></td><td>Assign work packages directly or provide them for self-service</td></tr>
  <tr><td><b>Calendar</b></td><td>Month/week/list view of the tasks</td></tr>
  <tr><td><b>Resources</b></td><td>People/devices, availability, daily rates</td></tr>
  <tr><td><b>Budget</b></td><td>Planned/actual costs, key figures, SAP reconciliation (owners only)</td></tr>
  <tr><td><b>History</b></td><td>Who changed what and when</td></tr>
</table>
<p class="help-tip">💡 <b>F1</b> or <b>?</b> opens the help for the current page at any time. You reach the complete manual via <b>Manual</b> in the top bar.</p>`,
  },
  projekte: {
    title: 'Project list',
    summary: 'Create and import projects, the sample project, owners.',
    html: `
<h2>Project list</h2>
<p>Here you see all projects you have access to: as <b>owner</b>, as <b>member</b> or as <b>admin</b>. Other people's projects are invisible to you.</p>
<h3>Actions</h3>
<ul>
  <li><b>+ New project</b> – the <b>wizard</b> guides you in five steps: <i>Type</i> (empty project, network/device rollout, server migration, release transition – the type creates phases, tasks and milestones), <i>Basic data</i> (name, description, start, working days, holidays; you become the owner, <i>admins</i> can choose a different one), <i>Team</i> (members via search, editor or reader), <i>Reports</i> (automatic project report) and <i>Done</i> (summary). You set up resources, budget and baseline afterwards in the project. <b>Quick create</b> in the wizard opens the short dialog with only name and start.</li>
  <li><b>Create sample project</b> – choose an example: <i>Network rollout Cisco → Extreme</i> (devices, sites), <i>Server migration hypervisor → new cluster</i> (120 VMs in four waves) or <i>Transition release change</i> (test, training, cutover, hypercare, handover) – each with plan, team, budget and actual costs. The texts of the server migration and the transition are created in your language. Every click creates a new sample.</li>
  <li><b>Import …</b> – MS Project XML (MSPDI) or OpenPlan JSON, see <i>Import &amp; export</i>.</li>
  <li><b>Delete</b> (on the card) – only for the owner/admin; permanently removes tasks, costs and documents.</li>
</ul>
<p>Each card shows the owner (👤), the number of tasks and the project start.</p>
<h3>Search &amp; filter</h3>
<p>The search field above the cards searches <b>name, description and owner</b> (several words = all must match; case and umlauts do not matter). You can also filter by <b>my projects</b> or by <b>owner</b> and sort by change, name, start or end. The browser remembers the selection (without the search text). Administrators find the same for <b>users</b> in the administration (name, email, role, sign-in type).
<p class="help-tip">💡 Can't see an expected project? Ask the owner to add you under <b>Settings → Members</b>.</p>`,
  },
  dashboard: {
    title: 'Management dashboard',
    summary: 'Portfolio traffic light, deadlines, milestones, risks, utilisation and budget on one page – exportable as image or PDF.',
    html: `
<h2>Management dashboard</h2>
<p>The <b>Dashboard</b> (top bar) gives board members, department heads and project leads an overview of <b>all projects they may see</b> (admins and “Viewer (all projects)” see all, everyone else their own). It is view-only and refreshes every 5 minutes. Use <b>PNG</b> and <b>PDF</b> at the top right to export the page for slides.</p>
<h3>Traffic-light rules</h3>
<ul>
  <li><b>Red</b> – a task plans its end <i>after its deadline</i>, OR more than <b>10 %</b> of the tasks are overdue, OR anything is <i>blocked</i>.</li>
  <li><b>Yellow</b> – not red, but at least one task is overdue.</li>
  <li><b>Green</b> – otherwise. <b>Completed</b> = all tasks done, <b>Empty</b> = no tasks yet.</li>
  <li>The <b>budget</b> does not feed into the traffic light but is shown next to it (actual / budget, CPI/SPI, ⚠ when exceeded) – only for projects whose costs you may see. “Overdue” means: planned end is before today and the task is not done.</li>
</ul>
<h3>Sections</h3>
<ul>
  <li><b>Tiles</b> – number of projects by colour, exceeded deadlines, overdue and blocked tasks, overloaded people, people absent today, average progress of running projects, total budget.</li>
  <li><b>Project traffic light</b> – one row per project (red first) with reason, progress, end, budget and next milestone; the chips filter by colour, a click on the name opens the project.</li>
  <li><b>Milestones</b> – timeline of the next 60 days (overdue red, critical violet).</li>
  <li><b>Risks &amp; action needed</b> – exceeded deadlines, blocked and overdue tasks with project and assignee; a click opens the task.</li>
  <li><b>Utilisation &amp; absence</b> – overload of the next 30 days and who is away today (same source as “Who works on what”).</li>
</ul>
<p class="help-tip">💡 Its value depends on maintained data: deadlines on tasks, status and assigned resources. The <b>portfolio report</b> (Reports, email) uses the same traffic light (wording there: critical / attention / on track / completed) and names the reason for each project; the budget is also shown next to it there and does not change the colour.</p>`,
  },
  uebersicht: {
    title: 'Who works on what (overview)',
    summary: 'People and projects at a glance – utilisation, absence, project membership.',
    html: `
<h2>Who works on what</h2>
<p>The <b>Who works on what</b> page (top bar) is meant for managers and project owners: across <b>all projects you may see</b> it shows who works where. Admins and “Viewer (all projects)” see every project, everyone else their own. The page is view-only – make changes in the project as usual.</p>
<h3>People tab</h3>
<ul>
  <li><b>Utilisation today</b> – sum of assignments across all projects (bar; red = more than available). <b>Peak 30 d</b> is the highest daily load over the next 30 days; ⚠ means overload or assignment during an absence.</li>
  <li><b>Absence</b> – who is away today (grey, with return date) or when the next absence is due. “Sick” is shown to others as “Other”; only the person concerned sees notes.</li>
  <li><b>Projects</b> – a chip per project with the number of open tasks; <b>★</b> = project lead, red border = overdue tasks (<b>!n</b>), orange border = blocked. A click opens the project, the tooltip names the role and the latest end.</li>
  <li>Filters <b>Overloaded (30 days)</b> and <b>Absent today</b> plus search across people and projects.</li>
</ul>
<h3>Projects tab</h3>
<p>One card per project: lead, end, progress (completed tasks), overdue and blocked tasks, and below all participants with role (★ project lead, 👥 member, 🔧 works on tasks), open tasks and current utilisation.</p>
<h3>Who appears?</h3>
<p>Project owners, members and all resources. A resource with a linked user (tab Resources → column <i>User</i>) is merged with that user even if it appears in several projects. Resources <b>without</b> a user (◌) are combined by name.</p>
<p class="help-tip">💡 Utilisation is only right when tasks have resources assigned. Everyone enters their personal absences under <b>My absences</b>.</p>`,
  },
  todo: {
    title: 'My tasks (to-do list)',
    summary: 'All open tasks assigned to you – across all projects, sorted by date.',
    html: `
<h2>My tasks</h2>
<p>Under <b>My tasks</b> (top bar) you see all open tasks that are <b>assigned to you</b> – across <b>all projects</b>, sorted by end or deadline and grouped into <b>Overdue</b>, <b>This week</b> and <b>Later</b>. The number chip next to the menu item shows the count (red if something is overdue).</p>
<ul>
  <li><b>✓</b> on the left marks the task as done (progress 100 %) – it disappears from the list.</li>
  <li>Clicking the name opens the details of the task in the project, clicking the project name opens the project.</li>
  <li>The chips at the top filter by <b>Overdue</b>, <b>This week</b>, <b>Later</b> or <b>Blocked</b>; the search covers project, WBS number, name and block reason.</li>
  <li>A set <b>deadline</b> takes precedence over the planned end. <b>●</b> = critical path; blocked tasks carry an orange border with the reason.</li>
  <li>Below the list you see how many open <b>work packages in the pool</b> of your projects are waiting to be claimed (tab <i>Packages</i>).</li>
</ul>
<p class="help-tip">💡 The list is empty? Then your <b>resource is not linked to your user</b> (tab Resources → column <i>User</i>), or nothing is assigned to you.</p>`,
  },
  gantt: {
    title: 'Gantt & task table',
    summary: 'Edit the table, drag bars, zoom, filter, multiple selection.',
    html: `
<h2>Gantt &amp; task table</h2>
<p>The table is on the left, the timeline on the right. Both scroll vertically together; the chart has its own horizontal scrollbar. The <b>divider</b> between them can be dragged (double-click = default width).</p>
<h3>Editing the table</h3>
<p><b>Double-click</b> a cell, <b>Enter</b> confirms, <b>Esc</b> cancels.</p>
<table>
  <tr><th>Column</th><th>Meaning</th></tr>
  <tr><td>✓</td><td>Tick = done (sets 100 %). Click again = open again.</td></tr>
  <tr><td>WBS</td><td>Outline number (1, 1.1, 1.2 …) – assigned automatically</td></tr>
  <tr><td>Duration</td><td>in working days; <b>◆</b> = milestone (duration 0)</td></tr>
  <tr><td>Start / End</td><td>calculated. Changing the start sets "Start no earlier than" (📌)</td></tr>
  <tr><td>%</td><td>Progress, coupled to the status</td></tr>
  <tr><td>Status</td><td>Open · In progress · Blocked · Done</td></tr>
  <tr><td>Predecessors</td><td>e.g. <code>2, 3SS+1D, 4FF-1D</code> – see <i>Dependencies</i></td></tr>
  <tr><td>Δ Start / Δ End</td><td>Deviation from the baseline (only with a baseline)</td></tr>
</table>
<h3>In the chart</h3>
<ul>
  <li><b>Drag a bar</b> – moves the task (sets "Start no earlier than").</li>
  <li><b>Drag the right edge</b> – changes the duration.</li>
  <li><b>Drag the blue dot at the bar end</b> onto another task – links them (finish→start).</li>
  <li><b>Drag a summary bar (black)</b> – moves the whole phase.</li>
  <li><b>Double-click</b> – opens the details (constraint, resources, documents, notes).</li>
  <li><b>◌ / ▣</b> behind the name marks a <i>work package</i>: ◌ = open in the pool, ▣ = claimed/assigned.</li>
  <li>The red dashed line is <b>today</b>; weekends and holidays are grey.</li>
</ul>
<h3>Toolbar</h3>
<ul>
  <li><b>↶ / ↷</b> (<b>Ctrl+Z</b> / <b>Ctrl+Y</b>) – undoes or repeats the last plan change. The tooltip names the change. Applies to tasks, dependencies, resources, assignments and baseline (up to 20 steps); not to project settings, budget and documents. The person who made the change and the owner may undo it.</li>
  <li><b>+ Task / ◆ Milestone</b> – inserts behind the selected row.</li>
  <li><b>⇤ ⇥ ↑ ↓</b> – outdent, indent, move up/down.</li>
  <li><b>✓ Done</b> and <b>Set status …</b> – apply to the whole selection.</li>
  <li><b>Today</b> jumps to the current day; <b>Days/Weeks/Months</b> changes the time scale.</li>
  <li><b>Status filter</b> – e.g. "Not done" or "Blocked only". Phases with matching subtasks stay visible.</li>
  <li><b>Critical path</b> / <b>Baseline</b> – switch the display on/off.</li>
  <li><b>Float</b> – shows the columns <b>Float</b> (total float) and <b>free float</b>, draws a dashed <b>float line</b> behind each bar and colours <b>near-critical</b> tasks orange. Set what counts as near with <b>near ≤ n d</b> (default 2 days).</li>
  <li><b>Export … → Image / PDF for slides</b> – creates a clean, always light Gantt for board and management as <b>PNG</b> (double resolution, sharp on slides), <b>SVG</b> (vector, can be inserted into PowerPoint) or <b>PDF</b> (print dialog → “Save as PDF”, margins “None”). You can choose the <b>scope</b> (all tasks, only <i>phases &amp; milestones</i> as a management view with labels on the bars, critical path only), <b>format</b> (slide 16:9, A4/A3 landscape or original size; too many rows are split across several pages), period, columns, title/subtitle as well as today line, critical path, baseline, dependencies and legend. The preview shows the result live; the browser remembers the settings.</li>
  <li><b>Critical only</b> – shows only tasks on the critical path with their phases (can be combined with the status filter).</li>
</ul>
<h3>Multiple selection</h3>
<p><b>Ctrl-click</b> selects single rows, <b>Shift-click</b> a range. Then e.g. <b>✓ Done</b>.</p>
<p class="help-tip">💡 Can't see the edit buttons? Then you only have read access in this project.</p>`,
  },
  struktur: {
    title: 'Structure: phases & milestones',
    summary: 'Summary tasks, indenting, moving phases, milestones.',
    html: `
<h2>Structure: phases &amp; milestones</h2>
<h3>Summary tasks (phases)</h3>
<p>A task with subtasks is a <b>summary task</b>. Its dates, duration, progress and status are <b>calculated from the subtasks</b> – so duration, end and % cannot be changed directly there (a hint explains this).</p>
<ul>
  <li><b>Indent ⇥</b> makes the selected row a subtask of the row above, <b>Outdent ⇤</b> reverses it.</li>
  <li><b>▾ / ▸</b> expands or collapses a phase.</li>
  <li><b>Moving a phase:</b> change the start of the phase or drag the summary bar. All entry subtasks are fixed accordingly, the rest follows via the dependencies.</li>
  <li><b>Setting the status of a phase</b> applies to <i>all</i> subtasks (with confirmation).</li>
</ul>
<h3>Dependencies on phases</h3>
<p>Links from/to a phase are mapped internally to its subtasks. A link between a phase and its <i>own</i> subtask is not allowed.</p>
<h3>Milestones ◆</h3>
<p>Milestones have duration 0 and – as in MS Project – lie at the <b>end</b> of the day. They are suited for approvals and handovers.</p>
<h3>Changing the order</h3>
<p><b>↑ ↓</b> moves within the level, <b>Alt+arrow keys</b> work the same way.</p>`,
  },
  abhaengigkeiten: {
    title: 'Dependencies & lag',
    summary: 'FS/SS/FF/SF, lag, notation in the Predecessors column.',
    html: `
<h2>Dependencies &amp; lag</h2>
<p>A dependency determines when a task may start or finish at the earliest.</p>
<table>
  <tr><th>Code</th><th>German</th><th>Meaning</th></tr>
  <tr><td><b>FS</b> (default)</td><td>EA</td><td><b>F</b>inish→<b>S</b>tart: the successor starts when the predecessor is finished</td></tr>
  <tr><td><b>SS</b></td><td>AA</td><td><b>S</b>tart→<b>S</b>tart: both start together (or offset)</td></tr>
  <tr><td><b>FF</b></td><td>EE</td><td><b>F</b>inish→<b>F</b>inish: both finish together</td></tr>
  <tr><td><b>SF</b></td><td>AE</td><td><b>S</b>tart→<b>F</b>inish: rare – the successor only finishes when the predecessor starts</td></tr>
</table>
<h3>Notation in the "Predecessors" column</h3>
<table>
  <tr><th>Input</th><th>Effect</th></tr>
  <tr><td><code>3</code></td><td>Finish→start to WBS 3</td></tr>
  <tr><td><code>2, 4</code></td><td>two predecessors (comma or semicolon)</td></tr>
  <tr><td><code>3SS</code></td><td>Start→start to WBS 3</td></tr>
  <tr><td><code>3FS+2D</code></td><td>Finish→start with <b>2 working days of lag</b></td></tr>
  <tr><td><code>4FF-1D</code></td><td>Finish→finish, the successor finishes 1 day <b>earlier</b> (negative lag = overlap)</td></tr>
</table>
<p>The German codes (<code>EA</code>, <code>AA</code>, <code>EE</code>, <code>AE</code>, and <code>T</code> for days) are understood as well.</p>
<h3>With the mouse</h3>
<p>Drag the blue dot at the bar end onto the successor task – this creates finish→start without lag. You can change type and lag in the column or in the detail dialog.</p>
<h3>Cycles</h3>
<p>A loop (A→B→A) is rejected; the message names the tasks involved and the plan remains unchanged.</p>`,
  },
  termine: {
    title: 'Dates, constraints & critical path',
    summary: 'How dates are calculated, constraints, float.',
    html: `
<h2>Dates, constraints &amp; critical path</h2>
<h3>How OpenPlan calculates</h3>
<p>Every task starts as early as possible – limited by predecessors, project start and constraints. Calculation is in <b>working days</b> according to the project calendar (default Mon–Fri, holidays configurable under <b>Settings</b>). There you choose a <b>federal state</b> and use <b>Load public holidays</b> to import the statutory holidays (source: api-feiertage.de) for the project year and the next two years; add your own days off (bridge days, company holidays) by hand – they are kept when you load again. The API currently only provides 2026–2028; add later years by hand.</p>
<h3>Constraints</h3>
<p>In the detail dialog (double-click the task):</p>
<table>
  <tr><th>Constraint</th><th>Effect</th></tr>
  <tr><td>As soon as possible</td><td>Default – only dependencies determine the date</td></tr>
  <tr><td>Start no earlier than</td><td>The task does not start before the date (📌). Also created when dragging in the chart</td></tr>
  <tr><td>Manual: start on (fixed)</td><td>The start is fixed; predecessors are ignored ("manually scheduled")</td></tr>
  <tr><td>End no later than</td><td>affects the float: shows how much room remains until the deadline</td></tr>
</table>
<h3>Float &amp; critical path</h3>
<ul>
  <li><b>Float</b> (total float): how many working days a task may slip without moving the project end (in the detail dialog).</li>
  <li><b>Critical</b> = float 0. These tasks are <b>red</b>, as are the arrows between them. Any delay there moves the project end.</li>
  <li>In very linear plans (e.g. a rollout site after site) almost everything is critical – that is correct, not an error.</li>
  <li>With the <b>Critical path</b> checkbox in the bar you hide the red colouring.</li>
</ul>
<p class="help-tip">💡 You cannot allow a start <i>earlier</i> than the predecessor unless you choose "Manual: start on (fixed)".</p>`,
  },
  status: {
    title: 'Status & progress',
    summary: 'Open, In progress, Blocked, Done – and how they relate to %.',
    html: `
<h2>Status &amp; progress</h2>
<p>Every task has a status: <b>Open</b>, <b>In progress</b>, <b>Blocked</b> (with an optional reason) or <b>Done</b>.</p>
<h3>Coupling with progress</h3>
<table>
  <tr><th>You …</th><th>Result</th></tr>
  <tr><td>set status <b>Done</b> / click the tick</td><td>Progress = 100 %</td></tr>
  <tr><td>set status <b>Open</b></td><td>Progress = 0 %</td></tr>
  <tr><td>set progress to <b>100 %</b></td><td>Status = Done</td></tr>
  <tr><td>set progress <b>&gt; 0 %</b> while "Open"</td><td>Status = In progress</td></tr>
  <tr><td>change from Done to <b>In progress</b> or <b>Blocked</b></td><td>Progress drops to 90 % (100 % does not fit "not finished")</td></tr>
  <tr><td>set status <b>Blocked</b></td><td>Progress stays; enter the reason in the detail dialog (appears as a tooltip)</td></tr>
</table>
<h3>Summary tasks</h3>
<p>The status of a phase is derived: all subtasks done → Done; one blocked → Blocked; otherwise In progress (if something has been started or finished) or Open. If you set the status of a phase yourself, it applies to <b>all subtasks</b>.</p>
<h3>Appearance</h3>
<ul>
  <li><b>Done:</b> row grey and struck through, bar pale with ✓.</li>
  <li><b>Blocked:</b> orange border, bar with ⛔ and dashed border; in the project header a chip "n blocked" counts them (click filters).</li>
</ul>
<h3>Several tasks at once</h3>
<p>Select with <b>Ctrl-/Shift-click</b>, then <b>✓ Done</b> or <b>Set status …</b>. The <b>status filter</b> in the bar hides completed tasks.</p>
<p class="help-tip">💡 Progress feeds into the budget key figures: completed tasks count fully as "earned value" (EV).</p>`,
  },
  basisplan: {
    title: 'Baseline & tracking',
    summary: 'Freeze the plan and track deviations.',
    html: `
<h2>Baseline &amp; tracking</h2>
<p>The <b>baseline</b> is a snapshot of your plan (dates and planned costs) against which you later compare the actual progress.</p>
<h3>Setting and deleting</h3>
<ul>
  <li><b>Set baseline</b> (owner only) saves start, end and planned costs of all tasks. Setting it again overwrites it.</li>
  <li><b>×</b> next to the button deletes the baseline.</li>
</ul>
<h3>Tracking in the Gantt</h3>
<ul>
  <li>Below each bar a <b>grey stripe</b> shows the baseline date.</li>
  <li>The columns <b>Δ Start</b> and <b>Δ End</b> give the deviation in working days: <span style="color:#dc2626">+3 D</span> = 3 days later than planned, <span style="color:#16a34a">−2 D</span> = earlier.</li>
  <li>With the <b>Baseline</b> checkbox in the bar you hide stripes and Δ columns.</li>
</ul>
<h3>Effect on the budget</h3>
<p>The baseline determines the <b>target</b> of the cost key figures (BAC, PV). Later plan changes do not alter the BAC – that is exactly how you recognise additional costs.</p>
<p class="help-tip">💡 Set the baseline as soon as the plan is approved – and before the first changes in the running project.</p>`,
  },
}
