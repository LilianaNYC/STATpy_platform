"""Embedded CSS. Plain string (no Python interpolation needed)."""

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter','Segoe UI',sans-serif}
:root{
  --navy:#0f1d35;--navy-light:#1a2d4f;--navy-accent:#243860;
  --blue:#2563eb;--blue-light:#3b82f6;
  --green:#16a34a;--green-bg:#dcfce7;
  --amber:#d97706;--amber-bg:#fef3c7;
  --red:#dc2626;--red-bg:#fee2e2;
  --orange:#ea580c;--orange-bg:#ffedd5;
  --gray:#6b7280;--gray-light:#f3f4f6;--border:#e5e7eb;
  --text:#111827;--text-muted:#6b7280;
  --card-shadow:0 1px 3px rgba(0,0,0,.1),0 1px 2px rgba(0,0,0,.06);
}
body{display:flex;height:100vh;overflow:hidden;background:#f8fafc}
.sidebar{width:220px;min-width:220px;background:var(--navy);display:flex;flex-direction:column;overflow-y:auto}
.sidebar-logo{padding:20px 16px;border-bottom:1px solid var(--navy-accent)}
.sidebar-logo .logo-icon{font-size:28px;margin-bottom:6px}
.sidebar-logo h1{color:#fff;font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;line-height:1.4}
.sidebar-logo p{color:#94a3b8;font-size:10px;margin-top:2px}
.nav-list{list-style:none;padding:8px 0;flex:1}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 16px;cursor:pointer;color:#94a3b8;font-size:13px;font-weight:500;transition:all .15s;border-left:3px solid transparent}
.nav-item:hover{background:var(--navy-accent);color:#e2e8f0}
.nav-item.active{background:var(--navy-accent);color:#fff;border-left-color:var(--blue-light)}
.nav-icon{font-size:16px;width:20px;text-align:center}
.sidebar-footer{padding:12px 16px;border-top:1px solid var(--navy-accent);color:#475569;font-size:10px;line-height:1.6}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.top-bar{background:#fff;border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:16px;flex-shrink:0}
.top-bar h2{font-size:16px;font-weight:700;color:var(--text);flex:1}
.top-bar .subtitle{font-size:11px;color:var(--text-muted);margin-top:2px}
.filter-group{display:flex;align-items:center;gap:8px}
.filter-group label{font-size:11px;color:var(--text-muted);font-weight:600;white-space:nowrap}
select.filter-select{font-size:12px;padding:5px 10px;border:1px solid var(--border);border-radius:6px;background:#fff;color:var(--text);cursor:pointer;min-width:180px}
.btn{font-size:12px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;background:#fff;cursor:pointer;display:flex;align-items:center;gap:6px;font-weight:500;color:var(--text)}
.btn:hover{background:var(--gray-light)}
.btn-primary{background:var(--blue);color:#fff;border-color:var(--blue)}
.btn-primary:hover{background:#1d4ed8}
.content{flex:1;overflow-y:auto;padding:20px 24px}
.tab-panel{display:none}
.tab-panel.active{display:block}
.dash-header{margin-bottom:16px}
.dash-header h2{font-size:18px;font-weight:700;color:var(--text)}
.dash-header p{font-size:12px;color:var(--text-muted);margin-top:3px}
.kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:20px}
.kpi-card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;box-shadow:var(--card-shadow)}
.kpi-icon{font-size:22px;margin-bottom:6px}
.kpi-label{font-size:10px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.kpi-value{font-size:22px;font-weight:800;color:var(--text);line-height:1}
.kpi-sub{font-size:11px;color:var(--text-muted);margin-top:4px}
.kpi-delta{font-size:11px;font-weight:600;margin-top:4px}
.delta-up{color:var(--green)}
.delta-dn{color:var(--red)}
.delta-neu{color:var(--gray)}
.section-card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px;box-shadow:var(--card-shadow);margin-bottom:16px}
.section-title{font-size:12px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}
.grid-1-2{display:grid;grid-template-columns:1fr 2fr;gap:16px}
.grid-2-1{display:grid;grid-template-columns:2fr 1fr;gap:16px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:var(--gray-light);color:var(--text-muted);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;padding:7px 10px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:7px 10px;border-bottom:1px solid #f1f5f9;color:var(--text);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f8fafc}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700;white-space:nowrap}
.badge-critical{background:#fee2e2;color:#dc2626}
.badge-high{background:#ffedd5;color:#c2410c}
.badge-medium{background:#fef3c7;color:#92400e}
.badge-low{background:#dcfce7;color:#15803d}
.badge-green{background:#dcfce7;color:#15803d}
.badge-amber{background:#fef3c7;color:#92400e}
.badge-red{background:#fee2e2;color:#dc2626}
.badge-blue{background:#dbeafe;color:#1e40af}
.badge-gray{background:#f3f4f6;color:#6b7280}
.badge-open{background:#fee2e2;color:#dc2626}
.badge-progress{background:#fef3c7;color:#92400e}
.badge-resolved{background:#dcfce7;color:#15803d}
.cell-none{background:#dcfce7;color:#15803d;font-weight:600}
.cell-low{background:#f0fdf4;color:#16a34a}
.cell-medium{background:#fef3c7;color:#92400e}
.cell-high{background:#ffedd5;color:#c2410c}
.cell-critical{background:#fee2e2;color:#dc2626;font-weight:700}
.chart-box{min-height:220px}
.chart-sm{min-height:160px}
.overview-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.ov-card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:box-shadow .15s}
.ov-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.12)}
.ov-card-title{font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px}
.ov-mode-btn{padding:5px 14px;font-size:11px;font-weight:600;border:1px solid var(--border);border-radius:6px;background:#f8fafc;color:var(--text-muted);cursor:pointer;transition:all .15s}
.ov-mode-btn:hover{background:#e2e8f0;color:var(--text)}
.ov-mode-active{background:var(--navy)!important;color:#fff!important;border-color:var(--navy)!important}
.sparkline-cell{font-family:monospace;font-size:11px;white-space:nowrap}
.insight-card{background:#f8fafc;border-left:3px solid var(--blue);border-radius:0 8px 8px 0;padding:10px 12px;margin-bottom:8px;font-size:12px;color:var(--text)}
.insight-icon{margin-right:6px}
.hm-cell{padding:4px 8px;text-align:center;font-size:11px;font-weight:600;border-radius:3px}
.hm-none{background:#dcfce7;color:#15803d}
.hm-minor{background:#fef9c3;color:#713f12}
.hm-moderate{background:#ffedd5;color:#c2410c}
.hm-high{background:#fee2e2;color:#dc2626}
.gov-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:700}
.gov-green{background:#dcfce7;color:#15803d}
.gov-moderate{background:#fef3c7;color:#92400e}
.gov-red{background:#fee2e2;color:#dc2626}
.summary-text{font-size:13px;color:var(--text);line-height:1.7;background:#f8fafc;border-radius:8px;padding:14px;border:1px solid var(--border)}
#chart-materiality{min-height:280px}
.page-footer{flex-shrink:0;background:#fff;border-top:1px solid var(--border);padding:8px 24px;display:flex;align-items:center;gap:24px;font-size:11px;color:var(--text-muted)}
.waterfall-label{font-size:10px}
@media(max-width:900px){
  .grid-2,.grid-3,.grid-1-2,.grid-2-1,.overview-grid{grid-template-columns:1fr}
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
}
/* PDF export mode — hide interactive controls during html2canvas capture */
body.exporting-pdf .ov-mode-btn,
body.exporting-pdf select.filter-select,
body.exporting-pdf button,
body.exporting-pdf [onclick],
body.exporting-pdf .ov-card { cursor: default !important; }
body.exporting-pdf .tab-panel select,
body.exporting-pdf .tab-panel button { display: none !important; }
body.exporting-pdf .tab-panel [style*="border-radius:0 0 8px 8px"] { display: none !important; }
body.exporting-pdf .tab-panel [style*="display:flex"][style*="Comparison Mode"] { display: none !important; }
body.exporting-pdf .tab-panel .ov-mode-btn { display: none !important; }
/* Export split-button + dropdown menu */
.export-menu-wrap{position:relative;display:flex;align-items:stretch}
.export-btn-main{border-radius:6px 0 0 6px !important;border-right:1px solid #1e40af !important}
.export-btn-chevron{padding:6px 10px;border-radius:0 6px 6px 0;background:#2563eb;color:#fff;border:1px solid #2563eb;border-left:none;cursor:pointer;font-size:10px;display:flex;align-items:center;justify-content:center;min-width:28px}
.export-btn-chevron:hover{background:#1d4ed8}
.export-menu{position:absolute;top:calc(100% + 4px);right:0;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.12);min-width:240px;z-index:50;display:none;overflow:hidden}
.export-menu.open{display:block}
.export-menu-item{padding:10px 14px;font-size:12px;color:var(--text);cursor:pointer;display:flex;align-items:flex-start;gap:10px;border-bottom:1px solid #f1f5f9}
.export-menu-item:last-child{border-bottom:none}
.export-menu-item:hover{background:#f8fafc}
.export-menu-item .icon{font-size:16px;line-height:1.2}
.export-menu-item .label{font-weight:600;font-size:12px;color:var(--text)}
.export-menu-item .sub{font-size:10px;color:var(--text-muted);margin-top:2px}
/* Export progress overlay */
.export-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(15,29,53,.7);z-index:9999;display:none;align-items:center;justify-content:center}
.export-overlay.active{display:flex}
.export-overlay-card{background:#fff;border-radius:10px;padding:24px 32px;box-shadow:0 4px 20px rgba(0,0,0,.3);text-align:center;min-width:240px}
.export-overlay-card .spinner{display:inline-block;width:32px;height:32px;border:3px solid #e5e7eb;border-top-color:#2563eb;border-radius:50%;animation:spin 0.8s linear infinite;margin-bottom:12px}
.export-overlay-card .msg{font-size:13px;font-weight:600;color:#111827}
.export-overlay-card .sub{font-size:11px;color:#6b7280;margin-top:4px}
@keyframes spin{to{transform:rotate(360deg)}}
"""
