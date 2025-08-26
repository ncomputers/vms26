// Purpose: draw detection overlays on MJPEG feeds using HTML canvas
(function(){
  const settings = {
    show_lines:false,
    show_track_lines:false,
    show_counts:false,
    show_face_boxes:false,
    show_ids:false,
    debug_logs:false,
    enable_live_charts:false,
    track_ppe:[],
    alert_anomalies:[],
    preview_anomalies:[],
    track_objects:[],
    thickness:2,
  };
  const dataMap = {};
  const defaults = {};
  const overlayState = {
    flags: {
      show_lines: false,
      show_track_lines: false,
      show_counts: false,
      show_ids: false,
      show_face_boxes: false,
      show_person: false,
      show_vehicle: false,
      show_faces: false,
    },
    key: null,
  };

  if(typeof document!== 'undefined'){
    const style=document.createElement('style');
    style.textContent='.feed{position:relative}.feed .overlay{position:absolute;inset:0;z-index:10;pointer-events:none}';
    document.head.appendChild(style);
  }

  function log(...args){
    if(settings.debug_logs) console.debug(...args);
  }

  function normToDisplay(x, y, imgW, imgH){
    return [x * imgW, y * imgH];
  }

  function pixToDisplay(x, y, srcW, srcH, imgW, imgH){
    return [x * imgW / srcW, y * imgH / srcH];
  }

  function scaleBox(box, srcW, srcH, imgW, imgH){
    if(!Array.isArray(box) || box.length < 4) return null;
    let [x, y, w, h] = box;
    let bx, by, bw, bh;
    if([x, y, w, h].every(v=>v <= 1.01)){
      bx = x * imgW;
      by = y * imgH;
      bw = w * imgW;
      bh = h * imgH;
    }else{
      bx = x * imgW / srcW;
      by = y * imgH / srcH;
      bw = w * imgW / srcW;
      bh = h * imgH / srcH;
    }
    if(![bx,by,bw,bh].every(Number.isFinite) || bw<=0 || bh<=0) return null;
    return [bx,by,bw,bh];
  }

  let lastRenderLog = 0;

  function setupFeed(img){
    if(!img) return;
    const container = img.closest('.feed-container');
    if(!container || container.dataset.overlay!=="true") return;
    const feedEl = img.closest('.feed') || container;
    const cam = img.dataset.cam;
    if(!cam) return;
    const entry = dataMap[cam] || (dataMap[cam] = {});
    entry.img = img;
    entry.container = container;
    entry.feed = feedEl;
    entry.token = container.dataset.token;

    entry.start = async () => {
      if(entry.active) return;
      const warn=document.getElementById('token-warning');
      if(!entry.token){
        try{
          const r=await fetch('/api/token');
          if(r.ok){
            const d=await r.json();
            entry.token=d.token;
            warn && warn.classList.add('d-none');
          }else{
            if(warn){
              warn.textContent='Authentication token missing';
              warn.classList.remove('d-none');
            }
            return;
          }
        }catch(e){
          if(warn){
            warn.textContent='Authentication token missing';
            warn.classList.remove('d-none');
          }
          return;
        }
      }
      warn && warn.classList.add('d-none');
      let canvas = feedEl.querySelector('canvas.overlay');
      if(!canvas){
        canvas = document.createElement('canvas');
        canvas.className = 'overlay';
        feedEl.appendChild(canvas);
      }
      const ctx = canvas.getContext('2d');
      entry.canvas = canvas;
      entry.ctx = ctx;
      function resize(){
        const w = img.clientWidth;
        const h = img.clientHeight;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        canvas.style.width = w + 'px';
        canvas.style.height = h + 'px';
        ctx.setTransform(dpr,0,0,dpr,0,0);
        ctx.lineWidth = (settings.thickness || 2) / dpr;
        ctx.clearRect(0,0,canvas.width,canvas.height);
        renderOverlay(ctx, canvas, entry);
      }
      entry._resize = resize;
      function onload(){
        entry.src = { w: img.naturalWidth || 0, h: img.naturalHeight || 0 };
        resize();
      }
      img.addEventListener('load', onload);
      if(img.complete) onload();
      window.addEventListener('resize', resize);
      img.addEventListener('error',()=>showToast('Stream error'));

      entry.active = true;
      entry.close = connectDetections(cam, entry);
    };

    entry.stop = () => {
      if(!entry.active) return;
      entry.active = false;
      if(entry.close){try{entry.close();}catch(e){}}
      entry.close = null;
      if(entry.ctx){entry.ctx.clearRect(0,0,entry.canvas.width,entry.canvas.height);}
      if(entry.canvas) entry.canvas.remove();
      window.removeEventListener('resize', entry._resize);
      entry.tracks = [];
      entry.lines = [];
      entry.ppe = [];
      entry.counts = {};
    };

    if(Object.values(overlayState.flags).some(Boolean)) entry.start();
  }

  function applyOverlay(){
    settings.show_lines = overlayState.flags.show_lines;
    settings.show_track_lines = overlayState.flags.show_track_lines;
    settings.show_counts = overlayState.flags.show_counts;
    settings.show_face_boxes = overlayState.flags.show_face_boxes;
    settings.show_ids = overlayState.flags.show_ids;
    const enabled = Object.values(overlayState.flags).some(Boolean);
    document.querySelectorAll('.feed-container[data-overlay="true"] img.feed-img').forEach(img=>{
      const cam = img.dataset.cam;
      const entry = dataMap[cam];
      if(!entry) return;
      if(enabled) entry.start(); else entry.stop();
    });
  }

  function renderOverlay(ctx, canvas, info){
    const dpr = window.devicePixelRatio || 1;
    ctx.lineWidth = (settings.thickness || 2) / dpr;
    const {src, img} = info;
    if(!src) return;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    const scale = Math.min(w / src.w, h / src.h);
    const imgW = src.w * scale;
    const imgH = src.h * scale;
    const offX = (w - imgW)/2;
    const offY = (h - imgH)/2;

    const now = Date.now();
    if(now - lastRenderLog > 60000){
      lastRenderLog = now;
    }

    const lines = Array.isArray(info.lines) && info.lines.length ? info.lines : [];
    if(settings.show_lines && lines.length){
      ctx.strokeStyle = 'red';
      lines.forEach(l=>{
        const [x1,y1] = normToDisplay(l[0], l[1], imgW, imgH);
        const [x2,y2] = normToDisplay(l[2], l[3], imgW, imgH);
        ctx.beginPath();
        ctx.moveTo(offX + x1, offY + y1);
        ctx.lineTo(offX + x2, offY + y2);
        ctx.stroke();
      });
    }
    if(Array.isArray(info.tracks)){
      const tracks = info.tracks.filter(t=>{
        if(t.label==='person') return overlayState.flags.show_person;
        if(t.label==='vehicle') return overlayState.flags.show_vehicle;
        if(t.label==='face') return overlayState.flags.show_faces;
        return true;
      });
      tracks.forEach(t=>{
        const b = scaleBox(t.box, src.w, src.h, imgW, imgH);
        if(!b) return;
        const [bx,by,bw,bh] = b;
        let crossColor = null;
        if(Array.isArray(t.trail) && lines.length && t.trail.length >= 2){
          const ln = lines[0];
          const trail = t.trail;
          const [px1,py1] = trail[trail.length-2];
          const [px2,py2] = trail[trail.length-1];
          if(ln[0] === ln[2]){ // vertical
            const lx = ln[0] * src.w;
            if((px1 - lx) * (px2 - lx) < 0){
              crossColor = px2 > px1 ? 'green' : 'red';
            }
          }else if(ln[1] === ln[3]){ // horizontal
            const ly = ln[1] * src.h;
            if((py1 - ly) * (py2 - ly) < 0){
              crossColor = py2 > py1 ? 'green' : 'red';
            }
          }
        }
        ctx.strokeStyle = crossColor || 'yellow';
        ctx.strokeRect(offX + bx, offY + by, bw, bh);
        if(settings.show_face_boxes && t.face){
          const fb = scaleBox(t.face, src.w, src.h, imgW, imgH);
          if(fb){
            const [fx,fy,fw,fh] = fb;
            ctx.strokeStyle = 'orange';
            ctx.strokeRect(offX + fx, offY + fy, fw, fh);
          }
        }
        if(settings.show_track_lines && Array.isArray(t.trail)){
          const trail = t.trail;
          ctx.strokeStyle = crossColor || 'red';
          ctx.beginPath();
          for(let i=1;i<trail.length;i++){
            const [x1,y1] = pixToDisplay(trail[i-1][0], trail[i-1][1], src.w, src.h, imgW, imgH);
            const [x2,y2] = pixToDisplay(trail[i][0], trail[i][1], src.w, src.h, imgW, imgH);
            ctx.moveTo(offX + x1, offY + y1);
            ctx.lineTo(offX + x2, offY + y2);
          }
          ctx.stroke();
        }
        if(settings.show_ids){
          const label = `${t.id} ${t.label||''} ${(t.conf||0).toFixed(2)}`.trim();
          ctx.fillStyle = 'yellow';
          ctx.font = '12px sans-serif';
          ctx.fillText(label, offX + bx, offY + by - 4);
        }
      });
    }
    if(Array.isArray(info.ppe)){
      const colors = {helmet:'lime', vest:'cyan'};
      info.ppe.forEach(p=>{
        const b = scaleBox(p.box, src.w, src.h, imgW, imgH);
        if(!b) return;
        const [bx,by,bw,bh] = b;
        const color = colors[p.type] || 'magenta';
        ctx.strokeStyle = color;
        ctx.strokeRect(offX + bx, offY + by, bw, bh);
        if(typeof p.score === 'number'){
          ctx.fillStyle = color;
          ctx.font = '10px sans-serif';
          ctx.fillText(`${Math.round(p.score*100)}%`, offX + bx + 2, offY + by + 10);
        }
      });
    }
    if(info.counts && settings.show_counts){
      ctx.fillStyle='white';
      ctx.font='16px sans-serif';
      const entered=info.counts.entered||0;
      const exited=info.counts.exited||0;
      const inside=info.counts.inside||0;
      ctx.fillText(`Entered ${entered}`,4,16);
      ctx.fillText(`Exited ${exited}`,4,32);
      ctx.fillText(`Inside ${inside}`,4,48);
      if(settings.enable_live_charts){
        window.dispatchEvent(new CustomEvent('overlayCounts',{detail:info.counts}));
      }
  }
  log('overlay rendered', info);
  }

  function enableLineEditor(cam){
    const entry = dataMap[cam];
    if(!entry) return;
    settings.show_lines = true;
    entry.start();
    const canvas = entry.canvas;
    if(!canvas) return;
    let drawing=false; let start=[0,0];
    function norm(e){const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height];}
    function onDown(e){drawing=true;start=norm(e);entry.lines=[[start[0],start[1],start[0],start[1]]];}
    function onMove(e){if(!drawing) return; const p=norm(e); entry.lines[0]=[start[0],start[1],p[0],p[1]];}
    function onUp(e){if(!drawing) return; drawing=false; const p=norm(e); entry.lines[0]=[start[0],start[1],p[0],p[1]]; cleanup();}
    function cleanup(){canvas.removeEventListener('mousedown',onDown);canvas.removeEventListener('mousemove',onMove);window.removeEventListener('mouseup',onUp);}
    canvas.addEventListener('mousedown',onDown);
    canvas.addEventListener('mousemove',onMove);
    window.addEventListener('mouseup',onUp);
    entry.lineEditorCleanup=cleanup;
  }

  async function saveLine(cam){
    const entry = dataMap[cam];
    if(!entry || !entry.lines || !entry.lines[0]) return;
    const [x1,y1,x2,y2]=entry.lines[0];
    const orientation = Math.abs(x2-x1) >= Math.abs(y2-y1) ? 'horizontal' : 'vertical';
    await fetch(`/api/cameras/${cam}/line`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({x1,y1,x2,y2,orientation})});
    if(entry.lineEditorCleanup) entry.lineEditorCleanup();
  }

  async function loadSettings(){
    try{
      const r=await fetch('/config');
      if(r.ok){
        const cfg = await r.json();
        Object.assign(settings, cfg);
        defaults.show_lines = settings.show_lines;
        defaults.show_track_lines = settings.show_track_lines;
        defaults.show_counts = settings.show_counts;
        defaults.show_face_boxes = settings.show_face_boxes;
        defaults.show_ids = settings.show_ids;
      }
    }catch(err){/* ignore */}
  }

  function showToast(msg){
    const t=document.createElement('div');
    t.textContent=msg;
    t.style.cssText='position:fixed;bottom:1rem;right:1rem;background:rgba(0,0,0,0.7);color:#fff;padding:4px 8px;border-radius:4px;font-size:12px;z-index:9999';
    document.body.appendChild(t);
    setTimeout(()=>t.remove(),3000);
  }

  function connectDetections(cam, info){
    const proto=location.protocol==='https:'?'wss':'ws';
    let ws;
    let active=true;
    let delay=1000;
    const logs=[];
    const tok=info.token?`&token=${encodeURIComponent(info.token)}`:'';
    const url=`${proto}://${location.host}/ws/detections?cam=${encodeURIComponent(cam)}${tok}`;
    const warn=document.getElementById('token-warning');
    if(info.token){
      warn && warn.classList.add('d-none');
    }else{
      warn && warn.classList.remove('d-none');
      return ()=>{};
    }
    const queue=[];
    let raf=null;
    function process(){
      raf=null;
      if(!queue.length) return;
      const msg=queue[queue.length-1];
      queue.length=0;
      if(msg.src) info.src=msg.src;
      info.tracks=msg.tracks||[];
      info.lines=msg.lines||[];
      info.ppe=Array.isArray(msg.ppe)?msg.ppe:[];
      info.counts=msg.counts||{};
      info.line_orientation=msg.line_orientation;
      info.line_ratio=msg.line_ratio;
      const {ctx,canvas}=info;
      if(ctx && canvas){
        ctx.clearRect(0,0,canvas.width,canvas.height);
        renderOverlay(ctx,canvas,info);
      }
    }
    function enqueue(msg){
      queue.push(msg);
      if(!raf) raf=requestAnimationFrame(process);
    }
    function connect(){
      ws=new WebSocket(url);
      ws.onmessage=e=>{
        logs.unshift(e.data);
        if(logs.length>5) logs.pop();
        const logEl=document.getElementById('yolo-log');
        if(logEl) logEl.textContent=logs.join('\n');
        try{
          const msg=JSON.parse(e.data);
          if(msg.error==='unauthorized'){
            showToast('Auth failed');
            warn && warn.classList.remove('d-none');
            ws.close();
            return;
          }
          warn && warn.classList.add('d-none');
          enqueue(msg);
        }catch(err){/* ignore */}
      };
      ws.onopen=()=>{delay=1000;};
      ws.onerror=e=>{console.warn('detections ws error', url, e);showToast('Socket error');};
      ws.onclose=e=>{
        console.warn('detections ws close', url, e);
        if(e.code===1008) showToast('Auth failed');
        if(active){
          if(delay>=10000) showToast('Reconnect failed');
          setTimeout(connect,delay);
          delay=Math.min(delay*2,10000);
        }
      };
    }
    connect();
    return ()=>{active=false; if(raf) cancelAnimationFrame(raf); try{ws.close();}catch(e){}};
  }

  function makeSocket(path,onMessage){
    const proto=location.protocol==='https:'?'wss':'ws';
    let ws;
    function connect(){
      ws=new WebSocket(`${proto}://${location.host}${path}`);
      let hb;
      ws.onopen=()=>{hb=setInterval(()=>{try{ws.send('ping');}catch(_){}},10000);};
      ws.onmessage=onMessage;
      ws.onclose=()=>{clearInterval(hb);setTimeout(connect,1000);};
      ws.onerror=()=>{ws.close();};
    }
    connect();
  }

  function initSettingsSocket(){
    makeSocket('/ws/config',e=>{
      try{
        const msg=JSON.parse(e.data);
        if(msg.type==='settings' && msg.data){
          Object.assign(settings, msg.data);
          document.querySelectorAll('canvas.overlay').forEach(c=>{
            const img=c.closest?.('.feed-container')?.querySelector?.('img.feed-img');
            const info=img?dataMap[img.dataset.cam]:null;
            if(info){renderOverlay(c.getContext('2d'),c,info);} });
        }
      }catch(err){/* ignore */}
    });
  }

  function initToggle(){
    const buttons=document.querySelectorAll('.overlay-toggle-group .overlay-toggle');
    if(!buttons.length) return;
    const img=document.querySelector('.feed-container[data-overlay="true"] img.feed-img');
    const camId=img?.dataset.cam || 'global';
    overlayState.key=`overlayFlags:${camId}`;
    const stored=localStorage.getItem(overlayState.key);
    overlayState.flags = Object.assign({}, overlayState.flags, stored?JSON.parse(stored):{});
    buttons.forEach(btn=>{
      const flag = btn.dataset.flag;
      btn.classList.toggle('active', !!overlayState.flags[flag]);
      btn.addEventListener('click',()=>{
        overlayState.flags[flag] = !overlayState.flags[flag];
        btn.classList.toggle('active', overlayState.flags[flag]);
        localStorage.setItem(overlayState.key, JSON.stringify(overlayState.flags));
        applyOverlay();
      });
    });
  }

  async function init(){
    const feeds=document.querySelectorAll('.feed-container[data-overlay="true"] img.feed-img');
    feeds.forEach(setupFeed);
    if(feeds.length){
      await loadSettings();
      initToggle();
      applyOverlay();
      initSettingsSocket();
      const cleanup=()=>{Object.values(dataMap).forEach(i=>i.stop&&i.stop());};
      window.addEventListener('pagehide',cleanup,{once:true});
      window.addEventListener('beforeunload',cleanup,{once:true});
    }
  }

  globalThis.feedOverlays = Object.assign(globalThis.feedOverlays||{}, {enableLineEditor, saveLine});

  if(typeof document!=='undefined' && !globalThis.__TEST__){
    document.addEventListener('DOMContentLoaded',()=>{init();});
  }else{
    globalThis.__overlay_test__={renderOverlay,settings,dataMap,setupFeed,applyOverlay,overlayState,defaults,init};
  }
})();
