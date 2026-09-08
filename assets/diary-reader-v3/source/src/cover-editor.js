import {data, defaultCover, customCover, rebuildCover} from "./books.js";
import {coverCanvas, loadImage} from "./paper.js";
import {saveCover, deleteCover} from "./cover-store.js";
const $=s=>document.querySelector(s);
const dialog=$("#cover-editor"), title=$("#cover-title"), upload=$("#cover-upload");
const status=$("#cover-status"), preview=$("#cover-preview"), apply=$("#cover-save"), reset=$("#cover-reset");
let draft, revision=0;
function busy(value){apply.disabled=value;reset.disabled=value;}
async function showPreview(){
  const token=++revision;busy(true);
  try{const c=await coverCanvas(title.value.trim()||defaultCover.title,draft.image);if(token!==revision)return;preview.getContext("2d").drawImage(c,0,0);}
  catch{status.textContent="图片无法读取，请换一张 PNG、JPEG 或 WebP 图片。";}
  finally{if(token===revision)busy(false);}
}
$("#cover-edit").onclick=()=>{draft={...(customCover||defaultCover)};title.value=draft.title;upload.value="";status.textContent="";dialog.showModal();showPreview();};
title.addEventListener("input",showPreview);
upload.addEventListener("change",async()=>{
  const file=upload.files[0];if(!file)return;
  if(!["image/png","image/jpeg","image/webp"].includes(file.type)||file.size>15*1024*1024){status.textContent="请选择 15 MB 以内的 PNG、JPEG 或 WebP 图片。";upload.value="";return;}
  busy(true);const url=URL.createObjectURL(file);
  try{
    const image=await loadImage(url), scale=Math.min(1,1200/Math.max(image.naturalWidth,image.naturalHeight));
    const c=document.createElement("canvas");c.width=Math.max(1,Math.round(image.naturalWidth*scale));c.height=Math.max(1,Math.round(image.naturalHeight*scale));
    c.getContext("2d").drawImage(image,0,0,c.width,c.height);draft.image=c.toDataURL("image/png");
    status.textContent="图片已在本机载入，保存后仅保存在此浏览器。";await showPreview();
  }catch{status.textContent="这张图片无法解码，请重新选择。";}
  finally{URL.revokeObjectURL(url);busy(false);}
});
async function commit(value){
  busy(true);
  try{
    if(value)await saveCover(data.book.id,value);else await deleteCover(data.book.id);
    await rebuildCover(value);window.dispatchEvent(new Event("reader:cover"));dialog.close();
  }catch{status.textContent="未能保存，请检查浏览器本地存储是否可用后重试。";}
  finally{busy(false);}
}
apply.onclick=()=>{if(!title.value.trim()){status.textContent="给日记本起个名字吧。";title.focus();return;}commit({title:title.value.trim(),image:draft.image});};
reset.onclick=()=>commit(null);
