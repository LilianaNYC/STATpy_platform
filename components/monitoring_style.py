"""Embedded CSS used only by the model monitoring dashboard."""

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter','Segoe UI',sans-serif}
:root{
  --navy:#0f1d35;--navy-accent:#243860;--blue:#2563eb;--blue-light:#3b82f6;
  --green:#16a34a;--red:#dc2626;--gray-light:#f3f4f6;--border:#e5e7eb;
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
.monitoring-controls{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;margin-top:8px}
.monitoring-filter{display:flex;flex-direction:column;gap:4px;position:relative}
.monitoring-filter>label{font-size:11px;color:var(--text-muted);font-weight:600}
.monitoring-filter select,.checkbox-dropdown-toggle{font-size:12px;padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:#fff;color:var(--text);min-width:118px;height:30px}
.monitoring-filter select:disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed}
.monitoring-mode-switch{display:flex;height:30px}
.monitoring-mode-switch button{padding:5px 10px;border:1px solid var(--border);background:#fff;color:var(--text-muted);cursor:pointer;font-size:11px;font-weight:600}
.monitoring-mode-switch button:first-child{border-radius:6px 0 0 6px}
.monitoring-mode-switch button:last-child{border-radius:0 6px 6px 0;border-left:none}
.monitoring-mode-switch button.active{background:var(--navy);border-color:var(--navy);color:#fff}
.monitoring-filter-help{flex-basis:100%;font-size:10px;color:var(--text-muted);margin-top:-2px}
.checkbox-dropdown{position:relative}
.checkbox-dropdown-toggle{min-width:190px;max-width:220px;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.checkbox-dropdown-toggle:disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed}
.checkbox-dropdown-menu{position:absolute;top:calc(100% + 4px);left:0;display:none;min-width:190px;padding:6px 0;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.12);z-index:60}
.checkbox-dropdown-menu.open{display:block}
.checkbox-dropdown-menu label{display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12px;color:var(--text);cursor:pointer;white-space:nowrap}
.checkbox-dropdown-menu label:hover{background:#f8fafc}
.checkbox-dropdown-menu input[type="checkbox"]{width:16px;height:16px;accent-color:var(--blue);cursor:pointer}
.checkbox-dropdown-menu input[type="checkbox"]:disabled{cursor:not-allowed}
.btn{font-size:12px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;background:#fff;cursor:pointer;display:flex;align-items:center;gap:6px;font-weight:500;color:var(--text)}
.btn-primary{background:var(--blue);color:#fff;border-color:var(--blue)}
.btn-primary:hover{background:#1d4ed8}
.content{flex:1;overflow-y:auto;padding:20px 24px}
.tab-panel{display:none}
.tab-panel.active{display:block}
.dash-header{margin-bottom:16px}
.dash-header h2{font-size:18px;font-weight:700;color:var(--text)}
.dash-header p{font-size:12px;color:var(--text-muted);margin-top:3px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.kpi-card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:14px;box-shadow:var(--card-shadow)}
.kpi-card-title{font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px}
.kpi-card-value{font-size:22px;font-weight:800;color:var(--text);line-height:1}
.kpi-card-subtext{font-size:11px;color:var(--text-muted);margin-top:6px}
.monitoring-overview-kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-bottom:20px}
.monitoring-overview-kpi{border-top:3px solid #64748b}
.monitoring-overview-kpi-red{border-top-color:var(--red)}
.monitoring-overview-kpi-red .kpi-card-value{color:var(--red)}
.monitoring-overview-kpi-amber{border-top-color:#d97706}
.monitoring-overview-kpi-amber .kpi-card-value{color:#d97706}
.monitoring-overview-kpi-green{border-top-color:var(--green)}
.monitoring-overview-kpi-green .kpi-card-value{color:var(--green)}
.monitoring-overview-scope{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.monitoring-overview-scope div{display:flex;flex-direction:column;gap:3px;min-width:145px;padding:8px 10px;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:var(--card-shadow)}
.monitoring-overview-scope span{font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.35px}
.monitoring-overview-scope strong{font-size:12px;color:var(--text)}
.monitoring-overview-scope .monitoring-overview-snapshot{background:#eff6ff;border-color:#bfdbfe}
.monitoring-overview-snapshot span{color:#1d4ed8}
.pd-page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.pd-overall-status{display:flex;flex-direction:column;gap:4px;min-width:148px;border-left:3px solid #94a3b8;background:#fff;border-radius:7px;padding:8px 11px;box-shadow:var(--card-shadow)}
.pd-overall-status span{font-size:9px;font-weight:800;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px}
.pd-overall-status strong{display:flex;align-items:center;gap:4px;color:var(--text);font-size:13px}
.pd-overall-status .pd-rag-dot{font-size:16px}
.pd-overall-green{border-left-color:var(--green)}
.pd-overall-amber{border-left-color:#d97706}
.pd-overall-red{border-left-color:var(--red)}
.pd-section-nav{position:sticky;top:-20px;z-index:5;display:flex;flex-wrap:wrap;gap:8px;padding:8px;background:rgba(248,250,252,.96);border:1px solid var(--border);border-radius:8px;margin-bottom:16px;backdrop-filter:blur(8px)}
.pd-section-nav a{display:inline-flex;align-items:center;justify-content:center;min-height:32px;padding:6px 12px;border:1px solid #e2e8f0;border-radius:7px;background:#fff;color:var(--text-muted);font-size:11px;font-weight:700;line-height:1.3;text-align:center;text-decoration:none}
.pd-section-nav a:hover,.pd-section-nav a:focus{background:#eff6ff;border-color:#bfdbfe;color:var(--navy);outline:none}
.pd-overview-section{margin-top:0}
.pd-overview-grid{display:block;margin-bottom:14px;width:100%}
.pd-overview-row{display:grid;gap:12px;align-items:stretch;width:100%;margin-bottom:12px}
.pd-overview-grid>.pd-overview-row:last-child{margin-bottom:0}
.pd-overview-row.pd-test-grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.pd-overview-row.pd-test-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.pd-executive-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:14px}
.pd-signal-card{display:flex;flex-direction:column;gap:4px;min-width:0;background:#fff;border:1px solid var(--border);border-top:3px solid #94a3b8;border-radius:9px;padding:10px;box-shadow:var(--card-shadow)}
.pd-overview-row>.pd-signal-card{gap:6px;padding:14px;min-height:152px;border-radius:10px}
.pd-overview-row>.pd-signal-card .pd-signal-card-topline{align-items:flex-start;gap:8px;line-height:1.3}
.pd-overview-row>.pd-signal-card .pd-signal-card-topline>span:first-child{display:block;max-width:100%;white-space:normal;text-wrap:balance;font-size:10px}
.pd-overview-row>.pd-signal-card .pd-signal-status{font-size:10px;text-align:right;white-space:nowrap}
.pd-overview-row>.pd-signal-card .pd-signal-status .pd-rag-dot{font-size:15px}
.pd-overview-row>.pd-signal-card strong{font-size:25px;margin-top:auto}
.pd-overview-row>.pd-signal-card small{font-size:10px;line-height:1.4}
.pd-signal-card-topline{display:flex;align-items:center;justify-content:space-between;gap:8px;color:var(--text-muted);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.35px}
.pd-signal-card strong{font-size:20px;color:var(--text);line-height:1.1}
.pd-signal-card small{font-size:10px;color:var(--text-muted)}
.pd-signal-status{display:flex;align-items:center;gap:2px;font-size:9px;text-align:right;text-transform:none;letter-spacing:0}
.pd-signal-status .pd-rag-dot{font-size:14px}
.pd-domain-summary-card{background:#fcfdff}
.pd-domain-summary-card strong{font-size:20px}
.pd-signal-green{border-top-color:var(--green)}
.pd-signal-amber{border-top-color:#d97706}
.pd-signal-red{border-top-color:var(--red)}
.pd-overall-signal-card.pd-signal-green>strong{color:var(--green)}
.pd-overall-signal-card.pd-signal-amber>strong{color:#d97706}
.pd-overall-signal-card.pd-signal-red>strong{color:var(--red)}
.pd-signal-reference{border-top-color:#64748b}
.pd-overall-signal-card{background:#f8fafc}
.pd-signal-reference-label{color:#64748b;font-size:9px;text-transform:none;letter-spacing:0}
.pd-signal-card small b{color:var(--text)}
.pd-executive-grid .pd-change{color:var(--text)!important}
.pd-retention-card{border-top-color:#64748b}
.pd-retention-card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:8px}
.pd-retention-card-heading h4{color:var(--text-muted);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.35px}
.pd-retention-card-heading small{display:block;margin-top:2px;color:var(--text-muted);font-size:9px}
.pd-retention-card-heading>strong{color:var(--text);font-size:20px}
.pd-retention-grid{display:flex;flex-direction:column;gap:4px;margin-top:auto}
.pd-retention-grid div{display:flex;align-items:center;justify-content:space-between;gap:6px;padding-top:4px;border-top:1px solid #eef2f7}
.pd-retention-grid span{color:var(--text-muted);font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.35px}
.pd-retention-grid strong{color:var(--text);font-size:11px;text-align:right}
.pd-domain-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:12px}
.pd-heading-row{display:flex;align-items:center;gap:8px}
.pd-domain-heading h3{font-size:16px;color:var(--text);line-height:1.25}
.pd-domain-heading p{font-size:11px;color:var(--text-muted);margin-top:3px}
.pd-info-chip{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1px solid #bfdbfe;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:11px;font-weight:800;line-height:1;cursor:help;flex-shrink:0}
.pd-domain-status{display:flex;flex-direction:column;gap:4px;min-width:132px;padding:8px 10px;border:1px solid var(--border);border-left:3px solid #94a3b8;border-radius:7px;background:#fff;box-shadow:var(--card-shadow)}
.pd-domain-status span{font-size:9px;font-weight:800;color:var(--text-muted);text-transform:uppercase;letter-spacing:.45px}
.pd-domain-status strong{display:flex;align-items:center;gap:4px;color:var(--text);font-size:12px}
.pd-domain-status small{display:block;color:var(--text-muted);font-size:9px;line-height:1.45;text-transform:none;letter-spacing:0}
.pd-domain-status .pd-rag-dot{font-size:15px}
.pd-domain-status-top{padding:10px 12px;border-left:1px solid var(--border);border-top:3px solid #94a3b8;border-radius:10px}
.pd-domain-green{border-left-color:var(--green)}
.pd-domain-amber{border-left-color:#d97706}
.pd-domain-red{border-left-color:var(--red)}
.pd-domain-status-top.pd-domain-green{border-top-color:var(--green);border-left-color:var(--border)}
.pd-domain-status-top.pd-domain-amber{border-top-color:#d97706;border-left-color:var(--border)}
.pd-domain-status-top.pd-domain-red{border-top-color:var(--red);border-left-color:var(--border)}
.pd-scope-bar{display:flex;gap:8px;flex-wrap:wrap;background:#fff;border:1px solid var(--border);border-radius:10px;padding:12px 14px;margin-bottom:18px;box-shadow:var(--card-shadow)}
.pd-scope-bar div{display:flex;flex-direction:column;gap:3px;min-width:118px;padding:7px 9px;background:#f8fafc;border:1px solid #eef2f7;border-radius:7px}
.pd-scope-bar span{font-size:10px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.35px}
.pd-scope-bar strong{font-size:12px;color:var(--text);font-weight:700}
.pd-scope-bar .pd-scope-snapshot{background:#eff6ff;border-color:#bfdbfe}
.pd-scope-bar .pd-scope-snapshot span{color:#1d4ed8}
.pd-overview-meta{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-bottom:10px;padding:9px 12px;border:1px solid var(--border);border-radius:9px;background:linear-gradient(135deg,#f8fafc,#fff);box-shadow:var(--card-shadow);font-size:11px;color:var(--text-muted)}
.pd-overview-meta strong{color:var(--text)}
.pd-overview-heatmap-wrap{overflow-x:auto;margin-bottom:14px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;box-shadow:var(--card-shadow)}
.pd-overview-heatmap{width:100%;min-width:1360px;border-collapse:collapse;table-layout:fixed}
.pd-overview-heatmap th,.pd-overview-heatmap td{border:1px solid #1f2937;padding:8px 10px;vertical-align:middle}
.pd-overview-heatmap thead th{background:#f8fafc;color:#111827;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.4px;text-align:center}
.pd-overview-blank{background:#fff}
.pd-overview-domain{width:180px;background:#eef2ff;color:#0f172a;font-size:21px;font-weight:800;line-height:1.05;text-align:left;white-space:nowrap}
.pd-overview-section-label{width:210px;background:#f8fafc;color:#111827;font-size:12px;font-weight:800;line-height:1.2;text-align:left}
.pd-overview-metric-cell{background:#fff;min-height:86px}
.pd-overview-metric-label{font-size:11px;font-weight:800;line-height:1.25}
.pd-overview-metric-value{display:flex;align-items:center;gap:5px;margin-top:10px;color:var(--text);font-size:18px;font-weight:800;line-height:1.1}
.pd-overview-metric-value .pd-rag-dot{font-size:16px}
.pd-overview-metric-green{background:linear-gradient(180deg,#ffffff 0%,#f0fdf4 100%)}
.pd-overview-metric-amber{background:linear-gradient(180deg,#ffffff 0%,#fffbeb 100%)}
.pd-overview-metric-red{background:linear-gradient(180deg,#ffffff 0%,#fef2f2 100%)}
.pd-overview-metric-na{background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%)}
.pd-overview-metric-empty{background:#f8fafc}
.pd-overview-summary-cell{min-width:190px}
.pd-overview-pd-rag-cell{min-width:190px;vertical-align:bottom}
.pd-overview-summary-link{display:flex;flex-direction:column;min-height:100%;color:inherit;text-decoration:none;cursor:pointer}
.pd-overview-summary-link:hover,.pd-overview-summary-link:focus{outline:none}
.pd-overview-summary-link:hover .pd-overview-metric-label,.pd-overview-summary-link:focus .pd-overview-metric-label{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px}
.pd-overview-summary-link:hover .pd-overview-metric-value,.pd-overview-summary-link:focus .pd-overview-metric-value{transform:translateY(-1px)}
.pd-overview-metric-label-green{color:var(--green)}
.pd-overview-metric-label-amber{color:#d97706}
.pd-overview-metric-label-red{color:var(--red)}
.pd-overview-metric-label-na{color:#64748b}
.pd-filter-application-note{margin-top:-8px;margin-bottom:18px;padding:8px 10px;border-left:3px solid #60a5fa;background:#eff6ff;border-radius:0 7px 7px 0;color:#475569;font-size:10px;line-height:1.5}
.pd-filter-application-note strong{color:#1d4ed8}
.pd-content-section{margin-top:20px}
.pd-content-heading{margin-bottom:12px}
.pd-content-kicker{font-size:10px;font-weight:800;color:var(--blue);text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px}
.pd-content-heading h3{font-size:16px;color:var(--text);line-height:1.25}
.pd-content-heading p{font-size:11px;color:var(--text-muted);margin-top:3px}
.pd-chart-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.pd-chart-heading-copy{min-width:0}
.pd-chart-heading .section-title{margin-bottom:4px}
.pd-chart-heading .pd-section-subtitle{margin:0}
.pd-chart-actions,.pd-section-actions{display:flex;align-items:flex-end;justify-content:flex-end;gap:8px;flex-wrap:wrap}
.pd-range-controls{display:flex;align-items:flex-end;gap:5px;flex-wrap:wrap;padding:6px;background:#f8fafc;border:1px solid var(--border);border-radius:7px}
.pd-range-controls label{display:flex;flex-direction:column;gap:2px}
.pd-range-controls span{font-size:9px;color:var(--text-muted);font-weight:800;text-transform:uppercase;letter-spacing:.35px}
.pd-range-controls select{height:26px;max-width:116px;padding:3px 5px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--text);font-size:10px}
.pd-range-controls label:first-child select{max-width:128px}
.pd-expand-button,.pd-expanded-close{display:flex;align-items:center;justify-content:center;gap:5px;height:29px;padding:5px 8px;border:1px solid var(--border);border-radius:6px;background:#fff;color:var(--navy);cursor:pointer;font-size:10px;font-weight:800}
.pd-expand-button:hover,.pd-expand-button:focus,.pd-expanded-close:hover,.pd-expanded-close:focus{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8;outline:2px solid transparent}
.pd-expand-button span:first-child{font-size:14px;line-height:1}
.pd-metric-group{margin-bottom:14px}
.pd-metric-group-title{display:flex;align-items:center;gap:7px;margin-bottom:8px;color:var(--text);font-size:12px;font-weight:700}
.pd-group-dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.pd-group-calibration{background:var(--blue)}
.pd-group-discrimination{background:#7c3aed}
.pd-performance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:14px}
.pd-kpi-dashboard-grid{grid-template-columns:repeat(6,minmax(0,1fr))}
.lgd-kpi-grid,.ead-kpi-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.lgd-window-control,.ead-window-control{display:flex;flex-direction:column;gap:2px;padding:6px;background:#f8fafc;border:1px solid var(--border);border-radius:7px}
.lgd-window-control span,.ead-window-control span{font-size:9px;color:var(--text-muted);font-weight:800;text-transform:uppercase;letter-spacing:.35px}
.lgd-window-control select,.ead-window-control select{height:26px;padding:3px 5px;border:1px solid var(--border);border-radius:5px;background:#fff;color:var(--text);font-size:10px}
.pd-metric-heading{margin-top:18px}
.pd-performance-card{background:#fff;border:1px solid var(--border);border-top:3px solid #64748b;border-radius:10px;padding:15px;box-shadow:var(--card-shadow)}
.pd-card-calibration{border-top-color:var(--blue)}
.pd-card-discrimination{border-top-color:#7c3aed}
.pd-performance-title{font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px}
.pd-performance-value{font-size:25px;font-weight:800;color:var(--text);line-height:1}
.pd-performance-detail{font-size:11px;color:var(--text-muted);margin-top:7px;min-height:28px}
.pd-performance-detail span{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.4px}
.pd-performance-comparison{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #f1f5f9;margin-top:12px;padding-top:10px}
.pd-performance-comparison div{display:flex;flex-direction:column;gap:4px}
.pd-performance-comparison span{font-size:9px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.35px}
.pd-performance-comparison strong{font-size:12px;color:var(--text)}
.pd-change{font-size:11px!important;font-weight:700!important;letter-spacing:0!important}
.pd-change-positive{color:var(--red)!important}
.pd-change-negative{color:var(--green)!important}
.pd-change-neutral{color:var(--text-muted)!important}
.pd-test-grid{display:grid;gap:12px;margin-bottom:14px}
.pd-test-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.pd-test-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.pd-test-grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.pd-test-grid-4>article{grid-column:span 1}
.pd-calibration-test-grid{grid-template-columns:1.45fr repeat(4,minmax(0,1fr));align-items:stretch}
.pd-calibration-summary-card{grid-row:span 2}
.pd-calibration-domain-status{align-self:stretch;justify-content:center}
.pd-discrimination-test-grid{grid-template-columns:repeat(3,minmax(0,1fr));align-items:stretch}
.pd-discrimination-domain-status{align-self:stretch;justify-content:center}
.pd-performance-test-grid{grid-template-columns:repeat(4,minmax(0,1fr));align-items:stretch}
.pd-performance-domain-status{align-self:stretch;justify-content:center}
.pd-test-card{background:#fff;border:1px solid var(--border);border-top:3px solid #94a3b8;border-radius:10px;padding:14px;box-shadow:var(--card-shadow)}
.pd-test-green{border-top-color:var(--green)}
.pd-test-amber{border-top-color:#d97706}
.pd-test-red{border-top-color:var(--red)}
.pd-test-card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.pd-test-card-heading span{font-size:9px;font-weight:800;color:var(--blue);text-transform:uppercase;letter-spacing:.45px}
.pd-card-title-row{display:flex;align-items:center;gap:6px}
.pd-test-card-heading h4{margin-top:3px;color:var(--text);font-size:12px;line-height:1.3}
.pd-test-status{display:flex;align-items:center;gap:3px;color:var(--text-muted);font-size:10px;font-weight:700}
.pd-test-status .pd-rag-dot{font-size:15px}
.pd-test-status-green{color:var(--green)}
.pd-test-status-amber{color:#d97706}
.pd-test-status-red{color:var(--red)}
.pd-test-status-na{color:var(--text-muted)}
.pd-test-value{margin-top:14px;color:var(--text);font-size:25px;font-weight:800;line-height:1}
.pd-test-meta{margin-top:6px;color:var(--text-muted);font-size:10px}
.pd-test-footnote{margin-top:12px;padding-top:10px;border-top:1px solid #eef2f7;color:var(--text-muted);font-size:9px;line-height:1.45}
.pd-formula-note{display:flex;flex-direction:column;gap:5px;margin-bottom:14px;padding:10px 12px;border-left:3px solid #7c3aed;border-radius:0 7px 7px 0;background:#f5f3ff;color:#5b21b6;font-size:11px;line-height:1.45}
.pd-formula-note code{overflow-x:auto;padding:5px 7px;border-radius:5px;background:#ede9fe;color:#4c1d95;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;white-space:nowrap}
.pd-formula-note span{color:#6b7280}
.pd-performance-note{font-size:11px;color:var(--text-muted);background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:10px 12px}
.pd-data-note{margin-bottom:10px;color:#92400e;background:#fffbeb;border-color:#fde68a}
.pd-retention-warning{margin-bottom:10px;padding:10px 12px;border:1px solid #fde68a;border-left:4px solid #d97706;border-radius:8px;background:#fffbeb;color:#92400e;font-size:11px;line-height:1.5}
.pd-retention-warning strong{margin-right:4px}
.pd-rag-section{margin-top:0}
.pd-rag-history-section .pd-content-heading{margin-bottom:8px}
.pd-section-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:10px}
.pd-section-heading .section-title{margin-bottom:4px}
.pd-section-heading .pd-section-subtitle{margin:0}
.pd-view-toggle{display:flex;flex-shrink:0}
.pd-view-toggle button{padding:5px 9px;border:1px solid var(--border);background:#fff;color:var(--text-muted);font-size:11px;font-weight:700;cursor:pointer}
.pd-view-toggle button:first-child{border-radius:6px 0 0 6px}
.pd-view-toggle button:last-child{border-left:none;border-radius:0 6px 6px 0}
.pd-view-toggle button.active{background:var(--navy);border-color:var(--navy);color:#fff}
.pd-rag-table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:8px}
.pd-rag-table{min-width:1240px;background:#fff}
.pd-rag-table th,.pd-rag-table td{text-align:center;white-space:nowrap}
.pd-rag-table th:first-child,.pd-rag-table td:first-child{position:sticky;left:0;text-align:left;min-width:210px;z-index:1}
.pd-rag-table th:first-child{z-index:2;background:var(--gray-light)}
.pd-rag-table td:first-child{background:#fff;font-weight:600}
.pd-rag-summary-row td{background:#f8fafc;font-weight:700}
.pd-rag-summary-start td{border-top:2px solid #cbd5e1}
.pd-rag-summary-row td:first-child{background:#f8fafc}
.pd-rag-dot{font-size:20px;line-height:1;color:#94a3b8}
.pd-rag-green{color:var(--green)}
.pd-rag-amber{color:#d97706}
.pd-rag-red{color:var(--red)}
.pd-rag-na{color:#94a3b8}
.pd-rag-legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;color:var(--text-muted);font-size:11px}
.pd-rag-legend span{display:flex;align-items:center;gap:5px}
.pd-rag-legend .pd-rag-dot{font-size:16px}
.pd-rag-movement{margin-top:10px;padding-top:10px;border-top:1px solid #eef2f7}
.pd-rag-movement-heading{display:flex;align-items:baseline;gap:8px;margin-bottom:7px}
.pd-rag-movement-heading strong{color:var(--text);font-size:11px;text-transform:uppercase;letter-spacing:.4px}
.pd-rag-movement-heading span{color:var(--text-muted);font-size:10px}
.pd-rag-movement-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:7px}
.pd-rag-movement-table{min-width:900px;background:#fff;font-size:11px}
.pd-rag-movement-table th,.pd-rag-movement-table td{text-align:center;padding:5px 7px}
.pd-rag-movement-table th:first-child,.pd-rag-movement-table td:first-child{position:sticky;left:0;z-index:1;min-width:190px;text-align:left}
.pd-rag-movement-table th:first-child{z-index:2;background:var(--gray-light)}
.pd-rag-movement-table td:first-child{background:#fff;font-weight:600}
.pd-rag-movement-summary td{border-bottom:2px solid #cbd5e1;background:#f8fafc;font-weight:700}
.pd-rag-movement-summary td:first-child{background:#f8fafc}
.pd-rag-cell{display:inline-flex;align-items:center;justify-content:center;min-width:23px;height:20px;padding:0 5px;border-radius:12px;color:#fff;font-size:9px;font-weight:800}
.pd-rag-cell-green{background:var(--green)}
.pd-rag-cell-amber{background:#d97706}
.pd-rag-cell-red{background:var(--red)}
.pd-rag-cell-na{background:#94a3b8}
.pd-migration-section{margin-top:16px}
.pd-section-subtitle{font-size:11px;color:var(--text-muted);margin-top:-5px;margin-bottom:12px}
.pd-migration-summary{display:flex;gap:18px;flex-wrap:wrap;padding:9px 12px;background:#f8fafc;border:1px solid var(--border);border-radius:8px;margin-bottom:8px}
.pd-migration-summary span{font-size:11px;color:var(--text-muted)}
.pd-migration-summary strong{font-size:12px;color:var(--text);margin-right:4px}
.pd-migration-chart{min-height:390px}
.pd-default-rate-trend-section{margin-top:0}
.pd-default-rate-trend-chart{min-height:420px}
.pd-discrimination-trend-section{margin-top:0}
.pd-discrimination-trend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.pd-discrimination-trend-chart{min-height:270px}
.pd-discrimination-trend-note{grid-column:1/-1}
.pd-primary-analysis-grid{display:grid;grid-template-columns:1fr;gap:16px}
.pd-trend-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.pd-trend-wide-card{grid-column:1/-1}
.pd-rating-default-rate-chart,.pd-distribution-shift-chart{min-height:310px}
.pd-stability-trend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.pd-stability-trend-chart{min-height:280px}
.pd-stability-trend-note{grid-column:1/-1}
.pd-migration-grid{display:grid;grid-template-columns:minmax(260px,.7fr) minmax(460px,1.3fr);gap:14px}
.pd-subchart-panel{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fff}
.pd-subchart-title{font-size:11px;color:var(--text-muted);font-weight:700;text-transform:uppercase;letter-spacing:.35px;margin-bottom:4px}
.pd-rating-direction-chart{min-height:230px}
.pd-expanded-modal{position:fixed;inset:0;z-index:10000;display:none;align-items:center;justify-content:center;padding:24px;background:rgba(15,29,53,.72)}
.pd-expanded-modal.active{display:flex}
.pd-expanded-dialog{display:flex;flex-direction:column;width:min(1500px,96vw);height:min(940px,94vh);overflow:hidden;border-radius:12px;background:#f8fafc;box-shadow:0 24px 70px rgba(15,23,42,.38)}
.pd-expanded-modal-header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 16px;border-bottom:1px solid var(--border);background:#fff}
.pd-expanded-modal-header div{display:flex;flex-direction:column;gap:2px}
.pd-expanded-modal-header span{font-size:9px;color:var(--blue);font-weight:800;text-transform:uppercase;letter-spacing:.7px}
.pd-expanded-modal-header strong{font-size:15px;color:var(--text)}
.pd-expanded-modal-body{flex:1;overflow:auto;padding:16px}
.pd-expanded-panel{min-height:100%;margin:0!important}
.pd-expanded-panel .pd-rag-table{min-width:100%}
.section-card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px;box-shadow:var(--card-shadow);margin-bottom:16px}
.section-title{font-size:12px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px}
.chart-box{min-height:220px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:var(--gray-light);color:var(--text-muted);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;padding:7px 10px;text-align:left;border-bottom:1px solid var(--border)}
td{padding:7px 10px;border-bottom:1px solid #f1f5f9;color:var(--text);vertical-align:middle}
tr:last-child td{border-bottom:none}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700;white-space:nowrap}
.badge-critical{background:#fee2e2;color:var(--red)}
.badge-green{background:#dcfce7;color:#15803d}
.page-footer{flex-shrink:0;background:#fff;border-top:1px solid var(--border);padding:8px 24px;display:flex;align-items:center;gap:24px;font-size:11px;color:var(--text-muted)}
.export-menu-wrap{position:relative;display:flex;align-items:stretch}
.export-btn-main{border-radius:6px 0 0 6px!important;border-right:1px solid #1e40af!important}
.export-btn-chevron{padding:6px 10px;border-radius:0 6px 6px 0;background:var(--blue);color:#fff;border:1px solid var(--blue);border-left:none;cursor:pointer;font-size:10px;display:flex;align-items:center;justify-content:center;min-width:28px}
.export-btn-chevron:hover{background:#1d4ed8}
.export-menu{position:absolute;top:calc(100% + 4px);right:0;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.12);min-width:240px;z-index:50;display:none;overflow:hidden}
.export-menu.open{display:block}
.export-menu-item{padding:10px 14px;font-size:12px;color:var(--text);cursor:pointer;display:flex;align-items:flex-start;gap:10px;border-bottom:1px solid #f1f5f9}
.export-menu-item:last-child{border-bottom:none}
.export-menu-item:hover{background:#f8fafc}
.export-menu-item .icon{font-size:16px;line-height:1.2}
.export-menu-item .label{font-weight:600;font-size:12px;color:var(--text)}
.export-menu-item .sub{font-size:10px;color:var(--text-muted);margin-top:2px}
.export-overlay{position:fixed;inset:0;background:rgba(15,29,53,.7);z-index:9999;display:none;align-items:center;justify-content:center}
.export-overlay.active{display:flex}
.export-overlay-card{background:#fff;border-radius:10px;padding:24px 32px;box-shadow:0 4px 20px rgba(0,0,0,.3);text-align:center;min-width:240px}
.export-overlay-card .spinner{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--blue);border-radius:50%;animation:spin .8s linear infinite;margin-bottom:12px}
.export-overlay-card .msg{font-size:13px;font-weight:600;color:var(--text)}
.export-overlay-card .sub{font-size:11px;color:var(--text-muted);margin-top:4px}
body.exporting-pdf button{display:none!important}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:900px){
  .grid-2,.grid-3,.monitoring-overview-kpi-grid,.pd-performance-grid{grid-template-columns:1fr}
  .pd-migration-grid,.pd-trend-detail-grid,.pd-primary-analysis-grid,.pd-overview-grid,.pd-executive-grid,.pd-test-grid{grid-template-columns:1fr}
  .pd-discrimination-trend-grid{grid-template-columns:1fr}
  .pd-stability-trend-grid{grid-template-columns:1fr}
  .pd-section-heading{flex-direction:column}
  .pd-domain-heading{flex-direction:column}
  .pd-chart-heading{flex-direction:column}
  .pd-chart-actions,.pd-section-actions{justify-content:flex-start}
  .pd-page-header{flex-direction:column}
  .pd-overall-status{width:100%}
  .pd-section-nav{overflow:visible;white-space:normal}
  .pd-overview-row,.pd-overview-row.pd-test-grid-3,.pd-overview-row.pd-test-grid-4{grid-template-columns:1fr}
  .pd-overview-row>.pd-signal-card{min-height:auto;padding:14px}
  .pd-overview-meta{flex-direction:column;align-items:flex-start}
  .pd-overview-domain{font-size:18px}
}
@media(min-width:901px) and (max-width:1400px){
  .pd-kpi-dashboard-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
  .pd-test-grid-4{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-calibration-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-calibration-summary-card{grid-row:auto}
  .pd-discrimination-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-performance-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .lgd-kpi-grid,.ead-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-overview-row.pd-test-grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}
  .pd-overview-row.pd-test-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
  .pd-overview-row>.pd-signal-card{min-height:144px;padding:14px}
  .pd-executive-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
"""
