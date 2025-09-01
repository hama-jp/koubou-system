const canvas = document.getElementById('clockCanvas');
const ctx = canvas.getContext('2d');
let radius;

/* ---------- キャンバスのリサイズ ----------
   画面サイズに合わせてキャンバスをリサイズし、描画座標を中心に設定します。 */
function resizeCanvas() {
  const size = Math.min(canvas.clientWidth, canvas.clientHeight);
  canvas.width = size;
  canvas.height = size;
  radius = size / 2;
  ctx.setTransform(1, 0, 0, 1, 0, 0); // 既存の変換をリセット
  ctx.translate(radius, radius);      // 原点を中心に移動
  radius *= 0.85;                     // より多くの余白を確保（0.90から0.85に変更）
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

/* ---------- 時計の描画 ----------
   1. 表面（フェイス）
   2. 文字盤（12,3,6,9）
   3. 時刻（針） */
function drawClock() {
  drawFace(ctx, radius);
  drawNumbers(ctx, radius);
  drawTime(ctx, radius);
}

/* ---------- 表面（フェイス） ----------
   グラデーションと影を付けて立体感を演出します。 */
function drawFace(ctx, radius) {
  // 影をリセット（前の描画の影響を受けないように）
  ctx.shadowColor = 'transparent';
  ctx.shadowBlur = 0;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 0;
  
  // 外側の円
  ctx.beginPath();
  ctx.arc(0, 0, radius, 0, 2 * Math.PI);
  ctx.fillStyle = '#fff';
  ctx.fill();

  // グラデーションの境界線
  const grad = ctx.createRadialGradient(0, 0, radius * 0.95, 0, 0, radius);
  grad.addColorStop(0, '#333');
  grad.addColorStop(1, '#777');
  ctx.strokeStyle = grad;
  ctx.lineWidth = radius * 0.04;  // 線幅を少し細く（0.05から0.04に）
  ctx.stroke();
  
  // 中心点
  ctx.beginPath();
  ctx.arc(0, 0, radius * 0.03, 0, 2 * Math.PI);
  ctx.fillStyle = '#000';
  ctx.fill();
}

/* ---------- 文字盤 ----------
   12,3,6,9 の数字を描画します。 */
function drawNumbers(ctx, radius) {
  ctx.font = `${radius * 0.15}px Arial`;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'center';
  const numbers = [12, 3, 6, 9];
  numbers.forEach(num => {
    const ang = num * Math.PI / 6;
    const x = Math.cos(ang) * radius * 0.8;
    const y = Math.sin(ang) * radius * 0.8;
    ctx.fillStyle = '#000';
    ctx.fillText(num.toString(), x, y);
  });
}

/* ---------- 時刻（針） ----------
   秒針・分針・時針をスムーズに描画します。 */
function drawTime(ctx, radius) {
  const now = new Date();
  const hour = now.getHours() % 12;
  const minute = now.getMinutes();
  const second = now.getSeconds();
  const millisecond = now.getMilliseconds();

  // 時針
  let hourAngle = (hour + minute / 60 + second / 3600) * Math.PI / 6;
  drawHand(ctx, hourAngle, radius * 0.5, radius * 0.07);

  // 分針
  let minuteAngle = (minute + second / 60 + millisecond / 60000) * Math.PI / 30;
  drawHand(ctx, minuteAngle, radius * 0.8, radius * 0.07);

  // 秒針（赤色）
  let secondAngle = (second + millisecond / 1000) * Math.PI / 30;
  drawHand(ctx, secondAngle, radius * 0.9, radius * 0.02, '#ff0000');
}

/* ---------- 針の描画 ----------
   角度、長さ、太さ、色を指定して描画します。 */
function drawHand(ctx, pos, length, width, color = '#000') {
  ctx.beginPath();
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.strokeStyle = color;
  ctx.moveTo(0, 0);
  ctx.rotate(pos);
  ctx.lineTo(0, -length);
  ctx.stroke();
  ctx.rotate(-pos);
}

/* ---------- アニメーション ----------
   requestAnimationFrame でスムーズに再描画します。 */
function animate() {
  // キャンバス全体をクリア（より確実に）
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.restore();
  
  drawClock();
  requestAnimationFrame(animate);
}
animate();