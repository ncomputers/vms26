module.exports = {
  globDirectory: 'static/',
  globPatterns: [
    '**/*.{js,css,png,webmanifest,html}'
  ],
  swSrc: 'static/src-sw.js',
  swDest: 'static/service-worker.js'
};
