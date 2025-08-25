(function(){
  function initMjpegFeeds(root=document){
    root.querySelectorAll('img.feed-img').forEach(img=>{
      const modal=img.closest('.modal');
      if(modal){
        modal.addEventListener('hidden.bs.modal',()=>img.removeAttribute('src'));
      }
    });
  }
  if (typeof module !== 'undefined') {
    module.exports = { initMjpegFeeds };
  } else {
    globalThis.initMjpegFeeds = initMjpegFeeds;
  }
  if (typeof document !== 'undefined' && !globalThis.__TEST__) {
    initMjpegFeeds();
  }
})();
