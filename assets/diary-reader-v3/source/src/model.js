export function filterEntries(data, {query="", period="", character="", date=""} = {}) {
  const q=query.trim().toLocaleLowerCase();
  return data.entries.filter(e => (!period || e.periodId===period) && (!character || e.characterIds?.includes(character)) && (!date || e.date===date) && [e.date,e.title,e.summary,e.content,e.body,...(e.tags||[]),...(e.characterIds||[]).map(id=>data.characters?.find(c=>c.id===id)?.name||id)].join(" ").toLocaleLowerCase().includes(q));
}
export function spreadFromHash(hash, entries) {
  if(hash==="#cover") return 0;
  if(hash==="#back") return entries.length+1;
  if(!hash.startsWith("#entry=")) return null;
  try {const i=entries.findIndex(e=>e.id===decodeURIComponent(hash.slice(7))); return i<0?null:i+1;} catch{return null;}
}
export function entryHash(id){return "#entry="+encodeURIComponent(id);}
export function contain(w,h,W,H){const s=Math.min(W/w,H/h);return {x:(W-w*s)/2,y:(H-h*s)/2,width:w*s,height:h*s};}
