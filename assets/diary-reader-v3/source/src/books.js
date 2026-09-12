import {fontReady, handFont, paperCanvas, coverCanvas} from "./paper.js";
import {readCover} from "./cover-store.js";
export const data = await fetch(import.meta.env.BASE_URL+"data/manifest.json").then(r=>{if(!r.ok)throw Error("日记清单加载失败");return r.json();});
export const asset = path => import.meta.env.BASE_URL+"data/"+path;
export const defaultCover = {title:data.book.title, image:asset(data.book.coverImageSrc||data.book.coverSrc)};
export let customCover = await readCover(data.book.id).catch(()=>null);
await fontReady;
function page(title, subtitle, lines, number) {
  const c=paperCanvas(), x=c.getContext("2d");
  x.fillStyle="#77756f";x.font="27px "+handFont;x.fillText(subtitle,88,128);
  x.fillStyle="#171715";x.font="46px "+handFont;x.fillText(title,88,244);
  x.fillStyle="#7ccfdf";x.fillRect(88,270,100,8);
  x.fillStyle="#171715";x.font="30px "+handFont;let y=360;
  for(const line of lines){let row="";for(const ch of line){if(x.measureText(row+ch).width>700){x.fillText(row,88,y);y+=58;row="";}row+=ch;}x.fillText(row,88,y);y+=58;}
  x.fillStyle="#77756f";x.font="25px "+handFont;x.fillText(number,88,1110);
  return c.toDataURL();
}
function blankDatePage(date, number) {
  const c=paperCanvas(), x=c.getContext("2d");
  x.fillStyle="#77756f";x.font="27px "+handFont;x.fillText(date,88,128);
  x.fillStyle="#171715";x.font="42px "+handFont;x.fillText("留白日",88,244);
  x.fillStyle="#7ccfdf";x.fillRect(88,270,100,8);
  x.fillStyle="#77756f";x.font="27px "+handFont;x.fillText("这一天，先留给空白。",88,360);
  x.fillStyle="#77756f";x.font="25px "+handFont;x.fillText(number,88,1110);
  return c.toDataURL();
}
function emptyPaper() { return paperCanvas().toDataURL(); }
const entryPages=[];
data.entries.forEach((e,i)=>{const number=String(i+1).padStart(2,"0");if(e.isBlank){entryPages.push(blankDatePage(e.date,number),emptyPaper());return;}const period=data.periods.find(p=>p.id===e.periodId);entryPages.push(page(e.title,e.date+"  /  "+(period?.title||""),[e.summary||"",e.content||e.body||"",(e.characterIds||[]).map(id=>data.characters?.find(c=>c.id)?.name||id).join(" · ")],number),"data/"+e.posterSrc);});
export const books=[{id:data.book.id,title:data.book.title,mark:"",ratio:3/4,pages:[]}];
export async function rebuildCover(value) {
  const settings=value||defaultCover;
  const cover=await coverCanvas(settings.title,settings.image);
  customCover=value;data.book.title=settings.title;books[0].title=settings.title;
  books[0].pages=[cover.toDataURL(),...entryPages,page("把日常，慢慢收藏。",settings.title,["这一册暂时读到这里。","下次见，仍是平凡而可爱的一天。"],"终")];
}
await rebuildCover(customCover);
