
/* ===================== 저축은행 Data Package 항목 차트 (kis_charts.py가 데이터/자리를 만들고 여기서 그림) ===================== */
var KIS = null;

// 차트 제목(가운데, 굵게)을 그림 안에 넣음. sub = 부제(예: 기준 분기)
function kisTitle(el, sub) {
  var t = '<b>' + el.dataset.name + '</b>' + (el.dataset.unit ? ' (' + el.dataset.unit + ')' : '');
  if (sub) t += '<br><sup>' + sub + '</sup>';
  return {text: t, x: 0.5, xanchor: 'center', font: {size: 14}};
}

// x축(분기 라벨)은 최신 분기를 기준으로 4분기(1년)마다 표시
function kisXAxis(n) {
  return {type: 'category', tickangle: -45, tickfont: {size: 10}, tickmode: 'linear', tick0: (n - 1) % 4, dtick: 4};
}

function kisInit() {
  if (KIS) return true;
  var el = document.getElementById('kis-data');
  if (!el) return false;
  KIS = {d: JSON.parse(el.textContent), company: null, preset: '전체', start: null, end: null, version: 0};
  KIS.company = KIS.d.allLabel;
  kisFillList(false);
  document.querySelectorAll('.period-bar button[data-preset="전체"]').forEach(function(b){
    if (b.closest('.kis-controls')) b.classList.add('active');
  });
  return true;
}

function kisFillList(all) {
  var list = document.getElementById('kisCompanyList');
  if (!list || !KIS) return;
  var names = all ? KIS.d.companies : KIS.d.rated;
  list.innerHTML = names.map(function(c){ return '<option value="' + c + '">'; }).join('');
}

function kisCompanyFocus(el) {
  if (!kisInit()) return;
  el.dataset.prev = el.value;
  el.value = '';
  kisFillList(false);
}
function kisCompanyInput(el) {
  if (!kisInit()) return;
  kisFillList(el.value.length > 0);
  if (KIS.d.series[el.value]) kisSetCompany(el.value);
}
function kisCompanyBlur(el) {
  if (!kisInit()) return;
  if (!el.value || !KIS.d.series[el.value]) el.value = KIS.company;
  else kisSetCompany(el.value);
}
function kisSetCompany(name) {
  if (KIS.company === name) return;
  KIS.company = name;
  document.querySelectorAll('.kis-company').forEach(function(i){ if (document.activeElement !== i) i.value = name; });
  KIS.version++;
  kisRenderVisible();
}

function kisPreset(preset, btn) {
  if (!kisInit()) return;
  KIS.preset = preset;
  document.querySelectorAll('.kis-controls .period-bar button').forEach(function(b){
    b.classList.toggle('active', b.dataset.preset === preset);
  });
  document.querySelectorAll('.kis-custom').forEach(function(b){ b.classList.remove('show'); });
  KIS.version++;
  kisRenderVisible();
}
function kisCustomToggle(btn) {
  if (!kisInit()) return;
  var box = btn.closest('.kis-controls').querySelector('.kis-custom');
  box.classList.toggle('show');
  btn.closest('.period-bar').querySelectorAll('button').forEach(function(b){ b.classList.remove('active'); });
  btn.classList.add('active');
}
function kisCustomApply(btn) {
  if (!kisInit()) return;
  var box = btn.closest('.kis-custom');
  var s = box.querySelector('.kis-start').value.trim(), e = box.querySelector('.kis-end').value.trim();
  if (!s || !e) return;
  KIS.preset = '설정'; KIS.start = s; KIS.end = e;
  document.querySelectorAll('.kis-start').forEach(function(i){ i.value = s; });
  document.querySelectorAll('.kis-end').forEach(function(i){ i.value = e; });
  document.querySelectorAll('.kis-controls .period-bar button').forEach(function(b){
    b.classList.toggle('active', b.dataset.preset === '설정');
  });
  KIS.version++;
  kisRenderVisible();
}

function kisIndices() {
  var q = KIS.d.quarters, n = q.length;
  var all = q.map(function(_, i){ return i; });
  if (KIS.preset === '설정' && KIS.start && KIS.end) {
    var s = q.indexOf(KIS.start), e = q.indexOf(KIS.end);
    if (s !== -1 && e !== -1) return all.filter(function(i){ return i >= s && i <= e; });
    return all;
  }
  var years = {'1Y': 1, '3Y': 3, '5Y': 5}[KIS.preset];
  if (!years) return all;
  var start = Math.max(0, n - years * 4);
  return all.filter(function(i){ return i >= start; });
}

