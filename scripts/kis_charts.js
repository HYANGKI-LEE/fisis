
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

var KIS_POOL = {};
// 업권 페이지마다 자기 데이터/선택 상태(KIS)를 따로 가짐: 지금 보이는 페이지의 것을 KIS로 고른다
function kisRoot() { return document.querySelector('.page.active') || document; }
function kisInit() {
  var root = kisRoot();
  var el = root.querySelector('script.kis-data');
  if (!el) return false;
  if (!KIS_POOL[el.id]) {
    var st = {d: JSON.parse(el.textContent), company: null, preset: '전체', start: null, end: null, version: 0, target: 8, key: el.id};
    st.company = st.d.baseGroup || st.d.allLabel;     // 증권사 페이지는 '유효등급 보유'가 기본 선택
    KIS_POOL[el.id] = st;
    KIS = st;
    kisFillList(false);
    root.querySelectorAll('.period-bar button[data-preset="전체"]').forEach(function(b){
      if (b.closest('.kis-controls')) b.classList.add('active');
    });
  }
  KIS = KIS_POOL[el.id];
  return true;
}

function kisFillList(all) {
  var list = kisRoot().querySelector('datalist.kis-datalist');
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
  kisRoot().querySelectorAll('.kis-company').forEach(function(i){ if (document.activeElement !== i) i.value = name; });
  KIS.version++;
  kisRenderVisible();
}

