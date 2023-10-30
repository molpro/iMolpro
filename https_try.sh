#!/bin/sh
conda create -n urllib_debug -y
conda activate urllib_debug
python << EOF
import os
import urllib.request as urllib2
for option in ['0','1']:
    print('trying option',option)
    os.environ['PYTHONHTTPSVERIFY']=option
    request = urllib2.Request('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/JSON?record_type=3d&name=water',
                              headers={'User-Agent': 'Mozilla/5.0'})
    with urllib2.urlopen(request) as f:
        print(f.read(300))
EOF
conda deactivate
conda env remove -n urllib_debug