// 보이는(활성 탭의) 차트만 그리고, 회사/기간이 바뀌면(version) 다시 그림
function kisRenderVisible() {
  if (!kisInit()) return;
  var idx = kisIndices();
  var ser = KIS.d.series[KIS.company] || {};
  document.querySelectorAll('.kis-chart').forEach(function(el){
    if (el.offsetParent === null) return;                       // 숨겨진 탭
    if (el.dataset.v === String(KIS.version)) return;           // 이미 최신
    el.dataset.v = String(KIS.version);
    if (el.dataset.multi) { kisRenderMulti(el, ser, idx); return; }
    if (el.dataset.scatter) { kisRenderScatter(el, idx); return; }
    if (el.dataset.cmp) { kisRenderCmp(el, ser, idx); return; }
    if (el.dataset.dist) { kisRenderDist(el, ser, idx); return; }
    var key = el.dataset.key, y = ser[key];
    if (!y) { emptyChartMsg(el.id, '데이터가 없어요.'); return; }
    // 데이터가 시작되기 전(앞쪽 빈 구간)은 잘라서 차트 폭을 낭비하지 않음
    var firstOk = 0;
    while (firstOk < idx.length && (y[idx[firstOk]] === null || y[idx[firstOk]] === undefined)) firstOk++;
    if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
    var idxC = idx.slice(firstOk);
    var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
    var yv = idxC.map(function(i){ return y[i]; });
    var isBar = el.dataset.type === 'bar';
    var unit = el.dataset.unit, name = el.dataset.name;
    var fmt = unit === '억원' ? ',.1f' : '.2f';
    var traces = [{
      x: x, y: yv, type: isBar ? 'bar' : 'scatter', mode: isBar ? undefined : 'lines+markers', name: name,
      marker: {color: isBar ? '#2980B9' : undefined}, line: isBar ? undefined : {color: '#2980B9', width: 2.2},
      connectgaps: true, hovertemplate: '%{x}<br>' + name + ' %{y:' + fmt + '}' + unit + '<extra></extra>'
    }];
    var layout = {height: 308, margin: {t: 50, b: 60, l: 60, r: 10}, showlegend: false, title: kisTitle(el),
                  xaxis: kisXAxis(x.length), yaxis: {tickformat: unit === '억원' ? ',' : undefined}};
    var shareKey = el.dataset.share;
    if (shareKey && ser[shareKey]) {
      var sv = idxC.map(function(i){ return ser[shareKey][i]; });
      traces.push({x: x, y: sv, type: 'scatter', mode: 'lines+markers', name: '비중', yaxis: 'y2', connectgaps: true,
                   line: {color: '#E67E73', width: 2}, hovertemplate: '%{x}<br>비중 %{y:.1f}%<extra></extra>'});
      layout.yaxis2 = {overlaying: 'y', side: 'right', showgrid: false, ticksuffix: '%', rangemode: 'tozero'};
      layout.margin.r = 45;
    }
    plotReact(el.id, traces, layout, {displaylogo: false, responsive: true});
  });
}

// 여러 선을 한 차트에 (차주별/담보별/업종별 추이)
function kisRenderMulti(el, ser, idx) {
  var specs = JSON.parse(el.dataset.multi), unit = el.dataset.unit;
  specs = specs.filter(function(sp){ return ser[sp.k]; });
  if (!specs.length) { emptyChartMsg(el.id, '데이터가 없어요.'); return; }
  var firstOk = idx.length;
  specs.forEach(function(sp){
    var j = 0;
    while (j < idx.length && (ser[sp.k][idx[j]] === null || ser[sp.k][idx[j]] === undefined)) j++;
    if (j < firstOk) firstOk = j;
  });
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var idxC = idx.slice(firstOk);
  var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
  var fmt = unit === '억원' ? ',.0f' : '.1f';
  var traces = specs.map(function(sp){
    return {x: x, y: idxC.map(function(i){ return ser[sp.k][i]; }), type: 'scatter', mode: 'lines+markers', name: sp.n,
            connectgaps: true, line: {color: sp.c, width: 2.2}, marker: {size: 5},
            hovertemplate: '%{x}<br>' + sp.n + ' %{y:' + fmt + '}' + unit + '<extra></extra>'};
  });
  plotReact(el.id, traces, {
    height: 352, margin: {t: 50, b: 60, l: 60, r: 10}, title: kisTitle(el),
    xaxis: kisXAxis(x.length),
    yaxis: {tickformat: unit === '억원' ? ',' : undefined, ticksuffix: unit === '%' ? '%' : ''},
    legend: {}
  }, {displaylogo: false, responsive: true});
}

