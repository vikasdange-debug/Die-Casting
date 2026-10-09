(() => {
  const input = document.getElementById('cad-file');
  if (!input) return;
  const zone = document.getElementById('dropzone');
  const title = document.getElementById('file-title');
  const subtitle = document.getElementById('file-subtitle');
  const form = document.getElementById('upload-form');
  const button = document.getElementById('submit-button');

  const showFile = file => {
    if (!file) return;
    title.textContent = file.name;
    subtitle.textContent = `${(file.size / 1048576).toFixed(2)} MB selected`;
  };
  input.addEventListener('change', () => showFile(input.files[0]));
  zone.addEventListener('dragover', event => {
    event.preventDefault();
    zone.classList.add('dragging');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
  zone.addEventListener('drop', event => {
    event.preventDefault();
    zone.classList.remove('dragging');
    if (event.dataTransfer.files.length) {
      input.files = event.dataTransfer.files;
      showFile(input.files[0]);
    }
  });
  form.addEventListener('submit', () => {
    button.disabled = true;
    button.textContent = 'Analyzing component…';
    button.setAttribute('aria-live', 'polite');
  });
})();
