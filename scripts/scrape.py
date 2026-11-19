"""Read-only PIU leaderboard export. Credentials stay in memory."""
import argparse, getpass, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
if __name__ == "__main__":
    import truststore
    truststore.inject_into_ssl()

import requests
from bs4 import BeautifulSoup

BASE = 'https://piugame.com'
LIST = BASE + '/leaderboard/over_ranking.php'

def soup(html):
    return BeautifulSoup(html, 'html.parser')

def chart_meta(root):
    title = root.select_one('.songName_w .tt')
    ball = root.select_one('.stepBall_in')
    if not title or not ball:
        raise ValueError('Chart metadata missing; PIU layout may have changed')
    srcs = [i.get('src', '') for i in ball.select('img')]
    mode = next((re.search(r'/([sd])_text\.png', s).group(1).upper() for s in srcs if re.search(r'/([sd])_text\.png', s)), None)
    digits = ''.join(re.search(r'_num_(\d)\.png', s).group(1) for s in srcs if re.search(r'_num_(\d)\.png', s))
    return {'title': title.get_text(strip=True), 'mode': mode, 'level': int(digits) if digits else None}

def parse_chart(html, url):
    doc = soup(html)
    root = doc.select_one('.overRangking_view_wrap')
    if not root:
        raise ValueError('Leaderboard missing; session expired or PIU layout changed')
    chart = chart_meta(root)
    rows = root.select('.rangking_list_w > ul.list > li')
    scores = []
    for row in rows:
        score = row.select_one('.score .tt')
        if not score:
            raise ValueError('A leaderboard row has no score')
        value = int(score.get_text(strip=True).replace(',', ''))
        if not 0 <= value <= 1000000:
            raise ValueError('Unexpected score range')
        scores.append(value)
    # Only numeric scores are exported: no names, account details, or credentials.
    chart.update(id=urlparse(url).query, url=url, scores=sorted(scores, reverse=True),
                 pgCount=sum(s == 1000000 for s in scores), pgCapped=len(scores) >= 300 and all(s == 1000000 for s in scores))
    return chart

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='docs/data.json')
    p.add_argument('--limit', type=int, help='Smoke test: export only this many charts')
    p.add_argument('--delay', type=float, default=0.5)
    p.add_argument('--stdin-auth', action='store_true', help='Read one JSON auth object from stdin')
    args = p.parse_args()
    session = requests.Session()
    session.headers['User-Agent'] = 'PIUChartAtlas/1.0 (personal leaderboard statistics)'
    # Validate HTTPS before asking the user for credentials.
    session.get(BASE, timeout=30).raise_for_status()
    if args.stdin_auth:
        import sys
        auth = json.loads(sys.stdin.readline())
    else:
        cookie = os.environ.get('PIU_COOKIE')
        auth = {'cookie': cookie} if cookie else {'email': os.environ.get('PIU_EMAIL') or input('PIU email: '), 'password': os.environ.get('PIU_PASSWORD') or getpass.getpass('PIU password: ')}
    if auth.get('cookie'):
        for part in auth['cookie'].split(';'):
            name, sep, value = part.strip().partition('=')
            if sep:
                session.cookies.set(name, value, domain='piugame.com', path='/')
    else:
        r = session.post(BASE + '/bbs/login_check.php', data={'mb_id': auth['email'], 'mb_password': auth['password'], 'url': '/leaderboard/over_ranking.php'}, timeout=30)
        r.raise_for_status()
    auth.clear()
    def fetch(url):
        if urlparse(url).hostname != 'piugame.com':
            raise ValueError('Unexpected destination')
        for attempt in range(3):
            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()
                time.sleep(max(0.2, args.delay))
                return response.text
            except requests.RequestException:
                if attempt == 2:
                    raise RuntimeError('PIU request failed after three attempts') from None
                time.sleep(2 ** attempt)
    first = soup(fetch(LIST))
    links = first.select('a[href*="over_ranking_view.php?no="]')
    if not links:
        raise RuntimeError('PIU sign-in did not provide leaderboard access')
    pages = [int(n) for n in re.findall(r'page=(\d+)', str(first))]
    last_page = max(pages, default=1)
    charts, seen = [], set()
    for page in range(1, last_page + 1):
        doc = first if page == 1 else soup(fetch(LIST + '?page=' + str(page)))
        entries = doc.select('a[href*="over_ranking_view.php?no="]')
        if not entries:
            raise RuntimeError('A listing page is empty; refusing an incomplete export')
        for a in entries:
            meta = chart_meta(a)
            if meta['mode'] not in ('S', 'D') or meta['level'] is None or meta['level'] < 20:
                continue
            url = urljoin(LIST, a['href'])
            if url in seen:
                continue
            seen.add(url)
            chart = parse_chart(fetch(url), url)
            if any(chart[k] != meta[k] for k in ('title', 'level', 'mode')):
                raise RuntimeError('Chart listing/detail mismatch')
            charts.append(chart)
            print(f"Exported {len(charts)} charts (page {page}/{last_page})", flush=True)
            if args.limit and len(charts) >= args.limit:
                break
        if args.limit and len(charts) >= args.limit:
            break
    if not charts:
        raise RuntimeError('No eligible charts found')
    payload = {'updatedAt': datetime.now(timezone.utc).isoformat(), 'source': LIST, 'complete': not bool(args.limit), 'leaderboardLimit': 300, 'charts': charts}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(target)
    print(f'Saved {len(charts)} charts')

if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.SSLError:
        raise SystemExit('HTTPS certificate validation failed. Check your system certificates and update dependencies with: .venv/bin/pip install --upgrade -r requirements.txt') from None
