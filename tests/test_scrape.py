import sys, unittest
sys.path.insert(0, 'scripts')
from scrape import parse_chart
class ParserTests(unittest.TestCase):
    def test_chart_and_pg(self):
        html='<div class="overRangking_view_wrap"><div class="songName_w"><p class="tt">Test &amp; song</p></div><div class="stepBall_in"><img src="/d_text.png"><img src="/d_num_2.png"><img src="/d_num_0.png"></div><div class="rangking_list_w"><ul class="list"><li><div class="score"><i class="tt">1,000,000</i></div></li><li><div class="score"><i class="tt">950,000</i></div></li></ul></div></div>'
        c=parse_chart(html,'https://piugame.com/leaderboard/over_ranking_view.php?no=test')
        self.assertEqual((c['mode'],c['level'],c['pgCount']),('D',20,1))
        self.assertEqual(c['scores'],[1000000,950000]);self.assertFalse(c['pgCapped'])
    def test_expired_session_fails(self):
        with self.assertRaises(ValueError):parse_chart('<form>Login</form>','https://piugame.com')
if __name__=='__main__':unittest.main()
