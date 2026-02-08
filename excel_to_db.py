import pandas as pd
import psycopg2
import os, sys

# ========= CONFIG =========
INPUT_FOLDER = "input_files"

DB_CONFIG = {
    "host": "localhost",
    "database": "api_specs",
    "user": "postgres",
    "password": "admin123",
    "port": "5432"
}
# ==========================


def process_sheet(df, sheet_name, conn, cur):

    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    print(f"\n📊 Processing sheet: {sheet_name}")

    # ---------- LEVEL COLUMNS ----------
    level_cols = [c for c in df.columns if c.lower().startswith("level")]
    level_cols.sort(key=lambda x: int("".join(filter(str.isdigit, x)) or "0"))
    other_cols = [c for c in df.columns if c not in level_cols]

    if not level_cols:
        print("❌ No level columns found. Skipping.")
        return

    print("   Level columns:", level_cols)
    print("   Attribute columns:", other_cols)

    # ---------- API NAME FROM FIRST LEVEL1 ----------
    api_name = None
    for _, row in df.iterrows():
        val = str(row[level_cols[0]]).strip()
        if val:
            api_name = val
            break

    if not api_name:
        api_name = sheet_name

    print("   🔌 API Name:", api_name)

    # ---------- AUTO ADD COLUMNS ----------
    for c in other_cols:
        cur.execute(f'ALTER TABLE api_spec ADD COLUMN IF NOT EXISTS "{c}" TEXT;')

    cur.execute('ALTER TABLE api_spec ADD COLUMN IF NOT EXISTS full_path TEXT;')
    conn.commit()

    # ---------- LOAD EXISTING PATHS ----------
    cur.execute("""
        SELECT field_id, full_path
        FROM api_spec
        WHERE api_name = %s
    """, (api_name,))
    path_to_id = {r[1]: r[0] for r in cur.fetchall()}

    current_levels = {}

    inserted = 0
    updated = 0
    skipped = 0

    # ---------- PROCESS EXCEL ----------
    for _, row in df.iterrows():

        if not any(str(row[c]).strip() for c in level_cols):
            continue

        for i, col in enumerate(level_cols, start=1):
            val = str(row[col]).strip()
            if val:
                current_levels[i] = val
                current_levels = {k: v for k, v in current_levels.items() if k <= i}

        parent_id = None

        for lvl in sorted(current_levels):

            name = current_levels[lvl]
            path = " > ".join(current_levels[x] for x in sorted(current_levels) if x <= lvl)
            full_path = f"{api_name}::{path}"

            values = [api_name, name, parent_id, full_path] + [str(row[c]).strip() for c in other_cols]

            if full_path in path_to_id:
                # ---------- CHECK IF DATA CHANGED ----------
                cur.execute(f'''
                    SELECT {",".join([f'"{c}"' for c in other_cols])}
                    FROM api_spec
                    WHERE api_name=%s AND full_path=%s
                ''', (api_name, full_path))

                old = cur.fetchone()
                new = tuple(str(row[c]).strip() for c in other_cols)

                if old != new:
                    set_sql = ",".join([f'"{c}"=%s' for c in other_cols])
                    cur.execute(f'''
                        UPDATE api_spec
                        SET field_name=%s, parent_field_id=%s, {set_sql}
                        WHERE api_name=%s AND full_path=%s
                    ''', [name, parent_id] + list(new) + [api_name, full_path])
                    updated += 1
                else:
                    skipped += 1

                field_id = path_to_id[full_path]

            else:
                cols = ['api_name','field_name','parent_field_id','full_path'] + [f'"{c}"' for c in other_cols]
                vals = ["%s","%s","%s","%s"] + ["%s"]*len(other_cols)

                cur.execute(f'''
                    INSERT INTO api_spec ({",".join(cols)})
                    VALUES ({",".join(vals)})
                    RETURNING field_id
                ''', values)

                field_id = cur.fetchone()[0]
                path_to_id[full_path] = field_id
                inserted += 1

            parent_id = field_id

    conn.commit()
    print(f"   ✅ Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}")


# ---------- MAIN ----------
def main():

    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith((".xlsx", ".xls"))]
    if not files:
        print("❌ No Excel file found in input_files")
        sys.exit()

    file_path = os.path.join(INPUT_FOLDER, files[0])
    print("📂 Excel:", file_path)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS api_spec (
        field_id SERIAL PRIMARY KEY,
        api_name TEXT,
        field_name TEXT,
        parent_field_id INT,
        full_path TEXT
    );
    """)
    conn.commit()

    xl = pd.ExcelFile(file_path)

    for sheet in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet)
        process_sheet(df, sheet, conn, cur)

    cur.close()
    conn.close()
    print("\n🎉 All sheets processed successfully.")


if __name__ == "__main__":
    main()
