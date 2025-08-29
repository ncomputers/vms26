module.exports = {
  globDirectory: 'static/',
  globPatterns: [
    '**/*.{js,css,png,webmanifest,html}'
  ],
  globIgnores: ['js/webcam.js', 'js/camera_modal.js'],
  swSrc: 'static/src-sw.js',
  swDest: 'static/service-worker.js'
};
