#!/usr/bin/env python3
"""抓取公開資料並輸出 docs/data/latest.json。
原則：任何來源失敗就標記 error 並保留舊資料，絕不補假數據。
只用標準函式庫。"""
import json, csv, io, os, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data'); os.makedirs(DATA, exist_ok=True)
HIST = os.path.join(DATA, 'history.json')
TW = dt.timezone(dt.timedelta(hours=8))
UA = {'User-Agent': 'Mozilla/5.0 (00631L-dashboard)'}

def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode('utf-8-sig')
def jget(url): return json.loads(get(url))
def num(x): return float(str(x).replace(',', '').strip())
def norm_date(s):
    s = str(s).replace('/', '').replace('-', '').strip()
    if len(s) == 8: return f'{s[:4]}-{s[4:6]}-{s[6:]}'
    if len(s) == 7: return f'{int(s[:3]) + 1911}-{s[3:5]}-{s[5:]}'   # 民國年
    raise ValueError(f'無法解析日期 {s}')
def pick(row, *needles):
    for k in row:
        if all(n.lower() in k.lower() for n in needles): return row[k]
    return None
def find_path(swagger_url, must, mustnot=()):
    sw = jget(swagger_url)
    for p in sw['paths']:
        if all(m.lower() in p.lower() for m in must) and not any(m.lower() in p.lower() for m in mustnot):
            base = (sw.get('servers') or [{}])[0].get('url', '')
            return swagger_url.rsplit('/swagger.json', 1)[0] + p if not base.startswith('http') else base + p
    raise RuntimeError('swagger 內找不到對應路徑：' + '/'.join(must))

hist = {'otc': {}, 'fut': {}, 'vix': {}, 'twmargin': {}}
if os.path.exists(HIST): hist.update(json.load(open(HIST, encoding='utf-8')))
sources = {}

def run(name, fn):
    try:
        asof = fn(); sources[name] = {'ok': True, 'asof': asof}
    except Exception as e:
        sources[name] = {'ok': False, 'error': f'{type(e).__name__}: {e}'[:300]}

def f_otc():   # 櫃買指數歷史（TPEx OpenAPI，路徑由 swagger 自動尋找）
    url = find_path('https://www.tpex.org.tw/openapi/swagger.json', ['index'], ['mmi', 'margin'])
    rows = jget(url)
    n = 0
    for r in rows:
        d, c = pick(r, 'date') or pick(r, '日期'), pick(r, 'close') or pick(r, '收盤')
        if d and c:
            try: hist['otc'][norm_date(d)] = num(c); n += 1
            except ValueError: pass
    if not n: raise RuntimeError('解析不到日期／收盤欄位，欄位：' + ','.join(rows[0].keys()))
    seed = os.path.join(DATA, 'seed_otc.csv')      # 選用：自行補 60 日歷史（date,close）
    if os.path.exists(seed):
        for r in csv.DictReader(open(seed, encoding='utf-8-sig')): hist['otc'].setdefault(norm_date(r['date']), num(r['close']))
    return max(hist['otc'])

def f_fut():   # 外資「臺股期貨」未平倉多空淨額；net = -多空淨額（正數＝淨空單口數）
    url = find_path('https://openapi.taifex.com.tw/swagger.json', ['MajorInstitutionalTraders', 'FuturesContractsBytheDate'], ['Option'])
    rows = jget(url); last = None
    for r in rows:
        who = ' '.join(str(v) for v in r.values())
        if '外資' not in who and 'Foreign' not in who: continue
        name = pick(r, 'contract') or pick(r, '商品') or ''
        if name not in ('臺股期貨', '台股期貨', 'TX'): continue
        net = pick(r, 'openinterest', 'net') or pick(r, '未平倉', '淨')
        d = pick(r, 'date') or pick(r, '日期')
        if net is None or d is None: continue
        last = norm_date(d); hist['fut'][last] = -num(net)
    if not last: raise RuntimeError('找不到外資臺股期貨列；欄位：' + ','.join(rows[0].keys()))
    return last

def f_vix():
    rows = list(csv.DictReader(io.StringIO(get('https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv'))))
    for r in rows[-40:]:
        m, d, y = r['DATE'].split('/'); hist['vix'][f'{y}-{int(m):02d}-{int(d):02d}'] = num(r['CLOSE'])
    return max(hist['vix'])

def f_twmargin():   # 證交所信用交易統計：融資金額（仟元）今日餘額
    for back in range(6):
        d = dt.datetime.now(TW) - dt.timedelta(days=back)
        j = jget(f'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={d:%Y%m%d}&selectType=MS&response=json')
        for t in j.get('tables', []):
            for row in t.get('data', []):
                if str(row[0]).startswith('融資金額'):
                    hist['twmargin'][f'{d:%Y-%m-%d}'] = num(row[-1]); return f'{d:%Y-%m-%d}'
    raise RuntimeError('近 6 天查無融資金額列')

for n, f in [('otc', f_otc), ('fut', f_fut), ('vix', f_vix), ('twmargin', f_twmargin)]: run(n, f)

json.dump(hist, open(HIST, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
ds = sorted(hist['otc']); cl = [hist['otc'][d] for d in ds]; otc = []
for i, d in enumerate(ds):
    otc.append({'date': d, 'close': cl[i], 'ma': round(sum(cl[i-59:i+1]) / 60, 2) if i >= 59 else None})
tail = lambda k, f, n=120: [{'date': d, f: hist[k][d]} for d in sorted(hist[k])[-n:]]
out = {'generated_at': dt.datetime.now(TW).strftime('%Y-%m-%d %H:%M'), 'sources': sources,
       'series': {'otc': otc[-120:], 'fut': tail('fut', 'net'), 'vix': tail('vix', 'close'), 'twmargin': tail('twmargin', 'val')}}
json.dump(out, open(os.path.join(DATA, 'latest.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print(json.dumps(sources, ensure_ascii=False, indent=1))
