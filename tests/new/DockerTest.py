from Test import Test
from os.path import isdir, join
from os import chown, walk
from traceback import format_exc

class DockerTest(Test) :

	def __init__(self, name, timeout, tests) :
		super().__init__(name, "docker", timeout, tests)

    def init() :
        try :
            super().init()
            for root, dirs, files in walk("/tmp/bw-data") :
                for name in dirs + files :
                    chown(join(root, name), 101, 101)
        except :
            self._log("exception while running DockerTest.init()\n" + format_exc(), error=True)
            return False
        return True

    def _setup_test(self) :
        try :
            super()._setup_test()
            # TODO :
        except :
            self._log("exception while running DockerTest._setup_test()\n" + format_exc(), error=True)
            return False
        return True
        

    def _cleanup_test(self) :
        pass