import sys, unittest, math
sys.path.insert(0,'scripts')
from model import fit_effects, annotate
class ModelTests(unittest.TestCase):
    def test_shared_player_adjustment(self):
        # Hard chart has stronger participants and a higher raw mean score.
        rows=[]
        for i in range(80):
            skill=-2 if i<40 else 2
            for chart,effect in [('easy',-0.5),('bridge',0),('hard',0.5)]:
                if chart=='easy' and i<30: continue
                if chart=='hard' and i>=50: continue
                rows.append((str(i),chart,1000000-round(math.expm1(8+skill+effect))))
        raw={c:sum(s for _,j,s in rows if j==c)/sum(j==c for _,j,_ in rows) for c in ('easy','hard')}
        self.assertGreater(raw['hard'],raw['easy'])
        effects,ok=fit_effects(rows,5)
        self.assertTrue(ok);self.assertLess(effects['easy'],effects['hard'])
    def test_missing_pairs_never_fabricate_estimates(self):
        charts=[{'id':'x','mode':'S','level':20,'scores':[1000000]}]
        self.assertEqual(annotate(charts)['fittedCharts'],0)
        self.assertIsNone(charts[0]['adjusted'])
    def test_private_records_removed(self):
        charts=[{'id':'x','mode':'S','level':20,'_observations':[('secret',1000000)]}]
        annotate(charts);self.assertNotIn('_observations',charts[0])
if __name__=='__main__':unittest.main()