function kisShort(name) { return name.replace('저축은행', ''); }

// 선택 회사(실선) vs 업권 전체(점선) 구성비 추이 비교
function kisRenderCmp(el, ser, idx) {
  var specs = JSON.parse(el.dataset.cmp), all = KIS.d.series[KIS.d.allLabel] || {};
  var isAll = KIS.company === KIS.d.allLabel;
  var firstOk = idx.length;
  specs.forEach(function(sp){
    [ser, all].forEach(function(src){
      if (!src[sp.k]) return;
      var j = 0;
      while (j < idx.length && (src[sp.k][idx[j]] === null || src[sp.k][idx[j]] === undefined)) j++;
      if (j < firstOk) firstOk = j;
    });
  });
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var idxC = idx.slice(firstOk);
  var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
  var traces = [];
  specs.forEach(function(sp){
    if (!isAll && ser[sp.k]) {
      traces.push({x: x, y: idxC.map(function(i){ return ser[sp.k][i]; }), type: 'scatter', mode: 'lines+markers',
                   name: sp.n + ' · ' + kisShort(KIS.company), legendgroup: sp.k, connectgaps: true,
                   line: {color: sp.c, width: 2.4}, marker: {size: 5},
                   hovertemplate: '%{x}<br>' + kisShort(KIS.company) + ' ' + sp.n + ' %{y:.1f}%<extra></extra>'});
    }
    if (all[sp.k]) {
      traces.push({x: x, y: idxC.map(function(i){ return all[sp.k][i]; }), type: 'scatter', mode: 'lines',
                   name: sp.n + (isAll ? '' : ' · 업권 전체'), legendgroup: sp.k, connectgaps: true,
                   line: {color: sp.c, width: 2, dash: isAll ? 'solid' : 'dot'},
                   hovertemplate: '%{x}<br>업권 전체 ' + sp.n + ' %{y:.1f}%<extra></extra>'});
    }
  });
  plotReact(el.id, traces, {
    height: 352, margin: {t: 50, b: 60, l: 60, r: 10}, title: kisTitle(el), xaxis: kisXAxis(x.length),
    yaxis: {ticksuffix: '%'}, legend: {}
  }, {displaylogo: false, responsive: true});
}

// 기준 분기(선택 기간의 마지막) 구성 분포: 업권 전체 vs 선택 회사 (100% 누적 막대)
function kisRenderDist(el, ser, idx) {
  var specs = JSON.parse(el.dataset.dist), all = KIS.d.series[KIS.d.allLabel] || {};
  var isAll = KIS.company === KIS.d.allLabel;
  var ents = [{name: '업권 전체', s: all}];
  if (!isAll) ents.push({name: kisShort(KIS.company), s: ser});
  var qi = -1;
  for (var j = idx.length - 1; j >= 0 && qi < 0; j--) {
    var okAll = ents.every(function(e){
      return specs.some(function(sp){ return e.s[sp.k] && e.s[sp.k][idx[j]] !== null && e.s[sp.k][idx[j]] !== undefined; });
    });
    if (okAll) qi = idx[j];
  }
  if (qi < 0) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var totals = ents.map(function(e){
    return specs.reduce(function(sum, sp){ var v = e.s[sp.k] ? e.s[sp.k][qi] : null; return sum + (v > 0 ? v : 0); }, 0);
  });
  var traces = specs.map(function(sp){
    var pct = ents.map(function(e, n){
      var v = e.s[sp.k] ? e.s[sp.k][qi] : null;
      return (v > 0 && totals[n]) ? v / totals[n] * 100 : 0;
    });
    return {type: 'bar', x: ents.map(function(e){ return e.name; }), y: pct, name: sp.n, marker: {color: sp.c},
            text: pct.map(function(p){ return p >= 4 ? sp.n + ' ' + p.toFixed(1) + '%' : ''; }),
            textposition: 'inside', insidetextanchor: 'middle', textfont: {size: 10},
            hovertemplate: '%{x}<br>' + sp.n + ' %{y:.1f}%<extra></extra>'};
  });
  plotReact(el.id, traces, {
    barmode: 'stack', height: 352, margin: {t: 60, b: 40, l: 50, r: 10}, showlegend: false,
    title: kisTitle(el, KIS.d.quarters[qi] + ' 기준'),
    yaxis: {range: [0, 100], ticksuffix: '%'}
  }, {displaylogo: false, responsive: true});
}

