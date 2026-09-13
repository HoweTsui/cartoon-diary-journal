import "./style.css";
try {await import("./main.js");}
catch(error){console.error(error);document.querySelector("#loading-card").hidden=true;document.querySelector("#render-note").textContent="当前设备以平面日记页展示。";const {requestedSpread,onSpread,enableStaticReader}=await import("./reader.js");enableStaticReader();window.addEventListener("reader:goto",()=>onSpread(requestedSpread()));}
