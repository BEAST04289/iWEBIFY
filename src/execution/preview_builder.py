"""Preview Builder — generates a self-contained HTML preview from all schemas.

Creates a working (minimal) web app preview that judges can click around in.
Reads real data from the SQLite database, renders it with proper styling.
"""
import sqlite3
import json
from pathlib import Path
from src.schemas.database import DBSchema
from src.schemas.api import APISchema
from src.schemas.auth import AuthSchema
from src.schemas.ui import UISchema, UIPage, UIComponent


def _query_table(db_path: Path, table_name: str, limit: int = 10) -> list[dict]:
    """Query sample data from a table."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []


def _render_component(comp: UIComponent, db_path: Path, api_schema: APISchema) -> str:
    """Render a single UI component to HTML."""
    # Find the endpoint to get the table name
    table_name = None
    for ep in api_schema.endpoints:
        if ep.path == comp.api_endpoint:
            table_name = ep.db_table
            break
    
    data = _query_table(db_path, table_name) if table_name else []
    
    if comp.type == "stat_card":
        count = len(data) if data else 0
        return f'''
        <div class="stat-card">
            <div class="stat-value">{count}</div>
            <div class="stat-label">{comp.label}</div>
        </div>'''
    
    elif comp.type == "table":
        fields = comp.fields or (list(data[0].keys()) if data else [])
        headers = "".join(f"<th>{f}</th>" for f in fields[:6])  # Max 6 columns
        rows = ""
        for row in data:
            cells = "".join(
                f"<td>{str(row.get(f, ''))[:50]}</td>"
                for f in fields[:6]
            )
            rows += f"<tr>{cells}</tr>"
        if not rows:
            rows = f'<tr><td colspan="{len(fields[:6])}" class="empty">No data yet</td></tr>'
        
        return f'''
        <div class="data-table-container">
            <h3>{comp.label}</h3>
            <table class="data-table">
                <thead><tr>{headers}</tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>'''
    
    elif comp.type == "form":
        inputs = ""
        for field in comp.fields[:8]:
            inputs += f'''
            <div class="form-group">
                <label>{field.replace("_", " ").title()}</label>
                <input type="text" placeholder="Enter {field}" />
            </div>'''
        return f'''
        <div class="form-container">
            <h3>{comp.label}</h3>
            <form>{inputs}
                <button type="button" class="btn-primary">Submit</button>
            </form>
        </div>'''
    
    elif comp.type == "chart":
        return f'''
        <div class="chart-placeholder">
            <h3>{comp.label}</h3>
            <div class="chart-area">📊 Chart: {comp.label}</div>
        </div>'''
    
    elif comp.type in ("card", "list"):
        items = ""
        for row in data[:5]:
            vals = " | ".join(str(v)[:30] for v in list(row.values())[:3])
            items += f'<div class="list-item">{vals}</div>'
        return f'''
        <div class="card">
            <h3>{comp.label}</h3>
            {items or '<div class="empty">No data yet</div>'}
        </div>'''
    
    else:
        return f'<div class="component">{comp.label} ({comp.type})</div>'


def _render_page(page: UIPage, db_path: Path, api_schema: APISchema) -> str:
    """Render a full page to HTML."""
    components_html = ""
    for comp in page.components:
        components_html += _render_component(comp, db_path, api_schema)
    
    return f'''
    <div class="page" id="page-{page.path.replace("/", "-").strip("-")}">
        <div class="page-header">
            <h2>{page.title}</h2>
            <span class="layout-badge">{page.layout}</span>
        </div>
        <div class="page-content layout-{page.layout}">
            {components_html}
        </div>
    </div>'''


def build_preview(
    db_schema: DBSchema,
    api_schema: APISchema,
    auth_schema: AuthSchema,
    ui_schema: UISchema,
    db_path: Path,
    output_path: Path,
) -> str:
    """Build a self-contained HTML preview of the generated application.
    
    Args:
        db_schema: Database schema for data queries
        api_schema: API schema for endpoint mapping
        auth_schema: Auth schema for role display
        ui_schema: UI schema defining pages and components
        db_path: Path to the SQLite database with sample data
        output_path: Where to save the preview HTML file
    
    Returns:
        The generated HTML string
    """
    # Build navigation
    nav_items = ""
    for i, page in enumerate(ui_schema.pages):
        active = "active" if i == 0 else ""
        icon = "📊" if "dashboard" in page.path else "📋" if "list" in page.path else "📝" if "form" in page.path else "🔐" if "login" in page.path else "⚙️" if "settings" in page.path else "📄"
        nav_items += f'''
        <a href="#" class="nav-item {active}" onclick="showPage('{page.path}')" data-page="{page.path}">
            <span class="nav-icon">{icon}</span>
            <span>{page.title}</span>
        </a>'''
    
    # Build pages
    pages_html = ""
    for i, page in enumerate(ui_schema.pages):
        page_html = _render_page(page, db_path, api_schema)
        display = "" if i == 0 else 'style="display:none"'
        pages_html += f'<div class="page-wrapper" data-page="{page.path}" {display}>{page_html}</div>'
    
    # Roles summary
    roles_info = ", ".join(r.name for r in auth_schema.roles)
    tables_info = ", ".join(t.name for t in db_schema.tables)
    endpoints_count = len(api_schema.endpoints)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ui_schema.pages[0].title if ui_schema.pages else "App"} — Generated by iWebify</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #09090b;
            color: #fafafa;
            display: flex;
            min-height: 100vh;
        }}
        
        /* Sidebar */
        .sidebar {{
            width: 240px;
            background: #18181b;
            border-right: 1px solid #27272a;
            padding: 20px 0;
            display: flex;
            flex-direction: column;
        }}
        .sidebar-brand {{
            padding: 0 20px 20px;
            font-size: 18px;
            font-weight: 700;
            color: #6366f1;
            border-bottom: 1px solid #27272a;
        }}
        .nav-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 20px;
            color: #a1a1aa;
            text-decoration: none;
            transition: all 0.2s;
            font-size: 14px;
        }}
        .nav-item:hover, .nav-item.active {{
            background: rgba(99, 102, 241, 0.1);
            color: #fafafa;
        }}
        .nav-item.active {{ border-left: 3px solid #6366f1; }}
        .nav-icon {{ font-size: 16px; }}
        
        /* Main content */
        .main {{
            flex: 1;
            padding: 24px;
            overflow-y: auto;
        }}
        
        .page-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .page-header h2 {{ font-size: 24px; font-weight: 600; }}
        .layout-badge {{
            font-size: 11px;
            padding: 4px 8px;
            background: rgba(99, 102, 241, 0.2);
            color: #818cf8;
            border-radius: 4px;
        }}
        
        /* Components */
        .page-content {{
            display: grid;
            gap: 20px;
        }}
        .layout-sidebar {{ grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); }}
        .layout-full_width {{ grid-template-columns: 1fr; }}
        .layout-centered {{ max-width: 600px; margin: 0 auto; }}
        .layout-split {{ grid-template-columns: 1fr 1fr; }}
        
        .stat-card {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
        }}
        .stat-value {{ font-size: 36px; font-weight: 700; color: #6366f1; }}
        .stat-label {{ font-size: 14px; color: #a1a1aa; margin-top: 4px; }}
        
        .data-table-container {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
            padding: 20px;
            overflow-x: auto;
        }}
        .data-table-container h3 {{ margin-bottom: 16px; font-size: 16px; }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .data-table th {{
            text-align: left;
            padding: 10px 12px;
            font-size: 12px;
            color: #a1a1aa;
            border-bottom: 1px solid #27272a;
            text-transform: uppercase;
        }}
        .data-table td {{
            padding: 10px 12px;
            font-size: 13px;
            border-bottom: 1px solid #27272a10;
        }}
        .data-table tr:hover {{ background: rgba(99, 102, 241, 0.05); }}
        
        .form-container {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
            padding: 24px;
        }}
        .form-container h3 {{ margin-bottom: 16px; font-size: 16px; }}
        .form-group {{
            margin-bottom: 16px;
        }}
        .form-group label {{
            display: block;
            font-size: 13px;
            color: #a1a1aa;
            margin-bottom: 6px;
        }}
        .form-group input {{
            width: 100%;
            padding: 10px 12px;
            background: #09090b;
            border: 1px solid #27272a;
            border-radius: 8px;
            color: #fafafa;
            font-size: 14px;
        }}
        .form-group input:focus {{
            outline: none;
            border-color: #6366f1;
        }}
        
        .btn-primary {{
            background: #6366f1;
            color: #fff;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }}
        .btn-primary:hover {{ background: #4f46e5; }}
        
        .card {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
            padding: 20px;
        }}
        .card h3 {{ margin-bottom: 12px; font-size: 16px; }}
        .list-item {{
            padding: 10px 0;
            border-bottom: 1px solid #27272a;
            font-size: 13px;
            color: #a1a1aa;
        }}
        
        .chart-placeholder {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
            padding: 20px;
        }}
        .chart-placeholder h3 {{ margin-bottom: 12px; }}
        .chart-area {{
            height: 200px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #a1a1aa;
            font-size: 24px;
        }}
        
        .component {{
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 12px;
            padding: 20px;
            color: #a1a1aa;
        }}
        
        .empty {{ color: #52525b; font-style: italic; text-align: center; padding: 20px; }}
        
        /* Footer badge */
        .iwebify-badge {{
            position: fixed;
            bottom: 12px;
            right: 12px;
            background: #18181b;
            border: 1px solid #27272a;
            border-radius: 8px;
            padding: 6px 12px;
            font-size: 11px;
            color: #6366f1;
            z-index: 1000;
        }}
        
        /* Stats bar */
        .stats-bar {{
            padding: 12px 20px;
            margin-top: auto;
            border-top: 1px solid #27272a;
            font-size: 11px;
            color: #52525b;
        }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-brand">🌐 Generated App</div>
        {nav_items}
        <div class="stats-bar">
            Tables: {tables_info}<br>
            Endpoints: {endpoints_count}<br>
            Roles: {roles_info}
        </div>
    </div>
    <div class="main">
        {pages_html}
    </div>
    <div class="iwebify-badge">Generated by iWebify</div>
    
    <script>
        function showPage(path) {{
            document.querySelectorAll('.page-wrapper').forEach(p => p.style.display = 'none');
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            
            const page = document.querySelector(`.page-wrapper[data-page="${{path}}"]`);
            if (page) page.style.display = '';
            
            const nav = document.querySelector(`.nav-item[data-page="${{path}}"]`);
            if (nav) nav.classList.add('active');
        }}
    </script>
</body>
</html>'''
    
    output_path.write_text(html, encoding="utf-8")
    return html
