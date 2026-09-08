import zipfile,xml.etree.ElementTree as E,json,pathlib
p=pathlib.Path(r'C:/Users/24294/Documents/xwechat_files/wxid_2hro74c3dhj722_fcdc/temp/RWTemp/2026-09/3b8d96e2a918aa0119e057cf7490eee2/光学设计智能体(1).pptx')
n={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with zipfile.ZipFile(p) as z:
 print(z.read('ppt/presentation.xml').decode()[:700])
 for f in sorted([f for f in z.namelist() if __import__('re').match(r'ppt/slides/slide\d+\.xml$',f)],key=lambda f:int(__import__('re').search(r'(\d+)\.xml',f).group(1))):
  r=E.fromstring(z.read(f)); print(f, '\n'+'\n'.join(t.text or '' for t in r.findall('.//a:t',n)))
 if 'docProps/thumbnail.jpeg' in z.namelist(): pathlib.Path('reports/optical_transfer/.build/reference-thumb.jpg').write_bytes(z.read('docProps/thumbnail.jpeg'))
