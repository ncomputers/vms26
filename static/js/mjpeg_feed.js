(function () {
  function initMjpegFeeds(root = document) {
    const opened = new Set();

    function openFeed(img) {
      const id = img.dataset.cam;
      if (!id || opened.has(img)) return;
      opened.add(img);
      fetch(`/api/cameras/${id}/show`, { method: "POST" }).catch(() => {});
      img.src = `/api/cameras/${id}/mjpeg`;
    }

    function closeFeed(img) {
      const id = img.dataset.cam;
      if (!id || !opened.has(img)) return;
      opened.delete(img);
      if (img.src) {
        img.src = "";
        img.removeAttribute("src");
      }
      fetch(`/api/cameras/${id}/hide`, { method: "POST" }).catch(() => {});
    }

    root.querySelectorAll("img.feed-img").forEach((img) => {
      const modal = img.closest(".modal");
      if (modal) {
        modal.addEventListener("shown.bs.modal", () => openFeed(img));
        modal.addEventListener("hidden.bs.modal", () => closeFeed(img));
      } else {
        openFeed(img);
        window.addEventListener("beforeunload", () => closeFeed(img), {
          once: true,
        });
      }
    });
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
