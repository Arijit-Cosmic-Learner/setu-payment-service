"""
Custom ReDoc HTML renderer with Setu branding, unified typography, and theme styling.
"""

def get_custom_redoc_html(openapi_url: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <title>{title}</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --primary: #0f172a;
      --card-border: #e2e8f0;
      --accent: #10b981;
      --accent-soft: #ecfdf5;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      margin: 0;
      padding: 0;
      background: #f8fafc;
      color: #0f172a;
    }}
    /* Top Navbar */
    .custom-navbar {{
      position: sticky;
      top: 0;
      z-index: 1000;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.85rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      height: 60px;
    }}
    .brand-group {{ display: flex; align-items: center; gap: 0.75rem; }}
    .brand-logo {{
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
      color: #fff;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1rem;
    }}
    .brand-title {{ font-size: 1.05rem; font-weight: 700; letter-spacing: -0.02em; }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.2rem 0.6rem;
      background: var(--accent-soft);
      color: #065f46;
      border: 1px solid #a7f3d0;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }}
    .status-dot {{
      width: 7px;
      height: 7px;
      background: var(--accent);
      border-radius: 50%;
    }}
    .nav-actions {{ display: flex; align-items: center; gap: 0.65rem; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.45rem 0.85rem;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.2s ease;
      cursor: pointer;
      border: 1px solid transparent;
    }}
    .btn-secondary {{ background: #fff; border-color: var(--card-border); color: #0f172a; }}
    .btn-secondary:hover {{ background: #f1f5f9; }}
    .btn-primary {{ background: var(--primary); color: #fff; }}
    .btn-primary:hover {{ background: #1e293b; }}
    
    /* ReDoc container */
    #redoc-container {{
      position: relative;
      height: calc(100vh - 60px);
      overflow-y: auto;
    }}
    /* ReDoc overrides */
    .menu-content {{
      background: #f8fafc !important;
      border-right: 1px solid #e2e8f0 !important;
      font-family: 'Inter', sans-serif !important;
    }}
    code, pre, .redoc-markdown pre {{
      font-family: 'JetBrains Mono', monospace !important;
    }}
  </style>
</head>
<body>
  <nav class="custom-navbar">
    <div class="brand-group">
      <a href="/" style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 0.75rem;">
        <div class="brand-logo">S</div>
        <div class="brand-title">Setu Payment API Docs</div>
      </a>
      <div class="status-badge">
        <div class="status-dot"></div>
        <span>v1.0.0</span>
      </div>
    </div>
    <div class="nav-actions">
      <a href="/" class="btn btn-secondary">← Back to Dashboard</a>
      <a href="/docs" target="_blank" class="btn btn-primary">Swagger UI (/docs)</a>
    </div>
  </nav>

  <div id="redoc-container"></div>

  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
  <script>
    Redoc.init('{openapi_url}', {{
      theme: {{
        colors: {{
          primary: {{
            main: '#0f172a'
          }},
          success: {{
            main: '#10b981'
          }},
          http: {{
            get: '#0284c7',
            post: '#10b981',
            put: '#f59e0b',
            delete: '#ef4444'
          }}
        }},
        typography: {{
          fontSize: '14.5px',
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
          headings: {{
            fontFamily: 'Inter, sans-serif',
            fontWeight: '700'
          }},
          code: {{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '13px'
          }}
        }},
        sidebar: {{
          backgroundColor: '#f8fafc',
          textColor: '#334155',
          activeTextColor: '#0f172a',
          width: '280px'
        }},
        rightPanel: {{
          backgroundColor: '#0f172a'
        }}
      }},
      hideDownloadButton: false,
      disableSearch: false,
      expandResponses: '200,201',
      requiredPropsFirst: true
    }}, document.getElementById('redoc-container'));
  </script>
</body>
</html>
"""
