(function(){
  async function startFeed(img){
    const cam=img.dataset.cam;
    if(!cam) return;
    const token=img.dataset.token?`?token=${img.dataset.token}`:'';
    fetch(`/api/cameras/${cam}/show`,{method:'POST'}).catch(()=>{});
    img.src=`/api/cameras/${cam}/mjpeg${token}`;
    const stop=()=>{
      img.removeAttribute('src');
      fetch(`/api/cameras/${cam}/hide`,{method:'POST'}).catch(()=>{});
    };
    const modal=img.closest('.modal');
    if(modal){
      modal.addEventListener('hidden.bs.modal',stop);
    }else{
      window.addEventListener('beforeunload',stop);
    }
  }
  function initMjpegFeeds(root=document){
    root.querySelectorAll('img.feed-img').forEach(img=>{startFeed(img);});

  }
  if (typeof module !== "undefined") {
    module.exports = { initMjpegFeeds };
  } else {
    globalThis.initMjpegFeeds = initMjpegFeeds;
  }
  if (typeof document !== "undefined" && !globalThis.__TEST__) {
    initMjpegFeeds();
  }
})();
