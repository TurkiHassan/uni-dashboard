import copy
import unittest
from blackboard_review import grade_value, parse_rows, merge_results, public_grades
from validate_data import validate

COURSE = {'id':'course1','name':'مقرر تجريبي','code':'TEST_1'}
ITEM = {'id':'one','courseId':'course1','course':'مقرر تجريبي','code':'TEST_1','item':'واجب','grade':'2 / 3'}

class ReviewTests(unittest.TestCase):
    def test_zero_is_a_real_grade(self):
        self.assertEqual(grade_value('٠ / ١٠')['grade'], '0 / 10')
        self.assertEqual(grade_value('٠ / ١٠')['pct'], 0)
        self.assertEqual(grade_value('Not graded')['grade'], '')
        self.assertEqual(grade_value('--')['grade'], '')
        self.assertIsNone(grade_value('4 / 0')['pct'])

    def test_decimal_and_letter_grades(self):
        self.assertEqual(grade_value('2,9/3 Final Grade: 2.9 points')['grade'], '2.9 / 3')
        self.assertEqual(grade_value('A+')['grade'], 'A+')

    def test_undated_items_and_headers(self):
        result = parse_rows(COURSE, {'headers':['Grade','Item Name','Status','Due Date'],
            'rows':[{'cells':['0 / 10','واجب','Graded','']}, {'cells':['Grade','Item Name','Status','Due Date']}]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['grade'], '0 / 10')
        self.assertEqual(result[0]['due'], '')

    def test_failed_course_keeps_old_grades_and_timestamp(self):
        old = {'items':[ITEM], 'courses':{}, 'lastSuccessAt':'2026-10-01T09:00:00+03:00'}
        result = merge_results(copy.deepcopy(old), [{'course':COURSE,'status':'ERROR'}], '2026-11-01T10:00:00+03:00')
        self.assertEqual(result['items'], old['items'])
        self.assertEqual(result['lastSuccessAt'], old['lastSuccessAt'])
        self.assertEqual(result['status'], 'ERROR')

    def test_partial_sync_only_replaces_successful_course(self):
        old2 = {**ITEM,'id':'two','courseId':'course2','code':'TEST_2'}
        new = {**ITEM,'grade':'0 / 3'}
        result = merge_results({'items':[ITEM,old2],'courses':{},'lastSuccessAt':'old'},
            [{'course':COURSE,'status':'OK','items':[new]},
             {'course':{'id':'course2','name':'آخر','code':'TEST_2'},'status':'LOGIN_REQUIRED'}], 'now')
        self.assertEqual(result['status'],'PARTIAL')
        self.assertIn(old2,result['items'])
        self.assertEqual(result['lastSuccessAt'],'old')
        self.assertEqual(result['changes'][0]['new'],'0 / 3')

    def test_grade_withdrawal_is_reported(self):
        result = merge_results({'items':[ITEM],'courses':{}},
            [{'course':COURSE,'status':'OK','items':[{**ITEM,'grade':''}]}],'now')
        self.assertEqual(result['changes'][0]['old'],'2 / 3')
        self.assertEqual(result['changes'][0]['new'],'')

    def test_placeholder_cleanup_does_not_create_grade_change(self):
        old={**ITEM,'item':'واجب No attempts submitted','grade':'--'}
        new={**ITEM,'item':'واجب','grade':''}
        result=merge_results({'items':[old],'courses':{}},[{'course':COURSE,'status':'OK','items':[new]}],'now')
        self.assertEqual(result['changes'],[])

    def test_public_payload_excludes_raw_data(self):
        result = public_grades({'items':[{**ITEM,'grade_raw':'hidden','password':'secret'}]})
        self.assertNotIn('password',result['items'][0])
        self.assertNotIn('grade_raw',result['items'][0])

    def test_invalid_grades_rejected_before_write(self):
        data={'courses':[{'code':'x','name':'y'}], 'tasks':[], 'announcements':[], 'events':[], 'studyPlan':[], 'updated':'now', 'grades':{'items':[{}]}}
        self.assertTrue(validate(data))

if __name__ == '__main__':
    unittest.main()
