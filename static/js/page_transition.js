// Handles global page fade transitions and provides timer/event cleanup
if(!window.pageScheduler){
  window.pageScheduler={
    timers:{},
    set(key,fn,interval){
      this.clear(key);
      this.timers[key]=setInterval(fn,interval);
      return this.timers[key];
    },
    clear(key){
      const t=this.timers[key];
      if(t){clearInterval(t);delete this.timers[key];}
    },
    clearAll(){
      Object.keys(this.timers).forEach(k=>this.clear(k));
    }
  };
}
if(!window.eventControllers){
  window.eventControllers={
    ctrls:{},
    get(key){
      this.ctrls[key]?.abort();
      const c=new AbortController();
      this.ctrls[key]=c;
      return c;
    },
    abortAll(){
      Object.values(this.ctrls).forEach(c=>c.abort());
      this.ctrls={};
    }
  };
}
window.addEventListener('pagehide',()=>{
  window.pageScheduler.clearAll();
  window.eventControllers.abortAll();
});
window.addEventListener('beforeunload',()=>{
  window.pageScheduler.clearAll();
  window.eventControllers.abortAll();
});
window.addEventListener('DOMContentLoaded',()=>{
  const fade=document.getElementById('page-fade');
  if(!fade) return;
  fade.classList.add('hidden');
  window.addEventListener('beforeunload',()=>{fade.classList.remove('hidden');});
});
