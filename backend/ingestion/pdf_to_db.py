import pdfplumber
import pandas as pd
import psycopg2
import os
import hashlib
from typing import List
import asyncio

async def process_pdf_file(file_path: str, user_id: int):
    """
    Process PDF file and extract hierarchical API specification tables
    """
    # Database configuration
    DB_CONFIG = {
        "host": "localhost",
        "database": "api_specs",
        "user": "postgres",
        "password": "admin123",
        "port": "5432"
    }

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Create table if it doesn't exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS api_spec (
        field_id SERIAL PRIMARY KEY,
        api_name TEXT,
        field_name TEXT,
        parent_field_id INT,
        full_path TEXT,
        user_id INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()

    BASE_API_NAME = os.path.splitext(os.path.basename(file_path))[0]

    print("📂 Using PDF:", file_path)
    print(f"🔌 Base API NAME: {BASE_API_NAME}")

    # Extract all tables from PDF
    all_raw_tables = []

    with pdfplumber.open(file_path) as pdf:
        print(f"\n📄 Scanning {len(pdf.pages)} pages...")
        for page_num, page in enumerate(pdf.pages, 1):
            page_tables = page.extract_tables()
            if page_tables:
                print(f"   Page {page_num}: Found {len(page_tables)} table(s)")
                for pt in page_tables:
                    if pt:
                        all_raw_tables.append(pd.DataFrame(pt))

    if not all_raw_tables:
        print("❌ No tables found in PDF")
        return

    print(f"\n📊 Total raw tables extracted: {len(all_raw_tables)}")

    # Merge continuation tables
    merged_tables = merge_continuation_tables(all_raw_tables)

    print(f"📊 Tables after merging continuations: {len(merged_tables)}")

    # Process each table
    for table_num, table_df in enumerate(merged_tables, 1):
        table_df = table_df.fillna("")

        # Detect level columns
        level_cols = [c for c in table_df.columns if str(c).strip().lower().startswith("level")]

        # Find API name
        api_name = find_api_name_from_table(table_df, level_cols)

        if not api_name:
            api_name = f"{BASE_API_NAME}_Table{table_num}"

        try:
            await process_table(table_df, table_num, api_name, user_id, conn, cur)
        except Exception as e:
            print(f"   ❌ Error processing table {table_num}: {e}")
            import traceback
            traceback.print_exc()
            continue

    cur.close()
    conn.close()
    print("\n🎉 All PDF tables processed successfully")


def clean_column_name(col, idx):
    """Clean and ensure valid column names"""
    col = str(col).strip()
    if not col or col == "" or col.lower() == "nan":
        return f"col_{idx}"
    # Remove special characters that might cause SQL issues
    col = col.replace('"', '').replace("'", "")
    return col if col else f"col_{idx}"


def get_table_hash(df):
    """Generate hash of table data to detect exact duplicates"""
    data_str = ""
    for _, row in df.iterrows():
        for col in df.columns:
            data_str += str(row[col]).strip() + "|"
        data_str += "\n"
    return hashlib.md5(data_str.encode()).hexdigest()


def merge_continuation_tables(tables):
    """Merge tables that are continuations across pages"""
    if not tables:
        return []
    
    merged = []
    current_table = None
    current_header = None
    
    for table_df in tables:
        if len(table_df) == 0:
            continue
        
        # Get first row as potential header
        first_row = table_df.iloc[0].astype(str).str.lower().str.strip()
        has_level_header = any("level" in str(val) for val in first_row.values)
        
        if has_level_header:
            # This is a new table start (has header row)
            if current_table is not None:
                # Save previous table
                merged.append(current_table)
            
            # Start new table
            header_row = table_df.iloc[0]
            current_header = [clean_column_name(col, idx) for idx, col in enumerate(header_row)]
            current_table = table_df.iloc[1:].copy()
            current_table.columns = current_header
            current_table = current_table.reset_index(drop=True)
        else:
            # This is a continuation of previous table
            if current_table is not None and current_header is not None:
                # Append rows to current table
                continuation_df = table_df.copy()
                continuation_df.columns = current_header
                current_table = pd.concat([current_table, continuation_df], ignore_index=True)
    
    # Don't forget the last table
    if current_table is not None:
        merged.append(current_table)
    
    return merged


