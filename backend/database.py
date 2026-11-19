import logging
import secrets
import sqlite3

from config import DATA_DIR, DB_PATH, ADMIN_USERNAME, ADMIN_PASSWORD

log = logging.getLogger("openplan")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'editor' CHECK (role IN ('admin','editor','viewer')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    start_date TEXT NOT NULL,
    work_days TEXT NOT NULL DEFAULT '0,1,2,3,4',
    holidays TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    name TEXT NOT NULL,
    duration INTEGER NOT NULL DEFAULT 1,
    percent REAL NOT NULL DEFAULT 0,
    constraint_type TEXT NOT NULL DEFAULT 'ASAP',
    constraint_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    baseline_start TEXT,
    baseline_finish TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','blocked','done')),
    status_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE TABLE IF NOT EXISTS deps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    pred_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    succ_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    type TEXT NOT NULL DEFAULT 'FS' CHECK (type IN ('FS','SS','FF','SF')),
    lag INTEGER NOT NULL DEFAULT 0,
    UNIQUE (pred_id, succ_id)
);
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    max_units REAL NOT NULL DEFAULT 100,
    cost_rate REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS absences (               -- Abwesenheiten je Ressource (Urlaub, Schulung, Krankheit, Sonstiges), Tage inklusive
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'vacation' CHECK (kind IN ('vacation','training','sick','other')),
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_absences_res ON absences(resource_id);
CREATE TABLE IF NOT EXISTS user_absences (           -- persönliche Abwesenheiten: gelten in allen Projekten, in denen der Benutzer eine Ressource ist
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'vacation' CHECK (kind IN ('vacation','training','sick','other')),
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_user_absences_user ON user_absences(user_id);
CREATE TABLE IF NOT EXISTS assignments (
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    units REAL NOT NULL DEFAULT 100,
    PRIMARY KEY (task_id, resource_id)
);
CREATE TABLE IF NOT EXISTS project_members (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'editor' CHECK (role IN ('editor','viewer')),
    PRIMARY KEY (project_id, user_id)
);
CREATE TABLE IF NOT EXISTS cost_centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    UNIQUE (project_id, code)
);
CREATE TABLE IF NOT EXISTS cost_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    UNIQUE (project_id, code)
);
CREATE TABLE IF NOT EXISTS cost_items (            -- Plan: feste Kosten je Vorgang (EUR)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    cost_type_id INTEGER REFERENCES cost_types(id),
    cost_center_id INTEGER REFERENCES cost_centers(id),
    amount REAL NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS budget_lines (          -- beide NULL = Gesamtbudget
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cost_center_id INTEGER REFERENCES cost_centers(id),
    cost_type_id INTEGER REFERENCES cost_types(id),
    amount REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS actuals (               -- Ist-Kosten (EUR), manuell oder per CSV-Import
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    booking_date TEXT NOT NULL,
    cost_type_id INTEGER REFERENCES cost_types(id),
    cost_center_id INTEGER REFERENCES cost_centers(id),
    amount REAL NOT NULL,
    reference TEXT NOT NULL DEFAULT '',            -- z. B. SAP-Belegnummer (Dubletten-Schutz)
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_actuals_project ON actuals(project_id, booking_date);
CREATE TABLE IF NOT EXISTS task_files (          -- Dokumente an Vorgängen (Datei liegt unter DATA_DIR/files)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    size INTEGER NOT NULL,
    mime TEXT NOT NULL DEFAULT 'application/octet-stream',
    comment TEXT NOT NULL DEFAULT '',
    uploaded_by TEXT NOT NULL DEFAULT '',
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    kind TEXT NOT NULL DEFAULT 'file',            -- 'file' (hochgeladen) | 'link' (z. B. OneDrive/SharePoint)
    url TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_task_files_task ON task_files(task_id);
CREATE TABLE IF NOT EXISTS task_templates (       -- Vorlagen-Bibliothek (global): ein Gerätetyp = eine Vorlage
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS task_template_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES task_templates(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    duration INTEGER NOT NULL DEFAULT 1,
    wait_days INTEGER NOT NULL DEFAULT 0,             -- Wartezeit (Lag) vor dem nächsten Schritt, z. B. Lieferzeit
    pred_pos INTEGER,                                 -- Position des Vorgänger-Schritts (EA), NULL = keiner
    books_price INTEGER NOT NULL DEFAULT 0,           -- Preis der Geräteliste -> Plankosten an diesem Schritt
    uses_window INTEGER NOT NULL DEFAULT 0,           -- Wartungsfenster der Geräteliste -> Erledigungszeitraum dieses Schritts
    takes_lead INTEGER NOT NULL DEFAULT 0,            -- „Lieferzeit (Tage)“ der Geräteliste überschreibt die Wartezeit dieses Schritts
    UNIQUE (template_id, position)
);
CREATE TABLE IF NOT EXISTS project_role_map (         -- Rolle der Vorlagenschritte -> Ressource im Projekt
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, role)
);
CREATE TABLE IF NOT EXISTS audit_log (          -- Nachvollziehbarkeit: Anmeldungen, Verwaltung, Backup, Löschungen
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    username TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(id DESC);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_comments_task ON comments(task_id, id);
CREATE TABLE IF NOT EXISTS reminder_log (          -- Entdoppelung automatischer Erinnerungen (Schlüssel je Vorgang/Termin)
    key TEXT PRIMARY KEY,
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notifications (      -- Glocke: Zuteilungen, Reports (mit Link)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER,
    kind TEXT NOT NULL,                          -- assigned | unassigned | report
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    read_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read_at, id DESC);
CREATE TABLE IF NOT EXISTS cost_center_owners (   -- Kostenstellenverantwortliche (global je Kostenstellen-Code)
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS report_subscriptions (  -- übergreifende Reports (Vorgesetzte / Kostenstellenverantwortliche)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('portfolio','costcenter')),
    name TEXT NOT NULL DEFAULT '',
    project_ids TEXT NOT NULL DEFAULT '',         -- Komma-Liste; leer = alle Projekte
    include_costs INTEGER NOT NULL DEFAULT 0,
    weekday INTEGER NOT NULL DEFAULT 0,           -- 0 = Montag … 6 = Sonntag, -1 = werktäglich
    hour INTEGER NOT NULL DEFAULT 7,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_sent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS app_settings (        -- in der Verwaltung gepflegte Einstellungen (z. B. LDAP), JSON je Schlüssel
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS undo_stack (          -- Snapshots für Rückgängig/Wiederholen (siehe history.py)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('undo','redo')),
    label TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    snapshot TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_undo_project ON undo_stack(project_id, kind, id DESC);
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id INTEGER,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_project ON journal(project_id, id DESC);
CREATE TABLE IF NOT EXISTS api_tokens (          -- langlebige Zugangsschlüssel für Dienstkonten (users.auth_source='service'); nur der SHA-256-Hash wird gespeichert
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    prefix TEXT NOT NULL,                        -- erste Zeichen, nur zur Anzeige
    scope TEXT NOT NULL DEFAULT 'read' CHECK (scope IN ('read','write')),
    project_ids TEXT NOT NULL DEFAULT '',        -- kommagetrennt; leer = alle Projekte, die das Konto sehen darf
    expires_at TEXT,
    last_used_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
CREATE TABLE IF NOT EXISTS external_refs (       -- Verweise auf Fremdsysteme je Vorgang (z. B. ServiceNow-Change, AWX-Job); ein Eintrag je Vorgang und System
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    system TEXT NOT NULL,
    ref TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    UNIQUE (task_id, system)
);
CREATE INDEX IF NOT EXISTS idx_external_refs_ref ON external_refs(ref COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS webhooks (            -- ausgehende Webhooks (siehe webhooks.py); secret für die HMAC-Signatur
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    events TEXT NOT NULL DEFAULT '*',            -- kommagetrennt, '*' = alle
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,   -- NULL = alle Projekte
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_try TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ok','failed')),
    last_code INTEGER,
    last_error TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_due ON webhook_deliveries(status, next_try);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_hook ON webhook_deliveries(webhook_id, id DESC);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Leichte Migrationen für bestehende Datenbanken."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    ucols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    if "email" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
    if "see_all" not in ucols:   # 1 = „Betrachter alle Projekte“ (nur zusammen mit Rolle viewer wirksam)
        conn.execute("ALTER TABLE users ADD COLUMN see_all INTEGER NOT NULL DEFAULT 0")
    if "lang" not in ucols:      # NULL = Standard (Deutsch)
        conn.execute("ALTER TABLE users ADD COLUMN lang TEXT")
    if "theme" not in ucols:     # NULL/'auto' = Systemeinstellung, sonst 'light' | 'dark'
        conn.execute("ALTER TABLE users ADD COLUMN theme TEXT")
    if "notify_email" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN notify_email INTEGER NOT NULL DEFAULT 1")
    for col, ddl in (("report_enabled", "INTEGER NOT NULL DEFAULT 0"), ("report_weekday", "INTEGER NOT NULL DEFAULT 0"),
                     ("report_hour", "INTEGER NOT NULL DEFAULT 7"), ("report_to", "TEXT NOT NULL DEFAULT 'owner'"), ("report_last", "TEXT")):
        if col not in cols:
            conn.execute("ALTER TABLE projects ADD COLUMN %s %s" % (col, ddl))
    if "display_name" not in ucols:  # Anzeigename (AD: displayName); leer = Benutzername wird angezeigt
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
    if "token_version" not in ucols:   # wird bei Passwortwechsel/-reset und „Sitzungen beenden“ erhöht -> alte Tokens werden ungültig
        conn.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
    if "reports_to" not in {r[1] for r in conn.execute("PRAGMA table_info(resources)")}:   # Organigramm: berichtet an (NULL = Projektleitung)
        conn.execute("ALTER TABLE resources ADD COLUMN reports_to INTEGER REFERENCES resources(id) ON DELETE SET NULL")
    if "funktion" not in {r[1] for r in conn.execute("PRAGMA table_info(resources)")}:   # Funktion der Ressource im Projekt (Freitext)
        conn.execute("ALTER TABLE resources ADD COLUMN funktion TEXT NOT NULL DEFAULT ''")
    if "auth_source" not in ucols:   # 'local' | 'ldap'
        conn.execute("ALTER TABLE users ADD COLUMN auth_source TEXT NOT NULL DEFAULT 'local'")
    if "owner_id" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN owner_id INTEGER REFERENCES users(id)")
    if "holiday_state" not in cols:     # Bundesland-Kürzel (nw, he, …) für den Feiertagsimport, leer = keins gewählt
        conn.execute("ALTER TABLE projects ADD COLUMN holiday_state TEXT NOT NULL DEFAULT ''")
    if "members_see_costs" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN members_see_costs INTEGER NOT NULL DEFAULT 0")
    rcols = {r[1] for r in conn.execute("PRAGMA table_info(resources)")}
    if "cost_center_id" not in rcols:
        conn.execute("ALTER TABLE resources ADD COLUMN cost_center_id INTEGER REFERENCES cost_centers(id)")
    if "cost_type_id" not in rcols:
        conn.execute("ALTER TABLE resources ADD COLUMN cost_type_id INTEGER REFERENCES cost_types(id)")
    tcols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)")}
    if "status" not in tcols:   # Bestand: Status aus Fortschritt ableiten
        conn.execute("ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
        conn.execute("UPDATE tasks SET status = CASE WHEN percent >= 100 THEN 'done' WHEN percent > 0 THEN 'in_progress' ELSE 'open' END")
    if "status_note" not in tcols:
        conn.execute("ALTER TABLE tasks ADD COLUMN status_note TEXT NOT NULL DEFAULT ''")
    fcols = {r[1] for r in conn.execute("PRAGMA table_info(task_files)")}
    if fcols and "kind" not in fcols:
        conn.execute("ALTER TABLE task_files ADD COLUMN kind TEXT NOT NULL DEFAULT 'file'")
    if fcols and "url" not in fcols:
        conn.execute("ALTER TABLE task_files ADD COLUMN url TEXT NOT NULL DEFAULT ''")
    for col, ddl in (("ext_key", "TEXT"), ("attrs", "TEXT"), ("tpl_step", "INTEGER"), ("tpl_id", "INTEGER")):   # Geräte-/Schritt-Kennung (Import)
        if col not in tcols:
            conn.execute("ALTER TABLE tasks ADD COLUMN %s %s" % (col, ddl))
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_extkey ON tasks(project_id, ext_key)")
    if "deadline" not in tcols:       # Frist = „bis“ des Erledigungszeitraums (das „von“ ist der Constraint „Beginn frühestens“)
        conn.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")
    if "status_since" not in tcols:   # seit wann der aktuelle Status gilt (für „blockiert seit n Tagen")
        conn.execute("ALTER TABLE tasks ADD COLUMN status_since TEXT")
        conn.execute("UPDATE tasks SET status_since=date('now') WHERE status='blocked'")
    conn.execute("CREATE TRIGGER IF NOT EXISTS trg_status_since AFTER UPDATE OF status ON tasks WHEN old.status != new.status "
                 "BEGIN UPDATE tasks SET status_since=date('now') WHERE id=new.id; END")
    conn.execute("CREATE TRIGGER IF NOT EXISTS trg_status_since_new AFTER INSERT ON tasks WHEN new.status_since IS NULL "
                 "BEGIN UPDATE tasks SET status_since=date('now') WHERE id=new.id; END")
    if "pool" not in tcols:     # Arbeitspaket zur Selbstübernahme
        conn.execute("ALTER TABLE tasks ADD COLUMN pool INTEGER NOT NULL DEFAULT 0")
    if "user_id" not in rcols:  # Verknüpfung Ressource <-> Benutzer (für „Übernehmen")
        conn.execute("ALTER TABLE resources ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
    if "baseline_cost" not in tcols:
        conn.execute("ALTER TABLE tasks ADD COLUMN baseline_cost REAL")
    # Projekte ohne Verantwortlichen: dem ersten Admin zuordnen
    admin = conn.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    if admin:
        conn.execute("UPDATE projects SET owner_id=? WHERE owner_id IS NULL", (admin[0],))


def init_db() -> None:
    from auth import hash_password
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            pw = ADMIN_PASSWORD or secrets.token_urlsafe(12)
            conn.execute("INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?,?, 'admin')",
                         (ADMIN_USERNAME, hash_password(pw)))
            if not ADMIN_PASSWORD:
                log.warning("Initialer Admin angelegt: %s / %s (ADMIN_PASSWORD setzen, um dies zu vermeiden)",
                            ADMIN_USERNAME, pw)
        from devices import seed_defaults
        seed_defaults(conn)
        from devices import seed_english
        seed_english(conn)
        conn.commit()
    finally:
        conn.close()