function kisPreset(preset, btn) {
  if (!kisInit()) return;
  KIS.preset = preset;
  kisRoot().querySelectorAll('.kis-controls .period-bar button').forEach(function(b){
    b.classList.toggle('active', b.dataset.preset === preset);
  });
  kisRoot().querySelectorAll('.kis-custom').forEach(function(b){ b.classList.remove('show'); });
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
  kisRoot().querySelectorAll('.kis-start').forEach(function(i){ i.value = s; });
  kisRoot().querySelectorAll('.kis-end').forEach(function(i){ i.value = e; });
  kisRoot().querySelectorAll('.kis-controls .period-bar button').forEach(function(b){
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
  var years = /^[0-9]+년$/.test(KIS.preset) ? parseInt(KIS.preset, 10) : 0;
  if (!years) return all;
  var start = Math.max(0, n - years * 4);
  return all.filter(function(i){ return i >= start; });
}

// 보이는(활성 탭의) 차트만 그리고, 회사/기간이 바뀌면(version) 다시 그림
function kisRenderVisible() {
  if (!kisInit()) return;
  kisStickyOffset();
  kisRenderTable();
  kisSyncStatements();
  ratingRender();
  var idx = kisIndices();
  var ser = KIS.d.series[KIS.company] || {};
  kisRoot().querySelectorAll('.kis-ctable').forEach(function(box){
    if (box.offsetParent === null || box.dataset.v === String(KIS.version)) return;
    box.dataset.v = String(KIS.version);
    kisRenderCtable(box, idx);
  });
  kisRoot().querySelectorAll('.kis-chart').forEach(function(el){
    if (el.offsetParent === null) return;                       // 숨겨진 탭
    if (el.dataset.v === String(KIS.version)) return;           // 이미 최신
    el.dataset.v = String(KIS.version);
    if (el.dataset.stackj) { kisRenderStackJ(el, ser, idx); return; }
    if (el.dataset.hbar) { kisRenderHbar(el, idx); return; }
    if (el.dataset.cbar) { kisRenderCbar(el, idx); return; }
    if (el.dataset.stack) { kisRenderStack(el, ser, idx); return; }
    if (el.dataset.multi) { kisRenderMulti(el, ser, idx); return; }
    if (el.dataset.scatter) { kisRenderScatter(el, idx); return; }
    if (el.dataset.cmp3) { kisRenderCmp3(el, ser, idx); return; }
    if (el.dataset.cmp3m) { kisRenderCmp3m(el, ser, idx); return; }
    if (el.dataset.buf) { kisRenderBuf(el, ser, idx); return; }
    if (el.dataset.dual) { kisRenderDual(el, ser, idx); return; }
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
  var base = KIS.d.baseGroup && KIS.d.members && KIS.d.members[KIS.d.baseGroup] ? KIS.d.baseGroup : null;   // 증권사: 유효등급 보유 회사만
  var names = base ? KIS.d.members[base] : KIS.d.rated.filter(function(c){ return c !== allLabel; });
  var xU = cfg.xu || '%', xF = xU === '%' ? ' %{x:.1f}%' : ' %{x:,.0f}' + xU, aggLabel = base || '업권 전체';
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
    customdata: others.map(function(p){ return kisShort(p.n); }), name: (base ? base + ' ' : '신평사 유효등급 ') + pts.length + '개사',
    marker: {color: '#2980B9', size: 9}, hovertemplate: '%{customdata}<br>' + cfg.xl.replace(' (%)','') + xF + ' / ' + cfg.yl.replace(' (%)','') + ' %{y:.1f}%<extra></extra>'
  }];
  if (sel.length) {
    traces.push({x: [sel[0].x], y: [sel[0].y], mode: 'markers+text', type: 'scatter', text: [kisShort(sel[0].n)], textposition: 'top center',
                 textfont: {size: 11, color: '#E8312F'}, name: '선택: ' + kisShort(sel[0].n),
                 marker: {color: '#E8312F', size: 13, symbol: 'diamond'},
                 hovertemplate: kisShort(sel[0].n) + '<br>' + cfg.xl.replace(' (%)','') + xF + ' / ' + cfg.yl.replace(' (%)','') + ' %{y:.1f}%<extra></extra>'});
  }
  var a = S[base || allLabel] || {};
  if (xU === '%' && a[cfg.x] && a[cfg.y] && a[cfg.x][qi] !== null) {
    traces.push({x: [a[cfg.x][qi]], y: [a[cfg.y][qi]], mode: 'markers+text', type: 'scatter', name: aggLabel,
                 text: ['전체'], textposition: 'top center', textfont: {size: 11, color: '#111'},
                 marker: {color: '#111', size: 11, symbol: 'x'},
                 hovertemplate: aggLabel + '<br>' + cfg.xl.replace(' (%)','') + xF + ' / ' + cfg.yl.replace(' (%)','') + ' %{y:.1f}%<extra></extra>'});
  }
  plotReact(el.id, traces, {
    height: 420, margin: {t: 60, b: 55, l: 55, r: 10},
    title: kisTitle(el, KIS.d.quarters[qi] + ' 기준'),
    xaxis: {title: cfg.xl, ticksuffix: xU === '%' ? '%' : '', tickformat: xU === '%' ? undefined : ',', type: cfg.xlog ? 'log' : 'linear', showgrid: true, gridcolor: '#eef0f3'},
    yaxis: {title: cfg.yl, ticksuffix: '%'},
    showlegend: false
  }, {displaylogo: false, responsive: true});
}

// 회사/기간 선택줄을 스크롤해도 맨 위(제목+탭바 아래)에 고정
function kisStickyOffset() {
  var h = document.querySelector('.page.active h1'), panel = document.querySelector('.page.active .tab-panel.active'),
      tb = panel && panel.parentElement.querySelector('.tab-bar');
  if (!h || !tb) return;
  var top = (parseInt(getComputedStyle(tb).top, 10) || h.offsetHeight) + tb.offsetHeight;   // 탭바의 sticky top + 탭바 높이
  kisRoot().querySelectorAll('.kis-controls').forEach(function(c){ c.style.top = top + 'px'; });
}
window.addEventListener('resize', function(){ if (KIS) kisStickyOffset(); });

// 선택 회사 vs 업권 전체 vs 신평사 유효등급 보유사 비교 추이
function kisRenderCmp3(el, ser, idx) {
  var cfg = JSON.parse(el.dataset.cmp3), k = cfg.k, S = KIS.d.series;
  var all = S[KIS.d.allLabel] || {};
  var isAll = KIS.company === KIS.d.allLabel;
  var sources = [];
  var gray = !!cfg.gray;   // 자산건전성처럼 비교선을 회색 계열로 그리는 차트
  var suffix = el.dataset.unit === '%' ? '%' : el.dataset.unit;   // '배' 같은 단위는 그대로 붙임
  var groups = KIS.d.groups || [KIS.d.ratedLabel];
  var pal = gray ? [['#666666', 'dot'], ['#B0B0B0', 'dash'], ['#999999', 'dashdot'], ['#CCCCCC', 'longdash']]
                 : [['#555555', 'dot'], ['#ED7D31', 'dash'], ['#70AD47', 'dashdot'], ['#8E44AD', 'longdash']];
  if (!isAll) sources.push({name: kisShort(KIS.company), s: ser, color: '#2980B9', width: 2.8, dash: 'solid'});
  sources.push({name: KIS.d.groups ? KIS.d.allLabel : '업권 전체', s: all, color: pal[0][0], width: 2.2, dash: pal[0][1]});
  groups.forEach(function(gl, gi){
    if (gl === KIS.company) return;     // 선택한 항목이 그룹이면 파란 실선으로 이미 그림
    sources.push({name: gl, s: S[gl] || {}, color: pal[gi + 1][0], width: 2.2, dash: pal[gi + 1][1]});
  });
  sources = sources.filter(function(src){ return src.s[k]; });
  var firstOk = idx.length;
  sources.forEach(function(src){
    var j = 0;
    while (j < idx.length && (src.s[k][idx[j]] === null || src.s[k][idx[j]] === undefined)) j++;
    if (j < firstOk) firstOk = j;
  });
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var idxC = idx.slice(firstOk);
  var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
  var traces = sources.map(function(src){
    return {x: x, y: idxC.map(function(i){ return src.s[k][i]; }), type: 'scatter', mode: 'lines', name: src.name, connectgaps: true,
            line: {color: src.color, width: src.width, dash: src.dash}, hovertemplate: '%{x}<br>' + src.name + ' %{y:.2f}' + suffix + '<extra></extra>'};
  });
  plotReact(el.id, traces, {
    height: 340, margin: {t: 50, b: 60, l: 55, r: 10}, title: kisTitle(el), xaxis: kisXAxis(x.length),
    yaxis: {ticksuffix: suffix === '%' ? '%' : ''}, legend: {}
  }, {displaylogo: false, responsive: true});
}

// 막대(좌축, 억원) + 증감률 선(우축, %)
function kisRenderDual(el, ser, idx) {
  var cfg = JSON.parse(el.dataset.dual);
  var bar = ser[cfg.bar], line = ser[cfg.line];
  if (!bar) { emptyChartMsg(el.id, '데이터가 없어요.'); return; }
  var firstOk = 0;
  while (firstOk < idx.length && (bar[idx[firstOk]] === null || bar[idx[firstOk]] === undefined)) firstOk++;
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var idxC = idx.slice(firstOk);
  var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
  var traces = [{x: x, y: idxC.map(function(i){ return bar[i]; }), type: 'bar', name: cfg.bn, marker: {color: '#2980B9'},
                 hovertemplate: '%{x}<br>' + cfg.bn + ' %{y:,.0f}억원<extra></extra>'}];
  if (line) {
    traces.push({x: x, y: idxC.map(function(i){ return line[i]; }), type: 'scatter', mode: 'lines', yaxis: 'y2', name: cfg.ln,
                 connectgaps: true, line: {color: '#E8312F', width: 2.6}, hovertemplate: '%{x}<br>' + cfg.ln + ' %{y:.1f}%<extra></extra>'});
  }
  plotReact(el.id, traces, {
    height: 340, margin: {t: 50, b: 60, l: 60, r: 45}, title: kisTitle(el), xaxis: kisXAxis(x.length),
    yaxis: {tickformat: ','}, yaxis2: {overlaying: 'y', side: 'right', showgrid: false, ticksuffix: '%'}, legend: {}
  }, {displaylogo: false, responsive: true});
}

// 탭별 상단 표(수익성/자산건전성/자본적정성): 최근 5개 연도(12월) + 4분기 전 + 당분기 (선택 회사 기준)
function kisQLabel(q) {   // '2026.Q2' -> '2026.06'
  var m = q.match(/^(\d{4})\.Q(\d)$/);
  return m ? m[1] + '.' + ('0' + (parseInt(m[2], 10) * 3)).slice(-2) : q;
}
function kisRenderTable() {
  kisRoot().querySelectorAll('.kis-table').forEach(function(tb){
    if (tb.offsetParent === null || tb.dataset.v === String(KIS.version)) return;
    tb.dataset.v = String(KIS.version);
    var rows = JSON.parse(tb.dataset.rows);
    var q = KIS.d.quarters, L = q.length - 1, ser = KIS.d.series[KIS.company] || {};
    var fy = [];
    for (var i = L; i >= 0 && fy.length < 5; i--) { if (q[i].slice(-2) === 'Q4') fy.unshift(i); }
    var cols = fy.map(function(i){ return {i: i, fy: true}; });
    cols.push({i: L - 4, fy: false});
    cols.push({i: L, fy: false});
    var fmt = function(v, u) {
      if (v === null || v === undefined) return '-';
      if (u === 'eok') return v.toLocaleString('ko-KR', {maximumFractionDigits: 0});
      if (u === 'x') return v.toFixed(1);
      return v.toLocaleString('ko-KR', {minimumFractionDigits: 1, maximumFractionDigits: 1}) + '%';
    };
    tb.querySelector('thead').innerHTML = '<tr><th>구분</th>' + cols.map(function(c){ return '<th>' + kisQLabel(q[c.i]) + '</th>'; }).join('') + '</tr>';
    tb.querySelector('tbody').innerHTML = rows.map(function(r){
      var pad = (r.i || 0) * 16;
      return '<tr' + (r.b ? ' class="kis-bold"' : '') + '><td style="padding-left:' + (10 + pad) + 'px;">' +
             r.n.replace('목표 BIS비율', '목표 BIS ' + KIS.target + '%') + '</td>' + cols.map(function(c){
        var key = c.fy ? r.fy : r.q;
        if (key.indexOf('calc:') === 0) return '<td>' + fmt(kisBufValue(ser, c.i, key.slice(5)), r.u) + '</td>';
        var arr = ser[key];
        return '<td>' + fmt(arr ? arr[c.i] : null, r.u) + '</td>';
      }).join('') + '</tr>';
    }).join('');
  });
}

// 여러 지표를 한 차트에: 지표별 색, 선택 회사(실선) / 업권 전체(점선) / 신평사 유효등급 보유사(파선)
function kisRenderCmp3m(el, ser, idx) {
  var cfg = JSON.parse(el.dataset.cmp3m), S = KIS.d.series;
  var all = S[KIS.d.allLabel] || {};
  var isAll = KIS.company === KIS.d.allLabel;
  var lines = [];
  var groups = KIS.d.groups || [KIS.d.ratedLabel];
  var gdash = ['dash', 'dashdot', 'longdash'];
  cfg.ks.forEach(function(m){
    if (!isAll && ser[m.k]) lines.push({name: m.n + ' · ' + kisShort(KIS.company), v: ser[m.k], color: m.c, width: 2.8, dash: 'solid'});
    if (all[m.k]) lines.push({name: m.n + (isAll ? '' : ' · 업권 전체'), v: all[m.k], color: m.c, width: 2.2, dash: isAll ? 'solid' : 'dot'});
    groups.forEach(function(gl, gi){
      if (gl === KIS.company) return;
      var gs = S[gl] || {};
      if (gs[m.k]) lines.push({name: m.n + ' · ' + (KIS.d.groups ? gl : '유효등급 ' + (gl.match(/[0-9]+/) || [''])[0] + '개사'),
                               v: gs[m.k], color: m.c, width: 2.2, dash: gdash[gi]});
    });
  });
  var firstOk = idx.length;
  lines.forEach(function(l){
    var j = 0;
    while (j < idx.length && (l.v[idx[j]] === null || l.v[idx[j]] === undefined)) j++;
    if (j < firstOk) firstOk = j;
  });
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var idxC = idx.slice(firstOk);
  var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
  var traces = lines.map(function(l){
    return {x: x, y: idxC.map(function(i){ return l.v[i]; }), type: 'scatter', mode: 'lines', name: l.name, connectgaps: true,
            line: {color: l.color, width: l.width, dash: l.dash}, hovertemplate: '%{x}<br>' + l.name + ' %{y:.2f}%<extra></extra>'};
  });
  plotReact(el.id, traces, {
    height: 340, margin: {t: 50, b: 60, l: 55, r: 10}, title: kisTitle(el), xaxis: kisXAxis(x.length),
    yaxis: {ticksuffix: '%'}, legend: {}
  }, {displaylogo: false, responsive: true});
}

// ---- 목표 BIS비율 도달 시 자본 감소 여력 (위험가중자산 불변, 세금 효과 없음 가정)
function kisSetTarget(el) {
  if (!kisInit()) return;
  var v = parseFloat(el.value);
  if (!isFinite(v) || v < 0) return;
  KIS.target = v;
  kisRoot().querySelectorAll('.kis-target').forEach(function(i){ if (i !== el) i.value = el.value; });
  KIS.version++;
  kisRenderVisible();
}
function kisBufValue(src, i, type) {
  var cap = src.cp_cap ? src.cp_cap[i] : null, rwa = src.cp_rwa ? src.cp_rwa[i] : null;
  if (cap === null || cap === undefined || rwa === null || rwa === undefined) return null;
  var need = KIS.target / 100 * rwa, buf = cap - need;
  if (type === 'need') return need;
  if (type === 'buf') return buf;
  var base = type === 'loan' ? (src.aq_loan ? src.aq_loan[i] : null) : (src.aq_sub ? src.aq_sub[i] : null);
  return (base && base > 0) ? buf / base * 100 : null;
}
function kisRenderBuf(el, ser, idx) {
  var cfg = JSON.parse(el.dataset.buf), S = KIS.d.series, mode = cfg.mode;
  var all = S[KIS.d.allLabel] || {}, rated = S[KIS.d.ratedLabel] || {};
  var isAll = KIS.company === KIS.d.allLabel;
  var sub = '목표 BIS비율 ' + KIS.target + '%';
  if (mode === 'amt') {   // 금액은 규모 차이가 커서 선택 회사(전체 선택 시 업권 전체)만 막대로
    var src = isAll ? all : ser;
    var firstA = 0;
    var vals = idx.map(function(i){ return kisBufValue(src, i, 'buf'); });
    while (firstA < vals.length && vals[firstA] === null) firstA++;
    if (firstA >= vals.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
    var xa = idx.slice(firstA).map(function(i){ return KIS.d.quarters[i]; }), ya = vals.slice(firstA);
    plotReact(el.id, [{x: xa, y: ya, type: 'bar', name: '자본 감소 여력',
                       marker: {color: ya.map(function(v){ return v !== null && v < 0 ? '#E8312F' : '#2980B9'; })},
                       hovertemplate: '%{x}<br>자본 감소 여력 %{y:,.0f}억원<extra></extra>'}], {
      height: 340, margin: {t: 60, b: 60, l: 60, r: 10}, title: kisTitle(el, sub), xaxis: kisXAxis(xa.length),
      yaxis: {tickformat: ','}, showlegend: false
    }, {displaylogo: false, responsive: true});
    return;
  }
  var sources = [];
  if (!isAll) sources.push({name: kisShort(KIS.company), s: ser, color: '#2980B9', width: 2.8, dash: 'solid'});
  sources.push({name: '업권 전체', s: all, color: '#666666', width: 2.2, dash: 'dot'});
  sources.push({name: KIS.d.ratedLabel, s: rated, color: '#B0B0B0', width: 2.2, dash: 'dash'});
  var firstOk = idx.length;
  var lines = sources.map(function(src){
    var v = idx.map(function(i){ return kisBufValue(src.s, i, mode); });
    var j = 0; while (j < v.length && v[j] === null) j++;
    if (j < firstOk) firstOk = j;
    return {src: src, v: v};
  });
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var x = idx.slice(firstOk).map(function(i){ return KIS.d.quarters[i]; });
  var traces = lines.map(function(l){
    return {x: x, y: l.v.slice(firstOk), type: 'scatter', mode: 'lines', name: l.src.name, connectgaps: true,
            line: {color: l.src.color, width: l.src.width, dash: l.src.dash},
            hovertemplate: '%{x}<br>' + l.src.name + ' %{y:.1f}%<extra></extra>'};
  });
  plotReact(el.id, traces, {
    height: 340, margin: {t: 60, b: 60, l: 55, r: 10}, title: kisTitle(el, sub), xaxis: kisXAxis(x.length),
    yaxis: {ticksuffix: '%', zeroline: true, zerolinecolor: '#999'}, legend: {}
  }, {displaylogo: false, responsive: true});
}

// 맨 위 공통 선택줄(회사/기간)이 바뀌면 재무상태표·손익계산서의 기존 차트/표도 같이 갱신
function kisSyncStatements() {
  if (!window.IS_STATE) return;
  Object.keys(IS_STATE).forEach(function(sec){
    var cap = document.getElementById('isCaption-' + sec);
    if (cap && cap.offsetParent !== null) onIsChange(sec);
  });
}

// 선택 회사의 구성 항목을 쌓은 막대로 (영업순수익 구성, 총자산 대비 손익 구성 등)
function kisRenderStack(el, ser, idx) {
  var specs = JSON.parse(el.dataset.stack), unit = el.dataset.unit;
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
  var fmt = unit === '억원' ? ',.0f' : '.2f';
  var traces = specs.map(function(sp){
    return {x: x, y: idxC.map(function(i){ return ser[sp.k][i]; }), type: 'bar', name: sp.n, marker: {color: sp.c},
            hovertemplate: '%{x}<br>' + sp.n + ' %{y:' + fmt + '}' + unit + '<extra></extra>'};
  });
  plotReact(el.id, traces, {
    barmode: 'relative', height: 352, margin: {t: 50, b: 60, l: 60, r: 10}, title: kisTitle(el),
    xaxis: kisXAxis(x.length), yaxis: {tickformat: unit === '억원' ? ',' : undefined, ticksuffix: unit === '%' ? '%' : ''},
    legend: {}
  }, {displaylogo: false, responsive: true});
}

// 구성 추이(조원): 선택 대상의 항목을 쌓은 막대 + 막대 위 합계(연말·최신 분기) + 선택적 비중 선(우축)
function kisRenderStackJ(el, ser, idx) {
  var cfg = JSON.parse(el.dataset.stackj);
  var bars = cfg.bars.filter(function(b){ return ser[b.k]; });
  if (!bars.length) { emptyChartMsg(el.id, '데이터가 없어요.'); return; }
  var firstOk = idx.length;
  bars.forEach(function(b){
    var j = 0;
    while (j < idx.length && (ser[b.k][idx[j]] === null || ser[b.k][idx[j]] === undefined)) j++;
    if (j < firstOk) firstOk = j;
  });
  if (firstOk >= idx.length) { emptyChartMsg(el.id, '이 기간엔 데이터가 없어요.'); return; }
  var idxC = idx.slice(firstOk);
  var x = idxC.map(function(i){ return KIS.d.quarters[i]; });
  var traces = bars.map(function(b){
    return {x: x, y: idxC.map(function(i){ var v = ser[b.k][i]; return (v === null || v === undefined) ? null : v / 1e4; }), type: 'bar',
            name: b.n, marker: {color: b.c}, hovertemplate: '%{x}<br>' + b.n + ' %{y:,.1f}조원<extra></extra>'};
  });
  var tot = idxC.map(function(i){
    var t = 0, any = false;
    bars.forEach(function(b){ var v = ser[b.k][i]; if (v !== null && v !== undefined) { t += v; any = true; } });
    return any ? t / 1e4 : null;
  });
  var lab = tot.map(function(t, n){
    var q = x[n];
    return (t !== null && (q.slice(-2) === 'Q4' || n === x.length - 1)) ? Math.round(t).toLocaleString('ko-KR') : '';
  });
  traces.push({x: x, y: tot, type: 'scatter', mode: 'text', text: lab, textposition: 'top center', textfont: {size: 10},
               showlegend: false, hoverinfo: 'skip', cliponaxis: false});
  var layout = {barmode: 'relative', height: 360, margin: {t: 50, b: 60, l: 55, r: 10}, title: kisTitle(el), xaxis: kisXAxis(x.length),
                yaxis: {tickformat: ',', rangemode: 'tozero'}, legend: {}};
  if (cfg.line && ser[cfg.line.k]) {
    traces.push({x: x, y: idxC.map(function(i){ return ser[cfg.line.k][i]; }), type: 'scatter', mode: 'lines', yaxis: 'y2', name: cfg.line.n,
                 connectgaps: true, line: {color: cfg.line.c, width: 2.6}, hovertemplate: '%{x}<br>' + cfg.line.n + ' %{y:.1f}%<extra></extra>'});
    layout.yaxis2 = {overlaying: 'y', side: 'right', showgrid: false, ticksuffix: '%', rangemode: 'tozero'};
    layout.margin.r = 45;
  }
  plotReact(el.id, traces, layout, {displaylogo: false, responsive: true});
}

// 자산 종류별 고정이하·요주의이하 비율 세로 막대: 증권사 전체 선택 시 항목당 2개, 그 외에는 선택 항목 vs 증권사 전체 4개
function kisRenderHbar(el, idx) {
  var items = JSON.parse(el.dataset.hbar), S = KIS.d.series, qi = idx[idx.length - 1];
  var refKey = KIS.d.baseGroup || KIS.d.allLabel;
  var allS = S[refKey] || {}, sel = S[KIS.company] || {}, isAll = KIS.company === refKey;
  var ratio = function(src, c, kind) {
    var t = src['ah_' + c + '_tot'], v = src['ah_' + c + '_' + kind];
    if (!t || !v) return null;
    var tt = t[qi], vv = v[qi];
    if (tt === null || tt === undefined || !(tt > 0) || vv === null || vv === undefined) return null;
    return vv / tt * 100;
  };
  var base = isAll ? allS : sel;
  var rows = items.filter(function(it){ return ratio(base, it.c, 'sub') !== null; });
  if (!rows.length) { emptyChartMsg(el.id, '이 분기엔 이 회사의 자산건전성 분류 데이터가 없어요.'); return; }
  var bal = function(src, c) {
    var t = src['ah_' + c + '_tot'];
    return (t && t[qi] !== null && t[qi] !== undefined) ? t[qi] : null;
  };
  var fmtBal = function(v){ return v === null ? '-' : v.toLocaleString('ko-KR', {maximumFractionDigits: 0}); };
  // 항목 이름 뒤에 선택 대상(증권사 전체 또는 선택 회사/그룹)의 분류대상 잔액(억원)을 붙임
  var names = rows.map(function(it){ return it.n + '(잔액 ' + fmtBal(bal(base, it.c)) + '억원)'; });
  var fmtText = function(arr){ return arr.map(function(v){ return v === null ? '' : v.toFixed(2) + '%'; }); };
  var mk = function(name, src, kind, color, dash) {
    var y = rows.map(function(it){ return ratio(src, it.c, kind); });
    return {type: 'bar', name: name, x: names, y: y, marker: {color: color}, text: fmtText(y), textposition: 'outside',
            customdata: rows.map(function(it){ return fmtBal(bal(src, it.c)); }),
            textfont: {size: 9}, cliponaxis: false,
            hovertemplate: '%{x}<br>' + name + ' %{y:.2f}%<br>해당 자산 잔액 %{customdata}억원<extra></extra>'};
  };
  var co = kisShort(KIS.company), allName = refKey;
  var traces = isAll
    ? [mk('고정이하', allS, 'sub', '#C0392B'), mk('요주의이하', allS, 'wat', '#2E75B6')]
    : [mk(co + ' 고정이하', sel, 'sub', '#C0392B'), mk(allName + ' 고정이하', allS, 'sub', '#E6A09A'),
       mk(co + ' 요주의이하', sel, 'wat', '#2E75B6'), mk(allName + ' 요주의이하', allS, 'wat', '#9DC3E6')];
  plotReact(el.id, traces, {
    barmode: 'group', height: 520, margin: {t: 100, b: 110, l: 55, r: 20},
    title: kisTitle(el, KIS.d.quarters[qi] + ' 기준'),
    xaxis: {type: 'category', tickangle: -35, tickfont: {size: 11}}, yaxis: {ticksuffix: '%', rangemode: 'tozero'},
    legend: {orientation: 'h', y: 1.0, yanchor: 'bottom', x: 0.5, xanchor: 'center'}
  }, {displaylogo: false, responsive: true});
}

// 회사별 표/막대에 보여줄 회사: 선택이 대형/중소형 같은 그룹이면 그 그룹 회사만, 아니면 전체 회사
function kisMemberNames() {
  var mem = KIS.d.members && KIS.d.members[KIS.company];
  if (mem) return mem;
  var baseMem = KIS.d.baseGroup && KIS.d.members && KIS.d.members[KIS.d.baseGroup];
  if (baseMem) {   // 개별 회사를 골라도 기본 그룹(유효등급 보유) 회사들을 보여주고, 그 밖의 회사를 골랐으면 그 회사도 덧붙임
    return (baseMem.indexOf(KIS.company) >= 0 || !KIS.d.series[KIS.company]) ? baseMem : baseMem.concat([KIS.company]);
  }
  var groupLabels = KIS.d.members ? Object.keys(KIS.d.members) : [];
  return KIS.d.companies.filter(function(c){ return c !== KIS.d.allLabel && groupLabels.indexOf(c) === -1; });
}

// 회사별 비교 막대: 지표/기준 분기를 고르면 전 회사를 큰 순서로 (선택 회사는 빨강)
function kisCbarChange(sel) {
  var el = sel.closest('.kis-cbar-box').querySelector('.kis-chart');
  if (!kisInit()) return;
  el.dataset.v = '';
  kisRenderVisible();
}
function kisRenderCbar(el, idx) {
  var cell = el.closest('.kis-cbar-box');
  var metric = cell.querySelector('.kis-cbar-metric').value, q = cell.querySelector('.kis-cbar-q').value;
  var spec = JSON.parse(el.dataset.cbar).filter(function(m){ return m.k === metric; })[0] || {};
  var qi = KIS.d.quarters.indexOf(q), S = KIS.d.series;
  var names = kisMemberNames();
  var pairs = names.map(function(c){ return [c, S[c] && S[c][metric] ? S[c][metric][qi] : null]; })
    .filter(function(p){ return p[1] !== null && p[1] !== undefined; });
  if (!pairs.length) { emptyChartMsg(el.id, q + '에는 ' + (spec.n || metric) + ' 데이터가 없어요. 다른 분기를 선택해보세요.'); return; }
  pairs.sort(function(a, b){ return b[1] - a[1]; });
  var unit = spec.u || '%';
  plotReact(el.id, [{
    x: pairs.map(function(p){ return p[0]; }), y: pairs.map(function(p){ return p[1]; }), type: 'bar',
    marker: {color: pairs.map(function(p){ return p[0] === KIS.company ? '#E8312F' : '#2980B9'; })},
    hovertemplate: '%{x}<br>' + (spec.n || metric) + ' %{y:' + (unit === '억원' ? ',.0f' : '.2f') + '}' + unit + '<extra></extra>'
  }], {
    height: 420, margin: {t: 20, b: 110, l: 60, r: 10}, xaxis: {tickangle: -45, tickfont: {size: 11}},
    yaxis: {title: (spec.n || metric) + ' (' + unit + ')', tickformat: unit === '억원' ? ',' : undefined}, showlegend: false
  }, {displaylogo: false, responsive: true});
}

// 회사별 최신 실적 표: 선택 기간의 마지막 분기 기준, 열 제목을 누르면 정렬
function kisCtableSort(th, ci) {
  var box = th.closest('.kis-ctable');
  var st = JSON.parse(box.dataset.sort || '{"c":-1,"d":-1}');
  st = (st.c === ci) ? {c: ci, d: -st.d} : {c: ci, d: ci === 0 ? 1 : -1};
  box.dataset.sort = JSON.stringify(st);
  if (!kisInit()) return;
  box.dataset.v = '';
  kisRenderVisible();
}
function kisRenderCtable(box, idx) {
  var cols = JSON.parse(box.dataset.ctable), S = KIS.d.series, qi = idx[idx.length - 1];
  var st = JSON.parse(box.dataset.sort || '{"c":-1,"d":-1}');
  var cellVal = function(c, col) {
    var s = S[c] && S[c][col.k];
    if (!s) return null;
    var cur = s[qi];
    if (cur === null || cur === undefined) return null;
    if (col.yoy) {
      var prev = qi >= 4 ? s[qi - 4] : null;
      return (prev === null || prev === undefined || prev === 0) ? null : (cur - prev) / Math.abs(prev) * 100;
    }
    return cur;
  };
  var fmt = function(v, u) {
    if (v === null || v === undefined) return '-';
    if (u === 'eok') return v.toLocaleString('ko-KR', {maximumFractionDigits: 0});
    if (u === 'x') return v.toFixed(1);
    return v.toLocaleString('ko-KR', {minimumFractionDigits: 1, maximumFractionDigits: 1}) + '%';
  };
  var names = kisMemberNames();
  var rows = names.map(function(c){ return {c: c, v: cols.map(function(col){ return cellVal(c, col); })}; });
  if (st.c >= 0) {
    rows.sort(function(a, b){
      var av = st.c === 0 ? a.c : a.v[st.c - 1], bv = st.c === 0 ? b.c : b.v[st.c - 1];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      return (av < bv ? -1 : av > bv ? 1 : 0) * st.d;
    });
  }
  var arrow = function(i){ return st.c === i ? (st.d === 1 ? ' ▲' : ' ▼') : ''; };
  var head = '<tr><th>No</th><th class="sortable" onclick="kisCtableSort(this,0)">금융회사명' + arrow(0) + '</th>' +
    cols.map(function(col, i){ return '<th class="sortable" onclick="kisCtableSort(this,' + (i + 1) + ')">' + col.n + arrow(i + 1) + '</th>'; }).join('') + '</tr>';
  var body = rows.map(function(r, i){
    return '<tr' + (r.c === KIS.company ? ' class="kis-bold"' : '') + '><td>' + (i + 1) + '</td><td>' + r.c + '</td>' +
      r.v.map(function(v, j){ return '<td>' + fmt(v, cols[j].u) + '</td>'; }).join('') + '</tr>';
  }).join('');
  var sumLabel = (KIS.d.members && KIS.d.members[KIS.company]) ? KIS.company : (KIS.d.baseGroup || KIS.d.allLabel);   // 합계 행: 선택한 그룹 또는 업권 전체
  var allv = cols.map(function(col){ return cellVal(sumLabel, col); });
  body += '<tr class="kis-bold"><td></td><td>' + sumLabel + '</td>' + allv.map(function(v, j){ return '<td>' + fmt(v, cols[j].u) + '</td>'; }).join('') + '</tr>';
  box.querySelector('thead').innerHTML = head;
  box.querySelector('tbody').innerHTML = body;
  var cap = box.parentElement.querySelector('.kis-ctable-q');
  if (cap) cap.textContent = KIS.d.quarters[qi];
}

// 전체 리스트 표: 열 제목을 누르면 정렬 (값은 각 셀의 data-v, 비어 있으면 항상 맨 아래)
function tblSort(th) {
  var table = th.closest('table'), tbody = table.tBodies[0];
  var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
  var isText = th.dataset.text === '1';
  var dir = th.dataset.dir ? -parseInt(th.dataset.dir, 10) : (isText ? 1 : -1);
  table.querySelectorAll('th').forEach(function(h){ h.dataset.dir = ''; var a = h.querySelector('.sort-arrow'); if (a) a.textContent = ''; });
  th.dataset.dir = String(dir);
  th.querySelector('.sort-arrow').textContent = dir === 1 ? ' ▲' : ' ▼';
  var rows = Array.prototype.slice.call(tbody.rows);
  var val = function(r){ var v = r.cells[idx].dataset.v; return v === undefined ? '' : v; };
  rows.sort(function(a, b){
    var av = val(a), bv = val(b);
    if (av === '' && bv === '') return 0;
    if (av === '') return 1;
    if (bv === '') return -1;
    var c = isText ? av.localeCompare(bv, 'ko') : (parseFloat(av) - parseFloat(bv));
    return c * dir;
  });
  rows.forEach(function(r, i){ tbody.appendChild(r); if (idx !== 0) r.cells[0].textContent = i + 1; });
}

/* ===================== 신용평가 탭: 한국기업평가 상호저축은행업 신용평가방법론(2025.03.24) 적용 ===================== */
var RATING = null;
// dir: hi = 클수록 좋음(>=), lo = 작을수록 좋음(<=). th = AA, A, BBB, BB 경계. star = 상대적으로 중요한 지표(◎)
var RATING_ITEMS = [
  {k: 'ind', g: '사업', n: '산업위험', w: 10, q: true},
  {k: 'share', g: '사업', n: '총자산시장점유율', w: 15, dir: 'hi', th: [8, 4, 2, 1], u: 'pct', star: true},
  {k: 'port', g: '사업', n: '대출포트폴리오 위험', w: 12.5, q: true},
  {k: 'mgmt', g: '사업', n: '경영 및 리스크 관리', w: 12.5, q: true},
  {k: 'roa', g: '재무', n: '총자산이익률(ROA)', w: 7.5, dir: 'hi', th: [3, 2, 1, 0], u: 'pct'},
  {k: 'nim', g: '재무', n: '순이자마진(NIM)', w: 5, dir: 'hi', th: [4, 3, 2, 1], u: 'pct'},
  {k: 'subr', g: '재무', n: '고정이하여신비율', w: 5, dir: 'lo', th: [2.5, 4.5, 6.5, 8.5], u: 'pct'},
  {k: 'cov', g: '재무', n: '대손충당금/고정이하여신', w: 7.5, dir: 'hi', th: [120, 100, 80, 60], u: 'pct'},
  {k: 'lev', g: '재무', n: '레버리지배율', w: 10, dir: 'lo', th: [5, 7.5, 10, 12.5], u: 'x', star: true},
  {k: 'bis', g: '재무', n: 'BIS기준 자기자본비율', w: 7.5, dir: 'hi', th: [16.5, 13.5, 10.5, 8], u: 'pct'},
  {k: 'liq', g: '재무', n: '유동성비율', w: 7.5, dir: 'hi', th: [150, 130, 115, 100], u: 'pct'}
];
var RATING_GRADES = ['AA', 'A', 'BBB', 'BB', 'B'];

function ratingGradeIdx(it, v) {
  if (v === null || v === undefined) return null;
  for (var i = 0; i < 4; i++) {
    if (it.dir === 'hi' ? v >= it.th[i] : v <= it.th[i]) return i;
  }
  return 4;
}
// Scoring 엑셀(Rating Numeric Matrix)의 평점 체계: 등급별 평균평점 / 부도율평점
//   평균평점: AAA 1, AA 3, A 6, BBB 9, BB 12, B 15, CCC 18 (사이 정수는 +/0/- 노치)
//   부도율평점(%): AAA 0.03, AA 0.11, A 0.30, BBB 1.63, BB 8.13, B 23.73, CCC 65
var GRADE_AVG = [3, 6, 9, 12, 15];                  // 인덱스: AA, A, BBB, BB, B
var GRADE_PD = [0.11, 0.30, 1.63, 8.13, 23.73];
var AVG_LABELS = ['', 'AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-', 'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'CCC+', 'CCC'];
var PD_GRADES = [['AAA', 0.03], ['AA', 0.11], ['A', 0.30], ['BBB', 1.63], ['BB', 8.13], ['B', 23.73], ['CCC', 65]];
// 합계 평균평점 -> 노치 등급 (엑셀과 같이 해당 정수 구간의 아래쪽 등급)
function ratingByAvg(avg) {
  var n = Math.max(1, Math.min(18, Math.floor(avg + 1e-9)));
  return AVG_LABELS[n];
}
// 합계 부도율평점 -> 등급 (평점이 속한 구간의 하단 등급)
function ratingByPd(pd) {
  var g = 'AAA';
  PD_GRADES.forEach(function(x){ if (pd + 1e-12 >= x[1]) g = x[0]; });
  return g;
}
function ratingBase(label) { return label.replace(/[+-]$/, ''); }
function ratingFmt(it, v) {
  if (v === null || v === undefined) return '-';
  return it.u === 'x' ? v.toFixed(1) + '배' : v.toFixed(1) + '%';
}
function ratingRender() {
  var tbl = document.getElementById('ratingResult');
  if (!tbl || tbl.offsetParent === null) return;
  if (!KIS) return;
  if (!RATING) {
    var el = document.getElementById('rating-data');
    if (!el) return;
    RATING = JSON.parse(el.textContent);
  }
  var company = KIS.company, isAll = company === RATING.allLabel;
  var vals = isAll ? RATING.all : RATING.companies[company];
  var q = {};
  document.querySelectorAll('.rating-q').forEach(function(s){ q[s.dataset.k] = parseInt(s.value, 10); });

  var rows = RATING_ITEMS.map(function(it){
    var v = it.q ? null : (vals ? vals[it.k] : null);
    var gi = it.q ? q[it.k] : ratingGradeIdx(it, v);
    return {it: it, v: v, gi: gi};
  });
  var usable = rows.filter(function(r){ return r.gi !== null && r.gi !== undefined; });
  var wsum = usable.reduce(function(t, r){ return t + r.it.w; }, 0);
  var avg = wsum ? usable.reduce(function(t, r){ return t + r.it.w / 100 * GRADE_AVG[r.gi]; }, 0) / (wsum / 100) : null;
  var pd = wsum ? usable.reduce(function(t, r){ return t + r.it.w / 100 * GRADE_PD[r.gi]; }, 0) / (wsum / 100) : null;
  var labAvg = avg === null ? null : ratingByAvg(avg), labPd = pd === null ? null : ratingByPd(pd);

  document.getElementById('ratingTitle').textContent =
    (isAll ? '저축은행 업권 전체(합산)' : company) + ' 신용평가방법론(2025.03.24) 적용 결과 (' + RATING.fy + ' 결산 기준)';

  var head = '<thead><tr><th colspan="2">구분</th><th>AAA</th>' + RATING_GRADES.map(function(g){ return '<th>' + g + '</th>'; }).join('') +
             '<th>지표값</th><th>가중치</th></tr></thead>';
  var body = '<tbody>';
  var gcount = {'사업': 4, '재무': 7}, gdone = {};
  rows.forEach(function(r){
    var it = r.it, tr = '<tr>';
    if (!gdone[it.g]) { gdone[it.g] = true; tr += '<td class="grp" rowspan="' + gcount[it.g] + '">' + (it.g === '사업' ? '사업' : '재무') + '</td>'; }
    tr += '<td class="item">' + it.n + '</td><td></td>';
    for (var i = 0; i < 5; i++) tr += '<td class="mark">' + (r.gi === i ? (it.star ? '◎' : '○') : '') + '</td>';
    tr += '<td class="num">' + (it.q ? '정성(선택)' : ratingFmt(it, r.v)) + '</td><td class="w">' + it.w.toFixed(1) + '%</td></tr>';
    body += tr;
  });
  [['모델등급 (평균평점 기준)', labAvg], ['모델등급 (부도율평점 기준)', labPd]].forEach(function(m){
    body += '<tr class="rating-model"><td colspan="2" class="item">' + m[0] + '</td><td class="mark">' + (m[1] === 'AAA' ? '○' : '') + '</td>';
    for (var j = 0; j < 5; j++) body += '<td class="mark">' + (m[1] && ratingBase(m[1]) === RATING_GRADES[j] ? '○' : '') + '</td>';
    body += '<td class="num">' + (m[1] || '-') + '</td><td class="w">100%</td></tr>';
  });
  body += '</tbody>';
  tbl.innerHTML = head + body;

  var st = document.getElementById('ratingScore');
  var sb = '<thead><tr><th>평가요소</th><th>지표값</th><th>등급</th><th>평균평점</th><th>부도율평점(%)</th><th>가중치</th><th>가중 평균평점</th><th>가중 부도율평점</th></tr></thead><tbody>';
  rows.forEach(function(r){
    var it = r.it, has = r.gi !== null && r.gi !== undefined;
    sb += '<tr><td class="item">' + it.n + '</td><td class="num">' + (it.q ? '정성(선택)' : ratingFmt(it, r.v)) + '</td><td>' +
          (has ? RATING_GRADES[r.gi] : '해당없음') + '</td><td>' + (has ? GRADE_AVG[r.gi] : '-') + '</td><td>' + (has ? GRADE_PD[r.gi] : '-') + '</td><td>' +
          it.w.toFixed(1) + '%</td><td>' + (has ? (it.w / 100 * GRADE_AVG[r.gi]).toFixed(3) : '-') + '</td><td>' +
          (has ? (it.w / 100 * GRADE_PD[r.gi]).toFixed(3) : '-') + '</td></tr>';
  });
  var note = wsum < 100 ? ' (해당없음 항목 제외, 가중치 ' + wsum.toFixed(1) + '% 기준으로 재환산)' : '';
  sb += '<tr class="rating-model"><td colspan="5" class="item">Total score' + note + '</td><td>' + wsum.toFixed(1) + '%</td><td>' +
        (avg === null ? '-' : avg.toFixed(3)) + '</td><td>' + (pd === null ? '-' : pd.toFixed(3)) + '</td></tr>' +
        '<tr class="rating-model"><td colspan="6" class="item">자기등급 (평균평점 기준 / 부도율평점 기준)</td><td>' + (labAvg || '-') + '</td><td>' + (labPd || '-') + '</td></tr></tbody>';
  st.innerHTML = sb;

  var refEl = document.getElementById('ratingRef');
  var ref = !isAll && RATING.refs[company];
  refEl.textContent = isAll
    ? '업권 전체를 고르면 합산 지표로 계산해요(총자산시장점유율은 해당 없어서 제외).'
    : ('참고: 신평사 실제 등급 - ' + (ref || '유효등급 없음'));
}
