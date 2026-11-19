"""Read-only PIU leaderboard export. Credentials stay in memory."""
import argparse, getpass, json, os, re, time, secrets, hmac, hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, local
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
if __name__ == "__main__":
    import truststore
    truststore.inject_into_ssl()

import requests
from bs4 import BeautifulSoup

BASE = 'https://piugame.com'
LIST = BASE + '/leaderboard/over_ranking.php'
RUN_KEY = secrets.token_bytes(32)

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
    observations = []
    for row in rows:
        score = row.select_one('.score .tt')
        if not score:
            raise ValueError('A leaderboard row has no score')
        value = int(score.get_text(strip=True).replace(',', ''))
        if not 0 <= value <= 1000000:
            raise ValueError('Unexpected score range')
        scores.append(value)
        # Display name + discriminator is a snapshot identity, not a permanent ID.
        names = row.select('.name_w .profile_name')
        if names:
            identity = '|'.join(n.get_text(strip=True) for n in names)
            key = hmac.new(RUN_KEY, identity.encode(), hashlib.sha256).hexdigest()
            observations.append((key, value))
    # Only numeric scores are exported: no names, account details, or credentials.
    chart.update(_observations=observations, id=urlparse(url).query, url=url, scores=sorted(scores, reverse=True),
                 pgCount=sum(s == 1000000 for s in scores), pgCapped=len(scores) >= 300 and all(s == 1000000 for s in scores))
    return chart

class Fetcher:
    """Worker-local sessions with one shared request-start rate limit."""
    def __init__(self, authenticated, delay):
        self.headers = dict(authenticated.headers)
        self.cookies = authenticated.cookies.copy()
        self.delay = max(0.2, delay)
        self.local = local()
        self.lock = Lock()
        self.next_start = 0.0
        self.sessions = []

    def session(self):
        if not hasattr(self.local, 'session'):
            session = requests.Session()
            session.headers.update(self.headers)
            session.cookies.update(self.cookies.copy())
            self.local.session = session
            with self.lock:
                self.sessions.append(session)
        return self.local.session

    def wait(self):
        while True:
            with self.lock:
                delay = self.next_start - time.monotonic()
                if delay <= 0:
                    self.next_start = time.monotonic() + self.delay
                    return
            time.sleep(delay)

    def cooldown(self, seconds):
        with self.lock:
            self.next_start = max(self.next_start, time.monotonic() + seconds)

    def close(self):
        for session in self.sessions:
            session.close()

    def __call__(self, url):
        if urlparse(url).hostname != 'piugame.com' or urlparse(url).scheme != 'https':
            raise ValueError('Unexpected destination')
        for attempt in range(3):
            self.wait()
            try:
                with self.session().get(url, timeout=30) as response:
                    if response.status_code in (429, 503):
                        retry = response.headers.get('Retry-After', '')
                        try:
                            seconds = float(retry)
                        except ValueError:
                            try:
                                seconds = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                            except (ValueError, TypeError, OverflowError):
                                seconds = 2 ** (attempt + 1)
                        self.cooldown(max(1, seconds))
                    response.raise_for_status()
                    return response.text
            except requests.exceptions.SSLError:
                raise
            except requests.RequestException as error:
                status = getattr(getattr(error, 'response', None), 'status_code', None)
                if status and 400 <= status < 500 and status != 429:
                    raise RuntimeError(f'PIU returned HTTP {status}; export stopped') from None
                if attempt == 2:
                    raise RuntimeError('PIU request failed after three attempts; previous snapshot retained') from None
                self.cooldown(2 ** attempt)


def fetch_chart(item, fetch):
    url, meta = item
    chart = parse_chart(fetch(url), url)
    if any(chart[k] != meta[k] for k in ('title', 'level', 'mode')):
        raise RuntimeError('Chart listing/detail mismatch')
    return chart

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='docs/data.json')
    p.add_argument('--limit', type=int, help='Smoke test: export only this many charts')
    p.add_argument('--delay', type=float, default=0.25, help='Minimum seconds between request starts across ALL workers (minimum 0.2)')
    p.add_argument('--workers', type=int, default=4, choices=range(1,9), help='Concurrent chart requests (1–8, default 4)')
    p.add_argument('--stdin-auth', action='store_true', help='Read one JSON auth object from stdin')
    args = p.parse_args()
    if args.limit is not None and args.limit < 1:
        p.error('--limit must be positive')
    if not 0 <= args.delay < float('inf'):
        p.error('--delay must be finite and nonnegative')
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
    fetch = Fetcher(session, args.delay)
    first = soup(fetch(LIST))
    links = first.select('a[href*="over_ranking_view.php?no="]')
    if not links:
        raise RuntimeError('PIU sign-in did not provide leaderboard access')
    pages = [int(n) for n in re.findall(r'page=(\d+)', str(first))]
    last_page = max(pages, default=1)
    charts, seen = [], set()
    print(f'Scraping with {args.workers} workers; global spacing {fetch.delay}s', flush=True)
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for page in range(1, last_page + 1):
                doc = first if page == 1 else soup(fetch(LIST + '?page=' + str(page)))
                entries = doc.select('a[href*="over_ranking_view.php?no="]')
                if not entries:
                    raise RuntimeError('A listing page is empty; refusing an incomplete export')
                batch = []
                for a in entries:
                    meta = chart_meta(a)
                    if meta['mode'] not in ('S', 'D') or meta['level'] is None or meta['level'] < 20:
                        continue
                    url = urljoin(LIST, a['href'])
                    if url in seen:
                        continue
                    seen.add(url)
                    batch.append((url, meta))
                    if args.limit and len(charts) + len(batch) >= args.limit:
                        break
                # One page at a time bounds queued work; map preserves source order.
                for chart in pool.map(lambda item: fetch_chart(item, fetch), batch):
                    charts.append(chart)
                    print(f"Exported {len(charts)} charts (page {page}/{last_page})", flush=True)
                if args.limit and len(charts) >= args.limit:
                    break
    finally:
        fetch.close()
        session.close()
    if not charts:
        raise RuntimeError('No eligible charts found')
    from model import annotate
    model = annotate(charts)
    print(f"Model fitted for {model['fittedCharts']} charts with sufficient shared-player coverage", flush=True)
    payload = {'model': model, 'updatedAt': datetime.now(timezone.utc).isoformat(), 'source': LIST, 'complete': not bool(args.limit), 'leaderboardLimit': 300, 'charts': charts}
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
