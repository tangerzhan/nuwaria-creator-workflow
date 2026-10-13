import unittest
from collections import Counter
from outreach import flat,status_names,Run,validate_status_tags
from mail_sync import typed

class MultiStatusTests(unittest.TestCase):
    def test_stage_conflicts(self):
        validate_status_tags({'已报价','已暂停'})
        validate_status_tags({'已报价','待二次回复'})
        with self.assertRaises(AssertionError):validate_status_tags({'已发信','已暂停'})
        with self.assertRaises(AssertionError):validate_status_tags({'待二次回复','已暂停'})
    def test_overlap_and_legacy_primary_reader(self):
        page={'properties':{'联系状态':{'type':'multi_select','multi_select':[{'id':'a','name':'已报价'},{'id':'b','name':'已暂停'}]}}}
        tags=flat(page)['联系状态']
        self.assertEqual(tags.get('name'),'已暂停')
        counts=Counter(status_names(tags))
        self.assertEqual(counts['已报价'],1)
        self.assertEqual(counts['已暂停'],1)
        Run.verify_properties(None,page,{'联系状态':{'multi_select':[{'name':'已暂停'},{'name':'已报价'}]}})

    def test_typed_and_legacy_formats(self):
        schema={'type':'multi_select','multi_select':{'options':[{'name':'已报价'},{'name':'待二次回复'}]}}
        payload=typed(schema,{'已报价','待二次回复'})
        self.assertEqual(status_names(payload['multi_select']),{'已报价','待二次回复'})
        self.assertEqual(status_names({'name':'已报价'}),{'已报价'})
        with self.assertRaises(AssertionError):typed(schema,{'made-up'})

if __name__=='__main__':unittest.main()
