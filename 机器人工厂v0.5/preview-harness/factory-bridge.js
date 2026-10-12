/* Injected by the preview harness into the sketch2sim factory page.
   v0.3: speak / draw / type / send buttons now live on the builder frame (kid-bar) and reach this
   page as postMessage commands (unbound:express, unbound:request-send). The in-page floating
   buttons are gone; this script keeps recognition, the confirm dialog and the build diary.
   v0.4: the recognised creature switches the factory page's own parts
   v0.5: cat / duck / crab; the build request takes the creature from the page's current species
         (so the stage switch decides the template), falling back to what was recognised.
   through window.RF_SET_SPECIES; drawings also carry it as cfg.species.
   Adds the "send to real build" handoff toward the Spark builder page.
   No-ops when the page is opened standalone (not inside the builder iframe). */
(function () {
  /* Recognition hooks — defined always (standalone or iframed); the factory
     falls back to its built-in heuristics if these throw. */
  /* Species detection: free expression decides what gets built (cat or duck
     template today). Sources: voice sentence text and the drawing VLM. */
  let lastCreature = '';
  function detectCreature(text) {
    const t = String(text || '').toLowerCase();
    if (/鸭|duck/.test(t)) return 'duck';
    if (/螃蟹|蟹|crab/.test(t)) return 'crab';
    if (/猫|cat/.test(t)) return 'flying_cat';
    return '';
  }
  const CREATURE_LABEL = { duck: '鸭子', flying_cat: '飞行猫', crab: '小螃蟹' };
  /* the creature decides the factory page's own parts (window.RF_SET_SPECIES) */
  const SPECIES_OF = { duck: 'duck', crab: 'crab', flying_cat: 'cat' };
  const CREATURE_OF = { cat: 'flying_cat', duck: 'duck', crab: 'crab' };
  function applySpecies(creature) {
    if (creature && typeof window.RF_SET_SPECIES === 'function') window.RF_SET_SPECIES(SPECIES_OF[creature]);
  }

  window.RF_LIVE_MIC = true;
  window.RF_ASR = async (blob) => {
    try {
      const r = await fetch('/api/asr', { method: 'POST', body: blob });
      const o = await r.json();
      if (o.text) {
        const creature = detectCreature(o.text);
        if (creature) lastCreature = creature;
      }
      return o.text || '';
    } catch (e) { return ''; }
  };
  window.RF_AUDIO = async (file) => ({ text: await window.RF_ASR(file) });
  window.RF_ANALYZE = async (imgEl) => {
    const scale = Math.min(1, 640 / Math.max(imgEl.naturalWidth, imgEl.naturalHeight));
    const c = document.createElement('canvas');
    c.width = Math.round(imgEl.naturalWidth * scale); c.height = Math.round(imgEl.naturalHeight * scale);
    c.getContext('2d').drawImage(imgEl, 0, 0, c.width, c.height);
    const blob = await new Promise((r) => c.toBlob(r, 'image/jpeg', 0.85));
    const r = await fetch('/api/analyze-drawing', { method: 'POST', body: blob });
    if (!r.ok) throw new Error('analyze failed');
    const o = await r.json();
    const creature = detectCreature(o.creature);
    if (creature) lastCreature = creature;
    const cfg = Object.assign({}, o.cfg);
    if (creature) cfg.species = SPECIES_OF[creature];
    return cfg;
  };

  if (window === window.parent) return; // standalone: no handoff button

  /* ---- kid-language helpers for the member-check dialog ---- */
  const COLOR_NAMES = [
    ['#F2A65A', '橙色'], ['#FFC531', '黄色'], ['#F2C33C', '黄色'], ['#FFB03A', '橙色'],
    ['#F0544B', '红色'], ['#E8513D', '红色'], ['#FF8FAE', '粉色'], ['#D9607E', '粉色'],
    ['#35C07A', '绿色'], ['#22B8C4', '青色'], ['#3D86E8', '蓝色'], ['#2867D7', '蓝色'], ['#8EA2E8', '蓝色'],
    ['#9B6BE8', '紫色'], ['#B088D8', '紫色'], ['#9B4FD6', '紫色'],
    ['#EAEFF4', '白色'], ['#5B626B', '灰色'], ['#23283B', '黑色'],
  ];
  function colorName(hex) {
    if (!/^#[0-9a-f]{6}$/i.test(hex || '')) return '彩色';
    const n = parseInt(hex.slice(1), 16);
    const r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    let best = '彩色', dist = Infinity;
    for (const [h, name] of COLOR_NAMES) {
      const m = parseInt(h.slice(1), 16);
      const d = (r - (m >> 16)) ** 2 + (g - ((m >> 8) & 255)) ** 2 + (b - (m & 255)) ** 2;
      if (d < dist) { dist = d; best = name; }
    }
    return best;
  }
  const SCENE_PLAY = {
    grass: '在草地上跑来跑去',
    moon: '在月球上轻轻跳',
    space: '在太空里飘来飘去',
  };
  const PART_NAMES = {
    body: { round: '圆滚滚的身子', slim: '瘦长的身子', stocky: '敦实的身子', quad: '四条腿' },
    ears: { cat: '猫耳朵', round: '圆耳朵', long: '长耳朵', horn: '小犄角' },
    wings: { b5: '五刃翅膀', b3: '三刃翅膀', bat: '蝙蝠翅膀', none: '没有翅膀' },
    paws: { pad: '肉垫爪', claw: '尖尖爪', hoof: '小蹄子', mitt: '圆手手' },
    tail: { long: '长尾巴', fluff: '蓬蓬尾', stub: '短尾巴', none: '没有尾巴' },
  };
  function showToast(text, isErr) {
    const old = document.getElementById('ub-toast');
    if (old) old.remove();
    const toast = document.createElement('div');
    toast.id = 'ub-toast';
    toast.textContent = text;
    if (isErr) toast.style.background = '#E8513D';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  const style = document.createElement('style');
  style.textContent = `
    #ub-toast{position:fixed;left:50%;top:24px;transform:translateX(-50%);z-index:9999;font:600 15px/1.4 ui-rounded,"PingFang SC",sans-serif;color:#fff;background:#35C07A;padding:12px 22px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.2)}
    #ub-check{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(24,34,45,.4);backdrop-filter:blur(4px)}
    #ub-check[hidden]{display:none}
    #ub-check .card{background:#FFF8F0;border-radius:24px;padding:28px 30px;max-width:340px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,.25);animation:ub-pop .35s cubic-bezier(.2,1.4,.4,1)}
    @keyframes ub-pop{0%{transform:scale(.85);opacity:0}100%{transform:none;opacity:1}}
    #ub-check .q{font:600 19px/1.7 ui-rounded,"PingFang SC",sans-serif;color:#18222D;margin:0 0 20px}
    #ub-check .q b{color:#E8513D}
    #ub-check .row{display:flex;gap:12px;justify-content:center}
    #ub-yes{font:600 17px/1 ui-rounded,"PingFang SC",sans-serif;padding:14px 24px;border-radius:999px;border:0;cursor:pointer;color:#fff;background:linear-gradient(135deg,#FF6B57,#E8513D);box-shadow:0 4px 0 rgba(0,0,0,.15)}
    #ub-no{font:600 17px/1 ui-rounded,"PingFang SC",sans-serif;padding:14px 24px;border-radius:999px;border:2px solid #C4D1DC;cursor:pointer;color:#5a6b85;background:#fff}
    #ub-yes:active,#ub-no:active{transform:translateY(1px)}
    #ub-check .q small{display:block;font-size:12px;color:#8494A4;font-weight:400;margin-top:10px}
  `;
  document.head.appendChild(style);
  /* member-check: confirm in kid language before any build request leaves the page */
  const check = document.createElement('div');
  check.id = 'ub-check';
  check.hidden = true;
  check.innerHTML = '<div class="card" role="dialog" aria-label="确认你的机器人">'
    + '<p class="q" id="ub-q"></p>'
    + '<div class="row"><button id="ub-yes" type="button">对的！🚀</button><button id="ub-no" type="button">再改改</button></div></div>';
  document.body.appendChild(check);

  let pending = null;
  function startSend() {
    if (typeof window.RF_BUILD_STATE !== 'function') return;
    const snap = window.RF_BUILD_STATE();
    const pair = snap.colorPair.length ? snap.colorPair : ['#F2A65A', '#8EA2E8'];
    pending = {
      type: 'unbound:build-request',
      color: pair[0], wing: pair[1],
      scene: snap.scene,             // grass | space | moon | custom
      mood: snap.cfg.mood,
      cfg: snap.cfg,
      creature: lastCreature,        // 'duck' | 'flying_cat' | ''
      svg: (typeof window.RF_RENDER === 'function') ? window.RF_RENDER() : '',
    };
    /* the creature on the stage decides the template (v0.5 stage switch); recognition is the fallback */
    pending.creature = CREATURE_OF[snap.cfg.species] || lastCreature;
    const play = SCENE_PLAY[snap.scene] || '在你想象的地方冒险';
    const c = snap.cfg;
    const parts = [PART_NAMES.body[c.body], PART_NAMES.ears[c.ears], PART_NAMES.wings[c.wings],
                   PART_NAMES.paws[c.paws], PART_NAMES.tail[c.tail]].filter(Boolean).join('、');
    const label = pending.creature === 'flying_cat' ? '' : (CREATURE_LABEL[pending.creature] || '');
    document.getElementById('ub-q').innerHTML = label
      ? '你的小伙伴是一只<b>' + label + '</b>！<b>' + colorName(pair[0]) + '</b>的，' + play + '——对吗？'
        + '<small>真的会造出这只' + label + '的机身颜色和场景。</small>'
      : '你的小伙伴：' + parts + '。<br><b>' + colorName(pair[0]) + '</b>的，' + play + '——对吗？'
        + '<small>真的会造出机身颜色和场景；其他样子先留在这个游戏里。</small>';
    check.hidden = false;
  }
  document.getElementById('ub-no').addEventListener('click', () => { check.hidden = true; pending = null; });
  check.addEventListener('click', (e) => { if (e.target === check) { check.hidden = true; pending = null; } });
  document.getElementById('ub-yes').addEventListener('click', () => {
    if (!pending) return;
    window.parent.postMessage(pending, '*');
    pending = null; check.hidden = true;
  });

  /* kid-first expression entries live on the builder frame; they arrive here as commands.
     audio -> ASR -> sentence, text -> sentence, image -> the page's own drawing scanner. */
  async function handleAudio(blob) {
    showToast('让我听听看…');
    const text = await window.RF_ASR(blob);
    if (!text) { showToast('没听清，再试一次？', true); return; }
    showToast('我听到：' + text);
    const creature = detectCreature(text);
    if (creature) lastCreature = creature;
    applySpecies(creature);
    if (typeof window.RF_SENTENCE === 'function') window.RF_SENTENCE(text);
  }
  function handleText(text) {
    const t = String(text || '').trim().slice(0, 200);
    if (!t) return;
    const creature = detectCreature(t);
    if (creature) lastCreature = creature;
    applySpecies(creature);
    showToast('我听到：' + t);
    if (typeof window.RF_SENTENCE === 'function') window.RF_SENTENCE(t);
  }
  function handleImage(file) {
    const input = document.getElementById('file');
    if (!input || !(file instanceof Blob)) { showToast('这张画打不开，换一张试试？', true); return; }
    const dt = new DataTransfer();
    dt.items.add(file instanceof File ? file : new File([file], 'drawing.jpg', { type: file.type || 'image/jpeg' }));
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  /* build diary + naming + photo wall — rendered inside the kid's own world */
  const diaryStyle = document.createElement('style');
  diaryStyle.textContent = `
    #ub-diary{position:fixed;left:18px;bottom:66px;z-index:9999;width:280px;background:#FFF8F0;border:2px solid #FFC531;border-radius:20px;padding:14px 16px;box-shadow:0 10px 30px rgba(0,0,0,.18)}
    #ub-diary[hidden]{display:none}
    #ub-diary .top{display:flex;align-items:center;gap:10px}
    #ub-diary .cat{font-size:30px;animation:ub-bob 1.6s ease-in-out infinite}
    @keyframes ub-bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
    #ub-diary-text{font:700 15px/1.5 ui-rounded,"PingFang SC",sans-serif;color:#18222D;margin:0}
    #ub-diary .bar{height:10px;background:#fff;border:1px solid #F0D89A;border-radius:999px;margin-top:10px;overflow:hidden}
    #ub-diary-fill{height:100%;width:5%;background:linear-gradient(90deg,#FFC531,#FF6B57);border-radius:999px;transition:width .6s ease}
    #ub-diary .name-row{display:flex;gap:8px;margin-top:10px}
    #ub-diary .name-row[hidden]{display:none}
    #ub-name{flex:1;min-width:0;font:14px/1.2 "PingFang SC",sans-serif;padding:9px 12px;border:2px solid #F0D89A;border-radius:12px}
    #ub-name-ok{font:600 13px/1 "PingFang SC",sans-serif;padding:9px 14px;border-radius:12px;border:0;background:#FFC531;color:#18222D;cursor:pointer;white-space:nowrap}
    #ub-wall{position:fixed;right:16px;top:16px;z-index:9998;display:flex;flex-direction:column;gap:8px;align-items:flex-end}
    #ub-wall img{width:76px;border:4px solid #fff;border-bottom-width:16px;border-radius:6px;box-shadow:0 6px 16px rgba(0,0,0,.25)}
    #ub-wall img:nth-child(odd){transform:rotate(-3deg)}
    #ub-wall img:nth-child(even){transform:rotate(2deg)}
    @media(prefers-reduced-motion:reduce){#ub-diary .cat{animation:none}}
  `;
  document.head.appendChild(diaryStyle);
  const diary = document.createElement('div');
  diary.id = 'ub-diary'; diary.hidden = true;
  diary.innerHTML = '<div class="top"><span class="cat" aria-hidden="true">🐱</span><p id="ub-diary-text">正在挑选身体…</p></div>'
    + '<div class="bar"><div id="ub-diary-fill"></div></div>'
    + '<div class="name-row" id="ub-name-row"><input id="ub-name" maxlength="8" placeholder="趁现在，给它起个名字吧！"><button id="ub-name-ok" type="button">就叫这个</button></div>';
  document.body.appendChild(diary);
  const wall = document.createElement('div');
  wall.id = 'ub-wall';
  wall.setAttribute('aria-label', '试飞照片墙');
  document.body.appendChild(wall);
  document.getElementById('ub-name-ok').addEventListener('click', () => {
    const input = document.getElementById('ub-name');
    const name = input.value.trim();
    if (!name) return;
    window.parent.postMessage({ type: 'unbound:robot-name', name }, '*');
    input.disabled = true;
    const btn = document.getElementById('ub-name-ok');
    btn.textContent = '好名字！'; btn.disabled = true;
  });
  window.addEventListener('message', (event) => {
    if (event.source !== window.parent) return;
    const d = event.data || {};
    if (d.type === 'unbound:request-send') { startSend(); return; }
    if (d.type === 'unbound:express') {
      if (d.kind === 'audio' && d.blob instanceof Blob) handleAudio(d.blob);
      else if (d.kind === 'text') handleText(d.text);
      else if (d.kind === 'image') handleImage(d.file);
      return;
    }
    if (d.type === 'unbound:build-stage') {
      if (!d.done && (d.pct || 5) <= 5) {  // fresh build: reset the naming row
        const row = document.getElementById('ub-name-row');
        row.hidden = false;
        const input = document.getElementById('ub-name');
        input.disabled = false; input.value = '';
        const btn = document.getElementById('ub-name-ok');
        btn.textContent = '就叫这个'; btn.disabled = false;
      }
      diary.hidden = false;
      document.getElementById('ub-diary-text').textContent = d.text;
      document.getElementById('ub-diary-fill').style.width = (d.pct || 5) + '%';
      if (d.done) {
        document.getElementById('ub-name-row').hidden = true;
        clearTimeout(diary._t);
        diary._t = setTimeout(() => { diary.hidden = true; }, d.ok ? 4000 : 5000);
      }
      return;
    }
    if (d.type === 'unbound:build-photo') {
      fetch('/api/artifacts/' + d.artifact).then((r) => r.blob()).then((blob) => {
        const img = document.createElement('img');
        img.src = URL.createObjectURL(blob);
        img.title = (d.name ? d.name + '的' : '') + '试飞照片（真实仿真运行截图）';
        wall.prepend(img);
        while (wall.children.length > 6) wall.lastChild.remove();
      }).catch(() => {});
      return;
    }
    if (d.type !== 'unbound:build-accepted' && d.type !== 'unbound:build-blocked') return;
    showToast(d.type === 'unbound:build-accepted' ? '✅ 收到！工厂开始建造啦' : '⚠️ ' + (d.reason || '现在还造不了'),
              d.type === 'unbound:build-blocked');
  });
})();
