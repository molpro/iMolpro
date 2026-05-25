import os
import subprocess
import time

import pymolpro
import sys

if __name__ == '__main__':
    try:
        backend = sys.argv[1]
    except:
        backend = 'local'
    print('Test backend', backend)
    project = pymolpro.Project(geometry='He', ansatz='RHF/cc-pVDZ')
    project.run(backend=backend, wait=True)
    assert project.status == 'completed'
    print('simple synchronous run successful')

    project = pymolpro.Project(geometry='Ne;Ne,Ne,2', ansatz='DF-HF/aug-cc-pV5Z')  # takes a few seconds typically
    project.run(backend=backend, force=True, wait=False)
    assert project.status == 'running'
    while not os.path.exists(project.filename('out')): time.sleep(.1)
    project.wait()
    assert project.status == 'completed'
    print('asynchronous run successful')
    # print(project.out)

    project.run(backend=backend, force=True, wait=False)
    assert project.status == 'running'
    while not os.path.exists(project.filename('out')): time.sleep(.1)
    project.kill()
    time.sleep(.5)
    assert project.status == 'killed'
    print('killed run successfully')
