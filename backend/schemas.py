from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: Optional[str] = Field(None, min_length=8, max_length=128)   # bei source='ldap' nicht nötig
    role: Literal["admin", "editor", "viewer"] = "editor"
    display_name: str = Field("", max_length=120)
    source: Literal["local", "ldap"] = "local"
    see_all: bool = False                      # nur mit Rolle viewer: „Betrachter alle Projekte“


class SeeAllIn(BaseModel):
    see_all: bool


class RoleIn(BaseModel):
    role: Literal["admin", "editor", "viewer"]


class ReportsToIn(BaseModel):
    reports_to: Optional[int] = None


class DisplayNameIn(BaseModel):
    display_name: str = Field("", max_length=120)


class AdminPasswordIn(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    start_date: date
    work_days: List[int] = [0, 1, 2, 3, 4]
    holidays: List[date] = []
    holiday_state: str = Field("", max_length=2)
    owner_id: Optional[int] = None          # nur Admin darf einen anderen als sich selbst setzen


class WizardIn(BaseModel):
    """Assistent „Neues Projekt“: Projektart, Grunddaten, Team und Berichte in einem Schritt anlegen."""
    kind: Literal["empty", "network", "migration", "release"] = "empty"
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    start_date: date
    work_days: List[int] = [0, 1, 2, 3, 4]
    holidays: List[date] = []
    holiday_state: str = Field("", max_length=2)
    owner_id: Optional[int] = None
    members: List["MemberIn"] = []
    report_enabled: bool = False
    report_weekday: int = Field(0, ge=0, le=6)
    report_hour: int = Field(7, ge=0, le=23)
    report_to: Literal["owner", "members"] = "owner"


class MemberIn(BaseModel):
    user_id: int
    role: Literal["editor", "viewer"] = "editor"


WizardIn.model_rebuild()


class ProjectPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    start_date: Optional[date] = None
    work_days: Optional[List[int]] = None
    holidays: Optional[List[date]] = None
    holiday_state: Optional[str] = Field(None, max_length=2)
    owner_id: Optional[int] = None
    report_enabled: Optional[bool] = None            # Projektreport (siehe reports.py)
    report_weekday: Optional[int] = Field(None, ge=0, le=6)
    report_hour: Optional[int] = Field(None, ge=0, le=23)
    report_to: Optional[Literal["owner", "members"]] = None


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    parent_id: Optional[int] = None
    after_id: Optional[int] = None          # direkt hinter diesem Geschwister einfügen
    duration: int = Field(1, ge=0, le=5000)
    percent: float = Field(0, ge=0, le=100)
    constraint_type: Literal["ASAP", "SNET", "MSO", "FNLT"] = "ASAP"
    constraint_date: Optional[date] = None
    deadline: Optional[date] = None         # Frist: spätestens erledigt bis
    notes: str = ""
    pool: bool = False                      # Arbeitspaket zur Selbstübernahme


Status = Literal["open", "in_progress", "blocked", "done"]


class BulkStatusIn(BaseModel):
    task_ids: List[int] = Field(min_length=1, max_length=2000)
    status: Status


class TaskPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=300)
    duration: Optional[int] = Field(None, ge=0, le=5000)
    percent: Optional[float] = Field(None, ge=0, le=100)
    constraint_type: Optional[Literal["ASAP", "SNET", "MSO", "FNLT"]] = None
    constraint_date: Optional[date] = None
    clear_constraint_date: bool = False
    deadline: Optional[date] = None
    clear_deadline: bool = False
    notes: Optional[str] = None
    status: Optional[Status] = None
    status_note: Optional[str] = Field(None, max_length=300)
    pool: Optional[bool] = None


class MoveIn(BaseModel):
    parent_id: Optional[int] = None
    index: int = Field(0, ge=0)


class ShiftIn(BaseModel):
    days: int = Field(ge=-3650, le=3650)     # Kalendertage


class PredIn(BaseModel):
    pred_id: int
    type: Literal["FS", "SS", "FF", "SF"] = "FS"
    lag: int = Field(0, ge=-2000, le=2000)


class ResourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    max_units: float = Field(100, ge=0, le=10000)
    cost_rate: Optional[float] = Field(None, ge=0)         # EUR pro Tag; Kosten-Felder nur für Verantwortliche
    cost_center_id: Optional[int] = None
    cost_type_id: Optional[int] = None
    user_id: Optional[int] = None           # nur wirksam, wenn im Request gesetzt (Verknüpfung mit Projektmitglied)
    reports_to: Optional[int] = None        # Organigramm: Vorgesetzte Ressource im selben Projekt (None = Projektleitung); nur wirksam, wenn im Request gesetzt
    funktion: str = Field("", max_length=120)   # Funktion im Projekt (Freitext, z. B. Projektleiter); nur wirksam, wenn im Request gesetzt


