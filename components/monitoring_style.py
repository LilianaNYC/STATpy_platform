"""Embedded CSS used only by the model monitoring dashboard."""

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter','Segoe UI',sans-serif}
:root{
  --navy:#0f1d35;--navy-accent:#243860;--blue:#2563eb;--blue-light:#3b82f6;
  --green:#16a34a;--red:#dc2626;--gray-light:#f3f4f6;--border:#e5e7eb;
  --text:#111827;--text-muted:#6b7280;
  --pd-blue:#0b4fd8;--pd-blue-soft:#eef6ff;--pd-line:#d7e3f3;--pd-panel:#f8fbff;
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
.monitoring-export-filter{align-self:flex-start}
.monitoring-export-filter>label{display:none}
.monitoring-filter select,.checkbox-dropdown-toggle{font-size:12px;padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:#fff;color:var(--text);min-width:118px;height:30px}
.monitoring-filter select:disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed}
.monitoring-mode-switch{display:flex;height:30px}
.monitoring-mode-switch button{padding:5px 10px;border:1px solid var(--border);background:#fff;color:var(--text-muted);cursor:pointer;font-size:11px;font-weight:600}
.monitoring-mode-switch button:first-child{border-radius:6px 0 0 6px}
.monitoring-mode-switch button:last-child{border-radius:0 6px 6px 0;border-left:none}
.monitoring-mode-switch button.active{background:var(--navy);border-color:var(--navy);color:#fff}
.monitoring-filter-help{flex-basis:100%;font-size:10px;color:var(--text-muted);margin-top:-2px}
.monitoring-section-subnav{flex-basis:100%;display:flex;flex-direction:column;gap:8px;margin-top:2px;padding:10px 12px;border:1px solid #dbe4f0;border-radius:12px;background:linear-gradient(135deg,#f8fbff 0%,#ffffff 42%,#f8fafc 100%);box-shadow:0 6px 18px rgba(15,23,42,.045)}
.monitoring-section-subnav[hidden]{display:none!important}
.monitoring-section-subnav-group{display:flex;align-items:flex-start;gap:12px}
.monitoring-section-subnav-group+.monitoring-section-subnav-group{padding-top:8px;border-top:1px solid #e2e8f0}
.monitoring-section-subnav-group.active{position:relative}
.monitoring-section-subnav-group.active::before{content:'';position:absolute;left:-12px;top:1px;bottom:1px;width:3px;border-radius:999px;background:linear-gradient(180deg,#2563eb 0%,#1d4ed8 100%)}
.monitoring-section-subnav-group-secondary.active::before{background:linear-gradient(180deg,#c2410c 0%,#9a3412 100%)}
.monitoring-section-subnav-group-secondary .monitoring-section-subnav-label{color:#9a3412}
.monitoring-section-subnav-label{min-width:198px;padding-top:1px;color:var(--navy);font-size:10px;font-weight:800;letter-spacing:.65px;text-transform:uppercase}
.monitoring-section-subnav-group.active .monitoring-section-subnav-label{color:#0f172a}
.monitoring-section-subnav-group-secondary.active .monitoring-section-subnav-label{color:#7c2d12}
.monitoring-section-subnav-links{display:flex;flex-wrap:wrap;gap:6px}
.monitoring-section-subnav-links button{display:inline-flex;align-items:center;justify-content:center;min-height:30px;padding:6px 11px;border:1px solid #dbe4f0;border-radius:999px;background:rgba(255,255,255,.96);color:#475569;font-size:10px;font-weight:700;line-height:1.2;text-align:center;cursor:pointer;box-shadow:0 1px 0 rgba(255,255,255,.95) inset;transition:background .15s,border-color .15s,color .15s,transform .15s}
.monitoring-section-subnav-links button:hover,.monitoring-section-subnav-links button:focus{background:#eff6ff;border-color:#bfdbfe;color:var(--navy);outline:none;transform:translateY(-1px)}
.monitoring-section-subnav-links button.active{background:var(--navy);border-color:var(--navy);color:#fff;box-shadow:0 6px 16px rgba(15,29,53,.14)}
.monitoring-section-subnav-group-secondary .monitoring-section-subnav-links button.active{background:#9a3412;border-color:#9a3412;box-shadow:0 6px 16px rgba(154,52,18,.16)}
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
.content{flex:1;overflow-y:auto;padding:10px 24px 20px}
.tab-panel{display:none}
.tab-panel.active{display:block}
#tab-pd_models{max-width:1760px;margin:0 auto}
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
.pd-page-header{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:18px}
.pd-overall-status{display:flex;flex-direction:column;gap:4px;min-width:148px;border-left:3px solid #94a3b8;background:#fff;border-radius:7px;padding:8px 11px;box-shadow:var(--card-shadow)}
.pd-overall-status span{font-size:9px;font-weight:800;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px}
.pd-overall-status strong{display:flex;align-items:center;gap:4px;color:var(--text);font-size:13px}
.pd-overall-status .pd-rag-dot{font-size:16px}
.pd-overall-green{border-left-color:var(--green)}
.pd-overall-amber{border-left-color:#d97706}
.pd-overall-red{border-left-color:var(--red)}
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
.pd-domain-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #eef2f7}
.pd-heading-row{display:flex;align-items:center;gap:8px}
.pd-domain-heading h3{font-size:20px;color:var(--text);line-height:1.2}
.pd-domain-heading p{max-width:78ch;font-size:12px;color:var(--text-muted);margin-top:5px;line-height:1.65}
.pd-info-chip{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border:1px solid #bfdbfe;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:11px;font-weight:800;line-height:1;cursor:help;flex-shrink:0}
.pd-domain-status{display:flex;flex-direction:column;gap:4px;min-width:132px;padding:8px 10px;border:1px solid var(--border);border-left:3px solid #94a3b8;border-radius:7px;background:#fff;box-shadow:var(--card-shadow)}
.pd-domain-status span{font-size:10px;font-weight:800;color:var(--text-muted);text-transform:uppercase;letter-spacing:.35px}
.pd-domain-status strong{display:flex;align-items:center;gap:4px;color:var(--text);font-size:13px}
.pd-domain-status small{display:block;color:var(--text-muted);font-size:10px;line-height:1.45;text-transform:none;letter-spacing:0}
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
.pd-overview-flow-wrap{overflow-x:auto;margin-bottom:16px;padding:14px 14px 16px;border:1px solid var(--pd-line);border-radius:14px;background:linear-gradient(180deg,#ffffff 0%,var(--pd-panel) 100%);box-shadow:0 16px 38px rgba(15,23,42,.055)}
.pd-overview-flow{--flow-gap:clamp(28px,2.4vw,42px);--flow-blue:var(--pd-blue);display:grid;grid-template-columns:minmax(120px,.62fr) minmax(218px,1.12fr) minmax(178px,.88fr) minmax(206px,1fr) minmax(154px,.74fr);grid-template-rows:64px 0 76px 76px 28px 76px 76px 36px 76px 36px 76px 76px;grid-template-areas:"stage-input stage-tests stage-assignment stage-dimension stage-performance" ". . . . ." "input-ecl tests-cal1 assignment1 dimension-calibration performance" "input-ecl tests-cal1 assignment1 dimension-calibration performance" "input-ecl . . dimension-calibration performance" "input-ecl tests-cal2 assignment2 dimension-calibration performance" "input-ecl tests-cal2 assignment2 dimension-calibration performance" "input-ecl tests-discrimination pass-discrimination dimension-discrimination performance" "input-ecl tests-discrimination pass-discrimination dimension-discrimination performance" ". . . . performance" "input-balance tests-balance pass-balance dimension-balance performance" "input-balance tests-balance pass-balance dimension-balance performance";column-gap:var(--flow-gap);row-gap:8px;min-width:980px;align-items:stretch;padding:0 2px 2px}
.pd-flow-stage-input{grid-area:stage-input}.pd-flow-stage-tests{grid-area:stage-tests}.pd-flow-stage-assignment{grid-area:stage-assignment}.pd-flow-stage-dimension{grid-area:stage-dimension}.pd-flow-stage-performance{grid-area:stage-performance}
.pd-flow-input-ecl{grid-area:input-ecl}.pd-flow-input-balance{grid-area:input-balance}.pd-flow-tests-calibration-1{grid-area:tests-cal1}.pd-flow-tests-calibration-2{grid-area:tests-cal2;transform:translateY(-22px)}.pd-flow-tests-discrimination{grid-area:tests-discrimination}.pd-flow-tests-balance{grid-area:tests-balance}.pd-flow-assignment-1{grid-area:assignment1}.pd-flow-assignment-2{grid-area:assignment2;transform:translateY(-22px)}.pd-flow-pass-discrimination{grid-area:pass-discrimination}.pd-flow-pass-balance{grid-area:pass-balance}.pd-flow-dimension-calibration{grid-area:dimension-calibration}.pd-flow-dimension-discrimination{grid-area:dimension-discrimination}.pd-flow-dimension-balance{grid-area:dimension-balance}.pd-flow-performance{grid-area:performance}
.pd-flow-input-balance,.pd-flow-tests-balance,.pd-flow-pass-balance,.pd-flow-dimension-balance{transform:translateY(-30px)}
.pd-flow-performance{margin-bottom:58px}
.pd-flow-input-ecl,.pd-flow-input-balance,.pd-flow-performance{display:flex;min-width:0}
.pd-overview-flow-stage{display:flex;align-items:center;justify-content:center;min-height:100%;padding:8px 10px;border-radius:8px;background:linear-gradient(180deg,#07358f 0%,#021f67 100%);box-shadow:0 12px 22px rgba(2,28,91,.22);color:#fff;text-align:center}
.pd-overview-flow-stage span{display:block;max-width:100%;font-size:12px;font-weight:800;line-height:1.18;text-transform:uppercase;letter-spacing:0;white-space:nowrap}
.pd-overview-flow-input{display:flex;flex:1;flex-direction:column;align-items:center;justify-content:center;min-width:0;padding:18px 14px;border:1px solid #93c5fd;border-radius:8px;background:linear-gradient(180deg,#fbfdff 0%,#eef6ff 100%);box-shadow:0 12px 28px rgba(59,130,246,.08);color:#0f172a;text-align:center}
.pd-overview-flow-input-balance{border-color:#c4b5fd;background:linear-gradient(180deg,#fbfaff 0%,#f5f3ff 100%)}
.pd-overview-flow-input strong{font-size:17px;line-height:1.2}.pd-overview-flow-input span{margin-top:6px;color:#64748b;font-size:11px;font-weight:700}
.pd-overview-flow-test-stack{position:relative;display:flex;flex-direction:column;justify-content:center;gap:8px;min-width:0}
.pd-overview-flow-test-stack>.pd-overview-flow-connector-in{height:3px;border-radius:999px;background:linear-gradient(90deg,rgba(11,79,216,.28) 0%,rgba(11,79,216,.78) 58%,var(--flow-blue) 100%)}
.pd-overview-flow-test-stack>.pd-overview-flow-connector-in::before{content:'';position:absolute;left:-5px;top:50%;width:9px;height:9px;border:2px solid var(--flow-blue);border-radius:999px;background:#fff;box-shadow:0 0 0 3px rgba(37,99,235,.12);transform:translateY(-50%)}
.pd-flow-tests-discrimination .pd-overview-flow-node{min-height:54px}
.pd-overview-flow-node{position:relative;display:flex;min-width:0;min-height:66px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;box-shadow:0 9px 20px rgba(15,23,42,.055);overflow:visible;transition:box-shadow .15s,border-color .15s}
.pd-overview-flow-node:hover{box-shadow:0 14px 28px rgba(15,23,42,.09)}
.pd-overview-flow-link{position:relative;z-index:1;display:flex;flex:1;flex-direction:column;align-items:center;justify-content:center;gap:5px;width:100%;min-height:100%;padding:10px 12px;color:inherit;text-align:center;text-decoration:none}
.pd-overview-flow-link:hover,.pd-overview-flow-link:focus{outline:none;box-shadow:0 0 0 3px rgba(37,99,235,.16) inset}
.pd-overview-flow-link:hover .pd-overview-flow-node-label,.pd-overview-flow-link:focus .pd-overview-flow-node-label{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px}
.pd-overview-flow-node-label{display:flex;align-items:center;justify-content:center;gap:5px;color:#111827;font-size:12px;font-weight:800;line-height:1.25}
.pd-overview-flow-node-value{display:flex;align-items:center;justify-content:center;gap:5px;color:#0f172a;font-size:15px;font-weight:800;line-height:1.1}
.pd-overview-flow-node-value-rag{font-size:16px}.pd-overview-flow-node-value .pd-rag-dot{font-size:16px}
.pd-overview-flow-node-note{color:#64748b;font-size:10px;line-height:1.35}
.pd-overview-flow-node-green{border-color:#93d2aa;background:linear-gradient(180deg,#ffffff 0%,#eefaf1 100%)}.pd-overview-flow-node-amber{border-color:#f2bf5c;background:linear-gradient(180deg,#ffffff 0%,#fff7e6 100%)}.pd-overview-flow-node-red{border-color:#f5a3a3;background:linear-gradient(180deg,#ffffff 0%,#fff1f1 100%)}.pd-overview-flow-node-na{background:linear-gradient(180deg,#ffffff 0%,#f8fafc 100%)}
.pd-flow-assignment-1,.pd-flow-assignment-2,.pd-flow-dimension-calibration,.pd-flow-dimension-discrimination,.pd-flow-dimension-balance{align-self:center;min-height:82px}
.pd-flow-dimension-calibration,.pd-flow-dimension-discrimination,.pd-flow-dimension-balance{min-height:104px}
.pd-flow-dimension-calibration{align-self:stretch;min-height:0;margin-top:0}
.pd-overview-flow-pass-through{position:relative;align-self:center;min-height:20px}
.pd-overview-flow-connector{position:absolute;top:50%;z-index:0;height:2px;background:var(--flow-blue);pointer-events:none}
.pd-overview-flow-connector-in{left:calc(-1 * var(--flow-gap));width:var(--flow-gap)}
.pd-overview-flow-connector-out{right:calc(-1 * var(--flow-gap));width:var(--flow-gap)}
.pd-overview-flow-connector::after{content:'';position:absolute;right:-1px;top:-5px;width:0;height:0;border-top:6px solid transparent;border-bottom:6px solid transparent;border-left:9px solid var(--flow-blue)}
.pd-overview-flow-node .pd-overview-flow-connector-in,.pd-overview-flow-node .pd-overview-flow-connector-out,.pd-overview-flow-pass-through .pd-overview-flow-connector-in{height:3px;border-radius:999px;background:linear-gradient(90deg,rgba(11,79,216,.28) 0%,rgba(11,79,216,.78) 58%,var(--flow-blue) 100%)}
.pd-overview-flow-node .pd-overview-flow-connector-in::before,.pd-overview-flow-node .pd-overview-flow-connector-out::before{content:'';position:absolute;left:-5px;top:50%;width:9px;height:9px;border:2px solid var(--flow-blue);border-radius:999px;background:#fff;box-shadow:0 0 0 3px rgba(37,99,235,.12);transform:translateY(-50%)}
.pd-flow-dimension-discrimination .pd-overview-flow-connector-in::before,.pd-flow-dimension-balance .pd-overview-flow-connector-in::before{display:none}
.pd-overview-flow-pass-through .pd-overview-flow-connector-in{left:calc(-1 * var(--flow-gap));right:calc(-1 * var(--flow-gap));width:auto}
.pd-flow-pass-discrimination .pd-overview-flow-connector-in::before,.pd-flow-pass-balance .pd-overview-flow-connector-in::before{content:'';position:absolute;left:-5px;top:50%;width:9px;height:9px;border:2px solid var(--flow-blue);border-radius:999px;background:#fff;box-shadow:0 0 0 3px rgba(37,99,235,.12);transform:translateY(-50%)}
.pd-overview-flow-pass-through .pd-overview-flow-connector-in::after,.pd-overview-flow-pass-through .pd-overview-flow-connector-out{display:none}
.pd-overview-flow-performance{--perf-color:#d97706;--perf-border:#f59e0b;--perf-bg-start:#fffaf0;--perf-bg-end:#ffedd5;--perf-shadow:rgba(217,119,6,.14);--perf-gauge-bg:#fff7ed;position:relative;display:flex;flex:1;flex-direction:column;align-items:center;justify-content:center;min-width:0;min-height:100%;padding:22px 14px;border:1px solid var(--perf-border);border-radius:8px;background:linear-gradient(180deg,var(--perf-bg-start) 0%,var(--perf-bg-end) 100%);box-shadow:0 14px 30px var(--perf-shadow);text-align:center}
.pd-overview-flow-performance-green{--perf-color:var(--green);--perf-border:#86efac;--perf-bg-start:#f7fef9;--perf-bg-end:#dcfce7;--perf-shadow:rgba(22,163,74,.14);--perf-gauge-bg:#f0fdf4}
.pd-overview-flow-performance-amber{--perf-color:#d97706;--perf-border:#f59e0b;--perf-bg-start:#fffaf0;--perf-bg-end:#ffedd5;--perf-shadow:rgba(217,119,6,.14);--perf-gauge-bg:#fff7ed}
.pd-overview-flow-performance-red{--perf-color:var(--red);--perf-border:#fca5a5;--perf-bg-start:#fff7f7;--perf-bg-end:#fee2e2;--perf-shadow:rgba(220,38,38,.14);--perf-gauge-bg:#fef2f2}
.pd-overview-flow-performance-na{--perf-color:#64748b;--perf-border:#cbd5e1;--perf-bg-start:#ffffff;--perf-bg-end:#f1f5f9;--perf-shadow:rgba(100,116,139,.12);--perf-gauge-bg:#f8fafc}
.pd-overview-flow-performance-title{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:0;color:#111827;font-size:16px;font-weight:800;line-height:1.35}
.pd-overview-flow-performance strong{display:flex;align-items:center;gap:6px;margin-top:14px;color:var(--text);font-size:25px;line-height:1.1}.pd-overview-flow-performance strong .pd-rag-dot{font-size:23px;color:var(--perf-color)}
.lgd-overview-flow{--flow-gap:clamp(26px,2.25vw,38px);--flow-blue:var(--pd-blue);display:grid;grid-template-columns:minmax(130px,.68fr) minmax(232px,1.16fr) minmax(184px,.9fr) minmax(210px,1fr) minmax(158px,.74fr);grid-template-rows:64px 0 96px 96px 96px;grid-template-areas:"stage-input stage-tests stage-assignment stage-dimension stage-performance" ". . . . ." "input-lgd tests-cal assignment-cal dimension-cal performance" "input-lgd tests-disc assignment-disc dimension-disc performance" "input-lgd tests-recovery assignment-recovery dimension-recovery performance";column-gap:var(--flow-gap);row-gap:9px;min-width:980px;align-items:stretch;padding:0 2px 2px}
.lgd-flow-stage-input{grid-area:stage-input}.lgd-flow-stage-tests{grid-area:stage-tests}.lgd-flow-stage-assignment{grid-area:stage-assignment}.lgd-flow-stage-dimension{grid-area:stage-dimension}.lgd-flow-stage-performance{grid-area:stage-performance}
.lgd-flow-input{grid-area:input-lgd;display:flex;min-width:0}.lgd-flow-tests-calibration{grid-area:tests-cal}.lgd-flow-tests-discrimination{grid-area:tests-disc}.lgd-flow-tests-recovery{grid-area:tests-recovery}.lgd-flow-assignment-calibration{grid-area:assignment-cal}.lgd-flow-assignment-discrimination{grid-area:assignment-disc}.lgd-flow-assignment-recovery{grid-area:assignment-recovery}.lgd-flow-dimension-calibration{grid-area:dimension-cal}.lgd-flow-dimension-discrimination{grid-area:dimension-disc}.lgd-flow-dimension-recovery{grid-area:dimension-recovery}.lgd-flow-performance{grid-area:performance;display:flex;min-width:0}
.lgd-flow-assignment-calibration,.lgd-flow-assignment-discrimination,.lgd-flow-assignment-recovery,.lgd-flow-dimension-calibration,.lgd-flow-dimension-discrimination,.lgd-flow-dimension-recovery{align-self:center;min-height:78px}
.lgd-flow-dimension-calibration,.lgd-flow-dimension-discrimination,.lgd-flow-dimension-recovery{min-height:90px}
.lgd-flow-tests-discrimination .pd-overview-flow-node,.lgd-flow-tests-recovery .pd-overview-flow-node{min-height:74px}
.pd-filter-application-note{margin-top:-8px;margin-bottom:18px;padding:8px 10px;border-left:3px solid #60a5fa;background:#eff6ff;border-radius:0 7px 7px 0;color:#475569;font-size:10px;line-height:1.5}
.pd-filter-application-note strong{color:#1d4ed8}
.pd-content-section{margin-top:20px;scroll-margin-top:24px}
.pd-live-section{padding:clamp(18px,1.35vw,24px) clamp(18px,1.45vw,26px) 12px;border:1px solid #dbe4f0;border-radius:16px;background:linear-gradient(180deg,#ffffff 0%,#fbfdff 100%);box-shadow:0 14px 38px rgba(15,23,42,.06)}
.pd-live-section .section-card{border-color:#e2e8f0;border-radius:14px;background:linear-gradient(180deg,#ffffff 0%,#fbfdff 100%);box-shadow:0 10px 26px rgba(15,23,42,.05)}
.pd-live-section .section-card:last-child{margin-bottom:8px}
.pd-chapter-section{margin-top:24px}
.pd-chapter-body{display:flex;flex-direction:column;gap:18px;padding-left:16px;margin-top:2px;border-left:2px solid #e2e8f0}
.pd-chapter-body-secondary{border-left-color:#fed7aa}
.pd-chapter-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;padding:20px 22px;border:1px solid #dbe4f0;border-radius:16px;background:linear-gradient(135deg,#eff6ff 0%,#ffffff 42%,#f8fafc 100%);box-shadow:0 14px 38px rgba(15,23,42,.08)}
.pd-chapter-heading-copy{max-width:780px}
.pd-chapter-kicker{font-size:11px;font-weight:800;color:var(--blue);text-transform:uppercase;letter-spacing:.75px;margin-bottom:5px}
.pd-chapter-heading h2{font-size:20px;line-height:1.15;color:var(--text)}
.pd-chapter-heading p{margin-top:6px;font-size:12px;line-height:1.55;color:var(--text-muted)}
.pd-chapter-note{display:inline-flex;align-items:center;justify-content:center;min-height:34px;padding:8px 12px;border:1px solid #bfdbfe;border-radius:999px;background:rgba(255,255,255,.88);color:#1d4ed8;font-size:11px;font-weight:800;letter-spacing:.35px;text-transform:uppercase;text-align:center}
.pd-placeholder-section{margin-top:16px}
.pd-placeholder-section{padding:16px 16px 4px;border:1px dashed #cbd5e1;border-radius:16px;background:linear-gradient(180deg,#ffffff 0%,#fcfcfd 100%)}
.pd-placeholder-section .pd-domain-heading{margin-bottom:12px;border-bottom-style:dashed}
.pd-placeholder-card{border-style:dashed;border-width:1px;border-color:#cbd5e1;background:linear-gradient(135deg,#ffffff 0%,#f8fafc 70%,#f1f5f9 100%)}
.pd-placeholder-badge{display:inline-flex;align-items:center;justify-content:center;min-height:24px;padding:4px 10px;border:1px solid #cbd5e1;border-radius:999px;background:#fff;color:#475569;font-size:10px;font-weight:800;letter-spacing:.45px;text-transform:uppercase}
.pd-placeholder-title{margin-top:12px;color:var(--text);font-size:16px;font-weight:800;line-height:1.2}
.pd-placeholder-card p{margin-top:8px;max-width:72ch;color:var(--text-muted);font-size:12px;line-height:1.65}
.pd-placeholder-tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.pd-placeholder-tags span{display:inline-flex;align-items:center;min-height:26px;padding:5px 10px;border:1px solid #dbe4f0;border-radius:999px;background:rgba(255,255,255,.84);color:#334155;font-size:11px;font-weight:700}
.pd-content-heading{margin-bottom:16px;padding-bottom:13px;border-bottom:1px solid #e8eef6}
.pd-content-kicker{font-size:11px;font-weight:800;color:var(--blue);text-transform:uppercase;letter-spacing:.65px;margin-bottom:3px}
.pd-content-heading h3{font-size:clamp(19px,1.3vw,22px);color:var(--text);line-height:1.18}
.pd-content-heading p{max-width:78ch;font-size:12px;color:var(--text-muted);margin-top:5px;line-height:1.65}
.pd-chart-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #eef2f7}
.pd-chart-heading-copy{flex:1 1 320px;min-width:0;padding-right:8px}
.pd-chart-heading .section-title{margin-bottom:6px;font-size:13px;line-height:1.35}
.pd-chart-heading .pd-section-subtitle{margin:0;max-width:78ch;font-size:12px;line-height:1.6}
.pd-chart-actions,.pd-section-actions{display:flex;align-items:flex-end;justify-content:flex-end;gap:10px 8px;flex-wrap:wrap;padding-top:2px}
.pd-range-controls{display:flex;align-items:flex-end;gap:5px;flex-wrap:wrap;padding:6px;background:#f8fafc;border:1px solid var(--border);border-radius:7px}
.pd-range-controls label{display:flex;flex-direction:column;gap:2px}
.pd-range-controls span{font-size:10px;color:var(--text-muted);font-weight:800;text-transform:uppercase;letter-spacing:.25px}
.pd-range-controls select{height:28px;max-width:132px;padding:4px 6px;border:1px solid var(--border);border-radius:6px;background:#fff;color:var(--text);font-size:11px}
.pd-range-controls label:first-child select{max-width:128px}
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
.pd-performance-comparison{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #f1f5f9;margin-top:auto;padding-top:12px}
.pd-performance-comparison div{display:flex;flex-direction:column;gap:4px}
.pd-performance-comparison span{font-size:9px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.35px}
.pd-performance-comparison strong{font-size:12px;color:var(--text)}
.pd-change{font-size:11px!important;font-weight:700!important;letter-spacing:0!important}
.pd-change-positive{color:var(--red)!important}
.pd-change-negative{color:var(--green)!important}
.pd-change-neutral{color:var(--text-muted)!important}
.pd-test-grid{display:grid;gap:14px;margin-bottom:18px}
.pd-test-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}
.pd-test-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
.pd-test-grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.pd-test-grid-4>article{grid-column:span 1}
.pd-calibration-test-grid{grid-template-columns:minmax(250px,1.35fr) repeat(4,minmax(0,1fr));align-items:stretch}
.pd-calibration-summary-card{grid-row:span 2}
.pd-calibration-domain-status{align-self:stretch;justify-content:center}
.pd-discrimination-test-grid{grid-template-columns:minmax(250px,1.2fr) repeat(2,minmax(0,1fr));align-items:stretch}
.pd-discrimination-domain-status{align-self:stretch;justify-content:center}
.pd-performance-test-grid{grid-template-columns:repeat(4,minmax(0,1fr));align-items:stretch}
.pd-performance-domain-status{align-self:stretch;justify-content:center}
.pd-test-card{display:flex;flex-direction:column;min-height:clamp(176px,12vw,208px);background:#fff;border:1px solid var(--border);border-top:3px solid #94a3b8;border-radius:12px;padding:15px;box-shadow:0 8px 22px rgba(15,23,42,.05)}
.pd-test-green{border-top-color:var(--green)}
.pd-test-amber{border-top-color:#d97706}
.pd-test-red{border-top-color:var(--red)}
.pd-test-card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.pd-test-card-heading span{font-size:10px;font-weight:800;color:var(--blue);text-transform:uppercase;letter-spacing:.3px}
.pd-card-title-row{display:flex;align-items:center;gap:6px}
.pd-test-card-heading h4{margin-top:3px;color:var(--text);font-size:13px;line-height:1.35}
.pd-test-status{display:flex;align-items:center;gap:3px;color:var(--text-muted);font-size:11px;font-weight:700}
.pd-test-status .pd-rag-dot{font-size:15px}
.pd-test-status-green{color:var(--green)}
.pd-test-status-amber{color:#d97706}
.pd-test-status-red{color:var(--red)}
.pd-test-status-na{color:var(--text-muted)}
.pd-test-value{margin-top:14px;color:var(--text);font-size:26px;font-weight:800;line-height:1}
.pd-test-meta{margin-top:7px;color:var(--text-muted);font-size:11px}
.pd-test-footnote{margin-top:12px;padding-top:10px;border-top:1px solid #eef2f7;color:var(--text-muted);font-size:9px;line-height:1.45}
.pd-formula-note{display:flex;flex-direction:column;gap:5px;margin-bottom:14px;padding:10px 12px;border-left:3px solid #7c3aed;border-radius:0 7px 7px 0;background:#f5f3ff;color:#5b21b6;font-size:11px;line-height:1.45}
.pd-formula-note code{overflow-x:auto;padding:5px 7px;border-radius:5px;background:#ede9fe;color:#4c1d95;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;white-space:nowrap}
.pd-formula-note span{color:#6b7280}
.pd-performance-note{font-size:11px;color:var(--text-muted);background:#f8fafc;border:1px solid var(--border);border-radius:10px;padding:10px 12px}
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
.pd-mev-model-panel{padding:18px 18px 12px;border-color:#dbe4f0;border-radius:16px;background:linear-gradient(180deg,#ffffff 0%,#fbfdff 100%);box-shadow:0 12px 30px rgba(15,23,42,.05)}
.pd-mev-summary-grid{grid-template-columns:minmax(420px,2.2fr) repeat(4,minmax(150px,1fr));align-items:stretch}
.pd-mev-summary-grid>.pd-test-card{min-width:0;min-height:158px;padding:12px 13px}
.pd-mev-summary-grid .pd-test-card-heading span{font-size:9px;letter-spacing:.24px}
.pd-mev-summary-grid .pd-test-card-heading h4{margin-top:2px;font-size:12px;line-height:1.25}
.pd-mev-summary-grid .pd-test-value{margin-top:10px;font-size:21px}
.pd-mev-summary-grid .pd-test-meta{margin-top:5px;font-size:10px;line-height:1.35;overflow-wrap:anywhere}
.pd-mev-rag-summary-card{grid-column:span 1;min-height:auto;border-top-color:#0f766e}
.pd-mev-development-card{border-top-color:#94a3b8;min-height:auto}
.pd-mev-development-list{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.pd-mev-development-row{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding-top:8px;border-top:1px solid #eef2f7}
.pd-mev-development-row:first-child{padding-top:0;border-top:none}
.pd-mev-development-row strong{flex:0 0 44%;font-size:11px;color:var(--text);line-height:1.4}
.pd-mev-development-row span{flex:1;font-size:10px;color:var(--text-muted);line-height:1.4;text-align:right;overflow-wrap:anywhere}
.pd-mev-rag-summary-list{display:flex;flex-direction:column;gap:10px;margin-top:10px}
.pd-mev-rag-model{padding-top:10px;border-top:1px solid #eef2f7}
.pd-mev-rag-model:first-child{padding-top:0;border-top:none}
.pd-mev-rag-model-header{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.pd-mev-rag-model-header strong{font-size:12px;color:var(--text);line-height:1.4}
.pd-mev-rag-counts{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:6px}
.pd-mev-rag-count{display:inline-flex;align-items:center;justify-content:center;min-height:24px;padding:4px 9px;border:1px solid transparent;border-radius:999px;font-size:10px;font-weight:800;letter-spacing:.35px;text-transform:uppercase;white-space:nowrap}
.pd-mev-rag-count-red{background:#fef2f2;border-color:#fecaca;color:#b91c1c}
.pd-mev-rag-count-amber{background:#fff7ed;border-color:#fed7aa;color:#9a3412}
.pd-mev-rag-tag-row{display:flex;align-items:flex-start;gap:8px;margin-top:7px}
.pd-mev-rag-tag-label{display:inline-flex;align-items:center;justify-content:center;min-width:56px;min-height:22px;padding:3px 8px;border-radius:999px;font-size:9px;font-weight:800;letter-spacing:.4px;text-transform:uppercase}
.pd-mev-rag-tag-label-red{background:#fef2f2;color:#b91c1c}
.pd-mev-rag-tag-label-amber{background:#fff7ed;color:#9a3412}
.pd-mev-rag-tags{display:flex;flex-wrap:wrap;gap:6px}
.pd-mev-rag-tag{display:inline-flex;align-items:center;min-height:22px;padding:3px 8px;border:1px solid transparent;border-radius:999px;font-size:9px;font-weight:700;line-height:1.2}
.pd-mev-rag-tag-red{background:#fff1f2;border-color:#fecdd3;color:#be123c}
.pd-mev-rag-tag-amber{background:#fff7ed;border-color:#fed7aa;color:#c2410c}
.pd-mev-rag-tag-neutral{background:#f8fafc;border-color:#e2e8f0;color:#64748b}
.pd-mev-filter-row{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:16px;padding:12px 14px;border:1px solid #dbe4f0;border-radius:14px;background:linear-gradient(135deg,#f8fbff 0%,#ffffff 55%,#f8fafc 100%)}
.pd-mev-filter-copy{max-width:560px}
.pd-mev-filter-copy p{margin-top:4px;color:var(--text-muted);font-size:11px;line-height:1.5}
.pd-mev-filter-controls{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap}
.pd-mev-filter-group{display:flex;flex-direction:column;gap:4px}
.pd-mev-filter-group label{font-size:10px;font-weight:800;color:var(--text-muted);text-transform:uppercase;letter-spacing:.35px}
.pd-mev-filter-actions{display:flex;align-items:flex-end}
.pd-mev-filter-select{min-width:220px;max-width:280px;height:32px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;background:#fff;color:var(--text);font-size:12px}
.pd-mev-filter-select:disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed}
.pd-mev-filter-dropdown .checkbox-dropdown-toggle{min-width:220px;max-width:280px;height:32px;padding:6px 10px}
.pd-mev-filter-dropdown .checkbox-dropdown-menu{min-width:220px;max-width:300px;max-height:280px;overflow:auto}
.pd-mev-filter-reset{min-height:32px;padding:6px 12px;border-radius:999px;border-color:#cbd5e1;background:rgba(255,255,255,.98);color:#334155;font-size:11px;font-weight:700;box-shadow:0 1px 0 rgba(255,255,255,.96) inset;transition:background .15s,border-color .15s,color .15s,transform .15s}
.pd-mev-filter-reset:hover,.pd-mev-filter-reset:focus{background:#eff6ff;border-color:#bfdbfe;color:var(--navy);outline:none;transform:translateY(-1px)}
.pd-mev-filter-reset:disabled{background:#f8fafc;border-color:#e2e8f0;color:#94a3b8;cursor:not-allowed;box-shadow:none;transform:none}
.pd-mev-model-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #e8eef6}
.pd-mev-model-copy h4{font-size:18px;color:var(--text);line-height:1.2}
.pd-mev-model-copy p{margin-top:6px;color:var(--text-muted);font-size:12px;line-height:1.6}
.pd-mev-model-badges{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}
.pd-mev-model-badge{display:inline-flex;align-items:center;justify-content:center;min-height:30px;padding:6px 12px;border:1px solid #dbe4f0;border-radius:999px;background:rgba(255,255,255,.92);color:#334155;font-size:10px;font-weight:800;letter-spacing:.35px;text-transform:uppercase}
.pd-mev-chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.pd-mev-chart-card{display:flex;flex-direction:column;gap:12px;padding:16px;border:1px solid #dbe4f0;border-radius:14px;background:linear-gradient(180deg,#ffffff 0%,#f8fbff 100%);box-shadow:0 10px 24px rgba(15,23,42,.045)}
.pd-mev-chart-header{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.pd-mev-chart-title{font-size:14px;font-weight:800;color:var(--text);line-height:1.3}
.pd-mev-chart-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:5px;color:var(--text-muted);font-size:11px;line-height:1.5}
.pd-mev-threshold-chip-row{display:flex;flex-wrap:wrap;gap:6px}
.pd-mev-threshold-chip{display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:5px 10px;border:1px solid transparent;border-radius:999px;font-size:10px;font-weight:700;line-height:1.25}
.pd-mev-threshold-chip strong{font-size:9px;font-weight:800;letter-spacing:.45px;text-transform:uppercase}
.pd-mev-threshold-chip-green{background:#ecfdf5;border-color:#bbf7d0;color:#166534}
.pd-mev-threshold-chip-amber{background:#fff7ed;border-color:#fed7aa;color:#9a3412}
.pd-mev-threshold-chip-red{background:#fef2f2;border-color:#fecaca;color:#b91c1c}
.pd-mev-marker-legend-row{display:flex;flex-wrap:wrap;gap:8px}
.pd-mev-marker-legend-item{display:inline-flex;align-items:center;gap:10px;min-height:42px;padding:7px 11px;border:1px solid #dbe4f0;border-radius:12px;background:rgba(248,250,252,.94)}
.pd-mev-marker-legend-item-development{border-color:rgba(15,23,42,.12);background:linear-gradient(180deg,rgba(255,255,255,.98) 0%,rgba(248,250,252,.98) 100%)}
.pd-mev-marker-legend-item-scenario{border-color:rgba(154,52,18,.14);background:linear-gradient(180deg,rgba(255,251,235,.98) 0%,rgba(255,247,237,.98) 100%)}
.pd-mev-marker-legend-line{display:inline-block;flex:0 0 30px;width:30px;height:0;border-top-width:2px;border-top-style:solid;border-top-color:#475569}
.pd-mev-marker-legend-line-development{border-top-color:#0f172a;border-top-style:dotted}
.pd-mev-marker-legend-line-scenario{border-top-color:#9a3412;border-top-style:dashed}
.pd-mev-marker-legend-copy{display:flex;flex-direction:column;gap:2px;min-width:0}
.pd-mev-marker-legend-label{font-size:9px;font-weight:800;letter-spacing:.38px;text-transform:uppercase;color:var(--text-muted);line-height:1.2}
.pd-mev-marker-legend-date{font-size:11px;font-weight:700;color:var(--text);line-height:1.25}
.pd-mev-chart{min-height:292px}
.pd-mev-empty-state{padding:18px 18px 8px;border-style:dashed;background:linear-gradient(135deg,#ffffff 0%,#f8fafc 70%,#f1f5f9 100%)}
.pd-migration-summary{display:flex;gap:18px;flex-wrap:wrap;padding:9px 12px;background:#f8fafc;border:1px solid var(--border);border-radius:8px;margin-bottom:8px}
.pd-migration-summary span{font-size:11px;color:var(--text-muted)}
.pd-migration-summary strong{font-size:12px;color:var(--text);margin-right:4px}
.pd-migration-chart{min-height:390px}
.pd-default-rate-trend-section{margin-top:0}
.pd-default-rate-trend-chart{min-height:460px}
.pd-calibration-trend-chart{min-height:320px}
.pd-notching-trend-chart{min-height:320px}
.pd-go-live-accuracy-trend-chart{min-height:320px}
.pd-default-rate-trend-chart-medium{min-height:320px}
.pd-default-rate-trend-chart-compact{min-height:270px}
.pd-discrimination-trend-section{margin-top:0}
.pd-discrimination-trend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.pd-discrimination-trend-chart{min-height:290px}
.pd-discrimination-trend-note{grid-column:1/-1}
.pd-primary-analysis-grid{display:grid;grid-template-columns:1fr;gap:16px}
.pd-trend-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.pd-trend-wide-card{grid-column:1/-1}
.pd-rating-default-rate-chart,.pd-distribution-shift-chart{min-height:280px}
.pd-stability-trend-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.pd-stability-trend-chart{min-height:250px}
.pd-stability-trend-note{grid-column:1/-1}
.pd-migration-grid{display:grid;grid-template-columns:minmax(260px,.7fr) minmax(460px,1.3fr);gap:14px}
.pd-subchart-panel{border:1px solid var(--border);border-radius:8px;padding:10px;background:#fff}
.pd-subchart-title{font-size:11px;color:var(--text-muted);font-weight:700;text-transform:uppercase;letter-spacing:.35px;margin-bottom:4px}
.pd-rating-direction-chart{min-height:230px}
.pd-content-section .section-card{margin-bottom:18px}
.pd-content-section:last-child{margin-bottom:0}

/* PD page spacing normalization */
#tab-pd_models .pd-page-header{gap:16px;margin-bottom:16px}
#tab-pd_models .pd-overall-status{padding:7px 10px}
#tab-pd_models .pd-overview-grid{margin-bottom:12px}
#tab-pd_models .pd-overview-row{gap:10px;margin-bottom:10px}
#tab-pd_models .pd-executive-grid,
#tab-pd_models .pd-performance-grid,
#tab-pd_models .pd-test-grid,
#tab-pd_models .pd-primary-analysis-grid,
#tab-pd_models .pd-trend-detail-grid,
#tab-pd_models .pd-discrimination-trend-grid,
#tab-pd_models .pd-stability-trend-grid,
#tab-pd_models .pd-migration-grid{gap:12px}
#tab-pd_models .pd-signal-card{padding:10px}
#tab-pd_models .pd-overview-row>.pd-signal-card{padding:12px;min-height:146px}
#tab-pd_models .pd-retention-card-heading{margin-bottom:6px}
#tab-pd_models .pd-retention-grid{gap:3px}
#tab-pd_models .pd-retention-grid div{padding-top:3px}
#tab-pd_models .pd-domain-heading{gap:14px;margin-bottom:14px;padding-bottom:10px}
#tab-pd_models .pd-domain-status{padding:7px 9px}
#tab-pd_models .pd-domain-status-top{padding:9px 11px}
#tab-pd_models .pd-scope-bar{gap:7px;padding:10px 12px;margin-bottom:16px}
#tab-pd_models .pd-scope-bar div{padding:6px 8px}
#tab-pd_models .pd-overview-flow-wrap{margin-bottom:12px;padding:10px 10px 12px}
#tab-pd_models .pd-overview-flow{row-gap:6px;grid-template-rows:44px 0 60px 60px 20px 60px 60px 26px 60px 26px 60px 60px}
#tab-pd_models .pd-flow-tests-calibration-2,
#tab-pd_models .pd-flow-assignment-2{transform:translateY(-17px)}
#tab-pd_models .pd-flow-input-balance,
#tab-pd_models .pd-flow-tests-balance,
#tab-pd_models .pd-flow-pass-balance,
#tab-pd_models .pd-flow-dimension-balance{transform:translateY(-23px)}
#tab-pd_models .pd-flow-performance{margin-bottom:44px}
#tab-pd_models .pd-overview-flow-stage{padding:4px 6px}
#tab-pd_models .pd-overview-flow-stage span{font-size:9.5px;line-height:1}
#tab-pd_models .pd-overview-flow-input{padding:11px 10px}
#tab-pd_models .pd-overview-flow-input span{margin-top:3px;line-height:1.1}
#tab-pd_models .pd-overview-flow-node{min-height:54px}
#tab-pd_models .pd-flow-tests-discrimination .pd-overview-flow-node{min-height:43px}
#tab-pd_models .pd-overview-flow-link{gap:3px;padding:7px 8px}
#tab-pd_models .pd-overview-flow-node-label{gap:4px;font-size:10px;line-height:1.08}
#tab-pd_models .pd-overview-flow-node-note{font-size:8px;line-height:1.1}
#tab-pd_models .pd-flow-assignment-1,
#tab-pd_models .pd-flow-assignment-2,
#tab-pd_models .pd-flow-dimension-calibration,
#tab-pd_models .pd-flow-dimension-discrimination,
#tab-pd_models .pd-flow-dimension-balance{min-height:66px}
#tab-pd_models .pd-flow-dimension-calibration,
#tab-pd_models .pd-flow-dimension-discrimination,
#tab-pd_models .pd-flow-dimension-balance{min-height:82px}
#tab-pd_models .pd-overview-flow-pass-through{min-height:16px}
#tab-pd_models .pd-overview-flow-performance{padding:13px 10px}
#tab-pd_models .pd-overview-flow-performance-title{gap:4px;font-size:13px;line-height:1.1}
#tab-pd_models .pd-overview-flow-performance strong{margin-top:10px}
#tab-pd_models #pd-analysis-scope{padding:12px 15px 7px}
#tab-pd_models #pd-analysis-scope .pd-content-heading{margin-bottom:9px;padding-bottom:8px}
#tab-pd_models #pd-analysis-scope .pd-content-heading p{margin-top:3px;line-height:1.5}
#tab-pd_models #pd-analysis-scope .pd-overview-grid{margin-bottom:9px}
#tab-pd_models #pd-analysis-scope .pd-overview-row{gap:6px;margin-bottom:6px}
#tab-pd_models #pd-analysis-scope .pd-overview-row>.pd-signal-card{gap:5px;padding:8px;min-height:118px}
#tab-pd_models #pd-analysis-scope .pd-overview-row>.pd-signal-card .pd-signal-card-topline{gap:6px}
#tab-pd_models #pd-analysis-scope .pd-overview-row>.pd-signal-card strong{font-size:23px}
#tab-pd_models #pd-analysis-scope .pd-overview-row>.pd-signal-card small{line-height:1.3}
#tab-pd_models #pd-analysis-scope .pd-overview-flow-wrap{margin-bottom:9px;padding:8px 8px 9px}
#tab-pd_models #pd-analysis-scope .pd-filter-application-note{margin-top:-3px;margin-bottom:8px;padding:6px 8px}
#tab-pd_models .pd-calibration-trend-chart,
#tab-pd_models .pd-notching-trend-chart,
#tab-pd_models .pd-go-live-accuracy-trend-chart{min-height:304px}
#tab-pd_models .pd-discrimination-trend-grid{gap:10px 12px}
#tab-pd_models .pd-discrimination-trend-chart{min-height:272px}
#tab-pd_models .pd-stability-trend-chart{min-height:236px}
#tab-pd_models .pd-content-section{margin-top:14px}
#tab-pd_models .pd-chapter-section{margin-top:18px}
#tab-pd_models .pd-chapter-body{gap:10px;padding-left:14px}
#tab-pd_models .pd-chapter-body>.pd-content-section:first-child{margin-top:8px}
#tab-pd_models .pd-chapter-heading{gap:16px;padding:18px 20px}
#tab-pd_models .pd-chapter-note{min-height:32px;padding:7px 11px}
#tab-pd_models .pd-live-section{padding:16px 18px 10px}
#tab-pd_models .pd-placeholder-section{margin-top:10px;padding:14px 18px 4px}
#tab-pd_models .pd-placeholder-title{margin-top:10px}
#tab-pd_models .pd-placeholder-card p{margin-top:7px}
#tab-pd_models .pd-placeholder-tags{margin-top:12px}
#tab-pd_models .pd-content-heading{margin-bottom:14px;padding-bottom:11px}
#tab-pd_models .pd-chart-heading{gap:12px;margin-bottom:14px;padding-bottom:10px}
#tab-pd_models .pd-chart-actions,
#tab-pd_models .pd-section-actions{gap:8px 6px}
#tab-pd_models .pd-range-controls{padding:5px}
#tab-pd_models .pd-metric-group{margin-bottom:12px}
#tab-pd_models .pd-performance-card{padding:13px}
#tab-pd_models .pd-performance-detail{margin-top:6px;min-height:24px}
#tab-pd_models .pd-performance-comparison{gap:10px;padding-top:10px}
#tab-pd_models .pd-test-card{padding:13px;min-height:clamp(164px,11.5vw,196px)}
#tab-pd_models .pd-test-value{margin-top:12px}
#tab-pd_models .pd-test-footnote{margin-top:10px;padding-top:8px}
#tab-pd_models .pd-formula-note{gap:4px;margin-bottom:12px;padding:9px 11px}
#tab-pd_models .pd-performance-note,
#tab-pd_models .pd-retention-warning{padding:9px 11px}
#tab-pd_models .pd-section-heading{gap:10px;margin-bottom:9px}
#tab-pd_models .pd-rag-legend{gap:12px;margin-top:8px}
#tab-pd_models .pd-rag-movement{margin-top:8px;padding-top:8px}
#tab-pd_models .pd-migration-summary{gap:14px;padding:8px 10px;margin-bottom:6px}
#tab-pd_models .pd-subchart-panel{padding:9px}
#tab-pd_models .pd-content-section .section-card{margin-bottom:16px}
#tab-pd_models .section-card{padding:14px;margin-bottom:14px}

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
  .pd-mev-summary-grid{grid-template-columns:1fr}
  .pd-mev-chart-grid{grid-template-columns:1fr}
  .pd-section-heading{flex-direction:column}
  .pd-domain-heading{flex-direction:column}
  .pd-chart-heading{flex-direction:column}
  .pd-chart-heading-copy{padding-right:0}
  .pd-chart-actions,.pd-section-actions{width:100%;justify-content:flex-start;padding-top:0}
  .pd-page-header{flex-direction:column}
  .pd-overall-status{width:100%}
  .monitoring-section-subnav-group{flex-direction:column}
  .monitoring-section-subnav-label{min-width:0}
  .pd-mev-filter-row{flex-direction:column;align-items:flex-start}
  .pd-mev-filter-copy{max-width:none}
  .pd-mev-filter-controls{width:100%}
  .pd-mev-filter-group{width:100%}
  .pd-mev-filter-actions{width:100%}
  .pd-mev-filter-select{min-width:100%;max-width:none;width:100%}
  .pd-mev-filter-dropdown .checkbox-dropdown-toggle,
  .pd-mev-filter-dropdown .checkbox-dropdown-menu{min-width:100%;max-width:none}
  .pd-mev-filter-reset{width:100%;justify-content:center}
  .pd-mev-rag-summary-card{grid-column:span 1}
  .pd-mev-development-row{flex-direction:column}
  .pd-mev-development-row span{text-align:left}
  .pd-mev-rag-model-header{flex-direction:column}
  .pd-mev-rag-counts{justify-content:flex-start}
  .pd-mev-rag-tag-row{flex-direction:column}
  .pd-mev-model-heading{flex-direction:column}
  .pd-mev-model-badges{justify-content:flex-start}
  .pd-live-section,.pd-placeholder-section{padding:14px 14px 2px}
  .pd-chapter-body{padding-left:0;border-left:none}
  .pd-chapter-heading{flex-direction:column;align-items:flex-start}
  .pd-chapter-note{text-align:left}
  .pd-overview-row,.pd-overview-row.pd-test-grid-3,.pd-overview-row.pd-test-grid-4{grid-template-columns:1fr}
  .pd-overview-row>.pd-signal-card{min-height:auto;padding:14px}
  .pd-overview-flow-wrap{padding:12px}
  .pd-overview-flow{--flow-gap:26px;grid-template-columns:minmax(112px,.58fr) minmax(196px,1fr) minmax(156px,.82fr) minmax(184px,.94fr) minmax(136px,.72fr);min-width:890px}
  .pd-overview-flow-stage{padding:7px 8px}.pd-overview-flow-stage span{font-size:10.5px}
  .pd-overview-flow-node-label{font-size:11px}.pd-overview-flow-node-value{font-size:14px}.pd-overview-flow-input strong{font-size:15px}
  .pd-overview-flow-performance-title{font-size:14px}.pd-overview-flow-performance strong{font-size:20px}
  .pd-overview-domain{font-size:18px}
  #tab-pd_models .pd-live-section,#tab-pd_models .pd-placeholder-section{padding:12px 12px 2px}
  #tab-pd_models .section-card{padding:12px}
  #tab-pd_models .pd-overview-row>.pd-signal-card{padding:12px}
  #tab-pd_models .pd-overview-flow-wrap{padding:10px}
  #tab-pd_models .pd-overview-flow{row-gap:6px;grid-template-rows:46px 0 56px 56px 18px 56px 56px 24px 56px 24px 56px 56px}
  #tab-pd_models .pd-overview-flow-stage{padding:5px 6px}
  #tab-pd_models .pd-overview-flow-stage span{font-size:9.5px}
  #tab-pd_models .pd-overview-flow-input{padding:10px 9px}
  #tab-pd_models .pd-overview-flow-link{gap:3px;padding:6px 7px}
  #tab-pd_models .pd-overview-flow-node{min-height:50px}
  #tab-pd_models .pd-flow-tests-discrimination .pd-overview-flow-node{min-height:40px}
  #tab-pd_models .pd-flow-assignment-1,
  #tab-pd_models .pd-flow-assignment-2,
  #tab-pd_models .pd-flow-dimension-calibration,
  #tab-pd_models .pd-flow-dimension-discrimination,
  #tab-pd_models .pd-flow-dimension-balance{min-height:60px}
  #tab-pd_models .pd-flow-dimension-calibration,
  #tab-pd_models .pd-flow-dimension-discrimination,
  #tab-pd_models .pd-flow-dimension-balance{min-height:72px}
  #tab-pd_models .pd-overview-flow-performance{padding:12px 9px}
}
@media(min-width:901px) and (max-width:1400px){
  .pd-kpi-dashboard-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
  .pd-test-grid-4{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-mev-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-mev-rag-summary-card{grid-column:span 2}
  .pd-calibration-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-calibration-summary-card{grid-row:auto}
  .pd-discrimination-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-performance-test-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .lgd-kpi-grid,.ead-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .pd-overview-flow{--flow-gap:clamp(26px,2.3vw,34px);grid-template-columns:minmax(114px,.62fr) minmax(202px,1.06fr) minmax(164px,.86fr) minmax(192px,.98fr) minmax(140px,.74fr);min-width:920px}
  .pd-overview-flow-stage span{font-size:11px}
  .pd-overview-flow-node-label{font-size:11px}.pd-overview-flow-node-value{font-size:14px}.pd-overview-flow-performance-title{font-size:15px}.pd-overview-flow-performance strong{font-size:22px}
  .pd-overview-row.pd-test-grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}
  .pd-overview-row.pd-test-grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}
  .pd-overview-row>.pd-signal-card{min-height:144px;padding:14px}
  .pd-executive-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
"""
