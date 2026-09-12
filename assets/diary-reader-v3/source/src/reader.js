import {data,asset,books} from "./books.js";
import "./cover-editor.js";
import {filterEntries,spreadFromHash,entryHash} from "./model.js";
const $=s=>document.querySelector(s);
const key="diary-reader-v3:"+data.book.id;
let saved="";try{saved=localStorage.getItem(key)||"";}catch{}
let spread=spreadFromHash(location.hash,data.entries)??spreadFromHash(saved,data.entries)??0;
export const requestedSpread=()=>spread;
let navigating=false;
export function onSpread(value){
 if(navigating && value!==spread)return;
 navigating=false;spread=value;
 const e=data.entries[value-1],p=data.periods.find(p=>p.id===e?.periodId);
 $("#entry-title").textContent=e?(e.isBlank?"留白日":e.title):data.book.title;
 $("#period-label").textContent=e?(e.isBlank?e.date+" / 留白日":e.date+" / "+(p?.title||"")):value===0?data.entries.filter(e=>!e.isBlank).length+" 篇日记 · "+data.periods.length+" 个时期":"这一册，已读完";
 const hash=e?entryHash(e.id):value===0?"#cover":"#back";
 history.replaceState(null,"",hash);try{localStorage.setItem(key,hash);}catch{}
 $("#entry-characters").replaceChildren();
 for(const id of e?.characterIds||[]){const c=data.characters.find(c=>c.id===id);if(!c)continue;const a=document.createElement("a");a.href="#character="+encodeURIComponent(id);a.textContent=c.name;a.onclick=ev=>{ev.preventDefault();$("#character-filter").value=id;renderResults();$("#contents").showModal();};$("#entry-characters").append(a);}
 $("#enlarge").disabled=value>data.entries.length||Boolean(e?.isBlank);
}
function go(value){spread=value;navigating=true;window.dispatchEvent(new Event("reader:goto"));onSpread(value);}
window.addEventListener("hashchange",()=>{const v=spreadFromHash(location.hash,data.entries);if(v!==null)go(v);else if(location.hash.startsWith("#character=")){const id=decodeURIComponent(location.hash.slice(11));$("#character-filter").value=id;renderResults();if(!$("#contents").open)$("#contents").showModal();}});
for(const [selector,items,label] of [["#period-filter",data.periods,"所有时期"],["#character-filter",data.characters,"所有人物"]]){const select=$(selector);select.add(new Option(label,""));for(const item of items)select.add(new Option(item.title||item.name,item.id));}
function renderResults(){
 const entries=filterEntries(data,{query:$("#search").value,period:$("#period-filter").value,character:$("#character-filter").value,date:$("#date-filter").value});
 $("#results").replaceChildren();
 for(const e of entries){const a=document.createElement("a");a.href=entryHash(e.id);const date=document.createElement("small");date.textContent=e.date;const title=document.createElement("strong");title.textContent=e.isBlank?"留白日":e.title;const summary=document.createElement("span");summary.textContent=e.isBlank?"这一天没有收录日记。":e.summary;a.append(date,title,summary);a.onclick=ev=>{ev.preventDefault();$("#contents").close();go(data.entries.indexOf(e)+1);};$("#results").append(a);}
 $("#result-count").textContent=entries.length?entries.length+" 篇日记":"没有匹配的日记，试试其他日期或关键词。";
}
for(const id of ["#search","#period-filter","#character-filter","#date-filter"])$(id).addEventListener("input",renderResults);
$("#contents-toggle").onclick=()=>{renderResults();$("#contents").showModal();};
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>b.closest("dialog").close());
$("#enlarge").onclick=()=>{const e=data.entries[spread-1];if(e?.isBlank)return;$("#poster-title").textContent=e?e.date+" · "+e.title:data.book.title;$("#poster-image").src=e?asset(e.posterSrc):books[0].pages[0];$("#poster-image").alt=e?.title||data.book.title;$("#poster-image").classList.remove("actual");$("#zoom-toggle").textContent="原始尺寸";$("#poster-dialog").showModal();};
$("#zoom-toggle").onclick=()=>{$("#poster-image").classList.toggle("actual");$("#zoom-toggle").textContent=$("#poster-image").classList.contains("actual")?"适应窗口":"原始尺寸";};
onSpread(spread);renderResults();
function syncTitle(){$("#book-name").textContent=data.book.title;document.title=data.book.title+" · 日记阅读器";}
syncTitle();
window.addEventListener("reader:cover",()=>{syncTitle();go(0);});
