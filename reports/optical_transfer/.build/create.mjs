import fs from 'node:fs/promises';
import path from 'node:path';
import {Presentation,PresentationFile,FileBlob} from '@oai/artifact-tool';
import {finalizePresentation} from 'file:///C:/Users/24294/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations/container_tools/artifact_tool_utils.mjs';
const root='C:/Windows/System32/auto-algo-opt/reports/optical_transfer', build=root+'/.build';
const skill='C:/Users/24294/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={ink:'#14313F',text:'#294652',teal:'#00878D',pale:'#EEF7F8',line:'#D8E3E7',gray:'#617784',orange:'#AA6424',amber:'#FBF4EB'};
function box(s,x,y,w,h,fill='none',stroke='none'){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:stroke==='none'?0:1}})}
function txt(s,text,x,y,w,h,size=23,bold=false,color=C.text,align='left'){let a=box(s,x,y,w,h);a.text=text;a.text.style={typeface:'Microsoft YaHei',fontSize:size,bold,color,alignment:align,verticalAlignment:'middle',autoFit:'none',insets:{left:0,right:0,top:0,bottom:0}};return a;}
function line(s,x,y,w,color=C.line){box(s,x,y,w,1.3,color);}
function link(s,a,b,from='right',to='left',color=C.teal){return s.shapes.connect(a,b,{kind:from==='right'&&to==='left'?'straight':'elbow',fromSide:from,toSide:to,line:{fill:color,width:1.8},tail:{type:'triangle',width:'sm',length:'sm'}});}
function node(s,x,y,w,h,title,body,kind='reuse'){let b=box(s,x,y,w,h,kind==='new'?C.amber:C.pale,C.line);txt(s,title,x+12,y+12,w-24,33,24,true,kind==='new'?C.orange:C.ink,'center');txt(s,body,x+12,y+51,w-24,h-60,21,false,C.text,'center');return b;}
function title(s,t,n,sub){s.background.fill='#FFFFFF';txt(s,t,64,42,1152,68,42,true,C.ink);txt(s,sub,64,115,1152,37,23);txt(s,n,1180,685,36,20,12,false,C.gray,'right');}
let s=p.slides.add();
title(s,'大模型算法优化迁移到光学设计的原理','01','迁移核心：进化“如何优化”的策略，由团队程序计算光学性能并判定结果');
txt(s,'双层优化闭环',64,174,700,40,29,true,C.teal);
txt(s,'外层：大模型进化优化策略',64,227,700,34,25,true,C.ink);
txt(s,'检索文献与历史卡片，结合父代策略生成候选控制程序。\n搜索算法组合、变量开放顺序、阶段目标和计算预算。',64,270,710,68,23);
txt(s,'内层：数值算法求解光学参数',64,359,700,34,25,true,C.ink);
txt(s,'候选策略调用团队优化器与光学仿真，更新曲率、厚度等\n参数。按固定验收条件计算 MTF、波前 RMS 与约束偏差。',64,402,715,68,23);
line(s,64,490,710);
txt(s,'评价与记忆：有效候选参与选优，结果回流下一轮',64,503,716,33,24,true,C.ink);
txt(s,'比较同等预算下的达标率与性能，保存优胜策略和失败原因。\n先迁移受约束的搜索控制器，再扩展初始结构生成与建模。',64,544,714,65,22);
box(s,806,181,1.3,423,C.line);
txt(s,'相关研究进展',841,174,374,40,29,true,C.teal);
txt(s,'EoH · ICML 2024 [1]',841,229,370,31,23,true,C.ink);
txt(s,'联合进化算法思路与代码，\n以实际评测筛选启发式算法。',841,267,370,61,21);
txt(s,'DeepLens · 2024 [2]',841,350,370,31,23,true,C.ink);
txt(s,'可微光线追迹结合课程学习，\n实现从随机曲面起步的透镜设计。',841,388,370,61,21);
txt(s,'OPTIAGENT · 2026 预印本 [3]',841,471,375,31,23,true,C.ink);
txt(s,'用光学数据与物理奖励训练 LLM，\n并衔接专用优化流程精修设计。',841,509,375,61,21);
line(s,64,628,1152);
txt(s,'项目现状：已具备 RAG、共享种群与搜索控制器。策略卡实验获方向性支持（10 组中 7 胜）。',64,638,1152,28,20,true,C.ink);
txt(s,'跨问题迁移尚无确定结论，光学接口与效果仍待验证。研究来源 [1]–[3] 及代码依据见备注。',64,671,1100,25,18,false,C.gray);
s.speakerNotes.textFrame.setText(`原理说明：迁移的是算法进化闭环与搜索控制机制，不将离散组合优化函数原样用于连续光学参数优化。外层候选为可执行控制策略，内层由团队优化器调用已校准的光学仿真。可调整优化代理目标，但用户验收条件固定。材料中的光学实现是迁移方案，仓库当前未发现光学问题注册与仿真接口。\n代码依据：eoh_rag/experiments/eoh_single_runner.py:887 调用 build_official_rag_context；rag_context_builder.py:312 构造检索、重排与历史卡门禁；pool_api.py 共享策略池；hooks.py:45 与 batch_runner 的等价内联回流；evaluator.py:49 的单目标基线判定需扩展为光学硬约束加性能评价。eoh_rag/search_control/tsp_controller.py 的原语白名单、加权预算与停止条件提供控制器迁移切入点。\n项目证据：reports/strategy_experiments/q3_v2/q3_report.md，10 个 seed 三臂配对，answer 对 pure 7/0/3，按预设规则 directional_support。reports/strategy_experiments/cross_problem_transfer/cross_report.md，9/15 完整配对，结论 inconclusive。上述结果均非光学效果。\n[1] Liu et al., Evolution of Heuristics, ICML 2024. https://arxiv.org/abs/2401.02051\n[2] Yang et al., Curriculum learning for ab initio deep learned refractive optics, Nature Communications 15,6572 (2024). https://www.nature.com/articles/s41467-024-50835-7\n[3] Geng et al., OPTIAGENT: A Physics-Driven Agentic Framework for Automated Optical Design, arXiv preprint, 27 Feb 2026. https://arxiv.org/abs/2602.23761\n检索日期：2026-09-06。参考用户 PPT 第 2、4、6、9 页的团队程序路线、优化与验收区分、阶段性实现设定。`);
s=p.slides.add();
title(s,'基于 auto-algo-opt 的光学设计优化流程','02','浅蓝：复用现有框架机制　　浅橙：新增光学适配　　首期采用给定初始结构');
const input=node(s,64,172,810,75,'光学任务与初始结构','', 'new');
txt(s,'固定验收指标、参数边界与仿真预算，注册光学问题和工具接口',82,212,774,26,20,false,C.text,'center');
const out=node(s,962,172,254,75,'设计与策略归档','', 'reuse');
txt(s,'结构参数、指标、策略版本',974,212,230,25,18,false,C.text,'center');
const a=node(s,64,300,252,143,'1  检索与父代选择','光学知识与历史卡片\n共享池选择优胜策略');
const b=node(s,364,300,252,143,'2  生成候选策略','LLM 改写搜索控制器\n校验接口、动作与预算');
const c=node(s,664,300,252,143,'3  执行光学优化','团队优化器调用仿真\n更新参数并返回指标','new');
const d=node(s,964,300,252,143,'4  验收与选优','硬约束先行，逐项验收\n同预算比较质量与耗时','new');
link(s,input,a,'bottom','top');link(s,a,b);link(s,b,c);link(s,c,d);link(s,d,out,'top','bottom');
txt(s,'达标',1107,259,66,28,19,false,C.teal);
const m=node(s,364,510,552,100,'5  轨迹记录与经验回流','保存策略、结构、指标变化、预算消耗及失败原因');
link(s,d,m,'bottom','right');txt(s,'未达标且\n预算剩余',957,463,126,60,19,false,C.teal);
link(s,m,a,'left','bottom');txt(s,'选优入池，历史卡回流',65,487,268,30,20,true,C.teal);
txt(s,'停滞时调整算法、变量开放顺序或重启设置',374,625,590,30,21,true,C.ink);
line(s,64,668,1152);
txt(s,'首期落地：接入团队仿真与指标适配器，对照固定优化流程。预算耗尽则输出未达标项与最佳可行结果。',64,679,1122,27,18,false,C.gray);
s.speakerNotes.textFrame.setText(`流程为迁移设计，浅蓝表示复用机制，不表示全部光学语料与策略已实现。浅橙表示新增光学领域接口。首期使用给定初始结构与团队光学计算程序，不使用 Zemax。\n模块映射：任务输入扩展 problem_registry.py / eoh_runner/registry.py 与问题规格；检索扩展 rag_context_builder.py 的问题词表与 API 约束卡，复用 PoolAPI 父代/精英读取；策略生成复用官方 EoH 与 eoh_single_runner.py；控制校验参考 search_control/tsp_controller.py 的白名单和预算机制；新增光学运行器，把候选控制策略接到团队优化器、仿真和指标提取；光学验收器扩展 evaluator.py 的现有单标量判定，不将当前 archive 判定直接当作光学达标。RunTracker、共享池与卡片合成用于结果留痕和回流。\n数值内循环位于节点 3：优化器更新曲率、厚度、间距等参数，仿真返回目标与约束，再执行下一次数值迭代。外循环位于节点 1–5：根据实测表现选择/进化优化策略。最终验收固定波长、视场、采样条件与指标阈值，避免代理目标改善但真实性能不改善。仿真接口应先用已知设计校准。\n实验建议属于拟开展方案：在同一光学任务集、初始结构与仿真预算下，比较固定优化流程与大模型控制流程的达标率、性能和计算成本。不能以当前组合优化基准的改善率推断光学收益。后续再接入初始结构库与建模回退。参考用户 PPT 第 2、6、7、9 页，图形与内容按当前代码重新组织。`);
await (await PresentationFile.exportPptx(p)).save(build+'/candidate.pptx');
for(let i=0;i<2;i++){const b=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(build+`/slide-${i+1}.png`,new Uint8Array(await b.arrayBuffer()));}
const result=await finalizePresentation({workspaceDir:root,candidatePath:build+'/candidate.pptx',finalPath:root+'/output/光学设计智能体_算法优化迁移.pptx',pythonExecutable:'C:/Users/24294/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:skill+'/container_tools/inspect_presentation_package_integrity.py',layoutValidatorPath:skill+'/container_tools/inspect_presentation_layout_geometry.py',layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],explicitTotalSlideCount:2,fontPolicy:{basis:'design',families:['Microsoft YaHei']},verifyArtifactToolImport:true,receiptPath:build+'/validation-final.json'});
console.log(JSON.stringify(result));




