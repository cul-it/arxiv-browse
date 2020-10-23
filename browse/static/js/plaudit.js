(function () {
  $output = $('#plauditContainer');
  const embedTag = document.createElement('script');
  embedTag.dataset.embedderId = "arxiv";
  embedTag.src = 'https://plaudit.pub/embed/endorsements.js';
  $output.append(embedTag);
})();
