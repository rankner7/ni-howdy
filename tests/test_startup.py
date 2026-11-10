import contextlib
import io
import unittest
from unittest.mock import patch
from nihowdy.server import main


class StartupTests(unittest.TestCase):
    def test_ctrl_c_during_preparation_exits_without_traceback(self):
        output=io.StringIO()
        with patch('sys.argv',['nihowdy']), patch('nihowdy.server.Store',side_effect=KeyboardInterrupt), contextlib.redirect_stdout(output):
            main()
        self.assertIn('Loading character data',output.getvalue())
        self.assertIn('Run ./run.sh to start again',output.getvalue())


if __name__=='__main__':
    unittest.main()
