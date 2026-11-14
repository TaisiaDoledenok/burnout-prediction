// Offline regression: run with node tests/test_teacher_dossier_race.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../dashboard.py'), 'utf8');
const update = source.slice(source.indexOf('let teacherDossierRequest=0;'), source.indexOf('function drawTeacherLoadChart('));
const load = source.slice(source.indexOf('async function loadTeacherDossier()'), source.indexOf("document.getElementById('overview-tab').addEventListener"));
const elements = {};
function element(id) {
  return elements[id] ||= {value:'', hidden:false, textContent:'', classList:{add(){}, remove(){}},
    replaceChildren(...children){this.options=children; this.selectedIndex=0; this.value=children[0]?.value || '';},
    appendChild(child){this.options.push(child);}, options:[{textContent:'School'}], selectedIndex:0};
}
function Option(text='', value='') { this.textContent=text; this.value=value; }
const requests = [];
const context = {document:{getElementById:element}, Option, Intl, encodeURIComponent,
  fmt:new Intl.NumberFormat('ru-RU'), teacherValueFmt:new Intl.NumberFormat('ru-RU'), teacherWord:()=>'',
  teacherDirectoryData:{teachers:[{user_id:1,name:'One',school_id:1},{user_id:2,name:'Two',school_id:2}]},
  renderTeacherSurveys(){}, drawTeacherBurnoutChart(){}, drawTeacherLoadChart(){}, formatReportDate:x=>x,
  fetch(url){return new Promise((resolve,reject)=>requests.push({url, resolve, reject}));}};
vm.createContext(context);
vm.runInContext(update + '\n' + load, context);
const reply = (request, name) => request.resolve({ok:true,json:async()=>({name})});
async function main() {
  const teacher=element('teacher-select'), school=element('school-select'), dossier=element('teacher-dossier'), status=element('teacher-status');
  school.value='1'; teacher.value='1';
  let first=context.loadTeacherDossier(); reply(requests.shift(),'One'); await first;
  assert.equal(element('teacher-name').textContent,'One'); assert.equal(dossier.hidden,false);
  teacher.value='2'; let second=context.loadTeacherDossier();
  assert.equal(dossier.hidden,true,'previous dossier must be hidden immediately while loading');
  teacher.value='1'; let third=context.loadTeacherDossier();
  const secondRequest=requests.shift(), thirdRequest=requests.shift();
  reply(thirdRequest,'One latest'); await third;
  reply(secondRequest,'Two stale'); await second;
  assert.equal(element('teacher-name').textContent,'One latest','older response must not overwrite selection');
  teacher.value='2'; let fourth=context.loadTeacherDossier(); const fourthRequest=requests.shift();
  school.value='1'; context.updateTeacherOptions();
  const schoolStatus=status.textContent;
  reply(fourthRequest,'Two stale'); await fourth;
  assert.equal(dossier.hidden,true,'school change invalidates pending response');
  assert.equal(status.textContent,schoolStatus,'school guidance must survive stale response');
  teacher.value='1'; let fifth=context.loadTeacherDossier(); const fifthRequest=requests.shift();
  teacher.value='2'; let sixth=context.loadTeacherDossier(); const sixthRequest=requests.shift();
  reply(sixthRequest,'Two latest'); await sixth;
  fifthRequest.reject(new Error('stale failure')); await fifth;
  assert.equal(dossier.hidden,false,'stale error must not hide current dossier');
  assert.equal(element('teacher-name').textContent,'Two latest');
  console.log('teacher dossier race regression passed');
}
main().catch(error=>{console.error(error); process.exitCode=1;});
