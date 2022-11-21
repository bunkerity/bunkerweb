from subprocess import TimeoutExpired
from ftw import logchecker, testrunner, http
from ftw.ruleset import Input
import pytest
import os

CRS_HEADER = 'X-CRS-Test'

def test_crs(test, logchecker_obj):
    runner = testrunner.TestRunner()
    for stage in test.stages:
        runner.run_stage(stage, logchecker_obj)


class FooLogChecker(logchecker.LogChecker):
    def __init__(self, config):
        super(FooLogChecker, self).__init__()
        self.log_location = self.find_log_location(config)
        self.backwards_reader = BackwardsReader(self.log_location)
        self.start_marker = None
        self.end_marker = None

    def mark_start(self, stage_id):
        self.start_marker = self.find_marker(stage_id)

    def mark_end(self, stage_id):
        self.end_marker = self.find_marker(stage_id)

    def find_marker(self, stage_id):
        stage_id_bytes = stage_id.encode('utf-8')
        header_bytes = CRS_HEADER.encode('utf-8')
        def try_once():
            self.mark_and_flush_log(stage_id)
            self.backwards_reader.reset()
            return self.backwards_reader.readline() or b''
            
        line = try_once()
        while not (header_bytes in line and stage_id_bytes in line):
            line = try_once()
        return line

    def get_logs(self):
        logs = []
        # At this point we're already at the end marker
        for line in self.backwards_reader.readlines():
            if line == self.start_marker:
                break

            logs.append(line.decode('utf-8'))
        return logs

    def mark_and_flush_log(self, header_value):
        """
        Send a valid request to the server with a special header that will
        generate an entry in the log. We can use this to flush the log and to
        mark the output so we know where our test output is.
        """
        http.HttpUA().send_request(Input(
            headers={
                'Host': 'localhost',
                'User-Agent': 'CRS',
                'Accept': '*/*',
                CRS_HEADER: header_value
            },
            version='HTTP/1.0'))

    @staticmethod
    def find_log_location(config):
        key = 'log_location_linux' 
        # First, try to find the log configuration from config.ini
        if key in config:
            return config[key]
        else:
            # Now we could check for the configuration that was passed
            # on the command line. Unfortunately, we use a default, so we
            # don't know whether it was *actually* on the command line.
            # Let's try to find the Docker container instead.
            import os.path
            import subprocess
            prefix = os.path.join('tests', 'logs')
            log_file_name = 'error.log'
            directory_name = 'modsec2-apache'
            process = subprocess.Popen(
                'docker ps --format "{{.Names}}"',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            try:
                out, _ = process.communicate(timeout=10)
            except TimeoutExpired:
                out = ''
            if b'modsec3-nginx' in out:
                directory_name = 'modsec3-nginx'
            return os.path.join(prefix, directory_name, log_file_name)



@pytest.fixture(scope='session')
def logchecker_obj(config):
    return FooLogChecker(config)

# Adapted from http://code.activestate.com/recipes/120686-read-a-text-file-backwards/
class BackwardsReader:
  def __init__(self, file, blksize=4096):
    """initialize the internal structures"""
    self.file = file
    # how big of a block to read from the file...
    self.blksize = blksize
    self.f = open(file, 'rb')

    self.reset()

  def readline(self):
    while len(self.data) == 1 and ((self.blkcount * self.blksize) < self.size):
      self.blkcount = self.blkcount + 1
      line = self.data[0]
      try:
        self.f.seek(-self.blksize * self.blkcount, os.SEEK_END) # read from end of file
        self.data = (self.f.read(self.blksize) + line).split(b'\n')
      except IOError:  # can't seek before the beginning of the file
        self.f.seek(0)
        self.data = (self.f.read(self.size - (self.blksize * (self.blkcount-1))) + line).split(b'\n')

    if len(self.data) == 0:
      return ""

    line = self.data.pop()
    return line + b'\n'

  def readlines(self):
      line = self.readline()
      while line:
          yield line
          line = self.readline()
        
  def reset(self):
    # get the file size
    self.size = os.stat(self.file)[6]
    # how many blocks we've read
    self.blkcount = 1
    # if the file is smaller than the blocksize, read a block,
    # otherwise, read the whole thing...
    if self.size > self.blksize:
      self.f.seek(-self.blksize * self.blkcount, 2) # read from end of file
    self.data = self.f.read(self.blksize).split(b'\n')
    # strip the last item if it's empty...  a byproduct of the last line having
    # a newline at the end of it
    if not self.data[-1]:
      self.data.pop()
