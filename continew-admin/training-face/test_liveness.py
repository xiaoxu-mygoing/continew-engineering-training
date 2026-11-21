import unittest
from liveness import completed
class ActionTests(unittest.TestCase):
    neutral=(0.04,2,1)
    actions={'mouth':(0.45,2,1),'down':(0.04,15,1),'turn':(0.04,2,18)}
    def test_complete_and_static(self):
        for action,value in self.actions.items():
            self.assertTrue(completed([self.neutral]*18+[value]*3+[self.neutral]*4,action))
            self.assertFalse(completed([value]*16,action))
            self.assertFalse(completed([self.neutral]*16,action))
    def test_wrong_action_and_missing_return(self):
        for action,value in self.actions.items():
            self.assertFalse(completed([self.neutral]*4+[value]*12,action))
            self.assertFalse(completed([self.neutral]*4+[value]+[self.neutral]*11,action))
            for other in self.actions:
                if other!=action:self.assertFalse(completed([self.neutral]*4+[value]*4+[self.neutral]*8,other))
    def test_direction(self):
        self.assertTrue(completed([self.neutral]*4+[(0.04,2,-18)]*4+[self.neutral]*8,'turn'))
        self.assertFalse(completed([self.neutral]*4+[(0.04,-15,1)]*4+[self.neutral]*8,'down'))
if __name__=='__main__':unittest.main()
