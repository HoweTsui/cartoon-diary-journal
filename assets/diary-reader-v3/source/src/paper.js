export const handFont = '"Yozai"';
export const fontReady = document.fonts.load('32px Yozai', '纸上小日子快乐日记').then(faces => {
  if (!faces.length) throw new Error("手写字体未加载，请刷新重试");
  return document.fonts.ready;
});

export function paperCanvas() {
  const canvas = document.createElement("canvas");
  canvas.width = 900;
  canvas.height = 1200;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, 900, 1200);
  ctx.strokeStyle = "rgba(124,207,223,.27)";
  ctx.lineWidth = 1.5;
  for (let y = 70; y < 1170; y += 58) {
    ctx.beginPath(); ctx.moveTo(30, y); ctx.lineTo(870, y); ctx.stroke();
  }
  ctx.beginPath(); ctx.moveTo(58, 28); ctx.lineTo(58, 1170); ctx.stroke();
  return canvas;
}

export async function loadImage(src) {
  const image = new Image();
  image.src = src;
  await image.decode();
  return image;
}

// Actual canvas path, used both for pixel clipping and the visible ink outline.
export function petalPath(ctx, cx = 450, cy = 625) {
  ctx.beginPath();
  for (let i = 0; i <= 240; i++) {
    const a = i / 240 * Math.PI * 2;
    const radius = 1 + 0.09 * Math.cos(8 * a);
    const x = cx + 230 * radius * Math.cos(a);
    const y = cy + 205 * radius * Math.sin(a);
    if (!i) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

export async function coverCanvas(title, source) {
  await fontReady;
  const image = await loadImage(source);
  const canvas = paperCanvas(), ctx = canvas.getContext("2d");
  ctx.textAlign = "center";
  ctx.fillStyle = "#171715";
  ctx.font = '27px ' + handFont;
  ctx.fillText("我的日记本", 450, 155);
  let size = 76;
  do { ctx.font = size + "px " + handFont; size -= 2; } while (ctx.measureText(title).width > 735 && size > 28);
  ctx.fillText(title, 450, 290);
  ctx.save();
  petalPath(ctx);
  ctx.clip();
  const scale = Math.max(510 / image.naturalWidth, 460 / image.naturalHeight);
  ctx.drawImage(image, 450 - image.naturalWidth * scale / 2, 625 - image.naturalHeight * scale / 2, image.naturalWidth * scale, image.naturalHeight * scale);
  ctx.restore();
  petalPath(ctx); ctx.strokeStyle = "#171715"; ctx.lineWidth = 3.5; ctx.stroke();
  ctx.font = '30px ' + handFont;
  ctx.fillStyle = "#171715"; ctx.fillText("把日常，慢慢翻开。", 450, 975);
  ctx.font = '23px ' + handFont;
  ctx.fillStyle = "#171715"; ctx.fillText("一页一页，收藏小小的快乐", 450, 1040);
  return canvas;
}
