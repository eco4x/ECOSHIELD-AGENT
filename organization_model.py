"""Additive organisation and department schema migration for ECOSHIELD."""
import os


def ensure_organization_schema(conn):
    """Create normalized organisation tables and link legacy employee rows."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (organization_id, name),
            FOREIGN KEY (organization_id) REFERENCES organizations(id)
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(employees)").fetchall()}
    if "organization_id" not in columns:
        conn.execute("ALTER TABLE employees ADD COLUMN organization_id INTEGER REFERENCES organizations(id)")
    if "department_id" not in columns:
        conn.execute("ALTER TABLE employees ADD COLUMN department_id INTEGER REFERENCES departments(id)")

    name = os.environ.get("ECOSHIELD_ORGANIZATION_NAME", "ECOSHIELD Demo Organization").strip()
    if not name:
        raise ValueError("ECOSHIELD_ORGANIZATION_NAME cannot be empty.")
    conn.execute(
        "INSERT OR IGNORE INTO organizations (name, slug) VALUES (?, ?)",
        (name, "ecoshield-demo"),
    )
    org = conn.execute("SELECT id FROM organizations WHERE slug = ?", ("ecoshield-demo",)).fetchone()
    org_id = org[0]

    employees = conn.execute(
        "SELECT id, department, organization_id, department_id FROM employees ORDER BY id"
    ).fetchall()
    for employee in employees:
        employee_org_id = employee[2] or org_id
        department_name = (employee[1] or "Unassigned").strip() or "Unassigned"
        conn.execute(
            "INSERT OR IGNORE INTO departments (organization_id, name) VALUES (?, ?)",
            (employee_org_id, department_name),
        )
        department = conn.execute(
            "SELECT id FROM departments WHERE organization_id = ? AND name = ?",
            (employee_org_id, department_name),
        ).fetchone()
        conn.execute(
            """UPDATE employees
               SET organization_id = COALESCE(organization_id, ?),
                   department_id = COALESCE(department_id, ?)
               WHERE id = ?""",
            (employee_org_id, department[0], employee[0]),
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_employees_organization_department ON employees (organization_id, department_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_departments_organization ON departments (organization_id)"
    )
    conn.commit()
