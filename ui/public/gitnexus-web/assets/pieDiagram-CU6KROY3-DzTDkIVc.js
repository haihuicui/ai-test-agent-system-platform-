import{F as e,H as t,I as n,K as r,N as i,S as a,Y as o,Z as s,j as c,tt as l}from"./chunk-67TQ5CYL-Y4kh-FWv.js";import{t as u}from"./chunk-AQ6EADP3-CCFje6lL.js";import{W as d,c as f,p,q as m}from"./chunk-7W6UQGC5-CgFyfZ6k.js";import"./chunk-KNLZD3CH-BuZBOcso.js";import{a as h,p as g}from"./chunk-QA3QBVWF-CzlKXtdT.js";import{a as _}from"./index-16B0GziA.js";import"./chunk-4R4BOZG6-mKhL59ul.js";import"./chunk-RERM46MO-DQNbXtfw.js";import{t as v}from"./chunk-JQRUD6KW-Dcq_Qnyy.js";import{t as y}from"./chunk-2T2R6R2M-BPmtGBzn.js";import"./chunk-UP6H54XL-DsKdC6jC.js";import"./chunk-UXSXWOXI-DR81EqLr.js";import"./chunk-C62D2QBJ-CDAWj26E.js";import"./chunk-CEXFNPSA-D68Tk6ls.js";import"./chunk-J5EP6P6S-DxWW0yvu.js";import"./chunk-RLI5ZMPA-DExu2DOK.js";import"./chunk-2UTLFMKG-CMBB1TMN.js";import"./chunk-RKZBBQEN-BmTPLSyv.js";import"./chunk-KGYTTC2M-C6PHeuay.js";var b=c.pie,x={sections:new Map,showData:!1,config:b},S=x.sections,C=x.showData,w=structuredClone(b),T={getConfig:u(()=>structuredClone(w),`getConfig`),clear:u(()=>{S=new Map,C=x.showData,o()},`clear`),setDiagramTitle:e,getDiagramTitle:r,setAccTitle:i,getAccTitle:l,setAccDescription:t,getAccDescription:a,addSection:u(({label:e,value:t})=>{if(t<0)throw Error(`"${e}" has invalid value: ${t}. Negative values are not allowed in pie charts. All slice values must be >= 0.`);S.has(e)||(S.set(e,t),m.debug(`added new section: ${e}, with value: ${t}`))},`addSection`),getSections:u(()=>S,`getSections`),setShowData:u(e=>{C=e},`setShowData`),getShowData:u(()=>C,`getShowData`)},E=u((e,t)=>{v(e,t),t.setShowData(e.showData),e.sections.map(t.addSection)},`populateDb`),D={parse:u(async e=>{let t=await y(`pie`,e);m.debug(t),E(t,T)},`parse`)},O=u(e=>`
  .pieCircle{
    stroke: ${e.pieStrokeColor};
    stroke-width : ${e.pieStrokeWidth};
    opacity : ${e.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${e.pieOuterStrokeColor};
    stroke-width: ${e.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${e.pieTitleTextSize};
    fill: ${e.pieTitleTextColor};
    font-family: ${e.fontFamily};
  }
  .slice {
    font-family: ${e.fontFamily};
    fill: ${e.pieSectionTextColor};
    font-size:${e.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${e.pieLegendTextColor};
    font-family: ${e.fontFamily};
    font-size: ${e.pieLegendTextSize};
  }
`,`getStyles`),k=u(e=>{let t=[...e.values()].reduce((e,t)=>e+t,0),n=[...e.entries()].map(([e,t])=>({label:e,value:t})).filter(e=>e.value/t*100>=1);return f().value(e=>e.value).sort(null)(n)},`createPieArcs`),A={parser:D,db:T,renderer:{draw:u((e,t,r,i)=>{m.debug(`rendering pie chart
`+e);let a=i.db,o=s(),c=h(a.getConfig(),o.pie),l=_(t),u=l.append(`g`);u.attr(`transform`,`translate(225,225)`);let{themeVariables:f}=o,[v]=g(f.pieOuterStrokeWidth);v??=2;let y=c.textPosition,b=d().innerRadius(0).outerRadius(185),x=d().innerRadius(185*y).outerRadius(185*y);u.append(`circle`).attr(`cx`,0).attr(`cy`,0).attr(`r`,185+v/2).attr(`class`,`pieOuterCircle`);let S=a.getSections(),C=k(S),w=[f.pie1,f.pie2,f.pie3,f.pie4,f.pie5,f.pie6,f.pie7,f.pie8,f.pie9,f.pie10,f.pie11,f.pie12],T=0;S.forEach(e=>{T+=e});let E=C.filter(e=>(e.data.value/T*100).toFixed(0)!==`0`),D=p(w).domain([...S.keys()]);u.selectAll(`mySlices`).data(E).enter().append(`path`).attr(`d`,b).attr(`fill`,e=>D(e.data.label)).attr(`class`,`pieCircle`),u.selectAll(`mySlices`).data(E).enter().append(`text`).text(e=>(e.data.value/T*100).toFixed(0)+`%`).attr(`transform`,e=>`translate(`+x.centroid(e)+`)`).style(`text-anchor`,`middle`).attr(`class`,`slice`);let O=u.append(`text`).text(a.getDiagramTitle()).attr(`x`,0).attr(`y`,-400/2).attr(`class`,`pieTitleText`),A=[...S.entries()].map(([e,t])=>({label:e,value:t})),j=u.selectAll(`.legend`).data(A).enter().append(`g`).attr(`class`,`legend`).attr(`transform`,(e,t)=>{let n=22*A.length/2;return`translate(216,`+(t*22-n)+`)`});j.append(`rect`).attr(`width`,18).attr(`height`,18).style(`fill`,e=>D(e.label)).style(`stroke`,e=>D(e.label)),j.append(`text`).attr(`x`,22).attr(`y`,14).text(e=>a.getShowData()?`${e.label} [${e.value}]`:e.label);let M=512+Math.max(...j.selectAll(`text`).nodes().map(e=>e?.getBoundingClientRect().width??0)),N=O.node()?.getBoundingClientRect().width??0,P=450/2-N/2,F=450/2+N/2,I=Math.min(0,P),L=Math.max(M,F)-I;l.attr(`viewBox`,`${I} 0 ${L} 450`),n(l,450,L,c.useMaxWidth)},`draw`)},styles:O};export{A as diagram};