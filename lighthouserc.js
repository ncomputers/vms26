module.exports = {
  ci: {
    collect: {
      url: ['http://localhost:8000'],
      numberOfRuns: 1
    },
    assert: {
      assertions: {
        'categories:pwa': ['warn', {minScore: 0.95}]
      }
    }
  }
};
