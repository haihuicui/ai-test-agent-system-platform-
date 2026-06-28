import{F as e,H as t,I as n,K as r,N as i,R as a,S as o,Y as s,j as c,l,tt as u}from"./chunk-67TQ5CYL-Y4kh-FWv.js";import{t as d}from"./chunk-AQ6EADP3-CCFje6lL.js";import{q as f}from"./chunk-7W6UQGC5-CgFyfZ6k.js";import"./chunk-KNLZD3CH-BuZBOcso.js";import{a as p}from"./chunk-QA3QBVWF-CzlKXtdT.js";import{a as m}from"./index-DoHC1P1_.js";import"./chunk-4R4BOZG6-mKhL59ul.js";import"./chunk-RERM46MO-DQNbXtfw.js";import{t as h}from"./chunk-JQRUD6KW-Dcq_Qnyy.js";import{t as g}from"./chunk-2T2R6R2M-BPmtGBzn.js";import"./chunk-UP6H54XL-DsKdC6jC.js";import"./chunk-UXSXWOXI-DR81EqLr.js";import"./chunk-C62D2QBJ-CDAWj26E.js";import"./chunk-CEXFNPSA-D68Tk6ls.js";import"./chunk-J5EP6P6S-DxWW0yvu.js";import"./chunk-RLI5ZMPA-DExu2DOK.js";import"./chunk-2UTLFMKG-CMBB1TMN.js";import"./chunk-RKZBBQEN-BmTPLSyv.js";import"./chunk-KGYTTC2M-C6PHeuay.js";var _={showLegend:!0,ticks:5,max:null,min:0,graticule:`circle`},v={axes:[],curves:[],options:_},y=structuredClone(v),b=c.radar,x=d(()=>p({...b,...l().radar}),`getConfig`),S=d(()=>y.axes,`getAxes`),C=d(()=>y.curves,`getCurves`),w=d(()=>y.options,`getOptions`),T=d(e=>{y.axes=e.map(e=>({name:e.name,label:e.label??e.name}))},`setAxes`),E=d(e=>{y.curves=e.map(e=>({name:e.name,label:e.label??e.name,entries:D(e.entries)}))},`setCurves`),D=d(e=>{if(e[0].axis==null)return e.map(e=>e.value);let t=S();if(t.length===0)throw Error(`Axes must be populated before curves for reference entries`);return t.map(t=>{let n=e.find(e=>e.axis?.$refText===t.name);if(n===void 0)throw Error(`Missing entry for axis `+t.label);return n.value})},`computeCurveEntries`),O={getAxes:S,getCurves:C,getOptions:w,setAxes:T,setCurves:E,setOptions:d(e=>{let t=e.reduce((e,t)=>(e[t.name]=t,e),{});y.options={showLegend:t.showLegend?.value??_.showLegend,ticks:t.ticks?.value??_.ticks,max:t.max?.value??_.max,min:t.min?.value??_.min,graticule:t.graticule?.value??_.graticule}},`setOptions`),getConfig:x,clear:d(()=>{s(),y=structuredClone(v)},`clear`),setAccTitle:i,getAccTitle:u,setDiagramTitle:e,getDiagramTitle:r,getAccDescription:o,setAccDescription:t},k=d(e=>{h(e,O);let{axes:t,curves:n,options:r}=e;O.setAxes(t),O.setCurves(n),O.setOptions(r)},`populate`),A={parse:d(async e=>{let t=await g(`radar`,e);f.debug(t),k(t)},`parse`)},j=d((e,t,n,r)=>{let i=r.db,a=i.getAxes(),o=i.getCurves(),s=i.getOptions(),c=i.getConfig(),l=i.getDiagramTitle(),u=M(m(t),c),d=s.max??Math.max(...o.map(e=>Math.max(...e.entries))),f=s.min,p=Math.min(c.width,c.height)/2;N(u,a,p,s.ticks,s.graticule),P(u,a,p,c),F(u,a,o,f,d,s.graticule,c),R(u,o,s.showLegend,c),u.append(`text`).attr(`class`,`radarTitle`).text(l).attr(`x`,0).attr(`y`,-c.height/2-c.marginTop)},`draw`),M=d((e,t)=>{let r=t.width+t.marginLeft+t.marginRight,i=t.height+t.marginTop+t.marginBottom,a={x:t.marginLeft+t.width/2,y:t.marginTop+t.height/2};return n(e,i,r,t.useMaxWidth??!0),e.attr(`viewBox`,`0 0 ${r} ${i}`),e.append(`g`).attr(`transform`,`translate(${a.x}, ${a.y})`)},`drawFrame`),N=d((e,t,n,r,i)=>{if(i===`circle`)for(let t=0;t<r;t++){let i=n*(t+1)/r;e.append(`circle`).attr(`r`,i).attr(`class`,`radarGraticule`)}else if(i===`polygon`){let i=t.length;for(let a=0;a<r;a++){let o=n*(a+1)/r,s=t.map((e,t)=>{let n=2*t*Math.PI/i-Math.PI/2;return`${o*Math.cos(n)},${o*Math.sin(n)}`}).join(` `);e.append(`polygon`).attr(`points`,s).attr(`class`,`radarGraticule`)}}},`drawGraticule`),P=d((e,t,n,r)=>{let i=t.length;for(let a=0;a<i;a++){let o=t[a].label,s=2*a*Math.PI/i-Math.PI/2;e.append(`line`).attr(`x1`,0).attr(`y1`,0).attr(`x2`,n*r.axisScaleFactor*Math.cos(s)).attr(`y2`,n*r.axisScaleFactor*Math.sin(s)).attr(`class`,`radarAxisLine`),e.append(`text`).text(o).attr(`x`,n*r.axisLabelFactor*Math.cos(s)).attr(`y`,n*r.axisLabelFactor*Math.sin(s)).attr(`class`,`radarAxisLabel`)}},`drawAxes`);function F(e,t,n,r,i,a,o){let s=t.length,c=Math.min(o.width,o.height)/2;n.forEach((t,n)=>{if(t.entries.length!==s)return;let l=t.entries.map((e,t)=>{let n=2*Math.PI*t/s-Math.PI/2,a=I(e,r,i,c);return{x:a*Math.cos(n),y:a*Math.sin(n)}});a===`circle`?e.append(`path`).attr(`d`,L(l,o.curveTension)).attr(`class`,`radarCurve-${n}`):a===`polygon`&&e.append(`polygon`).attr(`points`,l.map(e=>`${e.x},${e.y}`).join(` `)).attr(`class`,`radarCurve-${n}`)})}d(F,`drawCurves`);function I(e,t,n,r){return r*(Math.min(Math.max(e,t),n)-t)/(n-t)}d(I,`relativeRadius`);function L(e,t){let n=e.length,r=`M${e[0].x},${e[0].y}`;for(let i=0;i<n;i++){let a=e[(i-1+n)%n],o=e[i],s=e[(i+1)%n],c=e[(i+2)%n],l={x:o.x+(s.x-a.x)*t,y:o.y+(s.y-a.y)*t},u={x:s.x-(c.x-o.x)*t,y:s.y-(c.y-o.y)*t};r+=` C${l.x},${l.y} ${u.x},${u.y} ${s.x},${s.y}`}return`${r} Z`}d(L,`closedRoundCurve`);function R(e,t,n,r){if(!n)return;let i=(r.width/2+r.marginRight)*3/4,a=-(r.height/2+r.marginTop)*3/4;t.forEach((t,n)=>{let r=e.append(`g`).attr(`transform`,`translate(${i}, ${a+n*20})`);r.append(`rect`).attr(`width`,12).attr(`height`,12).attr(`class`,`radarLegendBox-${n}`),r.append(`text`).attr(`x`,16).attr(`y`,0).attr(`class`,`radarLegendText`).text(t.label)})}d(R,`drawLegend`);var z={draw:j},B=d((e,t)=>{let n=``;for(let r=0;r<e.THEME_COLOR_LIMIT;r++){let i=e[`cScale${r}`];n+=`
		.radarCurve-${r} {
			color: ${i};
			fill: ${i};
			fill-opacity: ${t.curveOpacity};
			stroke: ${i};
			stroke-width: ${t.curveStrokeWidth};
		}
		.radarLegendBox-${r} {
			fill: ${i};
			fill-opacity: ${t.curveOpacity};
			stroke: ${i};
		}
		`}return n},`genIndexStyles`),V=d(e=>{let t=p(a(),l().themeVariables);return{themeVariables:t,radarOptions:p(t.radar,e)}},`buildRadarStyleOptions`),H={parser:A,db:O,renderer:z,styles:d(({radar:e}={})=>{let{themeVariables:t,radarOptions:n}=V(e);return`
	.radarTitle {
		font-size: ${t.fontSize};
		color: ${t.titleColor};
		dominant-baseline: hanging;
		text-anchor: middle;
	}
	.radarAxisLine {
		stroke: ${n.axisColor};
		stroke-width: ${n.axisStrokeWidth};
	}
	.radarAxisLabel {
		dominant-baseline: middle;
		text-anchor: middle;
		font-size: ${n.axisLabelFontSize}px;
		color: ${n.axisColor};
	}
	.radarGraticule {
		fill: ${n.graticuleColor};
		fill-opacity: ${n.graticuleOpacity};
		stroke: ${n.graticuleColor};
		stroke-width: ${n.graticuleStrokeWidth};
	}
	.radarLegendText {
		text-anchor: start;
		font-size: ${n.legendFontSize}px;
		dominant-baseline: hanging;
	}
	${B(t,n)}
	`},`styles`)};export{H as diagram};