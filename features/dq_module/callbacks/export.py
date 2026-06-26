"""Export-menu callback wiring (UI <-> service glue).

``ui.common.export_bar()`` renders the per-page "Export ▾" dropdown; this
registers its four callbacks per page: open/close (client-side), this-page PDF
(client-side html2pdf), all-pages HTML and all-pages Excel (server-side
downloads). ``html_fn`` / ``excel_fn`` are passed in by the caller
(``data_access`` → ``services.report_service``), so this module imports no
pipeline code — keeping the dependency arrow callbacks → services only.
"""

from __future__ import annotations

from dash import dcc


# Click the toggle: open this menu (closing any other), then close on the next
# outside click. Plain string (not an f-string) — the JS braces stay single;
# the per-page id is injected with .replace("__K__", key).
_EXPORT_TOGGLE_JS = """function(n){
  if(!n){ return window.dash_clientside.no_update; }
  var menu = document.getElementById('dqd-__K__-export-menu');
  if(!menu){ return ''; }
  var isOpen = menu.classList.contains('open');
  document.querySelectorAll('.dqd-export-menu.open').forEach(function(m){ m.classList.remove('open'); });
  if(!isOpen){
    menu.classList.add('open');
    setTimeout(function(){
      var tgl = document.getElementById('dqd-__K__-export-toggle');
      function onDoc(e){
        if(menu.contains(e.target) || (tgl && tgl.contains(e.target))){ return; }
        menu.classList.remove('open');
        document.removeEventListener('mousedown', onDoc, true);
      }
      document.addEventListener('mousedown', onDoc, true);
    }, 0);
  }
  return '';
}"""

# Capture the live page to PDF with html2pdf (vendored in assets/js/). Targets
# the active .content scroll container; the export bar hides itself during
# capture via body.dqd-exporting. Filename comes from the bar's data-* attrs.
_EXPORT_PDF_JS = """function(n){
  if(!n){ return window.dash_clientside.no_update; }
  var menu = document.getElementById('dqd-__K__-export-menu');
  if(menu){ menu.classList.remove('open'); }
  if(typeof html2pdf === 'undefined'){
    alert('PDF library failed to load — reload the page and try again.');
    return '';
  }
  var content = document.querySelector('#page-content .content') || document.querySelector('.content');
  if(!content){ return ''; }
  var bar = content.querySelector('.dqd-export-bar');
  var label = (bar && bar.getAttribute('data-page')) || 'Dashboard';
  var qq = (bar && bar.getAttribute('data-quarter')) || '';
  var filename = 'DQ_' + label.replace(/[^A-Za-z0-9]+/g, '_') + (qq ? ('_' + qq) : '') + '.pdf';
  document.body.classList.add('dqd-exporting');
  return new Promise(function(resolve){
    requestAnimationFrame(function(){ requestAnimationFrame(function(){
      try{
        content.querySelectorAll('.js-plotly-plot').forEach(function(el){
          if(window.Plotly){ Plotly.Plots.resize(el); }
        });
      }catch(e){}
      var opt = {
        margin: [8, 8, 12, 8], filename: filename,
        image: { type: 'jpeg', quality: 0.96 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff',
                       logging: false, windowWidth: Math.max(1400, content.scrollWidth) },
        jsPDF: { unit: 'mm', format: 'a3', orientation: 'landscape', compress: true },
        pagebreak: { mode: ['css', 'legacy'] }
      };
      html2pdf().from(content).set(opt).save().then(function(){
        document.body.classList.remove('dqd-exporting'); resolve('');
      }).catch(function(e){
        document.body.classList.remove('dqd-exporting');
        alert('PDF export failed: ' + ((e && e.message) || e)); resolve('');
      });
    }); });
  });
}"""


def register_export(app, key: str, quarter: str, html_fn, excel_fn) -> None:
    """Wire one page's four export callbacks. Call once per page (the upstream
    page register_callbacks is already guarded by already_registered).

    ``html_fn()`` returns the full-report HTML string and ``excel_fn()`` the
    .xlsx bytes — both supplied by data_access so this layer stays free of
    pipeline imports.
    """
    from dash import Input, Output

    # Two client-side callbacks: open/close the menu, and capture-to-PDF.
    app.clientside_callback(
        _EXPORT_TOGGLE_JS.replace("__K__", key),
        Output(f"dqd-{key}-export-sink-toggle", "children"),
        Input(f"dqd-{key}-export-toggle", "n_clicks"),
        prevent_initial_call=True)
    app.clientside_callback(
        _EXPORT_PDF_JS.replace("__K__", key),
        Output(f"dqd-{key}-export-sink-pdf", "children"),
        Input(f"dqd-{key}-export-pdf", "n_clicks"),
        prevent_initial_call=True)

    q = quarter or ""

    @app.callback(Output(f"dqd-{key}-export-dl-html", "data"),
                  Input(f"dqd-{key}-export-html", "n_clicks"),
                  prevent_initial_call=True)
    def _dl_html(_n, _q=q):
        return dcc.send_string(html_fn(), f"DQ_Dashboard_Full_Report_{_q}.html")

    @app.callback(Output(f"dqd-{key}-export-dl-xlsx", "data"),
                  Input(f"dqd-{key}-export-xlsx", "n_clicks"),
                  prevent_initial_call=True)
    def _dl_xlsx(_n, _q=q):
        return dcc.send_bytes(excel_fn(), f"DQ_Dashboard_Report_{_q}.xlsx")
