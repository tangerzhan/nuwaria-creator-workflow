import unittest
from outreach import shipping_metrics

def row(shipping,contact='待寄样',archived=False):
    return {'archived':archived,'properties':{
        '是否已寄样':{'type':'select','select':{'name':shipping} if shipping else None},
        '联系状态':{'type':'select','select':{'name':contact}}}}

class ShippingStatsTests(unittest.TestCase):
    def test_manual_shipping_overrides_stale_contact_stage(self):
        pages=[row('运输中'),row('已送达'),row('已收件'),row('未寄样','待二次回复'),row(None)]
        result=shipping_metrics(pages)
        self.assertEqual(result['待寄样（按建联表未寄样）'],1)
        for state in ['运输中','已送达','已收件','未填写']:
            self.assertEqual(result['寄样情况：'+state],1)

    def test_archived_and_new_manual_options(self):
        result=shipping_metrics([row('运输中',archived=True),row('异常')])
        self.assertEqual(result['寄样情况：运输中'],0)
        self.assertEqual(result['寄样情况：异常'],1)

if __name__=='__main__':unittest.main()