// 가계자금대출 비중(x) vs 신용대출 비중(y): 신평사 유효등급 회사별 산점도 (기간 선택의 마지막 분기 기준)
function kisRenderScatter(el, idx) {
  var cfg = JSON.parse(el.dataset.scatter);
  var allLabel = KIS.d.allLabel, S = KIS.d.series;
  var names = KIS.d.rated.filter(function(c){ return c !== allLabel; });
  var qi = -1;
  for (var j = idx.length - 1; j >= 0 && qi < 0; j--) {
    var n = names.filter(function(c){
      var h = S[c] && S[c][cfg.x], cr = S[c] && S[c][cfg.y];
      return h && cr && h[idx[j]] !== null && cr[idx[j]] !== null;
    }).length;
    if (n) qi = idx[j];
  }
  if (qi < 0) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var pts = names.map(function(c){
    var s = S[c] || {};
    return {n: c, x: s[cfg.x] ? s[cfg.x][qi] : null, y: s[cfg.y] ? s[cfg.y][qi] : null};
  }).filter(function(p){ return p.x !== null && p.y !== null; });
  var sel = pts.filter(function(p){ return p.n === KIS.company; });
  var others = pts.filter(function(p){ return p.n !== KIS.company; });
  var traces = [{
    x: others.map(function(p){ return p.x; }), y: others.map(function(p){ return p.y; }), mode: 'markers+text', type: 'scatter',
    text: others.map(function(p){ return kisShort(p.n); }), textposition: 'top center', textfont: {size: 9, color: '#555'},
    customdata: others.map(function(p){ return kisShort(p.n); }), name: '신평사 유효등급 ' + pts.length + '개사',
    marker: {color: '#2980B9', size: 9}, hovertemplate: '%{customdata}<br>' + cfg.xl.replace(' (%)','') + ' %{x:.1f}% / ' + cfg.yl.replace(' (%)','') + ' %{y:.1f}%<extra></extra>'
  }];
  if (sel.length) {
    traces.push({x: [sel[0].x], y: [sel[0].y], mode: 'markers+text', type: 'scatter', text: [kisShort(sel[0].n)], textposition: 'top center',
                 textfont: {size: 11, color: '#E8312F'}, name: '선택: ' + kisShort(sel[0].n),
                 marker: {color: '#E8312F', size: 13, symbol: 'diamond'},
                 hovertemplate: kisShort(sel[0].n) + '<br>' + cfg.xl.replace(' (%)','') + ' %{x:.1f}% / ' + cfg.yl.replace(' (%)','') + ' %{y:.1f}%<extra></extra>'});
  }
  var a = S[allLabel] || {};
  if (a[cfg.x] && a[cfg.y] && a[cfg.x][qi] !== null) {
    traces.push({x: [a[cfg.x][qi]], y: [a[cfg.y][qi]], mode: 'markers', type: 'scatter', name: '업권 전체',
                 marker: {color: '#111', size: 11, symbol: 'x'},
                 hovertemplate: '업권 전체<br>' + cfg.xl.replace(' (%)','') + ' %{x:.1f}% / ' + cfg.yl.replace(' (%)','') + ' %{y:.1f}%<extra></extra>'});
  }
  plotReact(el.id, traces, {
    height: 420, margin: {t: 60, b: 55, l: 55, r: 10},
    title: kisTitle(el, KIS.d.quarters[qi] + ' 기준'),
    xaxis: {title: cfg.xl, ticksuffix: '%', showgrid: true, gridcolor: '#eef0f3'},
    yaxis: {title: cfg.yl, ticksuffix: '%'},
    legend: {}
  }, {displaylogo: false, responsive: true});
}
