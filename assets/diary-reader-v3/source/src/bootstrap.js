import "./style.css";
try {await import("./main.js");}
catch(error){console.error(error);document.querySelector("#loading-card").hidden=true;document.querySelector("#render-note").textContent="此设备无法启动三维书页。可用目录选择日记，再点击「放大原图」阅读。";const {requestedSpread,onSpread}=await import("./reader.js");window.addEventListener("reader:goto",()=>onSpread(requestedSpread()));}
