#!/usr/bin/python

import random
import sys
import time
import tempfile
import subprocess
import psutil
import shutil

class Sim(object):
  def __init__(self, _name, _trace):
    self.name = _name
    self.trace = _trace
  def argv(self, trc):
    return ''
  def parse_clk(self, stdout):
    return 0

class Ramulator(Sim):
  def __init__(self):
    super(Ramulator, self).__init__('Ramulator', 'ramulator')
  def argv(self, trc):
    return ['./ramulator', 'configs/DDR3-PolarFire-config.cfg', '--mode=dram', trc]
  def parse_clk(self, stdout):
    stdout = open("DDR3.stats")
    stdout.seek(0)
    for l in stdout.readlines():
      if 'ramulator.dram_cycles' in l:
        return int(l.split()[1])

def gen_random(cb, n, rw, s, bits):
  l = s/64
  b = n/l
  for i in range(b):
    base = random.getrandbits(bits) & 0xffffffffffc0
    r = bool(random.random() < rw)
    for j in range(l):
      cb(base+j*64, r, l*i+j)

def gen_stream(cb, n, rw):
  r = int(n * rw)
  w = n - r
  for i in range(r):
    cb(i*64, True, i)
  for i in range(w):
    cb((r+i)*64, False, r+i)

def gen_stream_chop(cb, n, rw):
  l = 1920*3
  r = int(n * rw)
  w = n - r
  a = 0 # address
  isread = False
  while(w>0 or r>0):
    isread = not isread
    for i in range(l):
      cb(a, isread, a)
      a += 64
      if isread:
        r -= 1
        if r<=0:
          break
      else:
        w -= 1
        if w<=0:
          break

def main(n_reqs, rw, rec):
  trace_names = ['ramulator']
  def make_cb(files):
    def real_cb(addr, rw, i):
      files['ramulator'].write('0x%x %s\n' % (addr, 'R' if rw else 'W'))
    return real_cb

  s = 64
  traces = []
  
  tmps = {name: tempfile.NamedTemporaryFile(prefix='random-') for name in trace_names}
  gen_random(make_cb(tmps), n_reqs, rw, s, 31)
  for f in tmps.itervalues():
    f.file.seek(0)
  traces.append(tmps)
  print 'Random trace created'

  tmps = {name: tempfile.NamedTemporaryFile(prefix='stream-') for name in trace_names}
  gen_stream(make_cb(tmps), n_reqs, rw)
  for f in tmps.itervalues():
    f.file.seek(0)
  traces.append(tmps)
  print 'Stream trace created'

  tmps = {name: tempfile.NamedTemporaryFile(prefix='streamchop-') for name in trace_names}
  gen_stream_chop(make_cb(tmps), n_reqs, rw)
  for f in tmps.itervalues():
    f.file.seek(0)
  traces.append(tmps)
  print 'Stream chopped trace created'

  if rec:
      for name, tmpf in traces[0].iteritems():
        shutil.copy(tmpf.name, './%s-random.trace' % name)
      for name, tmpf in traces[1].iteritems():
        shutil.copy(tmpf.name, './%s-stream.trace' % name)
      for name, tmpf in traces[2].iteritems():
        shutil.copy(tmpf.name, './%s-streamchop.trace' % name)

  sims = [Ramulator()]
  cnt = len(traces) * len(sims)

  blackhole = open('/dev/null', 'w')
  results = []
  for v in traces:
    res_dict = {}
    for sim in sims:
      tmp = tempfile.NamedTemporaryFile()
      p = subprocess.Popen(sim.argv(v[sim.trace].name), stdout=tmp.file, stderr=blackhole)
      print 'Starting %s %d' % (sim.name, p.pid)
      proc = psutil.Process(p.pid)
      t, mem = 0, 0
      while p.poll() is None:
        try:
          mem = max(mem, proc.memory_info()[0]) # RSS on mac
          t = sum(proc.cpu_times())
        except: print "======== Oops monitoring %s %d failed ===============" % (sim.name, p.pid)
        time.sleep(0.1)
      print '%s(%d) finished.' % (sim.name, p.pid)
      clk = sim.parse_clk(tmp.file)
      res_dict[sim.name] = {'Trace': v[sim.trace].name, 'SimulatedDRAMCycles': clk, 'Runtime (s)': "{:.2f}".format(t), 'MemoryUsage (MB)': "{:.2f}".format(float(mem)/2**20)}
      tmp.file.close()
    results.append(res_dict)
  blackhole.close()

  print "\n=== Simulation Results ==="
  for r in results:
    print r


if __name__ == '__main__':
  if len(sys.argv) < 3: print 'test_ddr3.py <n-requests> <read proportion> [record]'
  else: main(int(sys.argv[1]), float(sys.argv[2]), (len(sys.argv) > 3 and sys.argv[3] == 'record'))


