import hashlib
import json
import unittest
from serve_local import round_response, CONFIG_HASH
from contract import validate

class LocalServiceTests(unittest.TestCase):
    def test_repeat_identity_reproduces_and_digest_validates(self):
        r=round_response(50,0)
        self.assertEqual(r,round_response(50,0))
        self.assertEqual(r['configSha256'],CONFIG_HASH)
        self.assertEqual(r['sha256'],hashlib.sha256(r['bookJson'].encode()).hexdigest())
        validate(json.loads(r['bookJson']))
    def test_complete_base_and_bonus_responses(self):
        bonus=False
        for i in range(100):
            r=round_response(50,i);b=json.loads(r['bookJson'])
            self.assertEqual(r['roundId'],i)
            self.assertEqual(b['events'][-1]['type'],'finalWin')
            if any(e['type']=='freeSpinTrigger' for e in b['events']):
                validate(b);bonus=True;break
        self.assertTrue(bonus)
