import sys, time, unittest, threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import requests
sys.path.insert(0,'scripts')
from scrape import Fetcher

class ParallelTests(unittest.TestCase):
    def test_worker_sessions_are_isolated_and_requests_overlap(self):
        auth=requests.Session();auth.cookies.set('test','example')
        fetch=Fetcher(auth,0.2)
        barrier=threading.Barrier(2)
        def worker(_):
            session=fetch.session()
            barrier.wait(timeout=3)
            return session
        with ThreadPoolExecutor(max_workers=2) as pool:
            sessions=list(pool.map(worker,range(2)))
        self.assertIsNot(sessions[0],sessions[1])
        sessions[0].cookies.set('test','changed')
        self.assertEqual(sessions[1].cookies.get('test'),'example')
        self.assertEqual(auth.cookies.get('test'),'example')
        fetch.close();auth.close()

    def test_global_rate_limit_and_shared_cooldown(self):
        auth=requests.Session();fetch=Fetcher(auth,0.2)
        starts=[];lock=threading.Lock()
        def worker(_):
            fetch.wait()
            with lock:starts.append(time.monotonic())
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(worker,range(3)))
        self.assertTrue(all(b-a>=0.19 for a,b in zip(sorted(starts),sorted(starts)[1:])))
        fetch.cooldown(0.3);start=time.monotonic();fetch.wait()
        self.assertGreaterEqual(time.monotonic()-start,0.29)
        auth.close()

    def test_429_retry_after_and_permanent_errors(self):
        auth=requests.Session();fetch=Fetcher(auth,0.2)
        def response(status,headers=None):
            r=requests.Response();r.status_code=status;r.headers.update(headers or {});r._content=b'ok';r._content_consumed=True;return r
        with patch.object(fetch,'wait'),patch.object(fetch,'cooldown') as pause,patch.object(fetch,'session') as session:
            session.return_value.get.side_effect=[response(429,{'Retry-After':'7'}),response(200)]
            self.assertEqual(fetch('https://piugame.com/test'),'ok')
            pause.assert_any_call(7.0)
            session.return_value.get.side_effect=[response(403)]
            with self.assertRaisesRegex(RuntimeError,'403'):fetch('https://piugame.com/test')
        auth.close()

if __name__=='__main__':unittest.main()
