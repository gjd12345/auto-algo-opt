import fs from 'node:fs/promises';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('C:/Users/24294/Documents/xwechat_files/wxid_2hro74c3dhj722_fcdc/temp/RWTemp/2026-09/3b8d96e2a918aa0119e057cf7490eee2/光学设计智能体(1).pptx'));
console.log((await p.inspect({kind:'slide',maxChars:2000})).ndjson);
for(const i of [0,1]){const b=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(`reports/optical_transfer/.build/ref-${i+1}.png`,new Uint8Array(await b.arrayBuffer()));}