class AbsenceIn(BaseModel):
    resource_id: Optional[int] = None       # beim Anlegen Pflicht, beim Ändern nicht änderbar
    start_date: date
    end_date: date
    kind: Literal["vacation", "training", "sick", "other"] = "vacation"
    note: str = Field("", max_length=200)


class LdapSettingsIn(BaseModel):
    enabled: Optional[bool] = None
    url: Optional[str] = Field(None, max_length=300)
    base_dn: Optional[str] = Field(None, max_length=500)
    domain: Optional[str] = Field(None, max_length=200)
    bind_dn: Optional[str] = Field(None, max_length=500)
    bind_password: Optional[str] = Field(None, max_length=500)       # leer = unverändert lassen
    clear_bind_password: bool = False
    user_filter: Optional[str] = Field(None, max_length=500)
    ca_pem: Optional[str] = Field(None, max_length=20000)
    required_group: Optional[str] = Field(None, max_length=500)
    admin_group: Optional[str] = Field(None, max_length=500)
    auditor_group: Optional[str] = Field(None, max_length=500)
    default_role: Optional[Literal["editor", "viewer"]] = None
    auto_create: Optional[bool] = None
    nested_groups: Optional[bool] = None


class AcmeSettingsIn(BaseModel):
    directory_url: Optional[str] = Field(None, max_length=500)
    domains: Optional[List[str]] = None
    email: Optional[str] = Field(None, max_length=200)
    ca_pem: Optional[str] = Field(None, max_length=20000)
    auto_renew: Optional[bool] = None
    renew_days: Optional[int] = Field(None, ge=1, le=60)


class ProfileIn(BaseModel):
    email: Optional[str] = Field(None, max_length=200)
    notify_email: Optional[bool] = None
    lang: Optional[Literal["de", "en"]] = None
    theme: Optional[Literal["auto", "light", "dark"]] = None


class MailSettingsIn(BaseModel):
    enabled: Optional[bool] = None
    host: Optional[str] = Field(None, max_length=200)
    port: Optional[int] = Field(None, ge=1, le=65535)
    security: Optional[Literal["none", "starttls", "ssl"]] = None
    username: Optional[str] = Field(None, max_length=200)
    password: Optional[str] = Field(None, max_length=500)
    clear_password: bool = False
    from_addr: Optional[str] = Field(None, max_length=200)
    from_name: Optional[str] = Field(None, max_length=100)
    public_url: Optional[str] = Field(None, max_length=300)


class MailTestIn(BaseModel):
    to: str = Field(max_length=200)


class ReportSubIn(BaseModel):
    user_id: int
    kind: Literal["portfolio", "costcenter"]
    name: str = Field("", max_length=120)
    project_ids: List[int] = []                       # leer = alle Projekte
    include_costs: bool = False
    weekday: int = Field(0, ge=-1, le=6)
    hour: int = Field(7, ge=0, le=23)
    enabled: bool = True


class CostOwnerIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field("", max_length=200)
    user_id: int


class BackupSettingsIn(BaseModel):
    enabled: Optional[bool] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    keep: Optional[int] = Field(None, ge=1, le=365)


class ReminderSettingsIn(BaseModel):
    enabled: Optional[bool] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    due_days: Optional[int] = Field(None, ge=0, le=14)
    escalate_days: Optional[int] = Field(None, ge=1, le=60)
    blocked_days: Optional[int] = Field(None, ge=1, le=60)


class AcmeFetchCaIn(BaseModel):
    url: str = Field(max_length=500)


class LdapTestIn(BaseModel):
    settings: Optional[LdapSettingsIn] = None          # ungespeicherte Formularwerte
    username: str = ""
    password: str = ""


class AssignIn(BaseModel):
    resource_id: Optional[int] = None          # vorhandene Ressource …
    user_id: Optional[int] = None              # … oder Benutzer: die verknüpfte Ressource wird bei Bedarf angelegt
    units: float = Field(100, ge=0, le=10000)

    @model_validator(mode="after")
    def _one_target(self):
        if (self.resource_id is None) == (self.user_id is None):
            raise ValueError("Entweder resource_id oder user_id angeben")
        return self


class MasterIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field("", max_length=200)


class MasterImportIn(BaseModel):
    text: str = Field(max_length=500_000)       # Zeilen "Code;Name"


class CostItemIn(BaseModel):
    amount: float = Field(ge=-1e12, le=1e12)
    cost_type_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    description: str = Field("", max_length=300)


class BudgetLineIn(BaseModel):
    cost_center_id: Optional[int] = None
    cost_type_id: Optional[int] = None
    amount: float = Field(ge=0, le=1e13)


class ActualIn(BaseModel):
    booking_date: date
    amount: float = Field(ge=-1e12, le=1e12)
    task_id: Optional[int] = None
    cost_type_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    reference: str = Field("", max_length=80)
    description: str = Field("", max_length=300)


class CostSettingsIn(BaseModel):
    members_see_costs: bool