async def process_table(df, table_num, api_name, user_id, conn, cur):
    """Process a single table from PDF"""
    
    if len(df) == 0:
        print(f"   ⚠️ Table {table_num} is empty, skipping...")
        return
    
    df = df.fillna("")
    
    print(f"\n   📊 Processing Table #{table_num}")
    print(f"   ✅ Total Rows: {len(df)}")
    
    # Clean column names
    df.columns = [clean_column_name(col, idx) for idx, col in enumerate(df.columns)]
    
    # Detect level columns
    level_cols = [c for c in df.columns if str(c).strip().lower().startswith("level")]
    level_cols.sort(key=lambda x: int("".join(filter(str.isdigit, str(x))) or "0"))
    
    other_cols = [c for c in df.columns if c not in level_cols]
    all_cols = df.columns.tolist()
    
    print(f"   📋 Level columns: {level_cols if level_cols else 'None (flat table)'}")
    print(f"   📋 Other columns: {len(other_cols)} columns")
    print(f"   🔌 API NAME: {api_name}")
    
    # Check if exact same data exists
    current_hash = get_table_hash(df)
    
    try:
        cur.execute('SELECT COUNT(*) FROM api_spec WHERE api_name = %s AND user_id = %s;', (api_name, user_id))
        existing_count = cur.fetchone()[0]
        
        if existing_count > 0:
            # Get existing data
            cur.execute('''
                SELECT field_name, parent_field_id, api_name 
                FROM api_spec 
                WHERE api_name = %s AND user_id = %s
                ORDER BY field_id;
            ''', (api_name, user_id))
            
            existing_rows = cur.fetchall()
            existing_data_str = ""
            for row in existing_rows:
                existing_data_str += "|".join(str(x) for x in row) + "\n"
            
            existing_hash = hashlib.md5(existing_data_str.encode()).hexdigest()
            
            if current_hash == existing_hash:
                print(f"   ⏭️ Exact same data already exists for API '{api_name}', skipping upload...")
                return
            else:
                print(f"   🔄 Data changed for API '{api_name}', deleting old and uploading new...")
                cur.execute('DELETE FROM api_spec WHERE api_name = %s AND user_id = %s;', (api_name, user_id))
                conn.commit()
    except Exception as e:
        print(f"   ⚠️ Error checking existing data: {e}")
        conn.rollback()

    # Auto add columns
    for col in all_cols:
        try:
            cur.execute(f'''
                ALTER TABLE api_spec
                ADD COLUMN IF NOT EXISTS "{col}" TEXT;
            ''')
        except Exception as e:
            pass
    
    cur.execute('ALTER TABLE api_spec ADD COLUMN IF NOT EXISTS user_id INTEGER;')
    conn.commit()

    # Process rows
    try:
        if level_cols:
            # Hierarchical table
            await process_table_with_levels(df, table_num, api_name, user_id, level_cols, other_cols, conn, cur)
        else:
            # Flat table
            await process_table_without_levels(df, table_num, api_name, user_id, all_cols, conn, cur)
        
        print(f"   ✅ Table #{table_num} processed successfully")
    except Exception as e:
        print(f"   ❌ Error inserting data: {e}")
        conn.rollback()
        raise


async def process_table_with_levels(df, table_num, api_name, user_id, level_cols, other_cols, conn, cur):
    """Process table WITH level columns (hierarchical structure)"""
    
    print(f"   🚀 Loading hierarchical table data into DB...")
    
    path_to_id = {}
    current_levels = {}
    rows_inserted = 0
    
    for idx, row in df.iterrows():
        has_level_data = any(str(row[col]).strip() for col in level_cols if col in row.index)
        
        if not has_level_data:
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
            
            if full_path not in path_to_id:
                cols_sql = ['api_name', 'field_name', 'parent_field_id', 'full_path', 'user_id'] + [f'"{c}"' for c in other_cols]
                vals_sql = ["%s"] * (4 + len(other_cols))
                
                values = [api_name, name, parent_id, full_path, user_id] + [str(row[c]).strip() if c in row.index else "" for c in other_cols]
                
                cur.execute(f'''
                    INSERT INTO api_spec ({",".join(cols_sql)})
                    VALUES ({",".join(vals_sql)})
                    RETURNING field_id
                ''', values)
                
                new_id = cur.fetchone()[0]
                conn.commit()
                path_to_id[full_path] = new_id
                rows_inserted += 1
            
            parent_id = path_to_id[full_path]
    
    print(f"   ✅ Inserted {rows_inserted} hierarchical rows")


async def process_table_without_levels(df, table_num, api_name, user_id, all_cols, conn, cur):
    """Process table WITHOUT level columns (flat structure)"""
    
    print(f"   🚀 Loading flat table data into DB...")
    
    rows_inserted = 0
    
    for idx, row in df.iterrows():
        # Skip completely empty rows
        if all(str(row[col]).strip() == "" for col in all_cols if col in row.index):
            continue
        
        # Use first non-empty column value as field_name
        field_name = f"Row_{idx + 1}"
        for col in all_cols:
            if col in row.index:
                val = str(row[col]).strip()
                if val:
                    field_name = val
                    break
        
        cols_sql = ['api_name', 'field_name', 'parent_field_id', 'full_path', 'user_id'] + [f'"{c}"' for c in all_cols]
        vals_sql = ["%s"] * (4 + len(all_cols))
        
        # Generate a simple full_path for flat tables
        full_path = f"{api_name}::{field_name}"
        
        values = [api_name, field_name, None, full_path, user_id] + [str(row[c]).strip() if c in row.index else "" for c in all_cols]
        
        cur.execute(f'''
            INSERT INTO api_spec ({",".join(cols_sql)})
            VALUES ({",".join(vals_sql)})
        ''', values)
        rows_inserted += 1
    
    conn.commit()
    print(f"   ✅ Inserted {rows_inserted} flat rows")


def find_api_name_from_table(table_df, level_cols):
    """Find API name from table - look for row before Level columns start"""
    api_name = None
    
    # Look through rows to find API name
    for idx, row in table_df.iterrows():
        if level_cols:
            # Check if this row has level data
            has_level = any(str(row[col]).strip() for col in level_cols if col in row.index)
            if not has_level:
                # This row is before level data - might contain API name
                for col in table_df.columns:
                    if col in row.index:
                        val = str(row[col]).strip()
                        if val and val.lower() not in ['level', 'required', 'optional', 'type', 'data']:
                            api_name = val
                            break
                if api_name:
                    break
            else:
                # Found level data, stop searching
                break
        else:
            # For flat tables, use first non-empty cell
            for col in table_df.columns:
                if col in row.index:
                    val = str(row[col]).strip()
                    if val:
                        api_name = val
                        break
            if api_name:
                break
    
    return api_name