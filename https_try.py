import os
import urllib.request as urllib2
for option in ['0','1']:
    print('trying option',option)
    os.environ['PYTHONHTTPSVERIFY']=option
    request = urllib2.Request('https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/JSON?record_type=3d&name=water',
                              headers={'User-Agent': 'Mozilla/5.0'})
    with urllib2.urlopen(request) as f:
        print(f.read(300))