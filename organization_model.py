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


def _slugify(value):
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    if not slug:
        raise ValueError("Organisation name must contain letters or numbers.")
    return slug[:60]


def create_organization(conn, name):
    name = (name or "").strip()
    if not name or len(name) > 100:
        raise ValueError("Organisation name must contain 1 to 100 characters.")
    base = _slugify(name)
    slug = base
    suffix = 2
    while conn.execute("SELECT 1 FROM organizations WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base[:55]}-{suffix}"
        suffix += 1
    cursor = conn.execute(
        "INSERT INTO organizations (name, slug) VALUES (?, ?)", (name, slug)
    )
    conn.commit()
    return cursor.lastrowid


def create_department(conn, organization_id, name):
    name = (name or "").strip()
    if not name or len(name) > 80:
        raise ValueError("Department name must contain 1 to 80 characters.")
    organization = conn.execute(
        "SELECT id FROM organizations WHERE id = ? AND status = 'active'",
        (organization_id,),
    ).fetchone()
    if organization is None:
        raise ValueError("Active organisation not found.")
    try:
        cursor = conn.execute(
            "INSERT INTO departments (organization_id, name) VALUES (?, ?)",
            (organization_id, name),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError("That department already exists in this organisation.") from exc
        raise
    conn.commit()
    return cursor.lastrowid


def list_organizations(conn):
    rows = conn.execute(
        """SELECT o.id, o.name, o.slug, o.status, COUNT(DISTINCT d.id) AS department_count,
                  COUNT(DISTINCT e.id) AS employee_count
           FROM organizations o
           LEFT JOIN departments d ON d.organization_id = o.id
           LEFT JOIN employees e ON e.organization_id = o.id
           GROUP BY o.id ORDER BY o.name"""
    ).fetchall()
    return [dict(row) for row in rows]


def list_departments(conn, organization_id):
    rows = conn.execute(
        """SELECT d.id, d.organization_id, d.name, d.status,
                  COUNT(e.id) AS employee_count
           FROM departments d
           LEFT JOIN employees e ON e.department_id = d.id
           WHERE d.organization_id = ?
           GROUP BY d.id ORDER BY d.name""",
        (organization_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def assign_employee_department(conn, employee_id, organization_id, department_id):
    department = conn.execute(
        """SELECT id, name FROM departments
           WHERE id = ? AND organization_id = ? AND status = 'active'""",
        (department_id, organization_id),
    ).fetchone()
    if department is None:
        raise ValueError("Department does not belong to the selected organisation.")
    cursor = conn.execute(
        """UPDATE employees
           SET organization_id = ?, department_id = ?, department = ?
           WHERE id = ? AND organization_id = ?""",
        (organization_id, department_id, department["name"], employee_id, organization_id),
    )
    if cursor.rowcount != 1:
        raise ValueError("Employee does not belong to the selected organisation.")
    conn.commit()
