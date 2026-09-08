import fs from 'node:fs/promises';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('C:/Windows/System32/auto-algo-opt/reports/optical_transfer/output/光学设计智能体_算法优化迁移.pptx'));
for(let i=0;i<2;i++){const b=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(`reports/optical_transfer/.build/final-${i+1}.png`,new Uint8Array(await b.arrayBuffer()));}

